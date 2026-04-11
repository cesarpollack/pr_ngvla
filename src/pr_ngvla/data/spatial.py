"""
src/pr_ngvla/data/spatial.py
=============================
Spatial data loaders: shapefiles and raster DEM.

Coastline strategy
------------------
We use the GSHHS "h" (high-resolution) Level-1 file, exactly as the
project prototype (make_temp_map.py).  The prototype crops the global
file with a WIDER bounding box than the map extent to ensure Mona,
Vieques, and Culebra are included, then dissolves to one polygon.

Two distinct uses for geometry:
  coast_union     — GSHHS polygon  → drawn as the outer coastline line
                    (high resolution, matches prototype appearance)
  muni_land_union — dissolved municipality polygons → used as the ocean
                    mask boundary in visualization.maps.mask_ocean
                    (no interior rings for bays/lagoons, so no white
                    patches appear inside the island)
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
from shapely.ops import unary_union
from shapely.geometry import box as shapely_box

from pr_ngvla.config import WGS84, METRIC_CRS


# Wider bbox for coastline extraction — same as prototype make_temp_map.py
# Extends beyond the map display extent to ensure all islands are captured
_COAST_BBOX = shapely_box(-68.8, 17.0, -64.5, 19.2)


def load_vector_data(
    coast_shp: Path | str,
    muni_shp:  Path | str,
) -> tuple:
    """
    Load and align coastline and municipality shapefiles.

    Algorithm (mirrors prototype make_temp_map.py exactly):
    1. Read full GSHHS coastline file, clip to wide PR bbox.
    2. Filter to Polygon/MultiPolygon, dissolve → coast_union_proj (metric).
    3. Convert back to WGS84 → coast_union (used for drawing only).
    4. Load TIGER/Line municipalities, filter STATEFP==72.
    5. Clip municipalities to coast_union_proj → muni_clip.
    6. Dissolve muni_clip → muni_land_union (used for ocean masking only,
       because TIGER polygons have no interior water-body rings).

    Parameters
    ----------
    coast_shp : path to GSHHS h L1 shapefile  (GSHHS_h_L1.shp)
    muni_shp  : path to TIGER/Line county shapefile (tl_2024_us_county.shp)

    Returns
    -------
    muni_clip      : GeoDataFrame (WGS84) — 78 clipped municipality polygons
    coast_union    : shapely geometry (WGS84) — GSHHS outer boundary (drawing)
    muni_land_union: shapely geometry (WGS84) — dissolved municipalities (masking)
    """
    # --- 1. Coastline: read, crop, dissolve ---
    coast_all  = gpd.read_file(coast_shp).to_crs(WGS84)
    pr_bbox_gdf = gpd.GeoDataFrame(geometry=[_COAST_BBOX], crs=WGS84)

    # gpd.overlay intersection — same method as prototype
    coast_crop  = gpd.overlay(coast_all, pr_bbox_gdf, how="intersection")
    coast_proj  = coast_crop.to_crs(METRIC_CRS)

    # Keep only polygon geometries (discard any linestring artifacts)
    coast_polys = coast_proj[
        coast_proj.geometry.type.isin(["Polygon", "MultiPolygon"])
    ]
    # buffer(0) repairs self-intersections in GSHHS geometries (known issue)
    coast_union_proj = unary_union(coast_polys.geometry.buffer(0))

    coast_union = (
        gpd.GeoSeries([coast_union_proj], crs=METRIC_CRS)
        .to_crs(WGS84)
        .iloc[0]
    )

    # --- 2. Municipalities: load, filter PR, clip to coastline ---
    muni_all = gpd.read_file(muni_shp)
    muni_pr  = muni_all[muni_all["STATEFP"] == "72"].copy()

    muni_clip = (
        gpd.clip(muni_pr.to_crs(METRIC_CRS), coast_union_proj)
        .to_crs(WGS84)
    )

    # --- 3. Municipality land union: for ocean masking ---
    # Municipality polygons have no interior rings for bays/lagoons.
    # Using this for ocean masking prevents white patches inside the island
    # (which occur when using GSHHS coast_union, which has interior rings
    # for features like Laguna de Guánica and the SW coastal lagoons).
    muni_land_union = unary_union(muni_clip.geometry)

    return muni_clip, coast_union, muni_land_union


def load_dem(dem_path: Path | str) -> tuple:
    """
    Load a DEM GeoTIFF and return the elevation array and its extent.

    Pixels at or below sea level and nodata pixels are set to NaN.

    Returns
    -------
    elev   : 2D float32 ndarray — elevation [m], NaN over ocean
    extent : [lon_min, lon_max, lat_min, lat_max]
    """
    with rasterio.open(dem_path) as src:
        elev = src.read(1).astype("float32")
        if src.nodata is not None:
            elev[elev == src.nodata] = np.nan
        elev[elev <= 0] = np.nan
        bounds = src.bounds
        crs    = src.crs

    if crs is None or str(crs).upper() != "EPSG:4326":
        import warnings
        warnings.warn(f"DEM CRS is {crs}, expected EPSG:4326.", stacklevel=2)

    return elev, [bounds.left, bounds.right, bounds.bottom, bounds.top]
