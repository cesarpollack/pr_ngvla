#!/usr/bin/env python3
"""
phase1_map_rh.py
================
Phase 1 — Monthly climatology: Relative Humidity (%)
Data flow
---------
ERA5-Land t2m, d2m [K]  → rh_from_t_td() [physics.thermodynamics]
  → monthly_climatology() → 3×4 map
"""
import matplotlib; matplotlib.use("Agg")
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from pr_ngvla.config import (
    ERA5_MONTHLY_DIR, COAST_SHP, MUNI_SHP, OUT_MAPS,
    KELVIN_TO_CELSIUS, NOAA_ISD_DIR,
)
from pr_ngvla.data.loaders  import load_era5_monthly, load_noaa_isd_stations
from pr_ngvla.data.spatial  import load_vector_data
from pr_ngvla.data.temporal import monthly_climatology
from pr_ngvla.physics.thermodynamics import rh_from_t_td
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid,
    add_colorbar, add_station_overlay, MONTH_NAMES,
)

ERA5_FILE = ERA5_MONTHLY_DIR / "era5land_monthly_t2m_d2m_PR_2004_2023.nc"
OUT_PNG   = OUT_MAPS / "phase1_rh_monthly_climatology.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def load_data():
    ds    = load_era5_monthly(ERA5_FILE)
    t2m_c = ds["t2m"] + KELVIN_TO_CELSIUS
    d2m_c = ds["d2m"] + KELVIN_TO_CELSIUS
    rh    = xr.apply_ufunc(rh_from_t_td, t2m_c, d2m_c,
                           dask="parallelized", output_dtypes=[float])
    rh.attrs["units"] = "%"
    clim = monthly_climatology(rh)
    print(f"[INFO] RH range: {float(clim.min()):.1f} – {float(clim.max()):.1f} %")
    return clim


def create_figure(clim, coast_union, muni_clip, muni_land_union, stations):
    nrows, ncols = 3, 4
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 8), sharex=True, sharey=True)
    lons, lats = clim["longitude"].values, clim["latitude"].values

    # Adaptive range rounded to nearest 5 %
    vmin = float(np.floor(clim.min() / 5) * 5)
    vmax = float(np.ceil(clim.max()  / 5) * 5)

    mesh = None
    for idx in range(12):
        ax = axes.ravel()[idx]
        row, col = divmod(idx, ncols)
        mesh = ax.pcolormesh(lons, lats, clim.sel(month=idx+1).values,
                             cmap="YlGnBu", vmin=vmin, vmax=vmax,
                             shading="auto", zorder=1)
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        style_axes_grid(ax, row, col, nrows, ncols)
        add_station_overlay(ax, stations, fontsize=5)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)

    add_colorbar(fig, mesh, "Mean Relative Humidity (%)")
    fig.suptitle(
        "20-Year Climatological Mean Monthly Relative Humidity (%)\n"
        "Puerto Rico — ERA5-Land 2004–2023  [Magnus formula from T & Td]",
        fontsize=13, fontweight="bold", y=0.98,
    )
    fig.subplots_adjust(left=0.04, right=0.91, top=0.93, bottom=0.06,
                        hspace=0.25, wspace=0.05)
    return fig


def main():
    print("=" * 60)
    print("Phase 1 — Relative Humidity Monthly Climatology")
    print("=" * 60)
    clim = load_data()
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    stations = load_noaa_isd_stations(NOAA_ISD_DIR)
    fig = create_figure(clim, coast_union, muni_clip, muni_land_union, stations)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
