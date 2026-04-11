#!/usr/bin/env python3
"""
phase1_map_precip.py
====================
Phase 1 — Monthly climatology: Total Precipitation (mm/month)

ERA5-Land tp [m/day mean rate] → precip_to_mm_month() → mm/month
"""
import matplotlib; matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt

from pr_ngvla.config import ERA5_MONTHLY_DIR, COAST_SHP, MUNI_SHP, OUT_MAPS
from pr_ngvla.data.loaders  import load_era5_monthly
from pr_ngvla.data.spatial  import load_vector_data
from pr_ngvla.data.temporal import monthly_climatology, precip_to_mm_month
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, add_colorbar, MONTH_NAMES,
)

ERA5_FILE = ERA5_MONTHLY_DIR / "era5land_monthly_wind_tp_sp_PR_2004_2023.nc"
OUT_PNG   = OUT_MAPS / "phase1_precip_monthly_climatology.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def load_data():
    ds   = load_era5_monthly(ERA5_FILE)
    if "tp" not in ds:
        raise KeyError(f"'tp' not found. Available: {list(ds.data_vars)}")
    clim_rate = monthly_climatology(ds["tp"])   # m/day mean rate per month
    clim      = precip_to_mm_month(clim_rate)   # mm/month
    print(f"[INFO] Precip range: {float(clim.min()):.1f} – {float(clim.max()):.1f} mm/month")
    return clim


def create_figure(clim, coast_union, muni_clip, muni_land_union):
    nrows, ncols = 3, 4
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 8), sharex=True, sharey=True)
    lons, lats = clim["longitude"].values, clim["latitude"].values
    vmax = float(np.ceil(clim.max() / 50.0) * 50.0)
    mesh = None
    for idx in range(12):
        ax = axes.ravel()[idx]
        row, col = divmod(idx, ncols)
        mesh = ax.pcolormesh(lons, lats, clim.sel(month=idx+1).values,
                             cmap="Blues", vmin=0, vmax=vmax,
                             shading="auto", zorder=1)
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        style_axes_grid(ax, row, col, nrows, ncols)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)
    add_colorbar(fig, mesh, "Mean Total Precipitation (mm/month)")
    fig.suptitle("20-Year Climatological Mean Monthly Precipitation (mm/month)\n"
                 "Puerto Rico — ERA5-Land 2004–2023",
                 fontsize=13, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.04, right=0.91, top=0.93, bottom=0.06,
                        hspace=0.25, wspace=0.05)
    return fig


def main():
    print("=" * 60); print("Phase 1 — Precipitation Monthly Climatology"); print("=" * 60)
    clim = load_data()
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    fig = create_figure(clim, coast_union, muni_clip, muni_land_union)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")

if __name__ == "__main__":
    main()
