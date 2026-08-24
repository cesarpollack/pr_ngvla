#!/usr/bin/env python3
"""
scripts/build_noaa_variable_coverage_pr.py
==========================================

Build the Puerto Rico NOAA variable-level station coverage products from the
validated station-inventory stage.

Inputs
------
1. Validation-ready master station inventory:
   data_interim/noaa/station_inventory/pr_station_inventory_master.parquet

2. Raw NOAA metadata inventories:
   data_raw/noaa/isd/metadata/isd-inventory.csv
   data_raw/noaa/ghcn/metadata/ghcnd-inventory.txt

Outputs
-------
1. Long-form variable coverage table
2. Wide station-variable matrix
3. Small QC summary table

Design
------
This script is intentionally thin:
- load prepared inputs
- call reusable library logic in src/pr_ngvla/
- write reproducible outputs

No scientific logic should live here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import pr_ngvla.config as cfg
from pr_ngvla.data.noaa import (
    load_ghcnd_inventory,
    load_isd_inventory,
)
from pr_ngvla.data.noaa_variable_coverage import (
    build_mixed_resolution_validation_long,
    build_mixed_resolution_validation_wide,
    build_noaa_variable_coverage_long,
    build_noaa_variable_coverage_wide,
    summarize_mixed_resolution_validation,
    summarize_variable_coverage,
)


def main() -> None:
    # ------------------------------------------------------------------
    # Base directories from config (with safe fallbacks)
    # ------------------------------------------------------------------
    data_interim = Path(getattr(cfg, "DATA_INTERIM", "data_interim"))
    data_raw = Path(getattr(cfg, "DATA_RAW", "data_raw"))
    out_tables = Path(getattr(cfg, "OUT_TABLES", "outputs/tables"))

    noaa_interim_dir = data_interim / "noaa"
    station_inventory_dir = noaa_interim_dir / "station_inventory"
    coverage_dir = noaa_interim_dir / "variable_coverage"

    coverage_dir.mkdir(parents=True, exist_ok=True)
    out_tables.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Input paths
    # ------------------------------------------------------------------
    master_path = station_inventory_dir / "pr_station_inventory_master.parquet"
    ghcnh_master_path = (
        noaa_interim_dir
        / "ghcnh_station_inventory"
        / "pr_ghcnh_station_inventory_master.parquet"
    )
    isd_inventory_path = data_raw / "noaa" / "isd" / "metadata" / "isd-inventory.csv"
    ghcnd_inventory_path = data_raw / "noaa" / "ghcn" / "metadata" / "ghcnd-inventory.txt"

    if not master_path.exists():
        raise FileNotFoundError(
            f"Missing master inventory: {master_path}\n"
            "Build the NOAA station inventory stage first."
        )

    if not ghcnh_master_path.exists():
        raise FileNotFoundError(
            f"Missing GHCNh master inventory: {ghcnh_master_path}\n"
            "Build the GHCNh station inventory stage first."
        )

    if not isd_inventory_path.exists():
        raise FileNotFoundError(
            f"Missing raw ISD inventory: {isd_inventory_path}"
        )

    if not ghcnd_inventory_path.exists():
        raise FileNotFoundError(
            f"Missing raw GHCND inventory: {ghcnd_inventory_path}"
        )

    # ------------------------------------------------------------------
    # Load inputs
    # ------------------------------------------------------------------
    print("Loading input tables...")
    master = pd.read_parquet(master_path)
    ghcnh_master = pd.read_parquet(ghcnh_master_path)
    isd_inventory = load_isd_inventory(isd_inventory_path)
    ghcnd_inventory = load_ghcnd_inventory(ghcnd_inventory_path)

    include_daily_wind = bool(getattr(cfg, "VALIDATION_INCLUDE_DAILY_WIND", False))

    print(f"  master rows:           {len(master):,}")
    print(f"  ghcnh master rows:     {len(ghcnh_master):,}")
    print(f"  ghcnd inventory rows:  {len(ghcnd_inventory):,}")
    print(f"  isd inventory rows:    {len(isd_inventory):,}")
    print(f"  include daily wind:    {include_daily_wind}")

    # ------------------------------------------------------------------
    # Build coverage products
    # ------------------------------------------------------------------
    print("Building NOAA variable coverage products...")

    long_df = build_noaa_variable_coverage_long(
        master_inventory=master,
        ghcnd_inventory=ghcnd_inventory,
        isd_inventory=isd_inventory,
    )

    wide_df = build_noaa_variable_coverage_wide(long_df)
    summary_df = summarize_variable_coverage(long_df)

    mixed_long_df = build_mixed_resolution_validation_long(
        ghcnh_master_inventory=ghcnh_master,
        ghcnd_master_inventory=master,
        ghcnd_inventory=ghcnd_inventory,
        include_daily_wind=include_daily_wind,
    )
    mixed_wide_df = build_mixed_resolution_validation_wide(mixed_long_df)
    mixed_summary_df = summarize_mixed_resolution_validation(mixed_long_df)

    hourly_selector_wide_df = mixed_wide_df[
        mixed_wide_df["validation_tier"] == "hourly_core"
    ].copy()
    daily_selector_wide_df = mixed_wide_df[
        mixed_wide_df["validation_tier"] == "daily_broad"
    ].copy()

    # ------------------------------------------------------------------
    # Output paths
    # ------------------------------------------------------------------
    long_parquet = coverage_dir / "pr_noaa_variable_coverage_long.parquet"
    long_csv = coverage_dir / "pr_noaa_variable_coverage_long.csv"

    wide_parquet = coverage_dir / "pr_noaa_variable_coverage_wide.parquet"
    wide_csv = coverage_dir / "pr_noaa_variable_coverage_wide.csv"

    summary_csv = out_tables / "pr_noaa_variable_coverage_summary.csv"

    mixed_long_parquet = coverage_dir / "pr_mixed_resolution_validation_long.parquet"
    mixed_long_csv = coverage_dir / "pr_mixed_resolution_validation_long.csv"

    mixed_wide_parquet = coverage_dir / "pr_mixed_resolution_validation_wide.parquet"
    mixed_wide_csv = coverage_dir / "pr_mixed_resolution_validation_wide.csv"

    hourly_selector_parquet = coverage_dir / "pr_hourly_validation_selectors_ghcnh.parquet"
    hourly_selector_csv = coverage_dir / "pr_hourly_validation_selectors_ghcnh.csv"

    daily_selector_parquet = coverage_dir / "pr_daily_validation_selectors_ghcnd.parquet"
    daily_selector_csv = coverage_dir / "pr_daily_validation_selectors_ghcnd.csv"

    mixed_summary_csv = out_tables / "pr_mixed_resolution_validation_summary.csv"

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    print("Writing outputs...")

    long_df.to_parquet(long_parquet, index=False)
    long_df.to_csv(long_csv, index=False)

    wide_df.to_parquet(wide_parquet, index=False)
    wide_df.to_csv(wide_csv, index=False)

    summary_df.to_csv(summary_csv, index=False)

    mixed_long_df.to_parquet(mixed_long_parquet, index=False)
    mixed_long_df.to_csv(mixed_long_csv, index=False)

    mixed_wide_df.to_parquet(mixed_wide_parquet, index=False)
    mixed_wide_df.to_csv(mixed_wide_csv, index=False)

    hourly_selector_wide_df.to_parquet(hourly_selector_parquet, index=False)
    hourly_selector_wide_df.to_csv(hourly_selector_csv, index=False)

    daily_selector_wide_df.to_parquet(daily_selector_parquet, index=False)
    daily_selector_wide_df.to_csv(daily_selector_csv, index=False)

    mixed_summary_df.to_csv(mixed_summary_csv, index=False)

    # ------------------------------------------------------------------
    # Console QC
    # ------------------------------------------------------------------
    print("\nDone.")
    print(f"  Long coverage parquet: {long_parquet}")
    print(f"  Long coverage csv:     {long_csv}")
    print(f"  Wide matrix parquet:   {wide_parquet}")
    print(f"  Wide matrix csv:       {wide_csv}")
    print(f"  Summary csv:           {summary_csv}")
    print(f"  Mixed long parquet:    {mixed_long_parquet}")
    print(f"  Mixed long csv:        {mixed_long_csv}")
    print(f"  Mixed wide parquet:    {mixed_wide_parquet}")
    print(f"  Mixed wide csv:        {mixed_wide_csv}")
    print(f"  Hourly selectors:      {hourly_selector_csv}")
    print(f"  Daily selectors:       {daily_selector_csv}")
    print(f"  Mixed summary csv:     {mixed_summary_csv}")

    print("\nQuick QC summary:")
    if summary_df.empty:
        print("  WARNING: summary table is empty.")
    else:
        print(summary_df.to_string(index=False))

    print("\nStation counts by source in legacy wide matrix:")
    if wide_df.empty:
        print("  WARNING: wide matrix is empty.")
    else:
        counts = (
            wide_df.groupby("source", as_index=False)
            .agg(n_stations=("station_id", "nunique"))
            .sort_values("source", kind="stable")
        )
        print(counts.to_string(index=False))

    print("\nMixed-resolution selector summary:")
    if mixed_summary_df.empty:
        print("  WARNING: mixed-resolution summary table is empty.")
    else:
        print(mixed_summary_df.to_string(index=False))

    print("\nSelector station counts by tier:")
    if mixed_wide_df.empty:
        print("  WARNING: mixed-resolution selector table is empty.")
    else:
        tier_counts = (
            mixed_wide_df.groupby(["source", "validation_tier"], as_index=False)
            .agg(n_stations=("station_id", "nunique"))
            .sort_values(["source", "validation_tier"], kind="stable")
        )
        print(tier_counts.to_string(index=False))


if __name__ == "__main__":
    main()
