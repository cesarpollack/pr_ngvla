#!/usr/bin/env python3
"""
phase1_map_dem.py
=================
Phase 1 — Elevation map with NOAA ISD station overlay.

What this map shows
-------------------
- DEM topography (terrain colormap, 30m resolution)
- Municipality boundaries
- Our 5 NOAA ISD stations as labelled red triangles

Why this map matters for the presentation
------------------------------------------
The DEM is the physical explanation for every other spatial pattern
in this study.  The Cordillera Central (peaks >1000 m) running E–W
through the island centre:
  - Forces NE trade winds upward → orographic precipitation on N slopes
  - Creates a rain shadow on the S/SW coast (Lajas, Guánica, Ponce)
  - The SW rain shadow is the region of lowest RH, highest T−Td,
    lowest PWV — the best atmospheric conditions for radio astronomy

Showing the DEM first in the presentation gives the audience the
physical framework to interpret all subsequent climatology maps.

Data
----
- DEM:       data_raw/dem/pr_dem_30m.tif  (SRTM / Copernicus 30m, EPSG:4326)
- Stations:  data_raw/noaa/isd/station_catalog.csv
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pr_ngvla.config import DEM_PATH, COAST_SHP, MUNI_SHP, NOAA_ISD_DIR, OUT_MAPS
from pr_ngvla.data.loaders  import load_noaa_isd_stations
from pr_ngvla.data.spatial  import load_vector_data, load_dem
from pr_ngvla.visualization.maps import (
    plot_base_map, plot_dem, style_axes_single,
    add_colorbar, add_station_overlay, add_north_arrow,
)

OUT_PNG = OUT_MAPS / "phase1_dem_stations.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 60)
    print("Phase 1 — DEM + NOAA ISD Stations")
    print("=" * 60)

    # Load data
    elev, extent              = load_dem(DEM_PATH)
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    stations                  = load_noaa_isd_stations(NOAA_ISD_DIR)

    # Build figure
    fig, ax = plt.subplots(figsize=(12, 5))

    im = plot_dem(ax, elev, extent)
    plot_base_map(ax, coast_union, muni_clip)
    add_station_overlay(ax, stations)
    add_north_arrow(ax)
    style_axes_single(ax)

    add_colorbar(fig, im, "Elevation (m)", position=[0.92, 0.15, 0.018, 0.68])
    ax.legend(loc="lower left", fontsize=8, framealpha=0.8)
    ax.set_title("Puerto Rico — Topography and NOAA ISD Meteorological Stations",
                 fontsize=13, fontweight="bold")

    fig.subplots_adjust(left=0.07, right=0.91, top=0.93, bottom=0.10)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
