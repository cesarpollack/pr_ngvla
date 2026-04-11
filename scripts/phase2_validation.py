#!/usr/bin/env python3
"""
scripts/phase2_validation.py
=============================
Phase 2 — ERA5-Land vs NOAA ISD validation (orquestador).

Usage
-----
    python scripts/phase2_validation.py
    python scripts/phase2_validation.py --no-maria

Options
-------
    --no-maria  Include Hurricane Maria months (default: excluded)
"""

import argparse
import pandas as pd

from pr_ngvla.config import NOAA_ISD_DIR, ERA5_HOURLY_DIR
from pr_ngvla.analysis.validation import (
    validate_station,
    save_validation_table,
)
import xarray as xr

from pr_ngvla.analysis.validation import build_land_mask

def get_era5_grid() -> tuple:
    """Load ERA5 lat/lon grid from any hourly file."""
    f = sorted(ERA5_HOURLY_DIR.glob("era5land_hourly_t2m_d2m_PR_2004_01.nc"))[0]
    ds = xr.open_dataset(f)
    lats = ds["latitude"].values
    lons = ds["longitude"].values
    ds.close()
    return lats, lons

era5_lats, era5_lons = get_era5_grid()
land_mask = build_land_mask(era5_lats, era5_lons)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2 — ERA5 vs NOAA ISD validation"
    )
    parser.add_argument(
        "--no-maria",
        action="store_true",
        default=False,
        help="Include Hurricane Maria months (default: excluded)",
    )
    return parser.parse_args()


def main() -> None:
    args       = parse_args()
    exclude_maria = not args.no_maria

    print("=" * 60)
    print("Phase 2 — ERA5-Land vs NOAA ISD Validation")
    print(f"Maria exclusion: {exclude_maria}")
    print("=" * 60)

    # Load ERA5 grid once
    era5_lats, era5_lons = get_era5_grid()
    print(f"[INFO] ERA5 grid: {len(era5_lats)} lat × {len(era5_lons)} lon\n")

    # Station list from catalog
    catalog = pd.read_csv(NOAA_ISD_DIR / "station_catalog.csv")
    catalog.columns = [c.strip().upper().replace(" ", "_")
                       for c in catalog.columns]

    all_results = []

    for _, row in catalog.iterrows():
        station_id   = row["STATION_ID"]
        station_name = row["STATION_NAME"].replace(" ", "_")
        lat          = float(row["LAT"])
        lon          = float(row["LON"])

        # Find station file
        matches = sorted(NOAA_ISD_DIR.glob(f"{station_id}_*.csv"))
        if not matches:
            print(f"[WARN] No file found for {station_id} — skipping")
            continue

        station_file = matches[0]
        print(f"\n--- Station: {station_name} ({station_id}) ---")
        print(f"    Location: {lat:.3f}°N, {lon:.3f}°W")

        df = validate_station(
            station_id   = station_id,
            station_name = station_name,
            lat          = lat,
            lon          = lon,
            station_file = station_file,
            era5_lats    = era5_lats,
            era5_lons    = era5_lons,
            exclude_maria= exclude_maria,
            land_mask    = land_mask,
        )

        if not df.empty:
            all_results.append(df)

    if not all_results:
        print("[ERROR] No results generated.")
        return

    summary = pd.concat(all_results, ignore_index=True)

    # Print summary table
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    save_validation_table(summary)
    print("\n[DONE] Validation complete.")


if __name__ == "__main__":
    main()
