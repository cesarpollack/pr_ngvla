"""
scripts/phase3_map_composite.py

Phase 3 — Composite suitability index maps.

Generates:
  1. Annual mean composite index map (single panel) — poster figure
  2. Monthly composite index maps (12-panel grid) — supplementary

Usage:
    cd /export/ngvla/cpollack/pr_ngvla
    python scripts/phase3_map_composite.py

Output:
    outputs/maps/phase3/phase3_composite_annual.png
    outputs/maps/phase3/phase3_composite_monthly.png
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
from pathlib import Path

from pr_ngvla.config import (
    OUTPUTS, COAST_SHP, MUNI_SHP, NOAA_ISD_DIR,
    MAP_XLIM, MAP_YLIM,
)
from pr_ngvla.data.spatial import load_vector_data, load_dem
from pr_ngvla.data.loaders import load_noaa_isd_stations
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, style_axes_single,
    add_colorbar, add_station_overlay, add_north_arrow,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PHASE3_DIR = OUTPUTS / "phase3"
MAP_DIR = OUTPUTS / "maps" / "phase3"
MAP_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load composite data
# ---------------------------------------------------------------------------

print("Loading composite index data...")

ds_monthly = xr.open_dataset(PHASE3_DIR / "composite_index_monthly.nc")
ds_annual  = xr.open_dataset(PHASE3_DIR / "composite_index_annual.nc")

composite_monthly = ds_monthly["site_selection_index"]
composite_annual  = ds_annual["site_selection_index_annual"]

# ---------------------------------------------------------------------------
# Load spatial data (standard pattern)
# ---------------------------------------------------------------------------

print("Loading spatial data...")
muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)

print("Loading NOAA ISD stations...")
stations = load_noaa_isd_stations(NOAA_ISD_DIR)

# ---------------------------------------------------------------------------
# Color scale setup
# ---------------------------------------------------------------------------

CMAP = plt.cm.RdYlGn   # Red=least favorable, Green=most favorable

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

# ---------------------------------------------------------------------------
# Helper: determine vmin/vmax from data (land pixels only)
# ---------------------------------------------------------------------------

def get_vlims(da: xr.DataArray, percentile_low=2, percentile_high=98):
    """Robust vmin/vmax ignoring NaN (ocean)."""
    vals = da.values[~np.isnan(da.values)]
    if vals.size == 0:
        return 0.0, 1.0
    vmin = np.percentile(vals, percentile_low)
    vmax = np.percentile(vals, percentile_high)
    if vmax - vmin < 0.005:
        vmax = vmin + 0.005
    return float(vmin), float(vmax)


# ---------------------------------------------------------------------------
# BEST REGION ANALYSIS — computed from data, not assumed
# ---------------------------------------------------------------------------

import geopandas as gpd
from shapely.geometry import Point

print()
print("=" * 60)
print("BEST REGION ANALYSIS")
print("=" * 60)

# --- Flatten annual index to find top pixels ---
ann_vals  = composite_annual.values          # (lat, lon)
ann_lats  = composite_annual["latitude"].values
ann_lons  = composite_annual["longitude"].values

lon2d, lat2d = np.meshgrid(ann_lons, ann_lats)

land_mask = ~np.isnan(ann_vals)
flat_vals = ann_vals[land_mask]
flat_lons = lon2d[land_mask]
flat_lats = lat2d[land_mask]

# Sort descending
order = np.argsort(flat_vals)[::-1]
flat_vals = flat_vals[order]
flat_lons = flat_lons[order]
flat_lats = flat_lats[order]

# --- Load municipality shapefile for spatial join ---
muni_gdf = gpd.read_file(MUNI_SHP).to_crs("EPSG:4326")
# Keep only PR municipalities (STATEFP = '72')
if "STATEFP" in muni_gdf.columns:
    muni_gdf = muni_gdf[muni_gdf["STATEFP"] == "72"].copy()
# Name column
name_col = "NAME" if "NAME" in muni_gdf.columns else muni_gdf.columns[0]

def pixel_to_municipality(lon: float, lat: float) -> str:
    """Return municipality name for a given lon/lat, or 'Unknown'."""
    pt = Point(lon, lat)
    hits = muni_gdf[muni_gdf.geometry.contains(pt)]
    if len(hits) > 0:
        return hits.iloc[0][name_col]
    # Fallback: nearest centroid
    muni_gdf["dist"] = muni_gdf.geometry.centroid.distance(pt)
    return muni_gdf.loc[muni_gdf["dist"].idxmin(), name_col]

# --- Print top 10 pixels ---
print(f"\nTop 10 pixels by annual site selection index:")
print(f"{'Rank':>4}  {'Index':>7}  {'Lon':>9}  {'Lat':>8}  Municipality")
print("─" * 55)
for rank in range(min(10, len(flat_vals))):
    muni = pixel_to_municipality(flat_lons[rank], flat_lats[rank])
    print(f"  {rank+1:2d}   {flat_vals[rank]:.4f}   {flat_lons[rank]:+.3f}   "
          f"{flat_lats[rank]:.3f}   {muni}")

# --- Best single pixel → arrow target ---
best_lon = float(flat_lons[0])
best_lat = float(flat_lats[0])
best_val = float(flat_vals[0])
best_muni = pixel_to_municipality(best_lon, best_lat)

# --- Top 5% region centroid ---
n_top5 = max(1, int(0.05 * len(flat_vals)))
top5_lons = flat_lons[:n_top5]
top5_lats = flat_lats[:n_top5]
top5_vals = flat_vals[:n_top5]
top5_centroid_lon = float(np.mean(top5_lons))
top5_centroid_lat = float(np.mean(top5_lats))

# Municipalities represented in top 5%
top5_munis = {}
for lo, la, va in zip(top5_lons, top5_lats, top5_vals):
    m = pixel_to_municipality(lo, la)
    top5_munis[m] = top5_munis.get(m, [])
    top5_munis[m].append(va)

print(f"\nTop 5% region ({n_top5} pixels):")
print(f"  Centroid: ({top5_centroid_lon:.3f}, {top5_centroid_lat:.3f})")
print(f"  Mean index: {float(np.mean(top5_vals)):.4f}")
print(f"  Municipalities:")
for m, vals_m in sorted(top5_munis.items(), key=lambda x: -np.mean(x[1])):
    print(f"    {m}: mean={np.mean(vals_m):.4f}  ({len(vals_m)} pixels)")

# --- Monthly best region ---
print(f"\nBest municipality by month:")
if "month" in composite_monthly.dims:
    for mo in range(1, 13):
        da_m = composite_monthly.sel(month=mo)
        vals_m  = da_m.values[~np.isnan(da_m.values)]
        lons_m  = lon2d[~np.isnan(da_m.values)]
        lats_m  = lat2d[~np.isnan(da_m.values)]
        order_m = np.argsort(vals_m)[::-1]
        top_muni = pixel_to_municipality(lons_m[order_m[0]], lats_m[order_m[0]])
        print(f"  {MONTHS[mo-1]:>3}: max={vals_m[order_m[0]]:.4f}  "
              f"at ({lons_m[order_m[0]]:+.3f}, {lats_m[order_m[0]]:.3f})  → {top_muni}")

print()
print(f"Arrow target → best pixel: {best_muni} ({best_lon:.3f}, {best_lat:.3f})"
      f"  index={best_val:.4f}")
print("=" * 60)
print()


# ---------------------------------------------------------------------------
# FIGURE 1: Annual mean composite index (single panel)
# ---------------------------------------------------------------------------

print()
print("Generating annual composite map...")

vmin_ann, vmax_ann = get_vlims(composite_annual)
print(f"  Color range: [{vmin_ann:.4f}, {vmax_ann:.4f}]")

fig_ann = plt.figure(figsize=(12, 5))
ax_ann = fig_ann.add_axes(
    [0.05, 0.08, 0.80, 0.82],   # [left, bottom, width, height] — leaves room for colorbar
    projection=ccrs.PlateCarree(),
)

# Plot field
lons = composite_annual["longitude"].values
lats = composite_annual["latitude"].values
data = composite_annual.values

pcm = ax_ann.pcolormesh(
    lons, lats, data,
    cmap=CMAP, vmin=vmin_ann, vmax=vmax_ann,
    transform=ccrs.PlateCarree(), shading="auto",
)

# Ocean mask
mask_ocean(ax_ann, muni_land_union)

# Coastline
plot_base_map(ax_ann, coast_union, muni_clip)

# Station overlay
add_station_overlay(ax_ann, stations)

# North arrow
add_north_arrow(ax_ann)

# Axes styling
style_axes_single(ax_ann, MAP_XLIM, MAP_YLIM)

# Colorbar — manual axes, fully outside map
cbar_ax = fig_ann.add_axes([0.87, 0.12, 0.018, 0.74])  # [left, bottom, width, height]
import matplotlib.colors as mcolors_ann
sm_ann = plt.cm.ScalarMappable(
    cmap=CMAP, norm=mcolors.Normalize(vmin=vmin_ann, vmax=vmax_ann)
)
sm_ann.set_array([])
cbar = fig_ann.colorbar(sm_ann, cax=cbar_ax)
cbar.set_label(
    "Site selection index\n[0=least favorable, 1=most favorable]",
    fontsize=8.5,
)

# Title
ax_ann.set_title(
    "Annual mean site selection index\n"
    "ERA5-Land 2004–2023  |  Variables: RH, wind, precip, PWV  |  Equal weights",
    fontsize=10, pad=8,
)

# Annotation: SW corridor — arrow tip at actual best pixel (computed from data)
ax_ann.annotate(
    f"SW corridor\n(best region)\n{best_muni}",
    xy=(best_lon, best_lat),           # tip: actual best pixel
    xytext=(best_lon - 0.65, best_lat - 0.18),  # text: offset SW
    fontsize=7.5,
    color="darkgreen",
    fontweight="bold",
    arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1.0),
    transform=ccrs.PlateCarree(),
)

out_annual_map = MAP_DIR / "phase3_composite_annual.png"
fig_ann.savefig(out_annual_map, dpi=200, bbox_inches="tight")
plt.close(fig_ann)
print(f"  Saved: {out_annual_map}")


# ---------------------------------------------------------------------------
# FIGURE 2: Monthly composite index (12-panel grid, same layout as Phase 1)
# ---------------------------------------------------------------------------

print("Generating monthly composite map (12 panels)...")

# Shared color scale across all 12 months
vmin_all, vmax_all = get_vlims(composite_monthly)
print(f"  Color range (all months): [{vmin_all:.4f}, {vmax_all:.4f}]")

fig_mon, axes = plt.subplots(
    3, 4, figsize=(18, 10),
    subplot_kw={"projection": ccrs.PlateCarree()},
)

for i, ax in enumerate(axes.flat):
    m = i + 1
    data_m = composite_monthly.sel(month=m).values

    pcm_m = ax.pcolormesh(
        lons, lats, data_m,
        cmap=CMAP, vmin=vmin_all, vmax=vmax_all,
        transform=ccrs.PlateCarree(), shading="auto",
    )

    mask_ocean(ax, muni_land_union)
    plot_base_map(ax, coast_union, muni_clip)

    style_axes_grid(ax, MAP_XLIM, MAP_YLIM, 3, 4)
    ax.set_title(MONTHS[i], fontsize=9, fontweight="bold")

# Shared colorbar
cbar_ax = fig_mon.add_axes([0.92, 0.12, 0.015, 0.76])
sm = plt.cm.ScalarMappable(
    cmap=CMAP, norm=mcolors.Normalize(vmin=vmin_all, vmax=vmax_all)
)
sm.set_array([])
cb = fig_mon.colorbar(sm, cax=cbar_ax)
cb.set_label("Site selection index [0=least favorable, 1=most favorable]", fontsize=9)

fig_mon.suptitle(
    "Monthly site selection index — ERA5-Land 2004–2023\n"
    "Variables: RH > 50%, wind > 9 m/s, precip > 1 mm/hr, PWV > 26 mm  |  Equal weights",
    fontsize=11, y=1.01,
)

plt.tight_layout(rect=[0, 0, 0.91, 1.0])

out_monthly_map = MAP_DIR / "phase3_composite_monthly.png"
fig_mon.savefig(out_monthly_map, dpi=200, bbox_inches="tight")
plt.close(fig_mon)
print(f"  Saved: {out_monthly_map}")


# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

print()
print("Phase 3 maps: DONE")
print(f"Outputs in: {MAP_DIR}")
print("Files:")
print(f"  {out_annual_map.name}   ← poster figure")
print(f"  {out_monthly_map.name}  ← supplementary / poster")
