#!/usr/bin/env python3
"""
phase1_map_wind.py
==================
Phase 1 — Monthly climatology: 10m Wind Speed (m/s)
"""
import matplotlib; matplotlib.use("Agg")
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

from pr_ngvla.config import ERA5_MONTHLY_DIR, COAST_SHP, MUNI_SHP, OUT_MAPS
from pr_ngvla.data.loaders  import load_era5_monthly
from pr_ngvla.data.spatial  import load_vector_data
from pr_ngvla.data.temporal import monthly_climatology
from pr_ngvla.visualization.maps import (
    mask_ocean, plot_base_map, style_axes_grid, add_colorbar, MONTH_NAMES,
)

ERA5_FILE = ERA5_MONTHLY_DIR / "era5land_monthly_wind_tp_sp_PR_2004_2023.nc"
OUT_PNG   = OUT_MAPS / "phase1_wind_monthly_climatology.png"
OUT_MAPS.mkdir(parents=True, exist_ok=True)


def load_data():
    ds = load_era5_monthly(ERA5_FILE)
    if "u10" in ds and "v10" in ds:
        ws = np.sqrt(ds["u10"]**2 + ds["v10"]**2)
        print("[INFO] Wind speed from u10, v10")
    elif "si10" in ds:
        ws = ds["si10"]
        print("[INFO] Using si10 directly")
    else:
        raise KeyError(f"No wind variables found. Available: {list(ds.data_vars)}")
    ws.attrs["units"] = "m/s"
    clim = monthly_climatology(ws)
    print(f"[INFO] Wind range: {float(clim.min()):.2f} – {float(clim.max()):.2f} m/s")
    return clim


def create_figure(clim, coast_union, muni_clip, muni_land_union):
    nrows, ncols = 3, 4
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 8), sharex=True, sharey=True)
    lons, lats = clim["longitude"].values, clim["latitude"].values
    # Adaptive range: let the data determine the colour scale
    vmin = float(np.floor(clim.min() * 2) / 2)   # round down to nearest 0.5
    vmax = float(np.ceil(clim.max()  * 2) / 2)   # round up   to nearest 0.5
    mesh = None
    for idx in range(12):
        ax = axes.ravel()[idx]
        row, col = divmod(idx, ncols)
        mesh = ax.pcolormesh(lons, lats, clim.sel(month=idx+1).values,
                             cmap="RdYlGn_r", vmin=vmin, vmax=vmax,
                             shading="auto", zorder=1)
        mask_ocean(ax, muni_land_union)
        plot_base_map(ax, coast_union, muni_clip)
        style_axes_grid(ax, row, col, nrows, ncols)
        ax.set_title(MONTH_NAMES[idx], fontsize=10, fontweight="bold", pad=3)
    add_colorbar(fig, mesh, "Mean 10m Wind Speed (m/s)")
    fig.suptitle("20-Year Climatological Mean Monthly 10m Wind Speed (m/s)\n"
                 "Puerto Rico — ERA5-Land 2004–2023",
                 fontsize=13, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.04, right=0.91, top=0.93, bottom=0.06,
                        hspace=0.25, wspace=0.05)
    return fig


def main():
    print("=" * 60); print("Phase 1 — Wind Speed Monthly Climatology"); print("=" * 60)
    clim = load_data()
    muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
    fig = create_figure(clim, coast_union, muni_clip, muni_land_union)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Saved: {OUT_PNG}")

if __name__ == "__main__":
    main()
