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
    build_noaa_variable_coverage_long,
    build_noaa_variable_coverage_wide,
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
    isd_inventory_path = data_raw / "noaa" / "isd" / "metadata" / "isd-inventory.csv"
    ghcnd_inventory_path = data_raw / "noaa" / "ghcn" / "metadata" / "ghcnd-inventory.txt"

    if not master_path.exists():
        raise FileNotFoundError(
            f"Missing master inventory: {master_path}\n"
            "Build the NOAA station inventory stage first."
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
    isd_inventory = load_isd_inventory(isd_inventory_path)
    ghcnd_inventory = load_ghcnd_inventory(ghcnd_inventory_path)

    print(f"  master rows:          {len(master):,}")
    print(f"  ghcnd inventory rows: {len(ghcnd_inventory):,}")
    print(f"  isd inventory rows:   {len(isd_inventory):,}")

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

    # ------------------------------------------------------------------
    # Output paths
    # ------------------------------------------------------------------
    long_parquet = coverage_dir / "pr_noaa_variable_coverage_long.parquet"
    long_csv = coverage_dir / "pr_noaa_variable_coverage_long.csv"

    wide_parquet = coverage_dir / "pr_noaa_variable_coverage_wide.parquet"
    wide_csv = coverage_dir / "pr_noaa_variable_coverage_wide.csv"

    summary_csv = out_tables / "pr_noaa_variable_coverage_summary.csv"

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    print("Writing outputs...")

    long_df.to_parquet(long_parquet, index=False)
    long_df.to_csv(long_csv, index=False)

    wide_df.to_parquet(wide_parquet, index=False)
    wide_df.to_csv(wide_csv, index=False)

    summary_df.to_csv(summary_csv, index=False)

    # ------------------------------------------------------------------
    # Console QC
    # ------------------------------------------------------------------
    print("\nDone.")
    print(f"  Long coverage parquet: {long_parquet}")
    print(f"  Long coverage csv:     {long_csv}")
    print(f"  Wide matrix parquet:   {wide_parquet}")
    print(f"  Wide matrix csv:       {wide_csv}")
    print(f"  Summary csv:           {summary_csv}")

    print("\nQuick QC summary:")
    if summary_df.empty:
        print("  WARNING: summary table is empty.")
    else:
        print(summary_df.to_string(index=False))

    print("\nStation counts by source in wide matrix:")
    if wide_df.empty:
        print("  WARNING: wide matrix is empty.")
    else:
        counts = (
            wide_df.groupby("source", as_index=False)
            .agg(n_stations=("station_id", "nunique"))
            .sort_values("source", kind="stable")
        )
        print(counts.to_string(index=False))


if __name__ == "__main__":
    main()
