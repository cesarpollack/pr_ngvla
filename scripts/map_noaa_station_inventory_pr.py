#!/usr/bin/env python3
"""
scripts/map_noaa_station_inventory_pr.py
========================================

Create two Puerto Rico station inventory maps using the same spatial
preprocessing pipeline already used by the Phase 1 climatology scripts.

Products
--------
1. Strict Puerto Rico territorial inventory map
2. Validation-ready master inventory map (2004-2023 overlap)

Design rules
------------
- Keep this script thin: orchestration only.
- Reuse load_vector_data(...) from src/pr_ngvla/data/spatial.py
  so coastline and municipality preprocessing is centralized.
- Reuse shared plotting helpers from src/pr_ngvla/visualization/maps.py
"""

from __future__ import annotations

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point

from pr_ngvla.config import (
    COAST_SHP,
    MUNI_SHP,
    OUT_STATION_INVENTORY_MAPS,
    OUT_STATION_INVENTORY_TABLES,
    WGS84,
)
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.visualization.maps import (
    mask_ocean,
    plot_base_map,
    plot_station_inventory_map,
    style_axes_single,
)


def _ensure_directory(path) -> None:
    """
    Create a directory if it does not already exist.
    """
    path.mkdir(parents=True, exist_ok=True)


def _load_station_geodataframe(csv_path) -> gpd.GeoDataFrame:
    """
    Load a station inventory CSV and convert it to a WGS84 GeoDataFrame.

    Parameters
    ----------
    csv_path : Path
        Path to a station inventory CSV containing longitude/latitude columns.

    Returns
    -------
    GeoDataFrame
        Station table with point geometry in EPSG:4326.
    """
    df = pd.read_csv(csv_path)

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=[Point(xy) for xy in zip(df["longitude"], df["latitude"])],
        crs=WGS84,
    )
    return gdf


def _make_station_map(
    stations: gpd.GeoDataFrame,
    title: str,
    output_path,
    coast_union,
    muni_clip,
    muni_land_union,
) -> None:
    """
    Render one station inventory map.

    Parameters
    ----------
    stations : GeoDataFrame
        Stations to plot.
    title : str
        Figure title.
    output_path : Path
        Output PNG path.
    coast_union : shapely geometry
        Outer coastline returned by load_vector_data(...).
    muni_clip : GeoDataFrame
        Municipality polygons clipped to Puerto Rico coastline.
    muni_land_union : shapely geometry
        Dissolved municipality land polygon used for ocean masking.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    # Paint ocean white using the project-standard municipality land mask.
    mask_ocean(ax, muni_land_union)

    # Draw coastline and municipality boundaries using the shared renderer.
    plot_base_map(ax, coast_union=coast_union, muni_clip=muni_clip)

    # Overlay stations by source.
    plot_station_inventory_map(ax, stations, color_by="source")

    # Apply standard standalone map styling.
    style_axes_single(ax)
    ax.set_title(title, fontsize=18)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """
    Build the two Puerto Rico station inventory maps.
    """
    _ensure_directory(OUT_STATION_INVENTORY_MAPS)

    # ---------------------------------------------------------------------
    # Load the already-built inventory tables
    # ---------------------------------------------------------------------
    territory_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_pr_territory.csv"
    master_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_master.csv"

    territory_gdf = _load_station_geodataframe(territory_csv)
    master_gdf = _load_station_geodataframe(master_csv)

    # ---------------------------------------------------------------------
    # Reuse the centralized spatial preprocessing pipeline
    # ---------------------------------------------------------------------
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)

    # ---------------------------------------------------------------------
    # Map 1: strict Puerto Rico territorial inventory
    # ---------------------------------------------------------------------
    out_territory = OUT_STATION_INVENTORY_MAPS / "pr_station_inventory_pr_territory.png"
    _make_station_map(
        stations=territory_gdf,
        title="Puerto Rico station inventory — strict territory filter",
        output_path=out_territory,
        coast_union=coast_union,
        muni_clip=muni_clip,
        muni_land_union=muni_land_union,
    )

    # ---------------------------------------------------------------------
    # Map 2: validation-ready inventory
    # ---------------------------------------------------------------------
    out_master = OUT_STATION_INVENTORY_MAPS / "pr_station_inventory_master.png"
    _make_station_map(
        stations=master_gdf,
        title="Puerto Rico station inventory — validation-ready (2004–2023)",
        output_path=out_master,
        coast_union=coast_union,
        muni_clip=muni_clip,
        muni_land_union=muni_land_union,
    )

    print(f"Wrote: {out_territory}")
    print(f"Wrote: {out_master}")


if __name__ == "__main__":
    main()
