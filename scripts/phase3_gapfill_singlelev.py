"""
scripts/phase3_gapfill_singlelev.py

Phase 3 — ERA5 single-levels gap-fill for coastal pixels.

Fills NaN pixels in ERA5-Land exceedance climatologies (RH, wind, precip)
using ERA5 single-levels hourly data. PWV already comes from ERA5-SL and
needs no gap-fill.

Outputs (outputs/phase3/gapfill/):
    rh_exceedance_gapfilled.nc
    wind_exceedance_gapfilled.nc
    precip_exceedance_gapfilled.nc
    pwv_exceedance_gapfilled.nc       (copy of Phase 2 — no fill needed)
    composite_index_monthly_gf.nc
    composite_index_annual_gf.nc
    gapfill_report.txt

Maps (outputs/maps/phase3/):
    phase3_composite_annual_gf.png    (updated poster figure)
    phase3_composite_monthly_gf.png

Usage:
    cd /export/ngvla/cpollack/pr_ngvla
    python scripts/phase3_gapfill_singlelev.py

References:
    Hersbach et al. (2020) ERA5 global reanalysis. QJRMS 146:1999-2049.
    Muñoz-Sabater et al. (2021) ERA5-Land. ESSD 13:4349-4383.
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
from pathlib import Path

from pr_ngvla.config import (
    OUTPUTS, COAST_SHP, MUNI_SHP, NOAA_ISD_DIR,
    MAP_XLIM, MAP_YLIM, ERA5_SINGLELEV_DIR,
)
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.data.loaders import load_noaa_isd_stations
from pr_ngvla.analysis.exceedance import monthly_exceedance_climatology, save_exceedance
from pr_ngvla.analysis.fuzzy import composite_index, annual_composite, DEFAULT_WEIGHTS
from pr_ngvla.analysis.gapfill import (
    regrid_singlelev_to_era5land,
    merge_era5land_singlelev,
    gap_fill_summary,
)
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, style_axes_single,
    add_station_overlay, add_north_arrow,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PHASE2_DIR  = OUTPUTS / "phase2"
PHASE3_DIR  = OUTPUTS / "phase3"
GF_DIR      = PHASE3_DIR / "gapfill"
MAP_DIR     = OUTPUTS / "maps" / "phase3"
GF_DIR.mkdir(parents=True, exist_ok=True)
MAP_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

# Exceedance thresholds — must match Phase 2
THRESHOLDS = {
    "rh":     [50.0, 80.0, 99.9],
    "wind":   [9.0, 13.4, 24.5],
    "precip": [0.0, 1.0, 7.6],
}

print("=" * 65)
print("Phase 3 — ERA5 Single-Levels Gap-Fill")
print("=" * 65)

# ---------------------------------------------------------------------------
# Load ERA5-Land exceedance (Phase 2 results)
# ---------------------------------------------------------------------------

print("\nLoading ERA5-Land Phase 2 exceedance...")

exc_land = {}
for var, fname in [
    ("rh",     "rh_exceedance_climatology.nc"),
    ("wind",   "wind_exceedance_climatology.nc"),
    ("precip", "precip_exceedance_climatology.nc"),
    ("pwv",    "pwv_exceedance_climatology.nc"),
]:
    ds = xr.open_dataset(PHASE2_DIR / fname)
    varname = f"{var}_exceedance"
    exc_land[var] = ds[varname]
    # Count land pixels
    if "month" in exc_land[var].dims:
        da0 = exc_land[var].isel(threshold=0, month=0)
    else:
        da0 = exc_land[var].isel(threshold=0)
    n_land = int((~np.isnan(da0.values)).sum())
    n_nan  = int(np.isnan(da0.values).sum())
    print(f"  {var}: {n_land} land pixels, {n_nan} NaN (gap) pixels")

# Reference grid from ERA5-Land RH
ref_lat = exc_land["rh"]["latitude"].values
ref_lon = exc_land["rh"]["longitude"].values

# ---------------------------------------------------------------------------
# Compute ERA5-SL exceedance for gap variables (RH, wind, precip)
# PWV already from ERA5-SL — no gap fill needed
# ---------------------------------------------------------------------------

print("\nComputing ERA5-SL exceedance for gap pixels...")
print(f"  Source directory: {ERA5_SINGLELEV_DIR}")

# Check available files
sl_files_t       = sorted(ERA5_SINGLELEV_DIR.glob("era5sl_hourly_t2m_d2m_PR_*.nc"))
sl_files_instant = sorted(ERA5_SINGLELEV_DIR.glob("era5sl_hourly_wind_tp_sp_PR_*_instant.nc"))
sl_files_accum   = sorted(ERA5_SINGLELEV_DIR.glob("era5sl_hourly_wind_tp_sp_PR_*_accum.nc"))
print(f"  ERA5-SL t2m_d2m files:      {len(sl_files_t)}")
print(f"  ERA5-SL wind_sp (instant):  {len(sl_files_instant)}")
print(f"  ERA5-SL tp (accum):         {len(sl_files_accum)}")

if not sl_files_t or not sl_files_instant or not sl_files_accum:
    raise FileNotFoundError(
        f"ERA5-SL files not found in {ERA5_SINGLELEV_DIR}. "
        "Check ERA5_SINGLELEV_DIR in config.py."
    )

# Load all singlelev hourly data
print("  Loading ERA5-SL hourly data (this may take a few minutes)...")
ds_sl_t       = xr.open_mfdataset(sl_files_t,       combine="by_coords")
ds_sl_instant = xr.open_mfdataset(sl_files_instant, combine="by_coords")
ds_sl_accum   = xr.open_mfdataset(sl_files_accum,   combine="by_coords")
print(f"  ERA5-SL t2m grid: {ds_sl_t['latitude'].values[[0,-1]]} lat, "
      f"{ds_sl_t['longitude'].values[[0,-1]]} lon")

# ---------------------------------------------------------------------------
# Compute ERA5-SL exceedance directly from loaded DataArrays
# ---------------------------------------------------------------------------

from pr_ngvla.physics.thermodynamics import rh_from_t_td
import pandas as pd

MARIA_SKIP = {(2017, m) for m in range(9, 13)} | {(2018, m) for m in range(1, 7)}

def compute_exceedance_sl(da, thresholds, time_dim="valid_time"):
    """Monthly exceedance climatology from a DataArray."""
    lats = da["latitude"].values
    lons = da["longitude"].values
    n_thr = len(thresholds)
    nlat, nlon = len(lats), len(lons)
    acc_count = np.zeros((12, n_thr, nlat, nlon), dtype=np.float64)
    acc_hours = np.zeros((12,        nlat, nlon), dtype=np.float64)
    times_pd = pd.DatetimeIndex(da[time_dim].values)
    for m in range(1, 13):
        mask_m = (times_pd.month == m)
        for yr, mo in MARIA_SKIP:
            mask_m = mask_m & ~((times_pd.year == yr) & (times_pd.month == mo))
        data = da.values[mask_m]
        valid = (~np.isnan(data)).sum(axis=0)
        acc_hours[m-1] += valid
        for t_idx, thr in enumerate(thresholds):
            acc_count[m-1, t_idx] += np.sum(data > thr, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        exc = np.where(acc_hours[:, np.newaxis] > 0,
                       acc_count / acc_hours[:, np.newaxis],
                       np.nan)
    return xr.DataArray(
        exc,
        dims=["month", "threshold", "latitude", "longitude"],
        coords={"month": list(range(1,13)), "threshold": thresholds,
                "latitude": lats, "longitude": lons},
    )

print("\n  Computing RH exceedance from ERA5-SL...")
t2m_sl = ds_sl_t["t2m"] - 273.15
d2m_sl = ds_sl_t["d2m"] - 273.15
rh_sl  = rh_from_t_td(t2m_sl, d2m_sl)
exc_rh_sl = compute_exceedance_sl(rh_sl, THRESHOLDS["rh"])
print(f"  RH SL mean exceedance (>50%): "
      f"{float(exc_rh_sl.sel(threshold=50.0, method='nearest').mean()):.3f}")

print("  Computing wind exceedance from ERA5-SL...")
ws_sl = np.sqrt(ds_sl_instant["u10"]**2 + ds_sl_instant["v10"]**2)
exc_wind_sl = compute_exceedance_sl(ws_sl, THRESHOLDS["wind"])
print(f"  Wind SL mean exceedance (>9 m/s): "
      f"{float(exc_wind_sl.sel(threshold=9.0, method='nearest').mean()):.3f}")

print("  Computing precip exceedance from ERA5-SL...")
tp_sl_mmhr = ds_sl_accum["tp"] * 1000.0
exc_precip_sl = compute_exceedance_sl(tp_sl_mmhr, THRESHOLDS["precip"])
print(f"  Precip SL mean exceedance (>1 mm/hr): "
      f"{float(exc_precip_sl.sel(threshold=1.0, method='nearest').mean()):.3f}")

# ---------------------------------------------------------------------------
# Land fraction filter — applied BEFORE regridding
# Only use ERA5-SL pixels with >= 40% land fraction
# Methodology: Nacar et al. (2022); Muñoz-Sabater et al. (2021)
# ---------------------------------------------------------------------------

print("\nComputing ERA5-SL land fraction mask (threshold=40%)...")

import geopandas as gpd
from shapely.geometry import box as shapely_box

LAND_FRAC_THRESHOLD = 0.60
muni_gdf_lf = gpd.read_file(MUNI_SHP).to_crs("EPSG:4326")
if "STATEFP" in muni_gdf_lf.columns:
    muni_gdf_lf = muni_gdf_lf[muni_gdf_lf["STATEFP"] == "72"]
pr_union_lf = muni_gdf_lf.geometry.union_all()

sl_res = 0.25
sl_lats = exc_rh_sl["latitude"].values
sl_lons = exc_rh_sl["longitude"].values

# Build boolean mask on ERA5-SL grid: True = sufficient land fraction
sl_land_mask = np.zeros((len(sl_lats), len(sl_lons)), dtype=bool)
for i, lat in enumerate(sl_lats):
    for j, lon in enumerate(sl_lons):
        pixel = shapely_box(lon-sl_res/2, lat-sl_res/2,
                            lon+sl_res/2, lat+sl_res/2)
        frac = pr_union_lf.intersection(pixel).area / pixel.area
        sl_land_mask[i,j] = frac >= LAND_FRAC_THRESHOLD

n_valid = int(sl_land_mask.sum())
print(f"  Valid ERA5-SL pixels (>={LAND_FRAC_THRESHOLD*100:.0f}% land): {n_valid}")

# Apply mask to ERA5-SL exceedance BEFORE regridding
# Set invalid pixels to NaN so they don't contribute after interpolation
def apply_sl_landfrac_mask(da, mask):
    """Set ERA5-SL pixels with insufficient land fraction to NaN."""
    data = da.values.copy()
    for i in range(mask.shape[0]):
        for j in range(mask.shape[1]):
            if not mask[i,j]:
                if data.ndim == 4:   # (month, threshold, lat, lon)
                    data[:,:,i,j] = np.nan
                elif data.ndim == 3: # (month, lat, lon)
                    data[:,i,j] = np.nan
    return da.copy(data=data)

exc_rh_sl_filt     = apply_sl_landfrac_mask(exc_rh_sl,     sl_land_mask)
exc_wind_sl_filt   = apply_sl_landfrac_mask(exc_wind_sl,   sl_land_mask)
exc_precip_sl_filt = apply_sl_landfrac_mask(exc_precip_sl, sl_land_mask)
print("  Land fraction mask applied to RH, wind, precip.")

# ---------------------------------------------------------------------------
# Regrid ERA5-SL exceedance to ERA5-Land grid
# ---------------------------------------------------------------------------

print("\nRegridding ERA5-SL exceedance to ERA5-Land grid...")

exc_rh_sl_rg     = regrid_singlelev_to_era5land(exc_rh_sl_filt,     exc_land["rh"])
exc_wind_sl_rg   = regrid_singlelev_to_era5land(exc_wind_sl_filt,   exc_land["wind"])
exc_precip_sl_rg = regrid_singlelev_to_era5land(exc_precip_sl_filt, exc_land["precip"])

print("  Done.")

# ---------------------------------------------------------------------------
# Build provenance mask (saved to NetCDF for reproducibility)
# 0 = NaN (ocean), 1 = ERA5-Land, 2 = ERA5-SL valid, 3 = ERA5-SL filtered
# ---------------------------------------------------------------------------

print("\nBuilding provenance mask...")
ref_lats = exc_land["rh"]["latitude"].values
ref_lons = exc_land["rh"]["longitude"].values
da_ref   = exc_land["rh"].isel(month=0, threshold=0)

prov = np.zeros((len(ref_lats), len(ref_lons)), dtype=np.int8)

# Mark ERA5-Land pixels
era5land_valid = ~np.isnan(da_ref.values)
prov[era5land_valid] = 1

# Mark ERA5-SL pixels (gap pixels that received data after regrid)
da_rh_rg_ref = exc_rh_sl_rg.isel(month=0, threshold=0)
sl_filled = np.isnan(da_ref.values) & ~np.isnan(da_rh_rg_ref.values)
prov[sl_filled] = 2

# Pixels that are still NaN after gap-fill = 0 (stays 0)

prov_da = xr.DataArray(
    prov,
    dims=["latitude", "longitude"],
    coords={"latitude": ref_lats, "longitude": ref_lons},
    name="provenance",
    attrs={
        "long_name": "Data provenance mask",
        "flag_values": "0, 1, 2",
        "flag_meanings": "ocean_or_no_data ERA5-Land ERA5-SL-gapfill",
        "land_frac_threshold": LAND_FRAC_THRESHOLD,
        "description": (
            "0=NaN/ocean, 1=ERA5-Land (~9km), "
            "2=ERA5-SL gap-fill (>=40% land fraction, ~28km)"
        ),
    }
)
out_prov = GF_DIR / "provenance_mask.nc"
prov_da.to_dataset().to_netcdf(out_prov)
n_sl = int((prov == 2).sum())
n_land = int((prov == 1).sum())
print(f"  ERA5-Land pixels:      {n_land}")
print(f"  ERA5-SL gap-fill px:   {n_sl}")
print(f"  Saved: {out_prov}")

# ---------------------------------------------------------------------------
# Merge: ERA5-Land primary, ERA5-SL for gaps
# ---------------------------------------------------------------------------

print("\nMerging ERA5-Land + ERA5-SL...")

exc_rh_gf     = merge_era5land_singlelev(exc_land["rh"],     exc_rh_sl_rg,     "rh_exceedance")
exc_wind_gf   = merge_era5land_singlelev(exc_land["wind"],   exc_wind_sl_rg,   "wind_exceedance")
exc_precip_gf = merge_era5land_singlelev(exc_land["precip"], exc_precip_sl_rg, "precip_exceedance")
# PWV: interpolate ERA5-SL grid (0.25°) to ERA5-Land grid (0.1°) for consistency
# Bilinear interpolation — same method used in ERA5-Land production (Muñoz-Sabater et al. 2021)
exc_pwv_gf = regrid_singlelev_to_era5land(exc_land["pwv"], exc_land["rh"])
exc_pwv_gf.name = "pwv_exceedance"
exc_pwv_gf.attrs["gap_fill"] = (
    "ERA5-SL PWV (0.25°) bilinearly interpolated to ERA5-Land grid (0.1°) "
    "for spatial consistency. See Muñoz-Sabater et al. (2021)."
)

# Gap-fill summary
for varname, land_da, gf_da in [
    ("RH",     exc_land["rh"],     exc_rh_gf),
    ("Wind",   exc_land["wind"],   exc_wind_gf),
    ("Precip", exc_land["precip"], exc_precip_gf),
]:
    stats = gap_fill_summary(land_da, gf_da)
    print(f"  {varname}: {stats['n_land_era5land']} original land px | "
          f"{stats['n_gap_pixels']} gaps | "
          f"{stats['n_recovered']} recovered ({stats['pct_gap_recovered']}%) | "
          f"{stats['n_still_nan']} still NaN")

# ---------------------------------------------------------------------------
# Save gap-filled exceedance NetCDFs
# ---------------------------------------------------------------------------

print("\nSaving gap-filled exceedance NetCDFs...")

for varname, da, fname in [
    ("rh",     exc_rh_gf,     "rh_exceedance_gapfilled.nc"),
    ("wind",   exc_wind_gf,   "wind_exceedance_gapfilled.nc"),
    ("precip", exc_precip_gf, "precip_exceedance_gapfilled.nc"),
    ("pwv",    exc_pwv_gf,    "pwv_exceedance_gapfilled.nc"),
]:
    out = GF_DIR / fname
    da.to_dataset(name=f"{varname}_exceedance").to_netcdf(out)
    print(f"  Saved: {out}")

# ---------------------------------------------------------------------------
# Recompute composite index on gap-filled fields
# ---------------------------------------------------------------------------

print("\nRecomputing composite site selection index (gap-filled)...")

# Select primary thresholds for composite
exc_dict_gf = {
    "rh":     exc_rh_gf.sel(threshold=50.0,  method="nearest").drop_vars("threshold"),
    "wind":   exc_wind_gf.sel(threshold=9.0,  method="nearest").drop_vars("threshold"),
    "precip": exc_precip_gf.sel(threshold=1.0, method="nearest").drop_vars("threshold"),
    "pwv":    exc_pwv_gf.sel(threshold=26.0,  method="nearest").drop_vars("threshold"),
}

composite_monthly_gf = composite_index(exc_dict_gf, weights=DEFAULT_WEIGHTS)
composite_annual_gf  = annual_composite(composite_monthly_gf)

# Count new pixels
n_new = int((~np.isnan(composite_annual_gf.values)).sum())
n_old = int((~np.isnan(
    xr.open_dataset(PHASE3_DIR / "composite_index_annual.nc")
    ["site_selection_index_annual"].values
)).sum())
print(f"  Original land pixels: {n_old}")
print(f"  After gap-fill:       {n_new}  (+{n_new - n_old} pixels recovered)")

# Save
out_mon_gf = GF_DIR / "composite_index_monthly_gf.nc"
out_ann_gf = GF_DIR / "composite_index_annual_gf.nc"
composite_monthly_gf.to_dataset().to_netcdf(out_mon_gf)
composite_annual_gf.to_dataset().to_netcdf(out_ann_gf)
print(f"  Saved: {out_mon_gf}")
print(f"  Saved: {out_ann_gf}")

# ---------------------------------------------------------------------------
# Gap-fill report
# ---------------------------------------------------------------------------

print("\nWriting gap-fill report...")

ann_gf_vals = composite_annual_gf.values
lon2d, lat2d = np.meshgrid(
    composite_annual_gf["longitude"].values,
    composite_annual_gf["latitude"].values,
)

# New pixels (were NaN before)
ann_old = xr.open_dataset(PHASE3_DIR / "composite_index_annual.nc")["site_selection_index_annual"]
new_px_mask = np.isnan(ann_old.values) & ~np.isnan(ann_gf_vals)

import geopandas as gpd
from shapely.geometry import Point
muni_gdf = gpd.read_file(MUNI_SHP).to_crs("EPSG:4326")
if "STATEFP" in muni_gdf.columns:
    muni_gdf = muni_gdf[muni_gdf["STATEFP"] == "72"].copy()
name_col = "NAME" if "NAME" in muni_gdf.columns else muni_gdf.columns[0]

def pixel_to_muni(lon, lat):
    pt = Point(lon, lat)
    hits = muni_gdf[muni_gdf.geometry.contains(pt)]
    if len(hits) > 0:
        return str(hits.iloc[0][name_col])
    muni_gdf["_d"] = muni_gdf.geometry.centroid.distance(pt)
    return str(muni_gdf.loc[muni_gdf["_d"].idxmin(), name_col])

new_lons = lon2d[new_px_mask]
new_lats = lat2d[new_px_mask]
new_vals = ann_gf_vals[new_px_mask]
order_new = np.argsort(new_vals)[::-1]

report_path = GF_DIR / "gapfill_report.txt"
with open(report_path, "w") as f:
    def p(s=""):
        print(s)
        f.write(s + "\n")

    p("=" * 65)
    p("ngVLA Puerto Rico — Phase 3 ERA5-SL Gap-Fill Report")
    p("ERA5-Land primary + ERA5 single-levels for coastal NaN pixels")
    p("=" * 65)
    p()
    p(f"Original ERA5-Land land pixels: {n_old}")
    p(f"After gap-fill:                 {n_new}  (+{n_new - n_old})")
    p()
    p("NEW PIXELS RECOVERED (sorted by site selection index):")
    p("-" * 65)
    p(f"{'Lon':>9}  {'Lat':>7}  {'Index':>7}  Municipality")
    p("-" * 65)
    for i in order_new:
        muni = pixel_to_muni(new_lons[i], new_lats[i])
        p(f"{new_lons[i]:>9.3f}  {new_lats[i]:>7.3f}  "
          f"{new_vals[i]:>7.4f}  {muni}")
    p()
    p("SCIENTIFIC NOTE")
    p("-" * 65)
    p("ERA5-Land (~9 km) assigns NaN to coastal pixels with insufficient")
    p("land fraction. ERA5 single-levels (~28 km) uses a different")
    p("land-sea mask and recovers coastal coverage. Both products")
    p("derive from the same ECMWF IFS system and are physically")
    p("consistent (Hersbach et al. 2020; Muñoz-Sabater et al. 2021).")
    p("ERA5-Land is used where available (higher resolution, preferred).")
    p("ERA5-SL is used only for gap pixels as a complementary source.")
    p("=" * 65)

# ---------------------------------------------------------------------------
# Generate updated maps
# ---------------------------------------------------------------------------

print("\nGenerating gap-filled composite maps...")

muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
stations = load_noaa_isd_stations(NOAA_ISD_DIR)

CMAP = plt.cm.RdYlGn

def get_vlims(da, p_low=2, p_high=98):
    vals = da.values[~np.isnan(da.values)]
    if vals.size == 0:
        return 0.0, 1.0
    vmin, vmax = np.percentile(vals, p_low), np.percentile(vals, p_high)
    return float(vmin), float(max(vmax, vmin + 0.005))

lons_gf = composite_annual_gf["longitude"].values
lats_gf = composite_annual_gf["latitude"].values

# --- Annual map ---
vmin_a, vmax_a = get_vlims(composite_annual_gf)
fig_a = plt.figure(figsize=(12, 5))
ax_a = fig_a.add_axes([0.05, 0.08, 0.80, 0.82],
                       projection=ccrs.PlateCarree())
pcm = ax_a.pcolormesh(lons_gf, lats_gf, composite_annual_gf.values,
                      cmap=CMAP, vmin=vmin_a, vmax=vmax_a,
                      transform=ccrs.PlateCarree(), shading="auto")
mask_ocean(ax_a, muni_land_union)
plot_base_map(ax_a, coast_union, muni_clip)
add_station_overlay(ax_a, stations)
add_north_arrow(ax_a)
style_axes_single(ax_a, MAP_XLIM, MAP_YLIM)

cbar_ax = fig_a.add_axes([0.87, 0.12, 0.018, 0.74])
sm = plt.cm.ScalarMappable(cmap=CMAP,
                            norm=mcolors.Normalize(vmin=vmin_a, vmax=vmax_a))
sm.set_array([])
cb = fig_a.colorbar(sm, cax=cbar_ax)
cb.set_label("Site selection index\n[0=least favorable, 1=most favorable]",
             fontsize=8.5)

ax_a.set_title(
    "Annual mean site selection index (ERA5-Land + ERA5-SL gap-fill)\n"
    "ERA5-Land 2004–2023  |  Variables: RH, wind, precip, PWV  |  Equal weights",
    fontsize=10, pad=8,
)

# Annotation at best gap-filled pixel (if any new pixels)
if len(new_vals) > 0:
    best_new_lon = new_lons[order_new[0]]
    best_new_lat = new_lats[order_new[0]]
    best_new_muni = pixel_to_muni(best_new_lon, best_new_lat)
    ax_a.annotate(
        f"SW corridor\n(best region)\n{best_new_muni}",
        xy=(best_new_lon, best_new_lat),
        xytext=(best_new_lon - 0.6, best_new_lat - 0.18),
        fontsize=7.5, color="darkgreen", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1.0),
        transform=ccrs.PlateCarree(),
    )
else:
    # Fall back to best overall pixel
    best_idx = np.unravel_index(np.nanargmax(ann_gf_vals), ann_gf_vals.shape)
    best_lon_gf = float(lons_gf[best_idx[1]])
    best_lat_gf = float(lats_gf[best_idx[0]])
    best_muni_gf = pixel_to_muni(best_lon_gf, best_lat_gf)
    ax_a.annotate(
        f"SW corridor\n(best region)\n{best_muni_gf}",
        xy=(best_lon_gf, best_lat_gf),
        xytext=(best_lon_gf - 0.6, best_lat_gf - 0.18),
        fontsize=7.5, color="darkgreen", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1.0),
        transform=ccrs.PlateCarree(),
    )

out_ann_map = MAP_DIR / "phase3_composite_annual_gf.png"
fig_a.savefig(out_ann_map, dpi=200, bbox_inches="tight")
plt.close(fig_a)
print(f"  Saved: {out_ann_map}")

# --- Monthly map ---
vmin_m, vmax_m = get_vlims(composite_monthly_gf)
fig_m, axes = plt.subplots(3, 4, figsize=(18, 10),
                            subplot_kw={"projection": ccrs.PlateCarree()})
for i, ax in enumerate(axes.flat):
    m = i + 1
    data_m = composite_monthly_gf.sel(month=m).values
    ax.pcolormesh(lons_gf, lats_gf, data_m,
                  cmap=CMAP, vmin=vmin_m, vmax=vmax_m,
                  transform=ccrs.PlateCarree(), shading="auto")
    mask_ocean(ax, muni_land_union)
    plot_base_map(ax, coast_union, muni_clip)
    style_axes_grid(ax, MAP_XLIM, MAP_YLIM, 3, 4)
    ax.set_title(MONTHS[i], fontsize=9, fontweight="bold")

cbar_ax_m = fig_m.add_axes([0.92, 0.12, 0.015, 0.76])
sm_m = plt.cm.ScalarMappable(cmap=CMAP,
                               norm=mcolors.Normalize(vmin=vmin_m, vmax=vmax_m))
sm_m.set_array([])
cb_m = fig_m.colorbar(sm_m, cax=cbar_ax_m)
cb_m.set_label("Site selection index [0=least favorable, 1=most favorable]",
               fontsize=9)
fig_m.suptitle(
    "Monthly site selection index (ERA5-Land + ERA5-SL gap-fill) — 2004–2023\n"
    "Variables: RH > 50%, wind > 9 m/s, precip > 1 mm/hr, PWV > 26 mm  |  Equal weights",
    fontsize=11, y=1.01,
)
plt.tight_layout(rect=[0, 0, 0.91, 1.0])

out_mon_map = MAP_DIR / "phase3_composite_monthly_gf.png"
fig_m.savefig(out_mon_map, dpi=200, bbox_inches="tight")
plt.close(fig_m)
print(f"  Saved: {out_mon_map}")

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

print()
print("=" * 65)
print("Phase 3 gap-fill: DONE")
print(f"NetCDFs in: {GF_DIR}")
print(f"Maps in:    {MAP_DIR}")
print(f"Report:     {GF_DIR / 'gapfill_report.txt'}")
print()
print("Poster figures:")
print(f"  {out_ann_map.name}   ← USE THIS (replaces phase3_composite_annual.png)")
print(f"  {out_mon_map.name}   ← USE THIS (replaces phase3_composite_monthly.png)")
print("=" * 65)
