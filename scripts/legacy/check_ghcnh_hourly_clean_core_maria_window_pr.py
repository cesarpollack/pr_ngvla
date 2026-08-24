#!/usr/bin/env python3
"""
scripts/diagnostics/ghcnh/check_ghcnh_hourly_clean_core_maria_window_pr.py
================================================================================

Minimal diagnostic: check whether the GHCNh hourly clean core contains data
inside the Hurricane Maria analysis window.

Default window
--------------
2017-09-01 00:00 <= datetime_hour < 2017-11-01 00:00

This script only answers:
- Are there clean-core rows in that period?
- How many rows/stations are present?
- How many valid clean hours are present per core variable?

It does not read raw files, does not audit cleaning decisions, does not modify
any data, and does not generate maps.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


CLEAN_CORE_DEFAULT = (
    "data_interim/noaa/ghcnh_hourly/clean_core/"
    "ghcnh_hourly_clean_core_2004_2023.parquet"
)

CORE_VARIABLES = {
    "temperature_c": "T",
    "dew_point_temperature_c": "Td",
    "relative_humidity_pct": "RH",
    "wind_speed_m_s": "Wind speed",
    "station_level_pressure_hpa": "Pressure",
    "precipitation_mm": "Precipitation",
}


def find_repo_root(start: Path) -> Path:
    """Find the repository root by walking upward until a .git directory is found."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check GHCNh clean-core coverage during the Hurricane Maria window."
    )
    parser.add_argument(
        "--clean-core",
        default=CLEAN_CORE_DEFAULT,
        help="Path to the GHCNh hourly clean-core Parquet file.",
    )
    parser.add_argument(
        "--start",
        default="2017-09-01 00:00:00",
        help="Inclusive start datetime for the analysis window.",
    )
    parser.add_argument(
        "--end",
        default="2017-11-01 00:00:00",
        help="Exclusive end datetime for the analysis window.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path.cwd())
    clean_path = Path(args.clean_core)
    if not clean_path.is_absolute():
        clean_path = repo_root / clean_path

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)

    print("GHCNh clean-core Hurricane Maria window check")
    print(f"Repository root: {repo_root}")
    print(f"Clean core: {clean_path}")
    print(f"Analysis window: {start} <= datetime_hour < {end}")

    if not clean_path.exists():
        raise FileNotFoundError(f"Missing clean-core file: {clean_path}")

    df = pd.read_parquet(clean_path)
    if "datetime_hour" not in df.columns:
        raise ValueError("Clean core does not contain required column: datetime_hour")

    df = df.copy()
    df["datetime_hour"] = pd.to_datetime(df["datetime_hour"], errors="coerce")
    window = df[(df["datetime_hour"] >= start) & (df["datetime_hour"] < end)].copy()

    n_rows = int(len(window))
    n_stations = int(window["station_id"].nunique()) if "station_id" in window.columns else 0

    print("")
    if n_rows > 0:
        print("Answer: YES, the clean core contains information in this period.")
    else:
        print("Answer: NO, the clean core does not contain information in this period.")

    print(f"Clean-core rows in window: {n_rows:,}")
    print(f"Stations with at least one clean-core row in window: {n_stations:,}")

    if n_rows == 0:
        return

    print("")
    print("Valid clean hours by variable:")
    for column, label in CORE_VARIABLES.items():
        if column not in window.columns:
            print(f"  {label}: column missing")
            continue

        valid = window[column].notna()
        valid_hours = int(valid.sum())
        valid_stations = int(window.loc[valid, "station_id"].nunique()) if "station_id" in window.columns else 0
        print(f"  {label}: {valid_stations} stations, {valid_hours:,} valid hours")


if __name__ == "__main__":
    main()
