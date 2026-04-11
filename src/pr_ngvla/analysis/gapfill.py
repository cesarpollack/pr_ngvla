"""
src/pr_ngvla/analysis/gapfill.py

ERA5 single-levels gap-fill for coastal pixels missing in ERA5-Land.

Scientific justification
------------------------
ERA5-Land (~9 km) assigns NaN to coastal pixels where land fraction is below
an internal threshold. ERA5 single-levels (~28 km) uses a different land-sea
mask and recovers partial coverage for coastal zones such as Lajas and Guánica
in SW Puerto Rico. Both products derive from the same ECMWF IFS system
(Hersbach et al. 2020; Muñoz-Sabater et al. 2021), making them physically
consistent for merging.

Strategy
--------
For each exceedance variable (RH, wind, precip, PWV):
  - ERA5-Land pixel available  → use ERA5-Land (higher resolution, preferred)
  - ERA5-Land pixel NaN        → use ERA5-SL (interpolated to ERA5-Land grid)
  - ERA5-SL also NaN           → remains NaN (open ocean, Mona, Culebra)

The merged field is saved as a new NetCDF alongside the original Phase 2
files. The composite index is then recomputed on the merged fields.

Usage
-----
    from pr_ngvla.analysis.gapfill import merge_era5land_singlelev
"""

from __future__ import annotations
import numpy as np
import xarray as xr


def identify_gap_pixels(era5land_da: xr.DataArray) -> np.ndarray:
    """
    Return boolean mask (lat, lon) of pixels that are NaN in ERA5-Land.
    If da has a month dimension, uses the union of NaN across all months.
    """
    if "month" in era5land_da.dims:
        nan_mask = np.isnan(era5land_da.values).all(axis=0)
    else:
        nan_mask = np.isnan(era5land_da.values)
    return nan_mask  # True = gap pixel


def regrid_singlelev_to_era5land(
    sl_da: xr.DataArray,
    era5land_da: xr.DataArray,
) -> xr.DataArray:
    """
    Interpolate ERA5 single-levels DataArray to ERA5-Land grid (bilinear).

    Parameters
    ----------
    sl_da : xr.DataArray
        ERA5 single-levels data. Must have 'latitude' and 'longitude' coords.
    era5land_da : xr.DataArray
        ERA5-Land reference grid.

    Returns
    -------
    xr.DataArray
        sl_da interpolated to ERA5-Land lat/lon grid.
    """
    target_lat = era5land_da["latitude"]
    target_lon = era5land_da["longitude"]

    sl_regridded = sl_da.interp(
        latitude=target_lat,
        longitude=target_lon,
        method="linear",
    )
    return sl_regridded


def merge_era5land_singlelev(
    era5land_da: xr.DataArray,
    sl_da: xr.DataArray,
    var_name: str = "exceedance",
) -> xr.DataArray:
    """
    Merge ERA5-Land exceedance with ERA5-SL exceedance for gap pixels.

    ERA5-Land takes priority where data exists. ERA5-SL fills gaps.

    Parameters
    ----------
    era5land_da : xr.DataArray
        ERA5-Land exceedance. Shape: (month, threshold, lat, lon).
        NaN = gap pixel (coastal or ocean).
    sl_da : xr.DataArray
        ERA5 single-levels exceedance on ERA5-Land grid.
        Same shape as era5land_da.
    var_name : str
        Name for the output variable.

    Returns
    -------
    xr.DataArray
        Merged exceedance. ERA5-Land where available, ERA5-SL for gaps.
        Attrs include provenance information.
    """
    # xr.where: where condition is True → first arg, else → second arg
    # Use ERA5-Land where it is NOT NaN; use ERA5-SL where ERA5-Land is NaN
    merged = era5land_da.where(~np.isnan(era5land_da), other=sl_da)

    merged.name = var_name
    merged.attrs = era5land_da.attrs.copy()
    merged.attrs["gap_fill"] = (
        "ERA5-Land primary; ERA5 single-levels (0.25°) used for coastal "
        "NaN pixels (Lajas, Guánica area). Both from ECMWF IFS system. "
        "See Hersbach et al. (2020) and Muñoz-Sabater et al. (2021)."
    )
    merged.attrs["era5land_resolution"] = "~9 km (0.1°)"
    merged.attrs["era5sl_resolution"]   = "~28 km (0.25°)"

    return merged


def gap_fill_summary(
    era5land_da: xr.DataArray,
    merged_da: xr.DataArray,
) -> dict:
    """
    Return summary statistics of the gap-fill operation.

    Parameters
    ----------
    era5land_da : xr.DataArray
        Original ERA5-Land field (with NaN gaps).
    merged_da : xr.DataArray
        Gap-filled field.

    Returns
    -------
    dict with keys:
        n_land_era5land  : original land pixels
        n_gap            : pixels filled from ERA5-SL
        n_still_nan      : pixels still NaN after fill (open ocean)
        pct_recovered    : fraction of gaps recovered
    """
    # Annual union of NaN
    if "month" in era5land_da.dims:
        # Use first threshold and first month for pixel counting
        da0 = era5land_da.isel(threshold=0, month=0)
        m0  = merged_da.isel(threshold=0, month=0)
    else:
        da0 = era5land_da
        m0  = merged_da

    original_nan  = np.isnan(da0.values)
    merged_nan    = np.isnan(m0.values)

    n_total        = da0.values.size
    n_land_orig    = int((~original_nan).sum())
    n_gap          = int(original_nan.sum())
    n_recovered    = int((original_nan & ~merged_nan).sum())
    n_still_nan    = int(merged_nan.sum())
    pct_recovered  = 100.0 * n_recovered / n_gap if n_gap > 0 else 0.0

    return {
        "n_total":           n_total,
        "n_land_era5land":   n_land_orig,
        "n_gap_pixels":      n_gap,
        "n_recovered":       n_recovered,
        "n_still_nan":       n_still_nan,
        "pct_gap_recovered": round(pct_recovered, 1),
    }
