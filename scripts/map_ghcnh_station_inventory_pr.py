#!/usr/bin/env python3
"""
scripts/map_ghcnh_station_inventory_pr.py
=========================================

Generate two Puerto Rico GHCNh station maps:

1. strict territory filter
2. validation-ready master (2004-2023)

These are analogous to the NOAA maps already built for GHCND/ISD.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import pr_ngvla.config as cfg
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.visualization.maps import (
    add_north_arrow,
    finalize_station_inventory_figure,
    mask_ocean,
    plot_base_map,
    style_station_inventory_axes,
)


def _cfg_path(name: str, fallback: str) -> Path:
    return Path(getattr(cfg, name, fallback))


def _plot_station_map(
    df: pd.DataFrame,
    *,
    title: str,
    png_path: Path,
    coast_union,
    muni_clip,
    muni_land_union,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 4.5), dpi=150)

    mask_ocean(ax, muni_land_union)
    plot_base_map(ax, coast_union=coast_union, muni_clip=muni_clip)

    ax.scatter(
        df["lon"],
        df["lat"],
        s=22,
        marker="o",
        color="#1f77b4",
        edgecolors="white",
        linewidths=0.4,
        zorder=10,
        label="ghcnh",
    )

    ax.legend(title="source", loc="lower left", frameon=True)
    style_station_inventory_axes(ax, title=title)
    add_north_arrow(ax)

    finalize_station_inventory_figure(fig, png_path)
    plt.close(fig)


def main() -> None:
    data_interim = _cfg_path("DATA_INTERIM", "data_interim")
    out_maps = _cfg_path("OUT_MAPS", "outputs/maps")
    coast_shp = _cfg_path("COAST_SHP", "data_raw/shapefiles/GSHHS_h_L1.shp")
    muni_shp = _cfg_path("MUNI_SHP", "data_raw/shapefiles/tl_2024_us_county/tl_2024_us_county.shp")

    inv_dir = data_interim / "noaa" / "ghcnh_station_inventory"
    out_dir = out_maps / "station_inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    pr_territory_path = inv_dir / "pr_ghcnh_station_inventory_pr_territory.parquet"
    master_path = inv_dir / "pr_ghcnh_station_inventory_master.parquet"

    if not pr_territory_path.exists():
        raise FileNotFoundError(f"Missing file: {pr_territory_path}")
    if not master_path.exists():
        raise FileNotFoundError(f"Missing file: {master_path}")

    pr_territory = pd.read_parquet(pr_territory_path)
    master = pd.read_parquet(master_path)

    muni_clip, coast_union, muni_land_union = load_vector_data(coast_shp, muni_shp)

    _plot_station_map(
        pr_territory,
        title="Puerto Rico GHCNh station inventory — strict territory filter",
        png_path=out_dir / "pr_ghcnh_station_inventory_pr_territory.png",
        coast_union=coast_union,
        muni_clip=muni_clip,
        muni_land_union=muni_land_union,
    )

    _plot_station_map(
        master,
        title="Puerto Rico GHCNh station inventory — validation-ready (2004–2023)",
        png_path=out_dir / "pr_ghcnh_station_inventory_master.png",
        coast_union=coast_union,
        muni_clip=muni_clip,
        muni_land_union=muni_land_union,
    )

    print("Done.")
    print(out_dir / "pr_ghcnh_station_inventory_pr_territory.png")
    print(out_dir / "pr_ghcnh_station_inventory_master.png")


if __name__ == "__main__":
    main()
