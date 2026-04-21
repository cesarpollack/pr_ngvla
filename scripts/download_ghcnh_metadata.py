#!/usr/bin/env python3
"""
scripts/download_ghcnh_metadata.py
==================================

Download NOAA official GHCNh metadata files needed for the Puerto Rico hourly
station-inventory stage.

Files
-----
- ghcnh-station-list.csv
- ghcnh-inventory.txt
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

import pr_ngvla.config as cfg


GHCNH_STATION_LIST_URL = (
    "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/"
    "ghcnh-station-list.csv"
)
GHCNH_INVENTORY_URL = (
    "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/"
    "ghcnh-inventory.txt"
)


def main() -> None:
    data_raw = Path(getattr(cfg, "DATA_RAW", "data_raw"))
    out_dir = data_raw / "noaa" / "ghcnh" / "metadata"
    out_dir.mkdir(parents=True, exist_ok=True)

    station_list_path = out_dir / "ghcnh-station-list.csv"
    inventory_path = out_dir / "ghcnh-inventory.txt"

    print("Downloading GHCNh metadata...")
    print(f"  {GHCNH_STATION_LIST_URL}")
    urlretrieve(GHCNH_STATION_LIST_URL, station_list_path)

    print(f"  {GHCNH_INVENTORY_URL}")
    urlretrieve(GHCNH_INVENTORY_URL, inventory_path)

    print("\nDone.")
    print(f"  Station list: {station_list_path}")
    print(f"  Inventory:    {inventory_path}")


if __name__ == "__main__":
    main()
