"""
src/pr_ngvla/visualization/maps.py
====================================
Matplotlib/GeoPandas rendering functions for all Phase 1 (and later) maps.

Responsibilities
----------------
- Convert shapely geometries to matplotlib clip paths (make_clip_patch).
- Draw coastline + municipality boundaries on an axes (plot_base_map).
- Style subplot grid axes consistently (style_axes_grid).
- Style a single full-panel axes consistently (style_axes_single).
- Add a shared colorbar to a figure (add_colorbar).
- Overlay NOAA ISD station points (add_station_overlay).
- Add a north arrow (add_north_arrow).
- Plot the DEM as a shaded background (plot_dem).

Design rules
------------
- No I/O.  Every function receives data that has already been loaded.
- No physics.  Conversions happen in data.temporal or physics.thermodynamics.
- Every function is stateless: given the same inputs, same output.
"""

from __future__ import annotations

import calendar

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.ticker import FuncFormatter, MultipleLocator

from pr_ngvla.config import WGS84, MAP_XLIM, MAP_YLIM

MONTH_NAMES = [calendar.month_abbr[m] for m in range(1, 13)]


# ---------------------------------------------------------------------------
# Ocean mask
# ---------------------------------------------------------------------------

def mask_ocean(ax, land_union, x_lim: tuple = MAP_XLIM, y_lim: tuple = MAP_YLIM) -> None:
    """
    Paint the ocean white after a pcolormesh call.

    Approach: draw a white polygon = bounding_box MINUS land_polygon.

    Why land_union must be muni_land_union, NOT coast_union
    -------------------------------------------------------
    The GSHHS coastline polygon (coast_union) contains interior rings
    representing coastal lagoons and bays (e.g. Laguna de Guánica,
    Phosphorescent Bay in SW Puerto Rico).  Using coast_union here causes
    those interior water features to be painted white — visible as white
    patches inside the island interior.

    The dissolved municipality polygon (muni_land_union) has NO interior
    rings: TIGER/Line municipalities are purely land-administrative
    boundaries with no water-body cutouts.  Using it as the land mask
    produces a clean solid-fill with no white patches.

    zorder stack
    ------------
    1  pcolormesh (ERA5 data, full bbox)
    3  white ocean mask  ← this function
    4  municipality boundary lines
    5  coastline outline (GSHHS, high-res)

    Parameters
    ----------
    ax         : matplotlib Axes
    land_union : shapely geometry — dissolved municipality polygons (WGS84)
    x_lim, y_lim : display limits defining the ocean bounding box
    """
    from shapely.geometry import box as shapely_box
    bbox  = shapely_box(x_lim[0], y_lim[0], x_lim[1], y_lim[1])
    ocean = bbox.difference(land_union)
    gpd.GeoSeries([ocean], crs=WGS84).plot(
        ax=ax, facecolor="white", edgecolor="none", zorder=3,
    )


# ---------------------------------------------------------------------------
# Base map
# ---------------------------------------------------------------------------

def plot_base_map(ax, coast_union, muni_clip: gpd.GeoDataFrame) -> None:
    """
    Draw the outer coastline and internal municipality boundaries.

    zorder stack (from bottom):
        1  pcolormesh / imshow   (set in calling script)
        4  municipality lines    (light grey, thin)
        5  coastline outline     (dark grey, slightly thicker)

    Parameters
    ----------
    ax          : matplotlib Axes
    coast_union : shapely geometry — dissolved outer boundary
    muni_clip   : GeoDataFrame    — 78 clipped municipality polygons
    """
    gpd.GeoSeries(coast_union, crs=WGS84).plot(
        ax=ax, facecolor="none", edgecolor="0.25",
        linewidth=1.0, zorder=5,
    )
    muni_clip.boundary.plot(
        ax=ax, color="0.6", linewidth=0.3, zorder=4,
    )


# ---------------------------------------------------------------------------
# Axis styling
# ---------------------------------------------------------------------------

def style_axes_grid(
    ax,
    row:   int,
    col:   int,
    nrows: int,
    ncols: int,
    x_lim: tuple = MAP_XLIM,
    y_lim: tuple = MAP_YLIM,
) -> None:
    """
    Style one panel of a sharex/sharey subplot grid.

    Tick labels appear only on the bottom row (x) and left column (y)
    to avoid clutter in a multi-panel figure.

    Parameters
    ----------
    ax, row, col, nrows, ncols : self-explanatory
    x_lim, y_lim : (min, max) tuples — default to project-wide map extent
    """
    ax.set_xlim(*x_lim)
    ax.set_ylim(*y_lim)
    ax.set_aspect("equal", adjustable="box")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5))
    ax.tick_params(
        axis="x", labelbottom=(row == nrows - 1),
        labelsize=6, rotation=30,
    )
    ax.tick_params(
        axis="y", labelleft=(col == 0), labelsize=6,
    )


def style_axes_single(
    ax,
    x_lim: tuple = MAP_XLIM,
    y_lim: tuple = MAP_YLIM,
) -> None:
    """
    Style a standalone full-panel map axes (DEM map, suitability map, etc.)

    Includes degree–minute tick labels (e.g. 67°00'W) and axis labels,
    matching the poster style from the project prototype.

    Parameters
    ----------
    ax    : matplotlib Axes
    x_lim, y_lim : (min, max) display limits
    """
    def _degmin(value, hemi_pos, hemi_neg):
        hemi = hemi_pos if value >= 0 else hemi_neg
        v    = abs(value)
        deg  = int(v)
        mins = int(round((v - deg) * 60))
        if mins == 60:
            deg += 1; mins = 0
        return f"{deg}°{mins:02d}'{hemi}"

    ax.set_xlim(*x_lim)
    ax.set_ylim(*y_lim)
    ax.set_aspect("equal", adjustable="box")
    ax.xaxis.set_major_locator(MultipleLocator(1.0))
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda x, _: _degmin(x, "E", "W"))
    )
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda y, _: _degmin(y, "N", "S"))
    )
    ax.tick_params(axis="x", bottom=True, labelbottom=True, labelsize=9)
    ax.tick_params(axis="y", left=True,   labelleft=True,  labelsize=9)
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude",  fontsize=11)


# ---------------------------------------------------------------------------
# Colorbar
# ---------------------------------------------------------------------------

def add_colorbar(
    fig,
    mesh,
    label:    str,
    position: list = None,
) -> plt.colorbar:
    """
    Add a vertical colorbar to the right of the main axes area.

    Parameters
    ----------
    fig      : matplotlib Figure
    mesh     : the mappable returned by pcolormesh / imshow
    label    : colorbar axis label
    position : [left, bottom, width, height] in figure coordinates.
               Defaults to a standard right-side position for the 3×4 grid.

    Returns
    -------
    cbar : matplotlib Colorbar
    """
    if position is None:
        position = [0.93, 0.15, 0.015, 0.65]

    cbar_ax = fig.add_axes(position)
    cbar    = fig.colorbar(mesh, cax=cbar_ax)
    cbar.set_label(label, fontsize=11)
    cbar.ax.tick_params(labelsize=9)
    return cbar


# ---------------------------------------------------------------------------
# Station overlay
# ---------------------------------------------------------------------------

def add_station_overlay(
    ax,
    stations: gpd.GeoDataFrame,
    color:    str   = "crimson",
    marker:   str   = "o",
    size:     float = 20,
    label:    bool  = True,
    fontsize: int   = 5,
) -> None:
    """
    Overlay NOAA ISD station points on an axes.

    Parameters
    ----------
    ax       : matplotlib Axes
    stations : GeoDataFrame with LAT, LON, STATION_NAME columns
    color    : marker face colour
    marker   : matplotlib marker symbol
    size     : marker size (points²)
    label    : if True, annotate each station with its name
    fontsize : font size for station name labels
    """
    ax.scatter(
        stations["LON"], stations["LAT"],
        s=size, marker=marker, color=color,
        edgecolors="white", linewidths=0.5,
        zorder=10, label="NOAA ISD station",
    )

    if label:
        # Per-station offsets to avoid overlap
        offsets = {
            "RAFAEL":   (-20,  2),
            "EUGENIO":  (-22,  2),
            "FERNANDO": (-15,  3),
            "LUIS":     (  3,  -4),
            "NAVAL":    (  4,  0),
        }
        for _, row in stations.iterrows():
            short = row["STATION_NAME"].split()[0]
            dx, dy = offsets.get(short, (4, 4))
            ax.annotate(
                short,
                xy=(row["LON"], row["LAT"]),
                xytext=(dx, dy), textcoords="offset points",
                fontsize=fontsize, color="0.15",
                zorder=11,
            )

# ---------------------------------------------------------------------------
# North arrow
# ---------------------------------------------------------------------------

def add_north_arrow(
    ax,
    x:      float = 0.92,
    y:      float = 0.10,
    length: float = 0.08,
) -> None:
    """
    Draw a simple north arrow in axes-fraction coordinates.

    Parameters
    ----------
    ax     : matplotlib Axes
    x, y   : base position (axes fraction 0–1)
    length : arrow length (axes fraction)
    """
    ax.annotate(
        "",
        xy=(x, y + length), xytext=(x, y),
        xycoords="axes fraction",
        arrowprops=dict(
            arrowstyle="wedge,tail_width=0.6",
            facecolor="k", edgecolor="k",
        ),
        zorder=8,
    )
    ax.text(
        x, y + length + 0.005, "N",
        transform=ax.transAxes,
        ha="center", va="bottom", fontsize=11, zorder=8,
    )


# ---------------------------------------------------------------------------
# DEM background
# ---------------------------------------------------------------------------

def plot_dem(ax, elev: np.ndarray, extent: list):
    """
    Plot a DEM elevation array as a shaded background using imshow.

    Parameters
    ----------
    ax     : matplotlib Axes
    elev   : 2D float32 array — elevation [m], NaN for ocean
    extent : [lon_min, lon_max, lat_min, lat_max]

    Returns
    -------
    im : mappable — pass to add_colorbar()
    """
    return ax.imshow(
        elev, extent=extent, origin="upper",
        cmap="terrain", vmin=0,
        zorder=1,
    )

def plot_station_inventory_map(
    ax,
    stations: gpd.GeoDataFrame,
    color_by: str = "source",
    size: float = 20.0,
    alpha: float = 0.9,
    show_legend: bool = True,
) -> None:
    """
    Plot station points from a GeoDataFrame on a pre-existing axes.

    Parameters
    ----------
    ax : matplotlib Axes
        Axes on which to draw the station points.
    stations : GeoDataFrame
        GeoDataFrame in WGS84 containing point geometries.
    color_by : str, default="source"
        Column used to separate the points into categories for plotting.
    size : float, default=20.0
        Marker size in points^2.
    alpha : float, default=0.9
        Marker transparency.
    show_legend : bool, default=True
        Whether to draw a legend keyed by `color_by`.

    Notes
    -----
    This function assumes the caller already drew the basemap and already
    styled the axes. It only adds the station points.
    """
    if stations.empty:
        return

    if color_by not in stations.columns:
        ax.scatter(
            stations.geometry.x,
            stations.geometry.y,
            s=size,
            color="crimson",
            edgecolors="white",
            linewidths=0.4,
            alpha=alpha,
            zorder=10,
            label="Stations",
        )
        if show_legend:
            ax.legend(loc="lower left", fontsize=8, frameon=True)
        return

    categories = list(stations[color_by].dropna().unique())

    # Minimal fixed palette for the current two-source station inventory.
    palette = {
        "ghcnd": "tab:blue",
        "isd": "tab:red",
    }

    for category in categories:
        subset = stations[stations[color_by] == category]

        ax.scatter(
            subset.geometry.x,
            subset.geometry.y,
            s=size,
            color=palette.get(category, "black"),
            edgecolors="white",
            linewidths=0.4,
            alpha=alpha,
            zorder=10,
            label=str(category),
        )

    if show_legend:
        ax.legend(loc="lower left", fontsize=8, frameon=True, title=color_by)
