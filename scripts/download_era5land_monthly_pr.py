#!/usr/bin/env python3
"""
download_era5land_monthly_pr.py

Download ERA5-Land MONTHLY MEANS over Puerto Rico for 20 years (2004-2023).
This is used for TIER 1: monthly climatology maps.

Why monthly means in addition to hourly?
  ECMWF pre-computes monthly aggregates, so you download ~100x less data
  for the climatology maps. Monthly means are used to:
    1. Build the 12-month suitability maps (the primary poster output)
    2. Validate ERA5-Land against NOAA GHCN monthly station normals
    3. Compute seasonal bias correction factors (dry vs wet season)

Dataset: reanalysis-era5-land-monthly-means
  (separate CDS dataset from hourly; much smaller files)

Output layout:
  data_raw/era5/monthly/
    era5land_monthly_t2m_d2m_PR_2004_2023.nc      (single file, all years)
    era5land_monthly_wind_tp_sp_PR_2004_2023.nc

Usage:
  python download_era5land_monthly_pr.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import cdsapi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

YEARS  = [str(y) for y in range(2004, 2024)]
MONTHS = [f"{m:02d}" for m in range(1, 13)]
AREA_PR = [18.6, -68.0, 17.8, -65.0]
DATASET = "reanalysis-era5-land-monthly-means"
OUTDIR  = Path("data_raw/era5/monthly")

VARIABLE_GROUPS = {
    "A": {
        "variables":    ["2m_temperature", "2m_dewpoint_temperature"],
        "filename_tag": "t2m_d2m",
    },
    "B": {
        "variables":    [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "total_precipitation",
            "surface_pressure",
        ],
        "filename_tag": "wind_tp_sp",
    },
}


def build_request(variables: list[str]) -> dict:
    return {
        "product_type":    "monthly_averaged_reanalysis",
        "variable":        variables,
        "year":            YEARS,
        "month":           MONTHS,
        "time":            "00:00",   # monthly means have one time step
        "area":            AREA_PR,
        "data_format":     "netcdf",
        "download_format": "unarchived",
    }


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()

    log.info("Downloading ERA5-Land monthly means (2004-2023) — Puerto Rico")

    for group_key, group in VARIABLE_GROUPS.items():
        # All 20 years in a single file — monthly means are tiny
        filename = f"era5land_monthly_{group['filename_tag']}_PR_2004_2023.nc"
        target = OUTDIR / filename

        if target.exists():
            log.info("SKIP (exists): %s", target)
            continue

        log.info("Requesting group %s: %s", group_key, group["variables"])
        request = build_request(group["variables"])

        try:
            client.retrieve(DATASET, request, str(target))
            size_mb = target.stat().st_size / 1e6
            log.info("OK  %s  (%.1f MB)", filename, size_mb)
        except Exception as exc:
            log.error("FAILED group %s: %s", group_key, exc)

    log.info("Monthly download complete.")


if __name__ == "__main__":
    main()
