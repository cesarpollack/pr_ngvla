#!/usr/bin/env python3
"""
phase1_map_pwv.py
=================
Phase 1 — Monthly climatology: Precipitable Water Vapor (mm)
ERA5 single-levels TCWV [kg/m² ≡ mm]
"""
import matplotlib; matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt

from pr_ngvla.config import ERA5_PWV_DIR, COAST_SHP, MUNI_SHP, OUT_MAPS, NOAA_ISD_DIR
from pr_ngvla.data.loaders  import load_era5_pwv, load_noaa_isd_stations
from pr_ngvla.data.spatial  import load_vector_data
from pr_ngvla.data.temporal import monthly_climatology
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid,
    add_colorbar, add_station_overlay, MONTH_NAMES,
)

OUT_PNG = OUT_MAPS / "phase1_pwv_monthly_climatology.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def load_data():
    tcwv = load_era5_pwv(ERA5_PWV_DIR)
    time_dim = "valid_time" if "valid_time" in tcwv.dims else "time"
    clim = monthly_climatology(tcwv, time_dim=time_dim)
    print(f"[INFO] PWV range: {float(clim.min()):.1f} – {float(clim.max()):.1f} mm")
    return clim


def create_figure(clim, coast_union, muni_clip, muni_land_union, stations):
    nrows, ncols = 3, 4
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 8), sharex=True, sharey=True)
    lons, lats = clim["longitude"].values, clim["latitude"].values
    vmin = float(np.floor(clim.min() / 5) * 5)
    vmax = float(np.ceil(clim.max()  / 5) * 5)
    mesh = None
    for idx in range(12):
        ax = axes.ravel()[idx]
        row, col = divmod(idx, ncols)
        mesh = ax.pcolormesh(lons, lats, clim.sel(month=idx+1).values,
                             cmap="YlOrBr", vmin=vmin, vmax=vmax,
                             shading="auto", zorder=1)
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        style_axes_grid(ax, row, col, nrows, ncols)
        add_station_overlay(ax, stations, fontsize=5)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)
    add_colorbar(fig, mesh, "Mean PWV / TCWV (mm)")
    fig.suptitle("20-Year Climatological Mean Monthly Precipitable Water Vapour (mm)\n"
                 "Puerto Rico — ERA5 Single-Levels TCWV 2004–2023",
                 fontsize=13, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.04, right=0.91, top=0.93, bottom=0.06,
                        hspace=0.25, wspace=0.05)
    return fig


def main():
    print("=" * 60); print("Phase 1 — PWV Monthly Climatology"); print("=" * 60)
    clim = load_data()
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    stations = load_noaa_isd_stations(NOAA_ISD_DIR)
    fig = create_figure(clim, coast_union, muni_clip, muni_land_union, stations)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")

if __name__ == "__main__":
    main()
