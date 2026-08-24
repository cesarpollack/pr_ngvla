#!/usr/bin/env python3
"""
scripts/build_ghcnh_station_inventory_pr.py
===========================================

Build the Puerto Rico GHCNh metadata inventories:

- all_in_bbox
- pr_territory
- master (validation-ready, 2004-2023)

and write reproducible parquet/csv outputs.

This script is orchestration only.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import pr_ngvla.config as cfg
from pr_ngvla.data.ghcnh import (
    build_ghcnh_master_inventory,
    build_station_inventory_summary,
    filter_to_bbox,
    filter_to_pr_territory,
    load_ghcnh_inventory,
    load_ghcnh_station_list,
    standardize_ghcnh_station_list,
    summarize_ghcnh_inventory_period,
)
from pr_ngvla.data.spatial import load_vector_data


def _cfg_path(name: str, fallback: str) -> Path:
    return Path(getattr(cfg, name, fallback))


def main() -> None:
    data_raw = _cfg_path("DATA_RAW", "data_raw")
    data_interim = _cfg_path("DATA_INTERIM", "data_interim")

    south = float(getattr(cfg, "BBOX_SOUTH", 17.8))
    west = float(getattr(cfg, "BBOX_WEST", -68.0))
    north = float(getattr(cfg, "BBOX_NORTH", 18.6))
    east = float(getattr(cfg, "BBOX_EAST", -65.0))

    study_start = int(getattr(cfg, "STUDY_YEAR_START", 2004))
    study_end = int(getattr(cfg, "STUDY_YEAR_END", 2023))

    coast_shp = _cfg_path("COAST_SHP", "data_raw/shapefiles/GSHHS_h_L1.shp")
    muni_shp = _cfg_path("MUNI_SHP", "data_raw/shapefiles/tl_2024_us_county/tl_2024_us_county.shp")

    in_dir = data_raw / "noaa" / "ghcnh" / "metadata"
    out_dir = data_interim / "noaa" / "ghcnh_station_inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    station_list_path = in_dir / "ghcnh-station-list.csv"
    if not station_list_path.exists():
        station_list_path = in_dir / "ghcnh-station-list.txt"

    inventory_path = in_dir / "ghcnh-inventory.txt"

    if not station_list_path.exists():
        raise FileNotFoundError(f"Missing GHCNh station list: {station_list_path}")
    if not inventory_path.exists():
        raise FileNotFoundError(f"Missing GHCNh inventory: {inventory_path}")

    print("Loading GHCNh metadata...")
    station_list_raw = load_ghcnh_station_list(station_list_path)
    inventory_raw = load_ghcnh_inventory(inventory_path)

    stations = standardize_ghcnh_station_list(station_list_raw)
    inventory_summary = summarize_ghcnh_inventory_period(inventory_raw)

    print("Loading Puerto Rico vector data...")
    muni_clip, coast_union, muni_land_union = load_vector_data(coast_shp, muni_shp)

    print("Applying bbox filter...")
    all_in_bbox = filter_to_bbox(
        stations,
        south=south,
        west=west,
        north=north,
        east=east,
    )

    print("Applying strict territory filter...")
    pr_territory = filter_to_pr_territory(
        all_in_bbox,
        land_union=muni_land_union,
    )

    print("Building validation-ready master inventory...")
    master = build_ghcnh_master_inventory(
        pr_territory,
        inventory_summary,
        study_start_year=study_start,
        study_end_year=study_end,
    )

    summary = pd.concat(
        [
            pd.DataFrame([{"subset": "all_in_bbox"}]).join(build_station_inventory_summary(all_in_bbox)),
            pd.DataFrame([{"subset": "pr_territory"}]).join(build_station_inventory_summary(pr_territory)),
            pd.DataFrame([{"subset": "master"}]).join(build_station_inventory_summary(master)),
        ],
        ignore_index=True,
    )

    print("Writing outputs...")

    all_in_bbox.to_parquet(out_dir / "pr_ghcnh_station_inventory_all_in_bbox.parquet", index=False)
    all_in_bbox.to_csv(out_dir / "pr_ghcnh_station_inventory_all_in_bbox.csv", index=False)

    pr_territory.to_parquet(out_dir / "pr_ghcnh_station_inventory_pr_territory.parquet", index=False)
    pr_territory.to_csv(out_dir / "pr_ghcnh_station_inventory_pr_territory.csv", index=False)

    master.to_parquet(out_dir / "pr_ghcnh_station_inventory_master.parquet", index=False)
    master.to_csv(out_dir / "pr_ghcnh_station_inventory_master.csv", index=False)

    summary.to_csv(out_dir / "pr_ghcnh_station_inventory_summary.csv", index=False)

    print("\nDone.")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
