#!/usr/bin/env python3
"""
scripts/summarize_noaa_station_coverage_pr.py
=============================================

Write a short human-readable text summary for the Puerto Rico station
inventory products.

This summary is metadata-based only. It does NOT yet evaluate true
variable-level hourly completeness.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pr_ngvla.config import OUT_STATION_INVENTORY_TABLES


def main() -> None:
    """
    Read the inventory summary CSV and write a short text summary.
    """
    summary_csv = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_summary.csv"
    summary_txt = OUT_STATION_INVENTORY_TABLES / "pr_station_inventory_summary.txt"

    df = pd.read_csv(summary_csv)

    lines = []
    lines.append("Puerto Rico station inventory summary")
    lines.append("=" * 50)
    lines.append("")

    for subset in ["all_in_bbox", "pr_territory", "master"]:
        subset_df = df[df["subset"] == subset].copy()

        if subset_df.empty:
            continue

        lines.append(f"Subset: {subset}")
        lines.append("-" * 50)

        for _, row in subset_df.iterrows():
            lines.append(
                f"  {row['source']}: "
                f"n_total={row['n_total']}, "
                f"min_begin_year={row['min_begin_year']}, "
                f"max_end_year={row['max_end_year']}"
            )

        lines.append("")

    summary_txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {summary_txt}")


if __name__ == "__main__":
    main()
