#!/usr/bin/env python3
"""
scripts/build_noaa_station_inventory_pr.py
==========================================

Build the first-pass Puerto Rico NOAA station inventory.

What this script does
---------------------
1. Load authoritative global NOAA metadata:
   - ISD / Global Hourly station history
   - GHCN-Daily station metadata
   - GHCN-Daily inventory metadata

2. Standardize those source-specific metadata tables into a common schema.

3. Apply the project-standard Puerto Rico bounding box.

4. Flag and filter stations that overlap the study period 2004-01-01 to 2023-12-31.

5. Write two inventory tables:
   - all stations inside the Puerto Rico bbox
   - the subset inside the bbox that overlaps the study period

6. Write one compact summary table.

Design rules
------------
- This script is orchestration only.
- Source-specific parsing lives in src/pr_ngvla/data/noaa.py
- Paths and study constants live in src/pr_ngvla/config.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pr_ngvla.config import (
    NOAA_GHCN_INVENTORY_TXT,
    NOAA_GHCN_STATIONS_TXT,
    NOAA_ISD_HISTORY_CSV,
    NOAA_STATION_INVENTORY_DIR,
    OUT_STATION_INVENTORY_TABLES,
    PR_BBOX,
    STUDY_END_DATE,
    STUDY_START_DATE,
)
from pr_ngvla.data.noaa import (
    build_master_station_inventory,
    build_station_inventory_summary_by_subset,
    filter_candidate_pr_stations,
    filter_overlap_stations,
    filter_pr_territory_stations,
    flag_stations_in_bbox,
    flag_stations_overlapping_period,
    load_ghcnd_inventory,
    load_ghcnd_stations,
    load_isd_history,
    standardize_ghcnd_stations,
    standardize_isd_history,
)


def _ensure_directory(path: Path) -> None:
    """
    Create a directory if it does not already exist.
    """
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """
    Main entry point for the Puerto Rico station inventory build.
    """
    # -----------------------------------------------------------------------
    # Ensure output directories exist
    # -----------------------------------------------------------------------
    _ensure_directory(NOAA_STATION_INVENTORY_DIR)
    _ensure_directory(OUT_STATION_INVENTORY_TABLES)

    # -----------------------------------------------------------------------
    # Load authoritative global metadata
    # -----------------------------------------------------------------------
    isd_history_raw = load_isd_history(NOAA_ISD_HISTORY_CSV)
    ghcnd_stations_raw = load_ghcnd_stations(NOAA_GHCN_STATIONS_TXT)
    ghcnd_inventory_raw = load_ghcnd_inventory(NOAA_GHCN_INVENTORY_TXT)

    # -----------------------------------------------------------------------
    # Standardize each source into the common inventory schema
    # -----------------------------------------------------------------------
    isd_standard = standardize_isd_history(isd_history_raw)
    ghcnd_standard = standardize_ghcnd_stations(
        ghcnd_stations_raw,
        ghcnd_inventory_raw,
    )

    # -----------------------------------------------------------------------
    # Build the combined global metadata inventory
    # -----------------------------------------------------------------------
    inventory_global = build_master_station_inventory(
        [isd_standard, ghcnd_standard]
    )

    # -----------------------------------------------------------------------
    # Apply project-standard Puerto Rico bbox and study-period flags
    # -----------------------------------------------------------------------
    south, west, north, east = PR_BBOX

    inventory_global = flag_stations_in_bbox(
        inventory_global,
        south=south,
        west=west,
        north=north,
        east=east,
    )

    inventory_global = flag_stations_overlapping_period(
        inventory_global,
        start_date=STUDY_START_DATE,
        end_date=STUDY_END_DATE,
    )

    # -----------------------------------------------------------------------
    # Build the first-pass Puerto Rico inventories
    # -----------------------------------------------------------------------

    inventory_pr_bbox = filter_candidate_pr_stations(inventory_global)

    # Stricter Puerto Rico territorial filter:
    # - removes obvious spillover admitted by the coarse bbox
    # - preserves Puerto Rico historical/island/coastal rows such as
    #   Mona, Vieques, and Culebra
    inventory_pr_territory = filter_pr_territory_stations(inventory_pr_bbox)

    # Final first-pass validation inventory:
    # strict territorial subset overlapping the study period
    inventory_pr_overlap = filter_overlap_stations(inventory_pr_territory)

    # -----------------------------------------------------------------------
    # Build summaries
    # -----------------------------------------------------------------------
    summary_inventory = build_station_inventory_summary_by_subset(
        df_all_in_bbox=inventory_pr_bbox,
        df_pr_territory=inventory_pr_territory,
        df_master=inventory_pr_overlap,
    )

    # -----------------------------------------------------------------------
    # Define output paths
    # -----------------------------------------------------------------------
    bbox_csv = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_all_in_bbox.csv"
    bbox_parquet = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_all_in_bbox.parquet"

    territory_csv = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_pr_territory.csv"
    territory_parquet = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_pr_territory.parquet"

    overlap_csv = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_master.csv"
    overlap_parquet = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_master.parquet"

    summary_csv = NOAA_STATION_INVENTORY_DIR / "pr_station_inventory_summary.csv"

    # Duplicate human-facing outputs under outputs/tables/...
    out_bbox_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_all_in_bbox.csv"
    out_territory_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_pr_territory.csv"
    out_overlap_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_master.csv"
    out_summary_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_summary.csv"

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    inventory_pr_bbox.to_csv(bbox_csv, index=False)
    inventory_pr_bbox.to_parquet(bbox_parquet, index=False)

    inventory_pr_territory.to_csv(territory_csv, index=False)
    inventory_pr_territory.to_parquet(territory_parquet, index=False)

    inventory_pr_overlap.to_csv(overlap_csv, index=False)
    inventory_pr_overlap.to_parquet(overlap_parquet, index=False)

    summary_inventory.to_csv(summary_csv, index=False)

    # Human-facing CSV copies for quick inspection
    inventory_pr_bbox.to_csv(out_bbox_csv, index=False)
    inventory_pr_territory.to_csv(out_territory_csv, index=False)
    inventory_pr_overlap.to_csv(out_overlap_csv, index=False)
    summary_inventory.to_csv(out_summary_csv, index=False)

    # -----------------------------------------------------------------------
    # Console summary
    # -----------------------------------------------------------------------
    print("\nNOAA station inventory build complete")
    print("-" * 60)
    print(f"Global ISD metadata rows:              {len(isd_standard):>8}")
    print(f"Global GHCND metadata rows:            {len(ghcnd_standard):>8}")
    print(f"Combined global inventory rows:        {len(inventory_global):>8}")
    print(f"Stations inside PR bbox:               {len(inventory_pr_bbox):>8}")
    print(f"Stations in strict PR territory:       {len(inventory_pr_territory):>8}")
    print(f"Stations overlapping 2004-2023:        {len(inventory_pr_overlap):>8}")
    print("-" * 60)
    print(f"Wrote: {bbox_csv}")
    print(f"Wrote: {bbox_parquet}")
    print(f"Wrote: {territory_csv}")
    print(f"Wrote: {territory_parquet}")
    print(f"Wrote: {overlap_csv}")
    print(f"Wrote: {overlap_parquet}")
    print(f"Wrote: {summary_csv}")
    print(f"Wrote: {out_bbox_csv}")
    print(f"Wrote: {out_territory_csv}")
    print(f"Wrote: {out_overlap_csv}")
    print(f"Wrote: {out_summary_csv}")


if __name__ == "__main__":
    main()
