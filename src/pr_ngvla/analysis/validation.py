"""
src/pr_ngvla/analysis/validation.py
=====================================
Phase 2 — ERA5-Land vs NOAA ISD station validation.

For each station and each variable, extracts the nearest ERA5-Land
grid pixel, matches timestamps, and computes:
    - MBE  (Mean Bias Error)       — systematic offset
    - RMSE (Root Mean Square Error) — total error magnitude
    - r    (Pearson correlation)    — temporal agreement

Variables validated
-------------------
    rh   — Relative Humidity [%]     ISD: rh     | ERA5: t2m + d2m
    wind — 10-m Wind Speed [m/s]     ISD: ws     | ERA5: u10 + v10

Variables NOT validated (no hourly ISD data available)
------------------------------------------------------
    precip — ERA5 drizzle bias known; spatial validation via PRISM
    pwv    — No radiosonde data in PR; global validation via
             Muñoz-Sabater et al. (2021)

Design notes
------------
- Nearest-neighbor pixel selection (no interpolation).
- Maria exclusion applied to both ERA5 and ISD before comparison.
- Only overlapping timestamps are used.
- Output: dict of DataFrames (one per station) + summary CSV.

References
----------
- Muñoz-Sabater et al. (2021) ESSD 13:4349-4383
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from pr_ngvla.config import (
    ERA5_HOURLY_DIR,
    NOAA_ISD_DIR,
    OUTPUTS,
    KELVIN_TO_CELSIUS,
    MARIA_START,
    MARIA_END,
    STUDY_YEARS,
)
from pr_ngvla.physics.thermodynamics import rh_from_t_td

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUT_VALIDATION = OUTPUTS / "validation"

VARIABLES = {
    "rh":   {"isd_col": "rh",  "units": "%",   "label": "Relative Humidity"},
    "wind": {"isd_col": "ws",  "units": "m/s", "label": "10-m Wind Speed"},
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(obs: np.ndarray, mod: np.ndarray) -> dict:
    """
    Compute MBE, RMSE, and Pearson r from paired arrays.

    Parameters
    ----------
    obs : observed values (ISD)
    mod : modelled values (ERA5)

    Returns
    -------
    dict with keys: n, mbe, rmse, r
    """
    mask = np.isfinite(obs) & np.isfinite(mod)
    obs, mod = obs[mask], mod[mask]
    n = len(obs)
    if n < 10:
        return {"n": n, "mbe": np.nan, "rmse": np.nan, "r": np.nan}

    mbe  = float(np.mean(mod - obs))
    rmse = float(np.sqrt(np.mean((mod - obs) ** 2)))
    r    = float(np.corrcoef(obs, mod)[0, 1])

    return {"n": n, "mbe": mbe, "rmse": rmse, "r": r}


# ---------------------------------------------------------------------------
# Nearest ERA5 pixel selector
# ---------------------------------------------------------------------------

def nearest_era5_pixel(
    lat_station: float,
    lon_station: float,
    era5_lats: np.ndarray,
    era5_lons: np.ndarray,
    land_mask: np.ndarray | None = None,
) -> tuple[int, int]:
    """
    Return (lat_idx, lon_idx) of the nearest ERA5 grid cell to the station.
    If land_mask is provided (True = land), restricts search to land pixels.
    Uses Euclidean distance in degree space (sufficient for small domain).
    """
    dlat = era5_lats - lat_station
    dlon = era5_lons - lon_station
    dist = np.sqrt(dlat[:, None] ** 2 + dlon[None, :] ** 2)

    if land_mask is not None:
        # Set ocean pixels to inf so they are never selected
        dist = np.where(land_mask, dist, np.inf)

    idx = np.unravel_index(np.argmin(dist), dist.shape)
    return idx

# ---------------------------------------------------------------------------
# ERA5 hourly loader for a single pixel
# ---------------------------------------------------------------------------

def load_era5_pixel(
    var: str,
    lat_idx: int,
    lon_idx: int,
    years: list[int] = STUDY_YEARS,
    exclude_maria: bool = True,
) -> pd.Series:
    """
    Load ERA5 hourly data for a single grid pixel across all years.

    Returns a pd.Series indexed by UTC timestamp.
    """
    records = []

    for year in years:
        for month in range(1, 13):

            # Maria exclusion
            ym_str = f"{year}-{month:02d}"
            if exclude_maria and MARIA_START <= ym_str <= MARIA_END:
                continue

            # Select file based on variable
            if var == "rh":
                fname = f"era5land_hourly_t2m_d2m_PR_{year}_{month:02d}.nc"
            elif var == "wind":
                fname = f"era5land_hourly_wind_tp_sp_PR_{year}_{month:02d}.nc"
            else:
                raise ValueError(f"Unknown variable: {var}")

            fpath = ERA5_HOURLY_DIR / fname
            if not fpath.exists():
                continue

            ds = xr.open_dataset(fpath)
            time_dim = "valid_time" if "valid_time" in ds.dims else "time"

            if var == "rh":
                t_c  = ds["t2m"].values[:, lat_idx, lon_idx] + KELVIN_TO_CELSIUS
                td_c = ds["d2m"].values[:, lat_idx, lon_idx] + KELVIN_TO_CELSIUS
                vals = rh_from_t_td(t_c, td_c)
            elif var == "wind":
                u = ds["u10"].values[:, lat_idx, lon_idx]
                v = ds["v10"].values[:, lat_idx, lon_idx]
                vals = np.sqrt(u ** 2 + v ** 2)

            times = pd.to_datetime(ds[time_dim].values)
            ds.close()

            for t, v in zip(times, vals):
                records.append((t, v))

    if not records:
        return pd.Series(dtype=float)

    idx, vals = zip(*records)
    return pd.Series(vals, index=pd.DatetimeIndex(idx), name=f"era5_{var}")


# ---------------------------------------------------------------------------
# ISD loader for a single station
# ---------------------------------------------------------------------------

def load_isd_station(
    station_file: Path,
    var: str,
    exclude_maria: bool = True,
    study_years: list[int] = STUDY_YEARS,
) -> pd.Series:
    """
    Load NOAA ISD hourly data for a single station and variable.

    Returns a pd.Series indexed by UTC timestamp.
    """
    isd_col = VARIABLES[var]["isd_col"]

    df = pd.read_csv(station_file, parse_dates=["datetime"])
    df = df.set_index("datetime")
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).astype("datetime64[ns]")

    # Filter to study years
    df = df[df.index.year.isin(study_years)]

    # Maria exclusion
    if exclude_maria:
        maria_s = pd.Timestamp(MARIA_START + "-01")
        maria_e = pd.Timestamp(MARIA_END   + "-01") + pd.offsets.MonthEnd(1)
        df = df[~((df.index >= maria_s) & (df.index <= maria_e))]

    series = pd.to_numeric(df[isd_col], errors="coerce")
    series.name = f"isd_{var}"
    return series


# ---------------------------------------------------------------------------
# Single station validation
# ---------------------------------------------------------------------------

def validate_station(
    station_id: str,
    station_name: str,
    lat: float,
    lon: float,
    station_file: Path,
    era5_lats: np.ndarray,
    era5_lons: np.ndarray,
    land_mask: bool = None,
    exclude_maria: bool = True,
) -> pd.DataFrame:
    """
    Run validation for all variables at a single station.

    Returns a DataFrame with columns:
        station_id, station_name, variable, n, mbe, rmse, r
    """
    results = []

    for var in VARIABLES:
        print(f"  [{station_id}] {var} ...")

        # Find nearest ERA5 pixel
        lat_idx, lon_idx = nearest_era5_pixel(lat, lon, era5_lats, era5_lons, land_mask)
        nearest_lat = era5_lats[lat_idx]
        nearest_lon = era5_lons[lon_idx]
        dist_deg = np.sqrt((nearest_lat - lat)**2 + (nearest_lon - lon)**2)

        # Load ERA5 pixel time series
        era5_series = load_era5_pixel(
            var, lat_idx, lon_idx, exclude_maria=exclude_maria
        )

        # Load ISD time series
        isd_series = load_isd_station(
            station_file, var, exclude_maria=exclude_maria
        )

        # Align on common timestamps
        df_aligned = pd.DataFrame({
            "obs": isd_series,
            "mod": era5_series,
        }).dropna()

        if len(df_aligned) < 10:
            print(f"    [WARN] insufficient overlap: {len(df_aligned)} points")
            continue

        metrics = compute_metrics(
            df_aligned["obs"].values,
            df_aligned["mod"].values,
        )

        results.append({
            "station_id":   station_id,
            "station_name": station_name,
            "lat":          lat,
            "lon":          lon,
            "era5_lat":     round(float(nearest_lat), 2),
            "era5_lon":     round(float(nearest_lon), 2),
            "dist_deg":     round(float(dist_deg), 3),
            "variable":     var,
            "units":        VARIABLES[var]["units"],
            **metrics,
        })

    return pd.DataFrame(results)

def build_land_mask(era5_lats: np.ndarray, era5_lons: np.ndarray) -> np.ndarray:
    """
    Build a boolean land mask from ERA5-Land data.
    True = land pixel (non-NaN), False = ocean.
    """
    from pr_ngvla.config import ERA5_HOURLY_DIR
    f = sorted(ERA5_HOURLY_DIR.glob("era5land_hourly_t2m_d2m_PR_2004_01.nc"))[0]
    ds = xr.open_dataset(f)
    t  = ds["t2m"].values[0]   # first time step (lat, lon)
    ds.close()
    return ~np.isnan(t)

# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_validation_table(df: pd.DataFrame) -> Path:
    """Save summary validation table to outputs/validation/."""
    OUT_VALIDATION.mkdir(parents=True, exist_ok=True)
    outpath = OUT_VALIDATION / "era5_vs_isd_metrics.csv"
    df.to_csv(outpath, index=False, float_format="%.4f")
    print(f"[INFO] Saved: {outpath}")
    return outpath
