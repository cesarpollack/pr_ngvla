#!/usr/bin/env python3
"""
scripts/make_muni_reference_map.py

Municipality reference map for the poster (Fig. 2).
Follows project architecture — uses pr_ngvla library for all rendering.

Output: outputs/maps/muni_reference_map_pr.png
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

from pr_ngvla.config import (
    COAST_SHP, MUNI_SHP, NOAA_ISD_DIR,
    OUT_MAPS,
)
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.data.loaders import load_noaa_isd_stations
from pr_ngvla.visualization.maps import (
    mask_ocean,
    plot_base_map,
    style_axes_single,
    add_station_overlay,
    add_north_arrow,
)

OUT_PNG = OUT_MAPS / "muni_reference_map_pr.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def add_municipality_labels(ax, muni_clip) -> None:
    """Label each municipality at its representative point."""
    for _, row in muni_clip.iterrows():
        geom = row.geometry
        if geom.is_empty:
            continue
        rep  = geom.representative_point()
        name = row.get("NAME", "")
        text = ax.text(
            rep.x, rep.y, name,
            ha="center", va="center",
            fontsize=2.5, color="0.3",
            fontweight="normal", zorder=3,
        )
        text.set_path_effects([
            pe.Stroke(linewidth=1.0, foreground="white"),
            pe.Normal(),
        ])


def main() -> None:
    # Load vector data
    muni_clip, coast_union, muni_land_union = load_vector_data(
        COAST_SHP, MUNI_SHP
    )

    # Load stations — same GeoDataFrame used by all other map scripts
    stations = load_noaa_isd_stations(NOAA_ISD_DIR)

    # Figure
    fig, ax = plt.subplots(figsize=(8, 6))

    # Base map
    plot_base_map(ax, coast_union, muni_clip)

    # Municipality labels
    add_municipality_labels(ax, muni_clip)

    # Ocean mask
    mask_ocean(ax, muni_land_union)

    # Station overlay — identical style to all Phase 1/2/3 maps
    add_station_overlay(ax, stations, fontsize=5)

    # Axes + north arrow
    style_axes_single(ax)
    add_north_arrow(ax)

    ax.set_title(
        "Puerto Rico — Municipality Reference Map for Site Identification",
        fontsize=12,
    )

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"[OK] Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
