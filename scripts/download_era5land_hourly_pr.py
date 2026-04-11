#!/usr/bin/env python3
"""
download_era5land_hourly_pr.py

Download ERA5-Land HOURLY data over Puerto Rico for 20 years (2004-2023).

IMPORTANT — WHY MONTH-BY-MONTH:
  CDS enforces a per-request size limit. Requesting a full year of hourly
  ERA5-Land data returns a 403 "cost limits exceeded" error. Requesting
  one month at a time stays well within the limit.

Output: one file per month per variable group.
  era5land_hourly_t2m_d2m_PR_YYYY_MM.nc       (Group A)
  era5land_hourly_wind_tp_sp_PR_YYYY_MM.nc    (Group B)

Total files: 20 years x 12 months x 2 groups = 480 files
Skip-if-exists: safe to interrupt and resume at any point.

Variable groups:
  Group A: 2m_temperature + 2m_dewpoint_temperature
  Group B: 10m_u/v_wind + total_precipitation + surface_pressure

Dataset: reanalysis-era5-land (DOI: 10.24381/cds.e2161bac)
  Munoz-Sabater et al. (2021), ERA5-Land, ESSD 13:4349-4383

Usage:
  python download_era5land_hourly_pr.py               # all years, both groups
  python download_era5land_hourly_pr.py --group A     # Group A only
  python download_era5land_hourly_pr.py --group B     # Group B only
  python download_era5land_hourly_pr.py --years 2004 2005
  python download_era5land_hourly_pr.py --years 2004 --months 1 2 3
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

YEARS  = list(range(2004, 2024))
MONTHS = list(range(1, 13))

AREA_PR = [18.6, -68.0, 17.8, -65.0]   # [N, W, S, E]
DATASET = "reanalysis-era5-land"
OUTDIR  = Path("data_raw/era5/hourly")

DAYS  = [f"{d:02d}" for d in range(1, 32)]   # CDS ignores invalid days
HOURS = [f"{h:02d}:00" for h in range(0, 24)]

VARIABLE_GROUPS = {
    "A": {
        "variables": ["2m_temperature", "2m_dewpoint_temperature"],
        "filename_tag": "t2m_d2m",
        "description": "Air temperature + Dew point temperature",
    },
    "B": {
        "variables": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "total_precipitation",
            "surface_pressure",
        ],
        "filename_tag": "wind_tp_sp",
        "description": "Wind components + Precipitation + Surface pressure",
    },
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def build_request(year: int, month: int, variables: list) -> dict:
    """Build CDS API request for one month of ERA5-Land hourly data."""
    return {
        "variable":        variables,
        "year":            str(year),
        "month":           f"{month:02d}",
        "day":             DAYS,
        "time":            HOURS,
        "area":            AREA_PR,
        "data_format":     "netcdf",
        "download_format": "unarchived",
    }


def download_month_group(
    client: cdsapi.Client,
    year: int,
    month: int,
    group_key: str,
    outdir: Path,
) -> bool:
    """
    Download one month of ERA5-Land hourly for one variable group.
    Returns True if successful or already exists, False if failed.
    """
    group    = VARIABLE_GROUPS[group_key]
    filename = (
        f"era5land_hourly_{group['filename_tag']}_PR_{year}_{month:02d}.nc"
    )
    target = outdir / filename

    # Skip if file already exists and is not empty/corrupt (>10 KB)
    if target.exists() and target.stat().st_size > 10_000:
        log.info("SKIP (exists): %s", filename)
        return True

    log.info(
        "REQUEST  %d-%02d  group=%s  (%s)",
        year, month, group_key, group["description"],
    )

    try:
        client.retrieve(DATASET, build_request(year, month, group["variables"]), str(target))
        size_mb = target.stat().st_size / 1e6
        log.info("OK       %s  (%.1f MB)", filename, size_mb)
        return True

    except Exception as exc:
        log.error("FAILED   %d-%02d group=%s: %s", year, month, group_key, exc)
        if target.exists() and target.stat().st_size < 10_000:
            target.unlink()
            log.warning("Removed incomplete file: %s", filename)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download ERA5-Land hourly data for Puerto Rico — month by month"
    )
    p.add_argument(
        "--years", type=int, nargs="+", default=YEARS,
        help="Years to download (default: 2004-2023)",
    )
    p.add_argument(
        "--months", type=int, nargs="+", default=MONTHS,
        help="Months to download 1-12 (default: all)",
    )
    p.add_argument(
        "--group", choices=["A", "B", "both"], default="both",
        help="Variable group to download (default: both)",
    )
    p.add_argument(
        "--outdir", type=Path, default=OUTDIR,
        help=f"Output directory (default: {OUTDIR})",
    )
    return p.parse_args()


def main() -> None:
    args   = parse_args()
    groups = ["A", "B"] if args.group == "both" else [args.group]
    total  = len(args.years) * len(args.months) * len(groups)

    args.outdir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("ERA5-Land Hourly Downloader — Puerto Rico ngVLA")
    log.info("=" * 60)
    log.info("Strategy   : one request per year-month-group (avoids CDS size limit)")
    log.info("Years      : %d-%d (%d years)", min(args.years), max(args.years), len(args.years))
    log.info("Months     : %s", args.months)
    log.info("Groups     : %s", groups)
    log.info("Total reqs : %d", total)
    log.info("Area       : N=%.1f W=%.1f S=%.1f E=%.1f", *AREA_PR)
    log.info("Output     : %s", args.outdir.resolve())
    log.info("=" * 60)

    client = cdsapi.Client()
    ok, failed, n = 0, 0, 0

    for year in sorted(args.years):
        for month in sorted(args.months):
            for group_key in groups:
                n += 1
                log.info("[%d/%d]", n, total)
                if download_month_group(client, year, month, group_key, args.outdir):
                    ok += 1
                else:
                    failed += 1
                time.sleep(2)

    log.info("=" * 60)
    log.info("SUMMARY: %d succeeded, %d failed out of %d total", ok, failed, total)
    if failed:
        log.warning("Re-run to retry failed months — completed files are skipped automatically.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
