#!/usr/bin/env python3
"""
phase1_map_temperature.py
=========================
Phase 1 — Monthly climatology: 2-metre Air Temperature (°C)

Data flow
---------
ERA5-Land t2m [K]
  → load_era5_monthly()           data.loaders
  → + KELVIN_TO_CELSIUS           config
  → monthly_climatology()         data.temporal
  → create_figure()               this script
      └─ make_clip_patch()        visualization.maps
      └─ plot_base_map()          visualization.maps
      └─ style_axes_grid()        visualization.maps
      └─ add_colorbar()           visualization.maps

Scientific context
------------------
Temperature itself is within Normal ops range (−15 to +35 °C) island-wide.
Its primary role in this study is as an input to dew-point depression and
as spatial context for interpreting the other variables.
"""

import calendar
import matplotlib
matplotlib.use("Agg")
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

from pr_ngvla.config import (
    ERA5_MONTHLY_DIR, COAST_SHP, MUNI_SHP, OUT_MAPS, KELVIN_TO_CELSIUS,
)
from pr_ngvla.data.loaders  import load_era5_monthly
from pr_ngvla.data.spatial  import load_vector_data
from pr_ngvla.data.temporal import monthly_climatology
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, add_colorbar, MONTH_NAMES,
)

ERA5_FILE = ERA5_MONTHLY_DIR / "era5land_monthly_t2m_d2m_PR_2004_2023.nc"
OUT_PNG   = OUT_MAPS / "phase1_temperature_monthly_climatology.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def load_data():
    ds    = load_era5_monthly(ERA5_FILE)
    t2m_c = ds["t2m"] + KELVIN_TO_CELSIUS
    clim  = monthly_climatology(t2m_c)
    print(f"[INFO] T range: {float(clim.min()):.1f} – {float(clim.max()):.1f} °C")
    return clim


def create_figure(clim, coast_union, muni_clip, muni_land_union):
    nrows, ncols = 3, 4
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 8),
                             sharex=True, sharey=True)
    lons = clim["longitude"].values
    lats = clim["latitude"].values
    vmin = float(np.floor(clim.min()))
    vmax = float(np.ceil(clim.max()))
    mesh = None

    for idx in range(12):
        ax = axes.ravel()[idx]
        row, col = divmod(idx, ncols)
        mesh = ax.pcolormesh(lons, lats, clim.sel(month=idx+1).values,
                             cmap="RdYlBu_r", vmin=vmin, vmax=vmax,
                             shading="auto", zorder=1)
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        style_axes_grid(ax, row, col, nrows, ncols)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)

    add_colorbar(fig, mesh, "Mean 2m Temperature (°C)")
    fig.suptitle("20-Year Climatological Mean Monthly Temperature (°C)\n"
                 "Puerto Rico — ERA5-Land 2004–2023",
                 fontsize=14, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.04, right=0.91, top=0.93, bottom=0.06,
                        hspace=0.25, wspace=0.05)
    return fig


def main():
    print("=" * 60)
    print("Phase 1 — Temperature Monthly Climatology")
    print("=" * 60)
    clim = load_data()
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    fig  = create_figure(clim, coast_union, muni_clip, muni_land_union)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
