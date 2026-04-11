"""
pr_ngvla.data.era5
==================
Loaders for ERA5-Land hourly/monthly NetCDF files and ERA5 single-levels PWV.

All functions return xarray DataArrays or Datasets with:
  - Coordinates named 'time', 'latitude', 'longitude'
  - Physical units already converted (K→°C, Pa→hPa, m→mm)
  - Lazy loading via dask (chunks by year-month)

Usage
-----
>>> from pr_ngvla.data.era5 import open_era5land_hourly, open_era5_pwv
>>> ds = open_era5land_hourly(2020)
>>> pwv = open_era5_pwv(2020)
"""

from __future__ import annotations

import logging
from pathlib import Path

import xarray as xr

from pr_ngvla.config import (
    ERA5_HOURLY_DIR,
    ERA5_MONTHLY_DIR,
    ERA5_PWV_DIR,
    ERA5_T2M, ERA5_D2M, ERA5_U10, ERA5_V10, ERA5_TP, ERA5_SP, ERA5_TCWV,
    KELVIN_TO_CELSIUS, PA_TO_HPA, M_TO_MM,
)

log = logging.getLogger(__name__)

# Chunk size for dask lazy loading — tune to server RAM if needed
# With 1 TB RAM and ~10 GB per file, this is conservative and safe
_CHUNKS = {"time": 24 * 31}   # one month of hourly data per chunk


# ---------------------------------------------------------------------------
# ERA5-Land hourly
# ---------------------------------------------------------------------------

def open_era5land_hourly(
    year: int,
    variables: str = "all",
    data_dir: Path = ERA5_HOURLY_DIR,
) -> xr.Dataset:
    """
    Open ERA5-Land hourly data for one year as a lazy xarray Dataset.

    Parameters
    ----------
    year : int
        Year to load (2004–2023).
    variables : str
        'all'    → load both variable groups (t2m+d2m and wind+tp+sp)
        'thermo' → load only t2m + d2m (temperature group)
        'wind'   → load only u10 + v10 + tp + sp (wind/precip group)
    data_dir : Path
        Directory containing the ERA5-Land hourly NetCDF files.

    Returns
    -------
    xr.Dataset
        Variables in physical units: T2m (°C), Td2m (°C),
        wind components (m/s), precip (mm/hr), pressure (hPa).
    """
    file_a = data_dir / f"era5land_hourly_t2m_d2m_PR_{year}.nc"
    file_b = data_dir / f"era5land_hourly_wind_tp_sp_PR_{year}.nc"

    datasets = []

    if variables in ("all", "thermo"):
        if not file_a.exists():
            raise FileNotFoundError(f"ERA5-Land hourly Group A not found: {file_a}")
        log.info("Opening %s (lazy)", file_a.name)
        datasets.append(xr.open_dataset(file_a, chunks=_CHUNKS, engine="netcdf4"))

    if variables in ("all", "wind"):
        if not file_b.exists():
            raise FileNotFoundError(f"ERA5-Land hourly Group B not found: {file_b}")
        log.info("Opening %s (lazy)", file_b.name)
        datasets.append(xr.open_dataset(file_b, chunks=_CHUNKS, engine="netcdf4"))

    ds = xr.merge(datasets)
    ds = _convert_era5land_units(ds)
    return ds


def open_era5land_hourly_multiyear(
    years: list[int],
    variables: str = "all",
    data_dir: Path = ERA5_HOURLY_DIR,
) -> xr.Dataset:
    """
    Open ERA5-Land hourly data for multiple years, concatenated along time.
    Uses dask for lazy loading — safe with 96-core / 1 TB server.
    """
    datasets = [open_era5land_hourly(y, variables, data_dir) for y in years]
    log.info("Concatenating %d years of ERA5-Land hourly data...", len(years))
    return xr.concat(datasets, dim="time")


# ---------------------------------------------------------------------------
# ERA5-Land monthly means
# ---------------------------------------------------------------------------

def open_era5land_monthly(
    data_dir: Path = ERA5_MONTHLY_DIR,
) -> xr.Dataset:
    """
    Open ERA5-Land monthly means (2004–2023, all variables) as xr.Dataset.
    Used for Tier 1 climatology maps.
    """
    file_a = data_dir / "era5land_monthly_t2m_d2m_PR_2004_2023.nc"
    file_b = data_dir / "era5land_monthly_wind_tp_sp_PR_2004_2023.nc"

    for f in (file_a, file_b):
        if not f.exists():
            raise FileNotFoundError(f"ERA5-Land monthly file not found: {f}")

    ds = xr.merge([
        xr.open_dataset(file_a, engine="netcdf4"),
        xr.open_dataset(file_b, engine="netcdf4"),
    ])
    ds = _convert_era5land_units(ds)
    return ds


# ---------------------------------------------------------------------------
# ERA5 single-levels PWV (TCWV)
# ---------------------------------------------------------------------------

def open_era5_pwv(
    year: int,
    data_dir: Path = ERA5_PWV_DIR,
) -> xr.DataArray:
    """
    Open ERA5 single-levels Total Column Water Vapour for one year.

    TCWV (kg/m²) == PWV (mm) — conversion is 1:1.

    Returns
    -------
    xr.DataArray
        PWV in mm, named 'pwv'.
    """
    filepath = data_dir / f"era5_hourly_tcwv_PR_{year}.nc"
    if not filepath.exists():
        raise FileNotFoundError(f"ERA5 PWV file not found: {filepath}")

    log.info("Opening %s (lazy)", filepath.name)
    ds = xr.open_dataset(filepath, chunks=_CHUNKS, engine="netcdf4")

    tcwv = ds[ERA5_TCWV]
    tcwv = tcwv.rename("pwv")
    tcwv.attrs["units"] = "mm"
    tcwv.attrs["long_name"] = "Precipitable Water Vapour (TCWV)"
    return tcwv


# ---------------------------------------------------------------------------
# Internal unit conversion
# ---------------------------------------------------------------------------

def _convert_era5land_units(ds: xr.Dataset) -> xr.Dataset:
    """
    Convert ERA5-Land variables from native units to analysis units.

    Native ERA5 units:
      t2m, d2m : Kelvin      → convert to °C
      sp       : Pa          → convert to hPa
      tp       : m (accum.)  → convert to mm/hr

    Note on total_precipitation:
      ERA5-Land tp is accumulated from the start of the forecast step (hourly).
      For hourly data, each time step represents 1-hour accumulation.
      Dividing by 1 hour gives mm/hr directly.
    """
    ds = ds.copy()

    if ERA5_T2M in ds:
        ds[ERA5_T2M] = ds[ERA5_T2M] + KELVIN_TO_CELSIUS
        ds[ERA5_T2M].attrs["units"] = "°C"
        ds[ERA5_T2M].attrs["long_name"] = "2m air temperature"

    if ERA5_D2M in ds:
        ds[ERA5_D2M] = ds[ERA5_D2M] + KELVIN_TO_CELSIUS
        ds[ERA5_D2M].attrs["units"] = "°C"
        ds[ERA5_D2M].attrs["long_name"] = "2m dewpoint temperature"

    if ERA5_SP in ds:
        ds[ERA5_SP] = ds[ERA5_SP] * PA_TO_HPA
        ds[ERA5_SP].attrs["units"] = "hPa"
        ds[ERA5_SP].attrs["long_name"] = "Surface pressure"

    if ERA5_TP in ds:
        # m per hour → mm per hour
        ds[ERA5_TP] = ds[ERA5_TP] * M_TO_MM
        ds[ERA5_TP].attrs["units"] = "mm/hr"
        ds[ERA5_TP].attrs["long_name"] = "Total precipitation rate"
        # Clip negative values (numerical noise in ERA5)
        ds[ERA5_TP] = ds[ERA5_TP].clip(min=0.0)

    return ds
