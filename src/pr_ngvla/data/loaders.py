"""
src/pr_ngvla/data/loaders.py
=============================
ERA5 and NOAA ISD file readers.

Responsibilities
----------------
- Open NetCDF files and return raw xarray Datasets or DataArrays.
- Concatenate multi-file datasets (ERA5 annual PWV files).
- Fix known ERA5 quirks (longitude 0–360 → −180–180).
- Load NOAA ISD station metadata as a GeoDataFrame.

This module handles file I/O ONLY.  Unit conversions and physics
derivations belong in physics.thermodynamics; temporal aggregations
belong in data.temporal.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import xarray as xr

from pr_ngvla.config import WGS84


# ---------------------------------------------------------------------------
# ERA5-Land monthly
# ---------------------------------------------------------------------------

def load_era5_monthly(filepath: Path | str) -> xr.Dataset:
    """
    Open an ERA5-Land monthly NetCDF file.

    Returns the raw xr.Dataset.  The calling script selects the
    variable(s) it needs (e.g. ds["t2m"], ds["u10"]).

    Parameters
    ----------
    filepath : path to the NetCDF file

    Returns
    -------
    ds : xr.Dataset
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(
            f"ERA5-Land monthly file not found: {filepath}\n"
            f"Run scripts/download_era5land_monthly_pr.py first."
        )
    print(f"[INFO] Loading {filepath.name}")
    return xr.open_dataset(filepath)


# ---------------------------------------------------------------------------
# ERA5 single-levels PWV (one file per year)
# ---------------------------------------------------------------------------

def load_era5_pwv(pwv_dir: Path | str) -> xr.DataArray:
    """
    Load and concatenate all annual ERA5 PWV (TCWV) files.

    File naming convention (from download_era5_pwv_pr.py):
        era5_hourly_tcwv_PR_2004.nc, era5_hourly_tcwv_PR_2005.nc, … era5_hourly_tcwv_PR_2023.nc

    Longitude correction
    --------------------
    ERA5 single-levels CDS downloads sometimes use 0–360° longitude.
    This function detects and corrects it to −180–180° automatically.

    Parameters
    ----------
    pwv_dir : directory containing the annual PWV NetCDF files

    Returns
    -------
    tcwv : xr.DataArray (time, latitude, longitude)
        Total column water vapour [kg/m²] ≡ PWV [mm].
        Time dimension is named 'valid_time' or 'time' depending on
        the CDS download; the original name is preserved.
    """
    pwv_dir = Path(pwv_dir)
    files   = sorted(pwv_dir.glob("era5_hourly_tcwv_PR_*.nc"))

    if not files:
        raise FileNotFoundError(
            f"No PWV files found in {pwv_dir}.\n"
            f"Run scripts/download_era5_pwv_pr.py first."
        )
    print(f"[INFO] Found {len(files)} PWV files")

    # Open each file individually — open_mfdataset can fail on CDS files
    # with incompatible calendar attributes across years.
    datasets = []
    for f in files:
        ds = xr.open_dataset(f)
        if "tcwv" not in ds:
            raise KeyError(
                f"Variable 'tcwv' not found in {f.name}.\n"
                f"Available: {list(ds.data_vars)}"
            )
        datasets.append(ds["tcwv"])

    # Detect time dimension name (varies by CDS download configuration)
    time_dim = "valid_time" if "valid_time" in datasets[0].dims else "time"
    print(f"[INFO] Time dimension: '{time_dim}'")

    tcwv = xr.concat(datasets, dim=time_dim)

    # Fix longitude if 0–360° convention is used
    if float(tcwv["longitude"].max()) > 180:
        tcwv = tcwv.assign_coords(longitude=(tcwv["longitude"] - 360))
        tcwv = tcwv.sortby("longitude")
        print("[INFO] Longitude corrected: 0:360 → −180:180")

    tcwv.attrs["units"]     = "mm"   # kg/m² ≡ mm of PWV
    tcwv.attrs["long_name"] = "Precipitable Water Vapour"
    return tcwv


# ---------------------------------------------------------------------------
# NOAA ISD station metadata
# ---------------------------------------------------------------------------

def load_noaa_isd_stations(isd_dir: Path | str) -> gpd.GeoDataFrame:
    """
    Load NOAA ISD station metadata from the station catalog CSV.

    The catalog is written by download_noaa_isd_pr.py and contains one
    row per downloaded station with columns:
        STATION_ID, USAF, WBAN, STATION_NAME, LAT, LON, ELEV_M, ...

    Returns
    -------
    gdf : GeoDataFrame (EPSG:4326)
        Columns: STATION_ID, STATION_NAME, LAT, LON, ELEV_M, geometry
    """
    isd_dir  = Path(isd_dir)
    catalog  = isd_dir / "station_catalog.csv"

    if not catalog.exists():
        raise FileNotFoundError(
            f"Station catalog not found: {catalog}\n"
            f"Run scripts/download_noaa_isd_pr.py first."
        )

    df = pd.read_csv(catalog)

    # Normalise column names to uppercase for consistency
    # Normalize: strip whitespace, uppercase, replace spaces with underscores
    df.columns = [c.strip().upper().replace(" ", "_") for c in df.columns]

    required = {"STATION_ID", "STATION_NAME", "LAT", "LON"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns in {catalog.name}: {sorted(missing)}\n"
            f"Available: {sorted(df.columns)}"
        )

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["LON"], df["LAT"]),
        crs=WGS84,
    )

    print(f"[INFO] Loaded {len(gdf)} NOAA ISD stations from {catalog.name}")
    return gdf
