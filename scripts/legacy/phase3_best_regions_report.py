"""
scripts/phase3_best_regions_report.py

Phase 3 — Best candidate regions report.

For every pixel in the top N% of the annual site selection index, retrieves:
  - Site selection index (annual mean + monthly)
  - Phase 2 exceedance fractions for all variables and thresholds
  - Phase 1 monthly climatology means (T, RH, T-Td, wind, precip, PWV)
  - Municipality name

Outputs:
  outputs/phase3/best_regions_annual.csv      — one row per top pixel (annual)
  outputs/phase3/best_regions_monthly.csv     — one row per (pixel × month)
  outputs/phase3/best_regions_summary.txt     — human-readable report
  outputs/phase3/best_municipalities.csv      — aggregated by municipality

Usage:
    cd /export/ngvla/cpollack/pr_ngvla
    python scripts/phase3_best_regions_report.py [--top-pct 10]
"""

import argparse
import numpy as np
import xarray as xr
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

from pr_ngvla.config import (
    OUTPUTS, COAST_SHP, MUNI_SHP,
    ERA5_MONTHLY_DIR,
)
from pr_ngvla.data.loaders import load_era5_monthly
from pr_ngvla.data.temporal import monthly_climatology, precip_to_mm_month
from pr_ngvla.physics.thermodynamics import rh_from_t_td, dew_point_depression

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("--top-pct", type=float, default=10.0,
                    help="Top N%% of pixels to include in report (default: 10)")
args = parser.parse_args()
TOP_PCT = args.top_pct

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PHASE2_DIR = OUTPUTS / "phase2"
PHASE3_DIR = OUTPUTS / "phase3"
PHASE3_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

print("=" * 65)
print(f"Phase 3 — Best Candidate Regions Report  (top {TOP_PCT}%)")
print("=" * 65)

# ---------------------------------------------------------------------------
# Load site selection index
# ---------------------------------------------------------------------------

print("\nLoading site selection index...")
ds_ann = xr.open_dataset(PHASE3_DIR / "composite_index_annual.nc")
ds_mon = xr.open_dataset(PHASE3_DIR / "composite_index_monthly.nc")
idx_ann = ds_ann["site_selection_index_annual"]
idx_mon = ds_mon["site_selection_index"]

ann_lats = idx_ann["latitude"].values
ann_lons = idx_ann["longitude"].values
lon2d, lat2d = np.meshgrid(ann_lons, ann_lats)

ann_vals = idx_ann.values
land_mask = ~np.isnan(ann_vals)
n_land = int(land_mask.sum())
n_top = max(1, int(TOP_PCT / 100.0 * n_land))

flat_vals = ann_vals[land_mask]
flat_lons = lon2d[land_mask]
flat_lats = lat2d[land_mask]
order = np.argsort(flat_vals)[::-1]
flat_vals = flat_vals[order]
flat_lons = flat_lons[order]
flat_lats = flat_lats[order]

top_lons = flat_lons[:n_top]
top_lats = flat_lats[:n_top]
top_idx  = flat_vals[:n_top]

print(f"  Land pixels total: {n_land}")
print(f"  Top {TOP_PCT}% → {n_top} pixels")
print(f"  Index range in top {TOP_PCT}%: [{top_idx[-1]:.4f}, {top_idx[0]:.4f}]")

# ---------------------------------------------------------------------------
# Municipality lookup
# ---------------------------------------------------------------------------

print("\nLoading municipality shapefile...")
muni_gdf = gpd.read_file(MUNI_SHP).to_crs("EPSG:4326")
if "STATEFP" in muni_gdf.columns:
    muni_gdf = muni_gdf[muni_gdf["STATEFP"] == "72"].copy()
name_col = "NAME" if "NAME" in muni_gdf.columns else muni_gdf.columns[0]

def pixel_to_municipality(lon: float, lat: float) -> str:
    pt = Point(lon, lat)
    hits = muni_gdf[muni_gdf.geometry.contains(pt)]
    if len(hits) > 0:
        return str(hits.iloc[0][name_col])
    muni_gdf["_dist"] = muni_gdf.geometry.centroid.distance(pt)
    return str(muni_gdf.loc[muni_gdf["_dist"].idxmin(), name_col])

print("  Assigning municipalities to top pixels...")
munis = [pixel_to_municipality(lo, la) for lo, la in zip(top_lons, top_lats)]

# ---------------------------------------------------------------------------
# Load Phase 2 exceedance — all variables, all thresholds
# ---------------------------------------------------------------------------

print("\nLoading Phase 2 exceedance data...")

EXC_FILES = {
    "rh":     ("rh_exceedance_climatology.nc",     "rh_exceedance"),
    "wind":   ("wind_exceedance_climatology.nc",   "wind_exceedance"),
    "precip": ("precip_exceedance_climatology.nc", "precip_exceedance"),
    "pwv":    ("pwv_exceedance_climatology.nc",    "pwv_exceedance"),
}

exc_ds = {}
exc_thresholds = {}
for var, (fname, varname) in EXC_FILES.items():
    ds = xr.open_dataset(PHASE2_DIR / fname)
    exc_ds[var] = ds[varname]   # dims: (month, threshold, latitude, longitude)
    exc_thresholds[var] = ds["threshold"].values
    print(f"  {var}: thresholds = {exc_thresholds[var]}")

def get_exceedance_at_pixel(var: str, lon: float, lat: float) -> dict:
    """Return dict of threshold → monthly array (12,) for a pixel."""
    da = exc_ds[var]
    px = da.sel(latitude=lat, longitude=lon, method="nearest")
    result = {}
    for thr in exc_thresholds[var]:
        monthly = px.sel(threshold=thr, method="nearest").values  # (12,)
        result[float(thr)] = monthly
    return result

# ---------------------------------------------------------------------------
# Load Phase 1 monthly climatology
# ---------------------------------------------------------------------------

print("\nLoading Phase 1 climatology...")

# Temperature + dew point
ds_t = load_era5_monthly(ERA5_MONTHLY_DIR / "era5land_monthly_t2m_d2m_PR_2004_2023.nc")
t2m_clim  = monthly_climatology(ds_t["t2m"]) + (-273.15)   # K → °C
d2m_clim  = monthly_climatology(ds_t["d2m"]) + (-273.15)
tdep_clim = t2m_clim - d2m_clim                             # T - Td

# RH from Magnus formula (inputs in °C)
rh_clim = rh_from_t_td(t2m_clim, d2m_clim)

# Wind + precip
ds_w = load_era5_monthly(ERA5_MONTHLY_DIR / "era5land_monthly_wind_tp_sp_PR_2004_2023.nc")
u10_clim = monthly_climatology(ds_w["u10"])
v10_clim = monthly_climatology(ds_w["v10"])
ws_clim  = np.sqrt(u10_clim**2 + v10_clim**2)
tp_clim  = precip_to_mm_month(monthly_climatology(ds_w["tp"]))

# PWV — annual from ERA5 single-levels corrected buffered TCWV acquisition.
# The buffered domain is interpolation support only; final analysis remains restricted to Puerto Rico.
from pr_ngvla.config import ERA5_PWV_BUFFERED_PR_DIR

pwv_nc_list = sorted(ERA5_PWV_BUFFERED_PR_DIR.glob("*.nc"))
if not pwv_nc_list:
    raise FileNotFoundError(
        f"No corrected buffered PWV files found in {ERA5_PWV_BUFFERED_PR_DIR}. "
        "Run scripts/download_era5_pwv_pr.py with --buffered-pr first."
    )
pwv_ds = xr.open_mfdataset(pwv_nc_list, combine="by_coords")
pwv_var = [v for v in pwv_ds.data_vars if "tcwv" in v.lower() or "pwv" in v.lower()][0]
pwv_clim = monthly_climatology(pwv_ds[pwv_var])

CLIM_VARS = {
    "T2m_mean_C":   t2m_clim,
    "RH_mean_pct":  rh_clim,
    "Tdep_mean_C":  tdep_clim,
    "Wind_mean_ms": ws_clim,
    "Precip_mm_mo": tp_clim,
    "PWV_mean_mm":  pwv_clim,
}

def get_clim_at_pixel(lon: float, lat: float) -> dict:
    """Return annual mean and monthly array for each Phase 1 variable."""
    result = {}
    for name, da in CLIM_VARS.items():
        # select nearest pixel
        try:
            px = da.sel(latitude=lat, longitude=lon, method="nearest").values  # (12,)
        except Exception:
            try:
                px = da.sel(lat=lat, lon=lon, method="nearest").values
            except Exception:
                px = np.full(12, np.nan)
        result[name] = px  # shape (12,)
    return result

# ---------------------------------------------------------------------------
# Build annual summary table
# ---------------------------------------------------------------------------

print("\nBuilding annual summary table...")

rows_ann = []
for i, (lo, la, ix, mu) in enumerate(zip(top_lons, top_lats, top_idx, munis)):

    row = {
        "pixel_rank":  i + 1,
        "municipality": mu,
        "longitude":   round(float(lo), 4),
        "latitude":    round(float(la), 4),
        "site_selection_index_annual": round(float(ix), 5),
    }

    # Monthly index — annual mean already have; add min/max month
    mon_idx = idx_mon.sel(latitude=la, longitude=lo, method="nearest").values  # (12,)
    row["index_best_month"]  = MONTHS[int(np.argmax(mon_idx))]
    row["index_worst_month"] = MONTHS[int(np.argmin(mon_idx))]
    row["index_jan"] = round(float(mon_idx[0]), 5)
    row["index_feb"] = round(float(mon_idx[1]), 5)
    row["index_mar"] = round(float(mon_idx[2]), 5)
    row["index_apr"] = round(float(mon_idx[3]), 5)

    # Phase 1 climatology — annual means
    clim = get_clim_at_pixel(lo, la)
    for name, arr in clim.items():
        row[f"{name}_ann"] = round(float(np.nanmean(arr)), 3)
        # dry season mean (Jan–Apr)
        row[f"{name}_dry"] = round(float(np.nanmean(arr[:4])), 3)

    # Phase 2 exceedance — annual mean per threshold
    for var in ["rh", "wind", "precip", "pwv"]:
        exc = get_exceedance_at_pixel(var, lo, la)
        for thr, monthly_arr in exc.items():
            col = f"exc_{var}_{thr:.0f}_ann"
            row[col] = round(float(np.nanmean(monthly_arr)), 4)
            col_dry = f"exc_{var}_{thr:.0f}_dry"
            row[col_dry] = round(float(np.nanmean(monthly_arr[:4])), 4)

    rows_ann.append(row)

df_ann = pd.DataFrame(rows_ann)

# ---------------------------------------------------------------------------
# Build monthly detail table (top 10 pixels only — manageable size)
# ---------------------------------------------------------------------------

print("Building monthly detail table (top 10 pixels)...")

rows_mon = []
for i in range(min(10, n_top)):
    lo, la, mu = top_lons[i], top_lats[i], munis[i]

    clim = get_clim_at_pixel(lo, la)
    exc_all = {var: get_exceedance_at_pixel(var, lo, la) for var in ["rh","wind","precip","pwv"]}
    mon_idx = idx_mon.sel(latitude=la, longitude=lo, method="nearest").values

    for m in range(12):
        row = {
            "pixel_rank":   i + 1,
            "municipality": mu,
            "longitude":    round(float(lo), 4),
            "latitude":     round(float(la), 4),
            "month":        MONTHS[m],
            "month_num":    m + 1,
            "site_selection_index": round(float(mon_idx[m]), 5),
        }
        for name, arr in clim.items():
            row[name] = round(float(arr[m]), 3) if not np.isnan(arr[m]) else np.nan
        for var in ["rh", "wind", "precip", "pwv"]:
            for thr, monthly_arr in exc_all[var].items():
                row[f"exc_{var}_{thr:.0f}"] = round(float(monthly_arr[m]), 4)
        rows_mon.append(row)

df_mon = pd.DataFrame(rows_mon)

# ---------------------------------------------------------------------------
# Municipality aggregate table
# ---------------------------------------------------------------------------

print("Building municipality aggregate table...")

df_muni = (
    df_ann.groupby("municipality")
    .agg(
        n_pixels=("pixel_rank", "count"),
        index_annual_mean=("site_selection_index_annual", "mean"),
        index_annual_max=("site_selection_index_annual", "max"),
        T2m_ann=("T2m_mean_C_ann", "mean"),
        RH_ann=("RH_mean_pct_ann", "mean"),
        Tdep_ann=("Tdep_mean_C_ann", "mean"),
        Wind_ann=("Wind_mean_ms_ann", "mean"),
        Precip_ann=("Precip_mm_mo_ann", "mean"),
        PWV_ann=("PWV_mean_mm_ann", "mean"),
        exc_rh50_ann=("exc_rh_50_ann", "mean"),
        exc_precip1_ann=("exc_precip_1_ann", "mean"),
        exc_pwv26_ann=("exc_pwv_26_ann", "mean"),
        exc_wind9_ann=("exc_wind_9_ann", "mean"),
        T2m_dry=("T2m_mean_C_dry", "mean"),
        RH_dry=("RH_mean_pct_dry", "mean"),
        Precip_dry=("Precip_mm_mo_dry", "mean"),
        PWV_dry=("PWV_mean_mm_dry", "mean"),
        exc_rh50_dry=("exc_rh_50_dry", "mean"),
        exc_precip1_dry=("exc_precip_1_dry", "mean"),
        exc_pwv26_dry=("exc_pwv_26_dry", "mean"),
    )
    .sort_values("index_annual_mean", ascending=False)
    .reset_index()
)
df_muni = df_muni.round(4)

# ---------------------------------------------------------------------------
# Save CSVs
# ---------------------------------------------------------------------------

print("\nSaving outputs...")

out_ann  = PHASE3_DIR / "best_regions_annual.csv"
out_mon  = PHASE3_DIR / "best_regions_monthly.csv"
out_muni = PHASE3_DIR / "best_municipalities.csv"
out_txt  = PHASE3_DIR / "best_regions_summary.txt"

df_ann.to_csv(out_ann, index=False)
df_mon.to_csv(out_mon, index=False)
df_muni.to_csv(out_muni, index=False)

print(f"  {out_ann}")
print(f"  {out_mon}")
print(f"  {out_muni}")

# ---------------------------------------------------------------------------
# Human-readable summary report
# ---------------------------------------------------------------------------

with open(out_txt, "w") as f:
    def p(s=""):
        print(s)
        f.write(s + "\n")

    p("=" * 65)
    p(f"ngVLA Puerto Rico — Phase 3 Best Candidate Regions Report")
    p(f"Top {TOP_PCT}% of pixels by annual site selection index")
    p(f"ERA5-Land 2004–2023 | Equal weights (RH, wind, precip, PWV)")
    p("=" * 65)

    p()
    p("TOP 10 PIXELS — ANNUAL")
    p("-" * 65)
    p(f"{'Rk':>2}  {'Municipality':<18}  {'Lon':>8}  {'Lat':>7}  "
      f"{'Idx':>6}  {'BestMo':>6}  {'RH>50%':>7}  {'P>1mm':>7}  "
      f"{'PWV>26':>7}  {'W>9':>6}")
    p("-" * 65)
    for _, r in df_ann.head(10).iterrows():
        p(f"{int(r['pixel_rank']):2d}  {r.municipality:<18}  {r.longitude:>8.3f}  "
          f"{r.latitude:>7.3f}  {r.site_selection_index_annual:>6.4f}  "
          f"{r.index_best_month:>6}  "
          f"{r.exc_rh_50_ann:>7.3f}  {r.exc_precip_1_ann:>7.3f}  "
          f"{r.exc_pwv_26_ann:>7.3f}  {r.exc_wind_9_ann:>6.4f}")

    p()
    p("TOP MUNICIPALITIES — ANNUAL MEAN")
    p("-" * 65)
    p(f"{'Municipality':<18}  {'Pix':>4}  {'Idx':>6}  "
      f"{'T(°C)':>6}  {'RH(%)':>6}  {'Tdep':>5}  "
      f"{'W(m/s)':>6}  {'P(mm)':>6}  {'PWV':>5}  "
      f"{'RH>50%':>7}  {'P>1mm':>7}  {'PWV>26':>7}")
    p("-" * 65)
    for _, r in df_muni.iterrows():
        p(f"{r.municipality:<18}  {int(r.n_pixels):>4}  "
          f"{r.index_annual_mean:>6.4f}  "
          f"{r.T2m_ann:>6.1f}  {r.RH_ann:>6.1f}  {r.Tdep_ann:>5.2f}  "
          f"{r.Wind_ann:>6.2f}  {r.Precip_ann:>6.1f}  {r.PWV_ann:>5.1f}  "
          f"{r.exc_rh50_ann:>7.3f}  {r.exc_precip1_ann:>7.3f}  "
          f"{r.exc_pwv26_ann:>7.3f}")

    p()
    p("TOP MUNICIPALITIES — DRY SEASON (Jan–Apr)")
    p("-" * 65)
    p(f"{'Municipality':<18}  {'RH(%)':>6}  {'P(mm)':>6}  "
      f"{'PWV':>5}  {'RH>50%':>7}  {'P>1mm':>7}  {'PWV>26':>7}")
    p("-" * 65)
    for _, r in df_muni.iterrows():
        p(f"{r.municipality:<18}  {r.RH_dry:>6.1f}  {r.Precip_dry:>6.1f}  "
          f"{r.PWV_dry:>5.1f}  {r.exc_rh50_dry:>7.3f}  "
          f"{r.exc_precip1_dry:>7.3f}  {r.exc_pwv26_dry:>7.3f}")

    p()
    p("MONTHLY DETAIL — TOP 5 PIXELS")
    p("-" * 65)
    top5 = df_mon[df_mon["pixel_rank"] <= 5]
    for rank in range(1, 6):
        sub = top5[top5["pixel_rank"] == rank]
        if sub.empty:
            continue
        muni = sub.iloc[0]["municipality"]
        lo   = sub.iloc[0]["longitude"]
        la   = sub.iloc[0]["latitude"]
        p(f"\n  Rank {rank} — {muni} ({lo:.3f}, {la:.3f})")
        p(f"  {'Mo':>3}  {'Idx':>6}  {'T':>5}  {'RH':>5}  "
          f"{'Tdep':>5}  {'W':>5}  {'Prec':>6}  {'PWV':>5}  "
          f"{'RH>50':>6}  {'P>1':>6}  {'V>26':>6}")
        for _, r in sub.iterrows():
            p(f"  {r.month:>3}  {r.site_selection_index:>6.4f}  "
              f"{r.T2m_mean_C:>5.1f}  {r.RH_mean_pct:>5.1f}  "
              f"{r.Tdep_mean_C:>5.2f}  {r.Wind_mean_ms:>5.2f}  "
              f"{r.Precip_mm_mo:>6.1f}  {r.PWV_mean_mm:>5.1f}  "
              f"{r['exc_rh_50']:>6.3f}  {r['exc_precip_1']:>6.3f}  "
              f"{r['exc_pwv_26']:>6.3f}")

    p()
    p("NOTE ON MISSING COASTAL PIXELS")
    p("-" * 65)
    p("Municipalities such as Lajas and Guánica may not appear in this")
    p("report because their ERA5-Land pixels (~9 km resolution) have")
    p("insufficient land fraction and are assigned NaN in the source data.")
    p("ERA5 single-levels (0.25°, already downloaded) would recover")
    p("partial coverage for these coastal zones — identified as future work.")
    p("=" * 65)

print(f"  {out_txt}")
print()
print("DONE — check outputs/phase3/best_regions_summary.txt for full report")
