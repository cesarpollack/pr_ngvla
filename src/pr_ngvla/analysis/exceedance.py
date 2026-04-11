"""
src/pr_ngvla/analysis/exceedance.py
=====================================
Phase 2 — Hourly exceedance climatology.

For each variable and threshold boundary, computes the fraction of hours
per month (climatological mean over 2004–2023) that EXCEED that threshold.

Supported variables
-------------------
    rh      — Relative Humidity [%]          from t2m + d2m
    wind    — 10-m Wind Speed [m/s]          from u10 + v10
    precip  — Precipitation rate [mm/hr]     from tp
    pwv     — Precipitable Water Vapor [mm]  from tcwv

Output
------
    xr.Dataset saved to outputs/phase2/<var>_exceedance_climatology.nc
    Dimensions: (month: 12, threshold: N, latitude: 9, longitude: 31)
    Each threshold level is stored as a coordinate.

Design notes
------------
- Processes one month-file at a time to limit RAM usage.
- Thresholds are read directly from analysis.thresholds.THRESHOLDS.
- Hurricane Maria exclusion (2017-09 to 2018-06) is an optional flag.
- All physics delegated to physics.thermodynamics.
- File I/O delegated to data.loaders.

References
----------
- Selina et al. (2020) ENV0313
- Linford & Cooper (2023) Memo 117
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import xarray as xr

from pr_ngvla.config import (
    ERA5_HOURLY_DIR,
    ERA5_PWV_DIR,
    OUTPUTS,
    KELVIN_TO_CELSIUS,
    STUDY_YEARS,
    MARIA_START,
    MARIA_END,
)
from pr_ngvla.physics.thermodynamics import rh_from_t_td
from pr_ngvla.analysis.thresholds import THRESHOLDS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YEARS  = STUDY_YEARS
MONTHS = list(range(1, 13))

OUT_PHASE2 = OUTPUTS / "phase2"

# Map script variable names to THRESHOLDS keys
_THRESHOLD_KEY = {
    "rh":     "rh",
    "wind":   "wind",
    "precip": "precip_rate",
    "pwv":    "pwv",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _finite_thresholds(var: str) -> list[float]:
    """
    Extract finite threshold boundaries for a variable from THRESHOLDS.
    Skips the +inf sentinel (last tier).

    Returns list of floats, e.g. for 'rh': [50.0, 80.0, 99.9]
    """
    key = _THRESHOLD_KEY.get(var, var)
    return [
        upper for upper, _, _ in THRESHOLDS[key]
        if not math.isinf(upper)
    ]


def _is_maria(year: int, month: int) -> bool:
    """Return True if (year, month) falls within the Maria exclusion window."""
    ym_str = f"{year}-{month:02d}"
    return MARIA_START <= ym_str <= MARIA_END


# ---------------------------------------------------------------------------
# Variable derivation
# ---------------------------------------------------------------------------

def compute_variable(ds: xr.Dataset, var: str) -> xr.DataArray:
    """
    Derive the physical variable from a raw ERA5 hourly Dataset.

    Parameters
    ----------
    ds  : xr.Dataset — one month of ERA5-Land or PWV hourly data
    var : one of 'rh', 'wind', 'precip', 'pwv'

    Returns
    -------
    da : xr.DataArray (valid_time, latitude, longitude)
        Variable in physical units:
            rh     → [%]
            wind   → [m/s]
            precip → [mm/hr]
            pwv    → [mm]
    """
    if var == "rh":
        t_c  = ds["t2m"] + KELVIN_TO_CELSIUS
        td_c = ds["d2m"] + KELVIN_TO_CELSIUS
        da   = xr.apply_ufunc(rh_from_t_td, t_c, td_c)
        da.attrs["units"]     = "%"
        da.attrs["long_name"] = "Relative Humidity"

    elif var == "wind":
        da = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
        da.attrs["units"]     = "m/s"
        da.attrs["long_name"] = "10-m Wind Speed"

    elif var == "precip":
        # ERA5-Land tp: accumulated over 1-hr step [m] → rate [mm/hr]
        da = ds["tp"] * 1000.0
        da = da.clip(min=0.0)   # remove numerical negatives
        da.attrs["units"]     = "mm/hr"
        da.attrs["long_name"] = "Precipitation Rate"

    elif var == "pwv":
        da = ds["tcwv"]
        da.attrs["units"]     = "mm"
        da.attrs["long_name"] = "Precipitable Water Vapour"

    else:
        raise ValueError(
            f"Unknown variable '{var}'. "
            f"Supported: 'rh', 'wind', 'precip', 'pwv'."
        )

    return da


# ---------------------------------------------------------------------------
# Core exceedance engine
# ---------------------------------------------------------------------------

def monthly_exceedance_climatology(
    var: str,
    exclude_maria: bool = True,
) -> xr.Dataset:
    """
    Compute the climatological monthly exceedance fraction for a variable.

    For each month (1–12) and each threshold boundary, returns the fraction
    of hours (averaged over 20 years) where the variable EXCEEDS the threshold.

    Parameters
    ----------
    var            : 'rh', 'wind', 'precip', or 'pwv'
    exclude_maria  : if True, skip months 2017-09 through 2018-06

    Returns
    -------
    ds_out : xr.Dataset
        Dimensions : (month, threshold, latitude, longitude)
        Variable   : f"{var}_exceedance"  — values in [0, 1]
        Coordinates: month (1–12), threshold (finite boundary values)
    """
    thresholds = _finite_thresholds(var)
    n_thr      = len(thresholds)

    # Accumulators — shape (12, n_thr, lat, lon), initialized on first file
    acc_count = None
    acc_hours = None
    lat = lon = None

    for year in YEARS:
        for month in MONTHS:

            if exclude_maria and _is_maria(year, month):
                print(f"  [SKIP] {year}-{month:02d} (Maria exclusion)")
                continue

            # --- Load file for this month ---
            try:
                ds = _load_month(var, year, month)
            except FileNotFoundError as e:
                print(f"  [WARN] {e} — skipping")
                continue

            # --- Derive variable ---
            da = compute_variable(ds, var)

            # Initialize accumulators on first successful load
            if lat is None:
                lat  = da["latitude"].values
                lon  = da["longitude"].values
                nlat, nlon = len(lat), len(lon)
                acc_count = np.zeros((12, n_thr, nlat, nlon), dtype=np.float64)
                acc_hours = np.zeros((12,        nlat, nlon), dtype=np.float64)

            # --- Accumulate ---
            data  = da.values       # (time, lat, lon)
            m_idx = month - 1       # 0-based month index

            # Count only valid (land) pixels per time step
            valid_mask = (~np.isnan(data)).sum(axis=0)   # (lat, lon)
            acc_hours[m_idx] += valid_mask

            for t_idx, thr in enumerate(thresholds):
                acc_count[m_idx, t_idx] += np.sum(data > thr, axis=0)

            ds.close()
            print(f"  [OK] {var} {year}-{month:02d}")

    # --- Compute fraction ---
    hours_bc = acc_hours[:, np.newaxis, :, :]   # (12, 1, lat, lon)
    with np.errstate(invalid="ignore", divide="ignore"):
        fraction = np.where(hours_bc > 0, acc_count / hours_bc, np.nan)

    # --- Pack into xr.Dataset ---
    ds_out = xr.Dataset(
        {
            f"{var}_exceedance": xr.DataArray(
                fraction.astype(np.float32),
                dims=["month", "threshold", "latitude", "longitude"],
                coords={
                    "month":     MONTHS,
                    "threshold": thresholds,
                    "latitude":  lat,
                    "longitude": lon,
                },
                attrs={
                    "long_name":     (
                        f"Fraction of hours exceeding threshold — {var}"
                    ),
                    "units":         "1",
                    "exclude_maria": str(exclude_maria),
                },
            )
        }
    )

    return ds_out


# ---------------------------------------------------------------------------
# File loader (internal)
# ---------------------------------------------------------------------------

def _load_month(var: str, year: int, month: int) -> xr.Dataset:
    """
    Load the ERA5 hourly file for a given variable, year, and month.

    Raises FileNotFoundError if the expected file does not exist.
    """
    if var == "rh":
        fname = f"era5land_hourly_t2m_d2m_PR_{year}_{month:02d}.nc"
        fpath = ERA5_HOURLY_DIR / fname

    elif var in ("wind", "precip"):
        fname = f"era5land_hourly_wind_tp_sp_PR_{year}_{month:02d}.nc"
        fpath = ERA5_HOURLY_DIR / fname

    elif var == "pwv":
        # PWV files are annual — open full year, select month
        fname = f"era5_hourly_tcwv_PR_{year}.nc"
        fpath = ERA5_PWV_DIR / fname

    else:
        raise ValueError(f"Unknown variable: {var}")

    if not fpath.exists():
        raise FileNotFoundError(f"Missing: {fpath.name}")

    ds = xr.open_dataset(fpath)

    # For PWV: subset to the requested month
    if var == "pwv":
        time_dim = "valid_time" if "valid_time" in ds.dims else "time"
        ds = ds.sel({time_dim: ds[time_dim].dt.month == month})

    return ds


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_exceedance(ds_out: xr.Dataset, var: str) -> Path:
    """Save exceedance Dataset to outputs/phase2/ as NetCDF."""
    OUT_PHASE2.mkdir(parents=True, exist_ok=True)
    outpath = OUT_PHASE2 / f"{var}_exceedance_climatology.nc"
    ds_out.to_netcdf(outpath)
    print(f"[INFO] Saved: {outpath}")
    return outpath
