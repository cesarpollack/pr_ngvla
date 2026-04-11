"""
src/pr_ngvla/data/temporal.py
==============================
Temporal aggregation functions for ERA5 reanalysis data.

Responsibilities
----------------
- Compute 20-year monthly climatologies from monthly or hourly ERA5 data.
- Convert ERA5 precipitation from its native units to mm/month.
- (Future) Seasonal means, wet-hour frequency, hurricane Maria masking.

All functions accept xarray DataArrays and return xarray DataArrays,
preserving spatial coordinates.  No I/O, no plotting, no physics.
"""

from __future__ import annotations

import xarray as xr
import numpy as np

from pr_ngvla.config import DAYS_PER_MONTH, M_TO_MM


def monthly_climatology(
    da: xr.DataArray,
    time_dim: str = "valid_time",
) -> xr.DataArray:
    """
    Compute the 20-year climatological mean for each calendar month.

    Groups by calendar month (1–12) and averages all values for that
    month across the full time series (2004–2023 = 20 years × 12 months
    = 240 time steps for monthly data).

    Result shape: (12, latitude, longitude) — one layer per month.

    Parameters
    ----------
    da       : DataArray with a time dimension containing monthly stamps
    time_dim : name of the time dimension ('valid_time' or 'time')

    Returns
    -------
    clim : DataArray with a 'month' coordinate (1–12)
    """
    if time_dim not in da.dims:
        # Try the other common name before raising
        alt = "time" if time_dim == "valid_time" else "valid_time"
        if alt in da.dims:
            time_dim = alt
        else:
            raise KeyError(
                f"Time dimension '{time_dim}' not found in DataArray.\n"
                f"Available dims: {list(da.dims)}"
            )

    return da.groupby(f"{time_dim}.month").mean(dim=time_dim)


def precip_to_mm_month(
    clim_daily_rate: xr.DataArray,
) -> xr.DataArray:
    """
    Convert ERA5 monthly climatology from m/day (mean rate) to mm/month.

    ERA5-Land monthly 'tp' is the monthly mean of the daily accumulation
    rate, stored in metres per day [m/day].  It is NOT the monthly total.

    Conversion:
        mm/month = mean_daily_rate [m/day] × 1000 [mm/m] × days_in_month

    This function expects a DataArray already grouped by calendar month
    (i.e., shape (12, lat, lon) with a 'month' coordinate), as returned
    by monthly_climatology().

    Parameters
    ----------
    clim_daily_rate : DataArray (12, lat, lon) — ERA5 tp in m/day

    Returns
    -------
    monthly_mm : DataArray (12, lat, lon) — total precipitation in mm/month
    """
    monthly_mm = xr.zeros_like(clim_daily_rate)

    for m in range(1, 13):
        days = DAYS_PER_MONTH[m]
        monthly_mm.loc[dict(month=m)] = (
            clim_daily_rate.sel(month=m).values * M_TO_MM * days
        )

    monthly_mm.attrs["units"]     = "mm/month"
    monthly_mm.attrs["long_name"] = "Total Precipitation"
    return monthly_mm
