"""
scripts/phase3_map_gapfill.py

PURPOSE
-------
Generate publication-quality maps of the gap-filled site selection index
for the ngVLA Puerto Rico site characterization study.

Produces two figures intended for the PRISM 2026 conference poster:
  1. Annual mean site selection index (single panel) — primary poster figure
  2. Monthly site selection index (12-panel grid) — supplementary figure

INPUTS (must exist before running)
-----------------------------------
  outputs/phase3/gapfill/composite_index_annual_gf.nc
  outputs/phase3/gapfill/composite_index_monthly_gf.nc
  data_raw/shapefiles/GSHHS_h_L1.shp
  data_raw/shapefiles/tl_2024_us_county/tl_2024_us_county.shp
  data_raw/noaa/isd/station_catalog.csv

OUTPUTS
-------
  outputs/maps/phase3/phase3_composite_annual_gf.png   <- USE FOR POSTER
  outputs/maps/phase3/phase3_composite_monthly_gf.png  <- USE FOR POSTER

DEPENDENCIES
------------
  Must run BEFORE this script:
    1. scripts/phase2_exceedance.py
    2. scripts/phase3_composite_index.py
    3. scripts/phase3_gapfill_singlelev.py  (+ land mask applied)

SCIENTIFIC CONTEXT
------------------
  Gap-fill methodology: ERA5-Land (~9 km) primary; ERA5 single-levels
  (~28 km) used for coastal NaN pixels. Bilinear interpolation to ERA5-Land
  grid. Ocean pixels removed via PR municipality shapefile mask.
  96 land pixels total (59 ERA5-Land + 37 recovered via ERA5-SL).

  Key result: SW corridor (San Germán, Yauco, Cabo Rojo) shows highest
  annual site selection index. Best window: January–March.

REFERENCES
----------
  Hersbach et al. (2020) ERA5. QJRMS 146:1999-2049. DOI:10.1002/qj.3803
  Muñoz-Sabater et al. (2021) ERA5-Land. ESSD 13:4349-4383.
  Selina et al. (2020) ngVLA System Environmental Specification. NRAO.
  Linford & Cooper (2023) ngVLA Memo 117. NRAO.

USAGE
-----
  cd /export/ngvla/cpollack/pr_ngvla
  conda activate pr_ngvla
  python scripts/phase3_map_gapfill.py

AUTHOR
------
  César Pollack, UPR Río Piedras, 2026
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
from pathlib import Path

from pr_ngvla.config import (
    OUTPUTS, COAST_SHP, MUNI_SHP, NOAA_ISD_DIR,
    MAP_XLIM, MAP_YLIM,
)
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.data.loaders import load_noaa_isd_stations
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, style_axes_single,
    add_station_overlay, add_north_arrow,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GF_DIR  = OUTPUTS / "phase3" / "gapfill"
MAP_DIR = OUTPUTS / "maps" / "phase3"
MAP_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

CMAP = plt.cm.RdYlGn  # Red=least favorable, Green=most favorable

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------

for required in [
    GF_DIR / "composite_index_annual_gf.nc",
    GF_DIR / "composite_index_monthly_gf.nc",
]:
    if not required.exists():
        raise FileNotFoundError(
            f"Required input not found: {required}\n"
            "Run phase3_gapfill_singlelev.py first."
        )

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

print("Loading gap-filled composite index...")
ds_ann = xr.open_dataset(GF_DIR / "composite_index_annual_gf.nc")
ds_mon = xr.open_dataset(GF_DIR / "composite_index_monthly_gf.nc")

var_ann = list(ds_ann.data_vars)[0]
var_mon = list(ds_mon.data_vars)[0]

da_ann = ds_ann[var_ann]
da_mon = ds_mon[var_mon]

lons = da_ann["longitude"].values
lats = da_ann["latitude"].values

n_land = int((~np.isnan(da_ann.values)).sum())
print(f"  Land pixels: {n_land}")
print(f"  Annual index range: [{float(np.nanmin(da_ann.values)):.4f}, "
      f"{float(np.nanmax(da_ann.values)):.4f}]")

print("Loading spatial data...")
muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
stations = load_noaa_isd_stations(NOAA_ISD_DIR)

# ---------------------------------------------------------------------------
# Helper: robust color limits from land pixels only
# ---------------------------------------------------------------------------

def get_vlims(da: xr.DataArray, p_low: float = 2, p_high: float = 98):
    vals = da.values[~np.isnan(da.values)]
    if vals.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(vals, p_low))
    vmax = float(np.percentile(vals, p_high))
    return vmin, max(vmax, vmin + 0.005)

# ---------------------------------------------------------------------------
# Find best pixel for annotation (computed from data)
# ---------------------------------------------------------------------------

import geopandas as gpd
from shapely.geometry import Point

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

ann_vals = da_ann.values
lon2d, lat2d = np.meshgrid(lons, lats)
land_mask = ~np.isnan(ann_vals)

flat_vals = ann_vals[land_mask]
flat_lons = lon2d[land_mask]
flat_lats = lat2d[land_mask]
order = np.argsort(flat_vals)[::-1]

best_lon  = float(flat_lons[order[0]])
best_lat  = float(flat_lats[order[0]])
best_val  = float(flat_vals[order[0]])
best_muni = pixel_to_municipality(best_lon, best_lat)

print(f"  Best pixel: {best_muni} ({best_lon:.3f}, {best_lat:.3f}) "
      f"index={best_val:.4f}")

# ---------------------------------------------------------------------------
# FIGURE 1 — Annual mean (poster figure)
# ---------------------------------------------------------------------------

print("\nGenerating annual map...")
vmin_a, vmax_a = get_vlims(da_ann)
print(f"  Color range: [{vmin_a:.4f}, {vmax_a:.4f}]")

fig_a = plt.figure(figsize=(12, 5))
ax_a  = fig_a.add_axes([0.05, 0.08, 0.80, 0.82],
                        projection=ccrs.PlateCarree())

pcm_a = ax_a.pcolormesh(
    lons, lats, da_ann.values,
    cmap=CMAP, vmin=vmin_a, vmax=vmax_a,
    transform=ccrs.PlateCarree(), shading="auto",
)
mask_ocean(ax_a, muni_land_union)
plot_base_map(ax_a, coast_union, muni_clip)
add_station_overlay(ax_a, stations)
add_north_arrow(ax_a)
style_axes_single(ax_a, MAP_XLIM, MAP_YLIM)

# Colorbar
cbar_ax_a = fig_a.add_axes([0.87, 0.12, 0.018, 0.74])
sm_a = plt.cm.ScalarMappable(
    cmap=CMAP, norm=mcolors.Normalize(vmin=vmin_a, vmax=vmax_a))
sm_a.set_array([])
cb_a = fig_a.colorbar(sm_a, cax=cbar_ax_a)
cb_a.set_label(
    "Site selection index\n[0=least favorable, 1=most favorable]",
    fontsize=8.5)

# Title
ax_a.set_title(
    "Annual mean site selection index (ERA5-Land + ERA5-SL gap-fill)\n"
    "2004–2023  |  Variables: RH, wind, precip, PWV  |  Equal weights",
    fontsize=10, pad=8,
)

# Annotation — best pixel computed from data
ax_a.annotate(
    f"SW corridor\n(best region)\n{best_muni}",
    xy=(best_lon, best_lat),
    xytext=(best_lon - 0.7, best_lat - 0.20),
    fontsize=7.5,
    color="darkgreen",
    fontweight="bold",
    arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1.0),
    transform=ccrs.PlateCarree(),
)

out_ann = MAP_DIR / "phase3_composite_annual_gf.png"
fig_a.savefig(out_ann, dpi=200, bbox_inches="tight")
plt.close(fig_a)
print(f"  Saved: {out_ann}")

# ---------------------------------------------------------------------------
# FIGURE 2 — Monthly 12-panel grid
# ---------------------------------------------------------------------------

print("Generating monthly map...")
vmin_m, vmax_m = get_vlims(da_mon)
print(f"  Color range: [{vmin_m:.4f}, {vmax_m:.4f}]")

fig_m, axes = plt.subplots(
    3, 4, figsize=(18, 10),
    subplot_kw={"projection": ccrs.PlateCarree()},
)

for i, ax in enumerate(axes.flat):
    m = i + 1
    data_m = da_mon.sel(month=m).values
    ax.pcolormesh(
        lons, lats, data_m,
        cmap=CMAP, vmin=vmin_m, vmax=vmax_m,
        transform=ccrs.PlateCarree(), shading="auto",
    )
    mask_ocean(ax, muni_land_union)
    plot_base_map(ax, coast_union, muni_clip)
    add_station_overlay(ax, stations, fontsize=5)
    style_axes_grid(ax, MAP_XLIM, MAP_YLIM, 3, 4)
    ax.set_title(MONTHS[i], fontsize=9, fontweight="bold")

cbar_ax_m = fig_m.add_axes([0.92, 0.12, 0.015, 0.76])
sm_m = plt.cm.ScalarMappable(
    cmap=CMAP, norm=mcolors.Normalize(vmin=vmin_m, vmax=vmax_m))
sm_m.set_array([])
cb_m = fig_m.colorbar(sm_m, cax=cbar_ax_m)
cb_m.set_label(
    "Site selection index [0=least favorable, 1=most favorable]",
    fontsize=9)
fig_m.suptitle(
    "Monthly site selection index (ERA5-Land + ERA5-SL gap-fill) — 2004–2023\n"
    "Variables: RH > 50%, wind > 9 m/s, precip > 1 mm/hr, PWV > 26 mm"
    "  |  Equal weights",
    fontsize=11, y=1.01,
)
plt.tight_layout(rect=[0, 0, 0.91, 1.0])

out_mon = MAP_DIR / "phase3_composite_monthly_gf.png"
fig_m.savefig(out_mon, dpi=200, bbox_inches="tight")
plt.close(fig_m)
print(f"  Saved: {out_mon}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 55)
print("Phase 3 gap-fill maps: DONE")
print(f"  {out_ann.name}  <- POSTER FIGURE")
print(f"  {out_mon.name}  <- POSTER FIGURE")
print(f"  Best region: {best_muni} (index={best_val:.4f})")
print("=" * 55)
