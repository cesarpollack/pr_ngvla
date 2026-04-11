"""
src/pr_ngvla/map_utils.py

Shared cartographic utilities for all Phase 1 (and later) map scripts.

By centralising these functions here, every map script stays thin and
readable.  A bug fix or style change made here automatically propagates
to all six scripts — no need to edit each file individually.

Functions
---------
load_vector_data(coast_shp, muni_shp)
    Load coastline + municipality shapefiles, clip municipalities to the
    coastline polygon so both share *exactly* the same outer boundary.
    Returns the clipped GeoDataFrame and the dissolved outer boundary.

make_clip_patch(geom, ax)
    Convert a shapely Polygon / MultiPolygon to a matplotlib PathPatch
    suitable for clipping a pcolormesh to land area only.

plot_base_map(ax, coast_union, muni_clip)
    Draw the outer coastline and internal municipality boundaries on ax.

style_axes(ax, row, col, nrows, ncols, x_lim, y_lim)
    Set axis limits, tick spacing, and tick label visibility so that
    shared-axis subplots only show labels on the bottom / left edges.
"""

from __future__ import annotations

import numpy as np
import geopandas as gpd
import matplotlib.ticker as mticker
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Constants used by all map scripts
# ---------------------------------------------------------------------------

WGS84      = "EPSG:4326"    # geographic CRS — used for plotting
METRIC_CRS = "EPSG:32620"   # UTM zone 20N — used for geometric operations


# ---------------------------------------------------------------------------
# Vector data loader
# ---------------------------------------------------------------------------

def load_vector_data(
    coast_shp: str | object,
    muni_shp:  str | object,
) -> tuple:
    """
    Load and align the coastline and municipality shapefiles.

    The core problem this function solves
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    The NOAA coastline shapefile and the TIGER/Line municipality shapefile
    were created independently and their outer boundaries do NOT match
    perfectly.  If we use them as-is, pcolormesh cells near the coast
    bleed into the gap between the two boundaries.

    Solution (same approach as the project prototype)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    1. Load and dissolve the coastline into a single polygon in the metric
       CRS (UTM 20N) — this is the authoritative outer boundary.
    2. Use ``gpd.clip`` to trim the municipality polygons to that coastline
       polygon.  After clipping, every municipality edge that touches the
       coast is now *identical* to the coastline polygon edge.
    3. Dissolve the clipped municipalities back into a single outer polygon.
       This polygon is then used both as the pcolormesh clip mask AND as
       the drawn coastline line — one geometry, zero misalignment.

    Parameters
    ----------
    coast_shp : path-like
        Path to the NOAA GSHHS coastline shapefile (pr_coastline.shp).
    muni_shp : path-like
        Path to the TIGER/Line county shapefile (tl_2024_us_county.shp).

    Returns
    -------
    muni_clip : GeoDataFrame  (EPSG:4326)
        78 PR municipality polygons clipped to the coastline boundary.
    coast_union : shapely geometry  (EPSG:4326)
        Single dissolved polygon of all land area.  Use this as the
        pcolormesh clip path and as the outer boundary line.
    """

    # --- 1. Coastline ---
    # Read the shapefile and reproject to WGS84 for consistency.
    coast_gdf = gpd.read_file(coast_shp).to_crs(WGS84)

    # Reproject to metric CRS so that unary_union works in metres (more
    # numerically stable for polygon operations than degrees).
    coast_proj = coast_gdf.to_crs(METRIC_CRS)

    # Dissolve all coastline polygons into one single geometry.
    # This handles cases where the shapefile has separate polygons for
    # Puerto Rico main island, Vieques, Culebra, Mona, etc.
    coast_union_proj = unary_union(coast_proj.geometry)

    # Convert back to WGS84 for plotting.
    coast_union_wgs = (
        gpd.GeoSeries([coast_union_proj], crs=METRIC_CRS)
        .to_crs(WGS84)
        .iloc[0]
    )

    # --- 2. Municipalities ---
    # Read all US counties and keep only Puerto Rico (STATEFP == "72").
    muni_all = gpd.read_file(muni_shp)
    muni_pr  = muni_all[muni_all["STATEFP"] == "72"].copy()

    # Clip municipalities to the coastline polygon in metric CRS.
    # After this step the outer edge of every coastal municipality
    # coincides exactly with coast_union_proj — no gap, no overlap.
    muni_clip_proj = gpd.clip(muni_pr.to_crs(METRIC_CRS), coast_union_proj)

    # Reproject back to WGS84 for plotting.
    muni_clip = muni_clip_proj.to_crs(WGS84)

    # --- 3. Dissolved outer boundary ---
    # Dissolve the *clipped* municipalities into one polygon.
    # Because the municipalities were clipped to the coastline, this
    # dissolved polygon is guaranteed to match the drawn municipality
    # boundaries at the coast.  We use it as the pcolormesh clip mask.
    coast_union = unary_union(muni_clip.geometry)

    return muni_clip, coast_union


# ---------------------------------------------------------------------------
# Clip-path factory
# ---------------------------------------------------------------------------

def make_clip_patch(geom, ax) -> PathPatch:
    """
    Convert a shapely Polygon or MultiPolygon to a matplotlib PathPatch.

    How pcolormesh clipping works
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    matplotlib's ``pcolormesh`` draws one filled rectangle per grid cell.
    Cells that straddle the coastline are drawn as full rectangles, so
    colour bleeds over the ocean.

    By calling ``mesh.set_clip_path(make_clip_patch(coast_union, ax))``
    we tell matplotlib to only render the fill *inside* the given polygon.
    Any part of a grid cell that falls outside (over ocean) is masked.

    Parameters
    ----------
    geom : shapely Polygon or MultiPolygon
        The land-area polygon to use as the clip boundary.
    ax : matplotlib Axes
        The axes on which the patch will be applied.  The patch is added
        to the axes so its coordinate transform is correct.

    Returns
    -------
    patch : PathPatch
        The clip patch.  Pass this to ``mesh.set_clip_path(patch)``.
    """

    # Handle both single Polygon and MultiPolygon (e.g., PR + offshore islands).
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]

    verts, codes = [], []

    for poly in polys:
        # Exterior ring — the outer boundary of this polygon.
        ext = np.array(poly.exterior.coords)
        verts.append(ext)
        codes += (
            [MplPath.MOVETO]                      # first point: move to start
            + [MplPath.LINETO] * (len(ext) - 2)  # intermediate points: draw lines
            + [MplPath.CLOSEPOLY]                 # last point: close the ring
        )

        # Interior rings (holes) — e.g., a lagoon inside the land polygon.
        for interior in poly.interiors:
            inn = np.array(interior.coords)
            verts.append(inn)
            codes += (
                [MplPath.MOVETO]
                + [MplPath.LINETO] * (len(inn) - 2)
                + [MplPath.CLOSEPOLY]
            )

    # Build the matplotlib Path and wrap it in a PathPatch.
    path  = MplPath(np.concatenate(verts), codes)
    patch = PathPatch(path, transform=ax.transData)

    # Add the patch to the axes so matplotlib knows its coordinate system.
    ax.add_patch(patch)

    return patch


# ---------------------------------------------------------------------------
# Base-map drawing
# ---------------------------------------------------------------------------

def plot_base_map(ax, coast_union, muni_clip: gpd.GeoDataFrame) -> None:
    """
    Draw the outer coastline and internal municipality boundaries.

    Drawing order (zorder)
    ~~~~~~~~~~~~~~~~~~~~~~
    zorder=1  pcolormesh (set in the calling script)
    zorder=4  municipality internal boundaries  — thin, light grey lines
    zorder=5  outer coastline                   — slightly thicker, darker

    This ensures boundaries are always visible on top of the colour fill.

    Parameters
    ----------
    ax : matplotlib Axes
    coast_union : shapely geometry
        The dissolved outer boundary (from load_vector_data).
    muni_clip : GeoDataFrame
        The 78 clipped municipality polygons (from load_vector_data).
    """

    # Outer coastline — drawn as a single polygon outline.
    gpd.GeoSeries(coast_union, crs=WGS84).plot(
        ax=ax,
        facecolor="none",       # transparent fill — we only want the border
        edgecolor="0.25",       # dark grey
        linewidth=1.0,
        zorder=5,
    )

    # Internal municipality boundaries — only the edges, no fill.
    muni_clip.boundary.plot(
        ax=ax,
        color="0.6",            # light grey — subtle, not distracting
        linewidth=0.3,
        zorder=4,
    )


# ---------------------------------------------------------------------------
# Axes styling
# ---------------------------------------------------------------------------

def style_axes(ax, row: int, col: int, nrows: int, ncols: int,
               x_lim: tuple, y_lim: tuple) -> None:
    """
    Apply consistent axis styling to one subplot panel.

    In a shared-axis grid (sharex=True, sharey=True) we still want
    tick *labels* only on the bottom row and left column to avoid
    clutter.  This function handles that logic.

    Parameters
    ----------
    ax : matplotlib Axes
    row, col : int
        0-based row and column index of this panel in the grid.
    nrows, ncols : int
        Total rows and columns in the grid.
    x_lim, y_lim : tuple
        (min, max) longitude and latitude limits.
    """

    ax.set_xlim(*x_lim)
    ax.set_ylim(*y_lim)
    ax.set_aspect("equal", adjustable="box")

    # Tick marks every 1° longitude, every 0.5° latitude.
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5))

    # Only show tick labels on the edges to avoid clutter.
    ax.tick_params(
        axis="x",
        labelbottom=(row == nrows - 1),  # label only on bottom row
        labelsize=6,
        rotation=30,
    )
    ax.tick_params(
        axis="y",
        labelleft=(col == 0),            # label only on left column
        labelsize=6,
    )
