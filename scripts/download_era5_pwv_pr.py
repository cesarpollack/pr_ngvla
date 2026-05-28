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
from pathlib import Path

import cdsapi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

YEARS = list(range(2004, 2024))

# Puerto Rico bounding box [North, West, South, East]
AREA_PR = [18.6, -68.0, 17.8, -65.0]

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

def build_request(year: int) -> dict:
    return {
        "product_type":    "reanalysis",
        "variable":        [VARIABLE],
        "year":            str(year),
        "month":           MONTHS,
        "day":             DAYS,
        "time":            HOURS,
        "area":            AREA_PR,
        "data_format":     "netcdf",
        "download_format": "unarchived",
    }


def download_year(client: cdsapi.Client, year: int, outdir: Path) -> Path | None:
    filename = f"era5_hourly_tcwv_PR_{year}.nc"
    target = outdir / filename

    if target.exists():
        log.info("SKIP (exists): %s", target)
        return target

    log.info("REQUEST  year=%d  variable=total_column_water_vapour", year)

    try:
        client.retrieve(DATASET, build_request(year), str(target))
        size_gb = target.stat().st_size / 1e9
        log.info("OK       %s  (%.2f GB)", target.name, size_gb)
        return target
    except Exception as exc:
        log.error("FAILED   year=%d: %s", year, exc)
        if target.exists() and target.stat().st_size < 1000:
            target.unlink()
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download ERA5 single-levels TCWV (PWV) for Puerto Rico (2004-2023)"
    )
    p.add_argument("--years", type=int, nargs="+", default=YEARS)
    p.add_argument("--outdir", type=Path, default=OUTDIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("ERA5 Single-Levels PWV (TCWV) Downloader — PR ngVLA")
    log.info("=" * 60)
    log.info("Dataset : %s", DATASET)
    log.info("Variable: %s (TCWV ≈ PWV in mm)", VARIABLE)
    log.info("Years   : %d–%d", min(args.years), max(args.years))
    log.info("Output  : %s", args.outdir.resolve())
    log.info("Note    : 0.25° resolution (different from ERA5-Land 0.1°)")
    log.info("=" * 60)

    client = cdsapi.Client()
    ok, failed = 0, 0

    for year in sorted(args.years):
        result = download_year(client, year, args.outdir)
        if result is not None and "SKIP" not in str(result):
            ok += 1
        elif result is None:
            failed += 1
        time.sleep(2)

    log.info("SUMMARY: %d downloaded, %d failed", ok, failed)


if __name__ == "__main__":
    main()
