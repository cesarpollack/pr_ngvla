#!/usr/bin/env python3
"""
Build general no-threshold coverage tables for the PR GHCNh hourly clean core.

This script does not apply usability thresholds. It only organizes factual
coverage information from the clean hourly table:

- station × year × variable coverage, long format
- station × year coverage, wide format
- station × variable summary over the full study period
- variable summary over the full station network and study period

The expected-hours denominator is calendar-based:
- 8760 hours for common years
- 8784 hours for leap years

Inputs
------
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet

Outputs
-------
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


CORE_VARIABLES = [
    "temperature_c",
    "dew_point_temperature_c",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "station_level_pressure_hpa",
    "precipitation_mm",
]


def expected_hours_in_year(year: int) -> int:
    start = pd.Timestamp(year=int(year), month=1, day=1, hour=0)
    end = pd.Timestamp(year=int(year) + 1, month=1, day=1, hour=0)
    return int((end - start).total_seconds() // 3600)


def read_inventory(path: Path) -> pd.DataFrame:
    inv = pd.read_parquet(path)

    required = ["station_id", "station_name", "lat", "lon", "elevation_m"]
    missing = [c for c in required if c not in inv.columns]
    if missing:
        raise ValueError(
            f"Inventory missing required columns: {missing}. "
            f"Available columns: {list(inv.columns)}"
        )

    return (
        inv[required]
        .drop_duplicates(subset=["station_id"])
        .sort_values("station_id")
        .reset_index(drop=True)
    )


def build_full_station_year_grid(
    stations: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1))})
    grid = stations.merge(years, how="cross")
    grid["n_expected_hours"] = grid["year"].map(expected_hours_in_year).astype(int)
    return grid


def build_long_coverage(
    clean: pd.DataFrame,
    grid: pd.DataFrame,
) -> pd.DataFrame:
    clean = clean.copy()
    clean["datetime_hour"] = pd.to_datetime(clean["datetime_hour"], errors="coerce")
    clean["year"] = clean["datetime_hour"].dt.year.astype("Int64")

    base_cols = [
        "station_id",
        "station_name",
        "lat",
        "lon",
        "elevation_m",
        "year",
        "n_expected_hours",
    ]

    rows = []

    for var in CORE_VARIABLES:
        if var not in clean.columns:
            raise ValueError(f"Clean table missing variable column: {var}")

        grouped = (
            clean.groupby(["station_id", "year"], dropna=False)
            .agg(
                n_hours_valid=(var, lambda s: int(s.notna().sum())),
                sum_value=(var, "sum"),
                min_value=(var, "min"),
                max_value=(var, "max"),
                mean_value=(var, "mean"),
            )
            .reset_index()
        )

        out = grid[base_cols].merge(
            grouped,
            on=["station_id", "year"],
            how="left",
        )

        out["variable"] = var
        out["n_hours_valid"] = out["n_hours_valid"].fillna(0).astype(int)
        out["sum_value"] = out["sum_value"].fillna(0.0)
        out["fraction_of_year"] = out["n_hours_valid"] / out["n_expected_hours"]

        out = out[
            [
                "station_id",
                "station_name",
                "lat",
                "lon",
                "elevation_m",
                "year",
                "variable",
                "n_expected_hours",
                "n_hours_valid",
                "fraction_of_year",
                "min_value",
                "max_value",
                "mean_value",
                "sum_value",
            ]
        ]

        rows.append(out)

    long = pd.concat(rows, ignore_index=True)
    long = long.sort_values(["station_id", "year", "variable"]).reset_index(drop=True)
    return long


def build_wide_station_year(long: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    wide = grid[
        [
            "station_id",
            "station_name",
            "lat",
            "lon",
            "elevation_m",
            "year",
            "n_expected_hours",
        ]
    ].copy()

    metrics = ["n_hours_valid", "fraction_of_year", "min_value", "max_value", "mean_value"]

    for var in CORE_VARIABLES:
        sub = long[long["variable"] == var][
            ["station_id", "year"] + metrics
        ].copy()

        sub = sub.rename(
            columns={
                "n_hours_valid": f"{var}_n_hours",
                "fraction_of_year": f"{var}_fraction_of_year",
                "min_value": f"{var}_min",
                "max_value": f"{var}_max",
                "mean_value": f"{var}_mean",
            }
        )

        wide = wide.merge(sub, on=["station_id", "year"], how="left")

    return wide.sort_values(["station_id", "year"]).reset_index(drop=True)


def build_station_variable_summary(long: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["station_id", "station_name", "lat", "lon", "elevation_m", "variable"]

    summary = (
        long.groupby(group_cols, dropna=False)
        .agg(
            total_expected_hours=("n_expected_hours", "sum"),
            total_valid_hours=("n_hours_valid", "sum"),
            total_sum_value=("sum_value", "sum"),
            years_with_any_data=("n_hours_valid", lambda s: int((s > 0).sum())),
            min_clean_value=("min_value", "min"),
            max_clean_value=("max_value", "max"),
        )
        .reset_index()
    )

    summary["fraction_of_study_period"] = (
        summary["total_valid_hours"] / summary["total_expected_hours"]
    )

    summary["mean_clean_value"] = np.where(
        summary["total_valid_hours"] > 0,
        summary["total_sum_value"] / summary["total_valid_hours"],
        np.nan,
    )

    first_last = (
        long[long["n_hours_valid"] > 0]
        .groupby(group_cols, dropna=False)
        .agg(
            first_year_with_data=("year", "min"),
            last_year_with_data=("year", "max"),
        )
        .reset_index()
    )

    summary = summary.merge(first_last, on=group_cols, how="left")

    summary = summary[
        [
            "station_id",
            "station_name",
            "lat",
            "lon",
            "elevation_m",
            "variable",
            "total_expected_hours",
            "total_valid_hours",
            "fraction_of_study_period",
            "years_with_any_data",
            "first_year_with_data",
            "last_year_with_data",
            "min_clean_value",
            "max_clean_value",
            "mean_clean_value",
        ]
    ]

    return summary.sort_values(["station_id", "variable"]).reset_index(drop=True)


def build_variable_summary(long: pd.DataFrame) -> pd.DataFrame:
    summary = (
        long.groupby("variable", dropna=False)
        .agg(
            total_station_years=("station_id", "size"),
            total_expected_hours=("n_expected_hours", "sum"),
            total_valid_hours=("n_hours_valid", "sum"),
            total_sum_value=("sum_value", "sum"),
            station_years_with_any_data=("n_hours_valid", lambda s: int((s > 0).sum())),
            min_clean_value=("min_value", "min"),
            max_clean_value=("max_value", "max"),
        )
        .reset_index()
    )

    stations_any = (
        long[long["n_hours_valid"] > 0]
        .groupby("variable")["station_id"]
        .nunique()
        .rename("stations_with_any_data")
        .reset_index()
    )

    summary = summary.merge(stations_any, on="variable", how="left")
    summary["stations_with_any_data"] = summary["stations_with_any_data"].fillna(0).astype(int)

    summary["fraction_of_all_possible_station_hours"] = (
        summary["total_valid_hours"] / summary["total_expected_hours"]
    )

    summary["mean_clean_value"] = np.where(
        summary["total_valid_hours"] > 0,
        summary["total_sum_value"] / summary["total_valid_hours"],
        np.nan,
    )

    summary = summary[
        [
            "variable",
            "total_station_years",
            "station_years_with_any_data",
            "stations_with_any_data",
            "total_expected_hours",
            "total_valid_hours",
            "fraction_of_all_possible_station_hours",
            "min_clean_value",
            "max_clean_value",
            "mean_clean_value",
        ]
    ]

    return summary.sort_values("variable").reset_index(drop=True)


def write_table(df: pd.DataFrame, path_base: Path) -> None:
    csv_path = path_base.with_suffix(".csv")
    parquet_path = path_base.with_suffix(".parquet")

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    print(f"  {csv_path}")
    print(f"  {parquet_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build no-threshold coverage tables from GHCNh hourly clean core."
    )
    parser.add_argument(
        "--clean-core",
        default="data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet",
        help="Path to clean core parquet table.",
    )
    parser.add_argument(
        "--inventory",
        default="data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet",
        help="Path to station inventory parquet.",
    )
    parser.add_argument("--start-year", type=int, default=2004)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument(
        "--outdir",
        default="data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds",
        help="Output directory.",
    )

    args = parser.parse_args()

    clean_path = Path(args.clean_core)
    inventory_path = Path(args.inventory)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Reading:")
    print(f"  clean core: {clean_path}")
    print(f"  inventory:  {inventory_path}")

    clean = pd.read_parquet(clean_path)
    stations = read_inventory(inventory_path)

    grid = build_full_station_year_grid(
        stations=stations,
        start_year=args.start_year,
        end_year=args.end_year,
    )

    print("\nFull station-year grid:")
    print(f"  stations: {stations['station_id'].nunique()}")
    print(f"  years: {args.start_year}-{args.end_year}")
    print(f"  station-years: {len(grid)}")

    long = build_long_coverage(clean=clean, grid=grid)
    wide = build_wide_station_year(long=long, grid=grid)
    station_variable_summary = build_station_variable_summary(long=long)
    variable_summary = build_variable_summary(long=long)

    print("\nWriting no-threshold coverage tables:")
    write_table(
        long,
        outdir / "ghcnh_hourly_clean_core_station_year_variable_coverage_no_thresholds",
    )
    write_table(
        wide,
        outdir / "ghcnh_hourly_clean_core_station_year_coverage_wide_no_thresholds",
    )
    write_table(
        station_variable_summary,
        outdir / "ghcnh_hourly_clean_core_station_variable_summary_no_thresholds",
    )
    write_table(
        variable_summary,
        outdir / "ghcnh_hourly_clean_core_variable_summary_no_thresholds",
    )

    print("\nVariable summary:")
    print(variable_summary.to_string(index=False))


if __name__ == "__main__":
    main()
