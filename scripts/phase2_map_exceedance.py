#!/usr/bin/env python3
"""
scripts/phase2_map_exceedance.py
=================================
Phase 2 — Monthly exceedance fraction maps.

For each variable, plots the fraction of hours per month that exceed
the primary operationally-relevant threshold (one panel per month,
12 panels total).

Thresholds plotted (one per variable)
--------------------------------------
    rh     > 50%      (Good threshold)
    wind   > 9 m/s    (Good threshold)
    precip > 1 mm/hr  (drizzle-free threshold)
    pwv    > 26 mm    (Poor threshold — most discriminating for PR)

Usage
-----
    python scripts/phase2_map_exceedance.py --var rh
    python scripts/phase2_map_exceedance.py --var wind
    python scripts/phase2_map_exceedance.py --var precip
    python scripts/phase2_map_exceedance.py --var pwv
    python scripts/phase2_map_exceedance.py --var all
"""

import argparse
import matplotlib; matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt
import xarray as xr

from pr_ngvla.config import COAST_SHP, MUNI_SHP, OUTPUTS, NOAA_ISD_DIR
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.data.loaders import load_noaa_isd_stations
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid,
    add_colorbar, add_station_overlay, MONTH_NAMES,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUT_PHASE2     = OUTPUTS / "phase2"
OUT_MAPS_PH2   = OUTPUTS / "maps" / "phase2"

# Primary threshold to plot per variable and its label

PLOT_CONFIG = {
    "rh":     {"threshold": 50.0,  "units": "%",     "cmap": "YlOrRd",
                "vmax": 1.0,
                "label": "Fraction of hours RH > 50 %"},
    "wind":   {"threshold": 9.0,   "units": "m/s",   "cmap": "YlOrRd",
                "vmax": 0.1,
                "label": "Fraction of hours Wind > 9 m/s"},
    "precip": {"threshold": 1.0,   "units": "mm/hr", "cmap": "YlOrRd",
                "vmax": 1.0,
                "label": "Fraction of hours Precip > 1 mm/hr"},
    "pwv":    {"threshold": 26.0,  "units": "mm",    "cmap": "YlOrRd",
                "vmax": 1.0,
                "label": "Fraction of hours PWV > 26 mm"},
}

TITLES = {
    "rh":     "Fraction of Hours with RH > 50%\nPuerto Rico — ERA5-Land Hourly 2004–2023",
    "wind":   "Fraction of Hours with Wind Speed > 9 m/s\nPuerto Rico — ERA5-Land Hourly 2004–2023",
    "precip": "Fraction of Hours with Precipitation > 1 mm/hr\nPuerto Rico — ERA5-Land Hourly 2004–2023",
    "pwv":    "Fraction of Hours with PWV > 26 mm\nPuerto Rico — ERA5 Single-Levels Hourly 2004–2023",
}

SUPPORTED = ["rh", "wind", "precip", "pwv"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2 — Exceedance fraction maps"
    )
    parser.add_argument(
        "--var",
        required=True,
        choices=SUPPORTED + ["all"],
        help="Variable to plot",
    )
    return parser.parse_args()


def load_exceedance(var: str, threshold: float) -> np.ndarray:
    """
    Load exceedance climatology and extract the slice for a given threshold.

    Returns array of shape (12, lat, lon) — fraction in [0, 1].
    """
    nc_path = OUT_PHASE2 / f"{var}_exceedance_climatology.nc"
    ds  = xr.open_dataset(nc_path)
    da  = ds[f"{var}_exceedance"]
    arr = da.sel(threshold=threshold, method="nearest").values
    lats = da["latitude"].values
    lons = da["longitude"].values
    ds.close()
    return arr, lats, lons


def create_figure(
    arr, lats, lons,
    coast_union, muni_clip, muni_land_union,
    stations_gdf,
    var: str,
) -> plt.Figure:
    """Create 3×4 grid of monthly exceedance maps."""
    cfg   = PLOT_CONFIG[var]
    nrows, ncols = 3, 4

    fig, axes = plt.subplots(
        nrows, ncols, figsize=(14, 8), sharex=True, sharey=True
    )

    mesh = None
    for idx in range(12):
        ax       = axes.ravel()[idx]
        row, col = divmod(idx, ncols)

        mesh = ax.pcolormesh(
            lons, lats, arr[idx],
            cmap=cfg["cmap"], vmin=0.0, vmax=cfg["vmax"],
            shading="auto", zorder=1,
        )
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        add_station_overlay(ax, stations_gdf)
        style_axes_grid(ax, row, col, nrows, ncols)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)

    add_colorbar(fig, mesh, cfg["label"])
    fig.suptitle(
        TITLES[var],
        fontsize=13, fontweight="bold", y=0.98,
    )
    fig.subplots_adjust(
        left=0.04, right=0.91, top=0.93, bottom=0.06,
        hspace=0.25, wspace=0.05,
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(var: str) -> None:
    cfg = PLOT_CONFIG[var]
    print(f"[INFO] Plotting exceedance map: {var} > {cfg['threshold']} {cfg['units']}")

    # Load exceedance data
    arr, lats, lons = load_exceedance(var, cfg["threshold"])

    # Load vector data
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)

    # Load station overlay
    stations_gdf = load_noaa_isd_stations(NOAA_ISD_DIR)

    # Create figure
    fig = create_figure(
        arr, lats, lons,
        coast_union, muni_clip, muni_land_union,
        stations_gdf, var,
    )

    # Save
    OUT_MAPS_PH2.mkdir(parents=True, exist_ok=True)
    out_png = OUT_MAPS_PH2 / f"phase2_{var}_exceedance_climatology.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {out_png}")


def main() -> None:
    args = parse_args()
    if args.var == "all":
        for var in SUPPORTED:
            run(var)
    else:
        run(args.var)


if __name__ == "__main__":
    main()
