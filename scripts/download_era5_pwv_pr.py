#!/usr/bin/env python3
"""
download_era5_pwv_pr.py

Download ERA5 (single-levels) Total Column Water Vapour (TCWV) over
Puerto Rico for 20 years (2004-2023).

IMPORTANT: PWV (Precipitable Water Vapour) is NOT available in ERA5-Land,
which only covers surface variables. TCWV is in the ERA5 single-levels
product (reanalysis-era5-single-levels), which uses the full atmospheric
column integration.

TCWV (kg/m²) ≈ PWV (mm)
  The conversion is 1:1 because water density is 1000 kg/m³ and
  1 kg/m² of water = 1 mm depth.

Scientific justification:
  PWV is a primary ngVLA site-selection variable because atmospheric water
  vapour strongly affects high-frequency radio observations.

  ERA5-Land does not provide PWV/TCWV. Therefore, total column water vapour is
  downloaded from ERA5 single levels using the CDS variable
  total_column_water_vapour.

  TCWV has units of kg m^-2, which is numerically equivalent to millimetres of
  precipitable water depth.

  Do not report a specific numerical PWV validation-error value in the project
  documentation unless the exact validation reference and context have been
  checked and cited.
  General ERA5 and ERA5-Land references:
  Hersbach et al. (2020); Muñoz-Sabater et al. (2021).

Dataset: reanalysis-era5-single-levels
  (different from ERA5-Land — this is the full atmospheric model)

Resolution: 0.25° (~27.5 km) — coarser than ERA5-Land (0.1°)
  This is acceptable for PWV because:
  1. PWV is a column-integrated quantity, less affected by surface terrain
  2. MERRA-2 (0.625°) is used for cross-validation anyway
  3. For regional screening, 0.25° gives ~14 cells over Puerto Rico

Output layout:
  data_raw/era5/pwv/
    era5_hourly_tcwv_PR_YYYY.nc

Usage:
  python download_era5_pwv_pr.py
  python download_era5_pwv_pr.py --years 2004 2005
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

YEARS = list(range(2004, 2024))

# Puerto Rico bounding box [North, West, South, East]
# Original project analysis bbox. Kept as the default for backward compatibility.
AREA_PR = [18.6, -68.0, 17.8, -65.0]

# Buffered bbox used only when TCWV/PWV is being downloaded for interpolation
# onto the ERA5-Land target grid. This does not expand the final analysis
# domain; it only provides native ERA5 0.25-degree support around the target grid.
AREA_PR_BUFFERED_FOR_INTERPOLATION = [18.75, -68.25, 17.50, -64.75]

# ERA5 single-levels dataset (NOT era5-land)
DATASET = "reanalysis-era5-single-levels"

OUTDIR = Path("data_raw/era5/pwv")

VARIABLE = "total_column_water_vapour"  # CDS name for TCWV / PWV

MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS   = [f"{d:02d}" for d in range(1, 32)]
HOURS  = [f"{h:02d}:00" for h in range(0, 24)]

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------

def expected_era5_native_coords(area: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """
    Return expected ERA5 single-level native latitude/longitude coordinates
    for a CDS area request [North, West, South, East] on the 0.25-degree grid.
    """
    north, west, south, east = area

    lats = np.arange(90.0, -90.0001, -0.25)
    lons = np.arange(-180.0, 180.0001, 0.25)

    expected_lats = lats[(lats <= north + 1e-9) & (lats >= south - 1e-9)]
    expected_lons = lons[(lons >= west - 1e-9) & (lons <= east + 1e-9)]

    return np.round(expected_lats, 6), np.round(expected_lons, 6)


def normalize_longitudes(lons: np.ndarray) -> np.ndarray:
    """Normalize longitudes to the -180..180 convention for validation."""
    values = np.asarray(lons, dtype=float)
    values = np.where(values > 180.0, values - 360.0, values)
    return np.round(values, 6)


def validate_tcwv_file(filepath: Path, area: list[float]) -> tuple[bool, str]:
    """
    Validate that an existing/downloaded TCWV NetCDF file is usable for the
    requested area before skipping or accepting it.

    This prevents partial/corrupt files from being silently reused.
    """
    if not filepath.exists():
        return False, "file does not exist"

    try:
        with xr.open_dataset(filepath) as ds:
            # CDS requests use the long variable name "total_column_water_vapour",
            # but the NetCDF variable commonly appears as the GRIB short name "tcwv".
            tcwv_var = "tcwv" if "tcwv" in ds.data_vars else VARIABLE if VARIABLE in ds.data_vars else None
            if tcwv_var is None:
                return (
                    False,
                    f"missing TCWV variable; expected one of ['tcwv', {VARIABLE!r}]; "
                    f"available={list(ds.data_vars)}",
                )

            lat_name = "latitude" if "latitude" in ds.coords else "lat" if "lat" in ds.coords else None
            lon_name = "longitude" if "longitude" in ds.coords else "lon" if "lon" in ds.coords else None

            if lat_name is None or lon_name is None:
                return False, "missing latitude/longitude coordinates"

            time_dim = "valid_time" if "valid_time" in ds.dims else "time" if "time" in ds.dims else None
            if time_dim is None:
                return False, "missing valid_time/time dimension"

            if ds.sizes.get(time_dim, 0) <= 0:
                return False, f"empty time dimension: {time_dim}"

            expected_lats, expected_lons = expected_era5_native_coords(area)
            got_lats = np.round(np.asarray(ds[lat_name].values, dtype=float), 6)
            got_lons = normalize_longitudes(ds[lon_name].values)

            if got_lats.shape != expected_lats.shape or not np.allclose(got_lats, expected_lats):
                return (
                    False,
                    f"latitude mismatch: got={got_lats.tolist()} expected={expected_lats.tolist()}",
                )

            if got_lons.shape != expected_lons.shape or not np.allclose(got_lons, expected_lons):
                return (
                    False,
                    f"longitude mismatch: got={got_lons.tolist()} expected={expected_lons.tolist()}",
                )

            return True, (
                f"valid TCWV file: time={ds.sizes[time_dim]}, "
                f"lat={ds.sizes[lat_name]}, lon={ds.sizes[lon_name]}"
            )

    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def quarantine_invalid_file(filepath: Path, reason: str) -> Path:
    """Move an invalid existing/downloaded file aside instead of overwriting it silently."""
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    quarantine_path = filepath.with_name(f"{filepath.name}.invalid_{stamp}")
    filepath.rename(quarantine_path)
    log.warning("Moved invalid file to %s  reason=%s", quarantine_path, reason)
    return quarantine_path


# ---------------------------------------------------------------------------

def build_request(year: int, area: list[float]) -> dict:
    return {
        "product_type":    "reanalysis",
        "variable":        [VARIABLE],
        "year":            str(year),
        "month":           MONTHS,
        "day":             DAYS,
        "time":            HOURS,
        "area":            area,
        "data_format":     "netcdf",
        "download_format": "unarchived",
    }


def download_year(
    client: cdsapi.Client,
    year: int,
    outdir: Path,
    area: list[float],
) -> tuple[str, Path | None]:
    filename = f"era5_hourly_tcwv_PR_{year}.nc"
    target = outdir / filename

    if target.exists():
        is_valid, reason = validate_tcwv_file(target, area)
        if is_valid:
            log.info("SKIP (valid existing): %s  %s", target, reason)
            return "skipped", target

        log.warning("Existing file failed validation: %s  %s", target, reason)
        quarantine_invalid_file(target, reason)

    log.info(
        "REQUEST  year=%d  variable=total_column_water_vapour  area=%s",
        year,
        area,
    )

    try:
        client.retrieve(DATASET, build_request(year, area), str(target))
        size_gb = target.stat().st_size / 1e9

        is_valid, reason = validate_tcwv_file(target, area)
        if not is_valid:
            log.error("Downloaded file failed validation: %s  %s", target, reason)
            quarantine_invalid_file(target, reason)
            return "failed", None

        log.info("OK       %s  (%.2f GB)  %s", target.name, size_gb, reason)
        return "downloaded", target
    except Exception as exc:
        log.error("FAILED   year=%d: %s", year, exc)
        if target.exists() and target.stat().st_size < 1000:
            target.unlink()
        return "failed", None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download ERA5 single-levels TCWV (PWV) for Puerto Rico (2004-2023)"
    )
    p.add_argument("--years", type=int, nargs="+", default=YEARS)
    p.add_argument("--outdir", type=Path, default=OUTDIR)
    p.add_argument(
        "--buffered-pr",
        action="store_true",
        help=(
            "Use buffered Puerto Rico bbox for TCWV/PWV interpolation support: "
            "[18.75, -68.25, 17.50, -64.75]. "
            "Default keeps the original project bbox."
        ),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    area = AREA_PR_BUFFERED_FOR_INTERPOLATION if args.buffered_pr else AREA_PR
    args.outdir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("ERA5 Single-Levels PWV (TCWV) Downloader — PR ngVLA")
    log.info("=" * 60)
    log.info("Dataset : %s", DATASET)
    log.info("Variable: %s (TCWV ≈ PWV in mm)", VARIABLE)
    log.info("Years   : %d–%d", min(args.years), max(args.years))
    log.info("Area    : %s", area)
    log.info("Output  : %s", args.outdir.resolve())
    log.info("Note    : 0.25° resolution (different from ERA5-Land 0.1°)")
    log.info("=" * 60)

    client = cdsapi.Client()
    downloaded, skipped, failed = 0, 0, 0

    for year in sorted(args.years):
        status, _ = download_year(client, year, args.outdir, area)
        if status == "downloaded":
            downloaded += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1
        time.sleep(2)

    log.info(
        "SUMMARY: %d downloaded, %d skipped_valid_existing, %d failed",
        downloaded,
        skipped,
        failed,
    )


if __name__ == "__main__":
    main()
