#!/usr/bin/env python3
"""
scripts/diagnostics/ghcnh/check_ghcnh_hourly_raw_2017_maria_window_pr.py
=============================================================================

Diagnose whether local raw GHCNh Parquet files for Puerto Rico contain records
inside the Hurricane Maria analysis window.

Purpose
-------
This is a raw-data diagnostic only. It answers the first question in the audit:

    raw 2017 exists -> raw Hurricane Maria window exists?

The script intentionally does not inspect the clean core. If raw data are absent
inside the selected Maria window, the audit should stop at the raw-data stage.
If raw data are present, a separate follow-up diagnostic can compare raw data
against the clean core and cleaning-decision logs.

Default window
--------------
Maria analysis window:
    2017-09-01 00:00 <= DATE < 2017-11-01 00:00

Comparison months:
    2017-08, 2017-09, 2017-10, 2017-11

Inputs
------
Default raw Parquet directory:
    data_raw/noaa/ghcnh/hourly/by_year/2017/parquet

Outputs
-------
Default output directory:
    outputs/diagnostics/ghcnh_hourly/raw_2017_maria_window

Files written:
    ghcnh_raw_2017_file_inventory.csv
    ghcnh_raw_2017_monthly_counts.csv
    ghcnh_raw_2017_station_variable_counts.csv
    ghcnh_raw_2017_maria_window_summary.md

This script does not modify raw data, interim data, or project products.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


RAW_VARIABLES = {
    "temperature": "temperature",
    "dew_point_temperature": "dew_point_temperature",
    "relative_humidity": "relative_humidity",
    "wind_speed": "wind_speed",
    "station_level_pressure": "station_level_pressure",
    "precipitation": "precipitation",
}

MONTH_WINDOWS = {
    "2017-08": ("2017-08-01", "2017-09-01"),
    "2017-09": ("2017-09-01", "2017-10-01"),
    "2017-10": ("2017-10-01", "2017-11-01"),
    "2017-11": ("2017-11-01", "2017-12-01"),
}


@dataclass(frozen=True)
class FileInventoryRow:
    raw_file: str
    station_id: str | None
    station_name: str | None
    n_rows_total: int
    n_rows_with_parseable_date: int
    first_date: str | None
    last_date: str | None
    n_rows_2017_08: int
    n_rows_2017_09: int
    n_rows_2017_10: int
    n_rows_2017_11: int
    n_rows_maria_window: int
    has_maria_window_rows: bool
    read_status: str
    error_message: str | None


@dataclass(frozen=True)
class StationVariableCountRow:
    raw_file: str
    station_id: str | None
    station_name: str | None
    variable: str
    column_present: bool
    n_numeric_total: int
    n_numeric_2017_08: int
    n_numeric_2017_09: int
    n_numeric_2017_10: int
    n_numeric_2017_11: int
    n_numeric_maria_window: int


@dataclass(frozen=True)
class MonthlyCountRow:
    month: str
    n_files_with_rows: int
    n_stations_with_rows: int
    n_raw_rows: int
    temperature_numeric: int
    dew_point_temperature_numeric: int
    relative_humidity_numeric: int
    wind_speed_numeric: int
    station_level_pressure_numeric: int
    precipitation_numeric: int


def find_repo_root(start: Path) -> Path:
    """
    Locate the repository root by searching for .git upward from start.
    If .git is not found, use the current working directory.
    """
    start = start.resolve()
    candidates = [start, *start.parents]
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return Path.cwd().resolve()


def parse_station_id_from_filename(path: Path) -> str | None:
    """Extract station ID from filenames like GHCNh_RQC00660061_2017.parquet."""
    match = re.match(r"^GHCNh_(?P<station>.+)_2017\.parquet$", path.name)
    if not match:
        return None
    return match.group("station")


def first_non_empty(df: pd.DataFrame, column: str) -> str | None:
    """Return the first non-empty value from a column, if available."""
    if column not in df.columns:
        return None
    values = df[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return None
    return str(values.iloc[0])


def parse_dates(df: pd.DataFrame) -> pd.Series:
    """Parse the GHCNh DATE column without changing time zones."""
    if "DATE" not in df.columns:
        return pd.Series(pd.NaT, index=df.index)
    return pd.to_datetime(df["DATE"], errors="coerce")


def numeric_count(df: pd.DataFrame, variable: str, mask: pd.Series | None = None) -> int:
    """Count parseable numeric values for one raw variable."""
    if variable not in df.columns:
        return 0
    values = pd.to_numeric(df[variable], errors="coerce")
    if mask is not None:
        values = values.loc[mask]
    return int(values.notna().sum())


def window_mask(dt: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Inclusive-start/exclusive-end time mask."""
    return dt.notna() & (dt >= start) & (dt < end)


def count_rows_in_window(dt: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Count rows with parseable DATE inside a time window."""
    return int(window_mask(dt, start, end).sum())


def safe_iso(value: Any) -> str | None:
    """Convert a timestamp-like value to ISO string, preserving None for NaT."""
    if pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def inspect_one_file(
    path: Path,
    *,
    maria_start: pd.Timestamp,
    maria_end: pd.Timestamp,
) -> tuple[FileInventoryRow, list[StationVariableCountRow], dict[str, dict[str, int | set[str]]]]:
    """
    Inspect one raw Parquet file and return inventory, variable counts, and
    monthly contribution dictionaries.
    """
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 - diagnostic should record failures, not crash immediately.
        file_row = FileInventoryRow(
            raw_file=str(path),
            station_id=parse_station_id_from_filename(path),
            station_name=None,
            n_rows_total=0,
            n_rows_with_parseable_date=0,
            first_date=None,
            last_date=None,
            n_rows_2017_08=0,
            n_rows_2017_09=0,
            n_rows_2017_10=0,
            n_rows_2017_11=0,
            n_rows_maria_window=0,
            has_maria_window_rows=False,
            read_status="failed",
            error_message=str(exc),
        )
        return file_row, [], {}

    dt = parse_dates(df)
    station_id = first_non_empty(df, "STATION") or parse_station_id_from_filename(path)
    station_name = first_non_empty(df, "Station_name")

    month_masks: dict[str, pd.Series] = {}
    month_row_counts: dict[str, int] = {}
    for month, (start_s, end_s) in MONTH_WINDOWS.items():
        mask = window_mask(dt, pd.Timestamp(start_s), pd.Timestamp(end_s))
        month_masks[month] = mask
        month_row_counts[month] = int(mask.sum())

    maria_mask = window_mask(dt, maria_start, maria_end)

    parseable_dt = dt.dropna()
    file_row = FileInventoryRow(
        raw_file=str(path),
        station_id=station_id,
        station_name=station_name,
        n_rows_total=int(len(df)),
        n_rows_with_parseable_date=int(dt.notna().sum()),
        first_date=safe_iso(parseable_dt.min()) if not parseable_dt.empty else None,
        last_date=safe_iso(parseable_dt.max()) if not parseable_dt.empty else None,
        n_rows_2017_08=month_row_counts["2017-08"],
        n_rows_2017_09=month_row_counts["2017-09"],
        n_rows_2017_10=month_row_counts["2017-10"],
        n_rows_2017_11=month_row_counts["2017-11"],
        n_rows_maria_window=int(maria_mask.sum()),
        has_maria_window_rows=bool(maria_mask.sum() > 0),
        read_status="ok",
        error_message=None,
    )

    variable_rows: list[StationVariableCountRow] = []
    for variable in RAW_VARIABLES:
        variable_rows.append(
            StationVariableCountRow(
                raw_file=str(path),
                station_id=station_id,
                station_name=station_name,
                variable=variable,
                column_present=variable in df.columns,
                n_numeric_total=numeric_count(df, variable),
                n_numeric_2017_08=numeric_count(df, variable, month_masks["2017-08"]),
                n_numeric_2017_09=numeric_count(df, variable, month_masks["2017-09"]),
                n_numeric_2017_10=numeric_count(df, variable, month_masks["2017-10"]),
                n_numeric_2017_11=numeric_count(df, variable, month_masks["2017-11"]),
                n_numeric_maria_window=numeric_count(df, variable, maria_mask),
            )
        )

    monthly_contrib: dict[str, dict[str, int | set[str]]] = {}
    for month, mask in month_masks.items():
        row_count = int(mask.sum())
        station_set: set[str] = set()
        if row_count > 0 and station_id is not None:
            station_set.add(station_id)

        month_info: dict[str, int | set[str]] = {
            "n_files_with_rows": 1 if row_count > 0 else 0,
            "n_raw_rows": row_count,
            "stations": station_set,
        }
        for variable in RAW_VARIABLES:
            month_info[f"{variable}_numeric"] = numeric_count(df, variable, mask)
        monthly_contrib[month] = month_info

    return file_row, variable_rows, monthly_contrib


def combine_monthly_counts(monthly_parts: list[dict[str, dict[str, int | set[str]]]]) -> pd.DataFrame:
    """Combine per-file monthly counts into one summary table."""
    rows: list[MonthlyCountRow] = []

    for month in MONTH_WINDOWS:
        n_files_with_rows = 0
        n_raw_rows = 0
        stations: set[str] = set()
        variable_counts = {f"{variable}_numeric": 0 for variable in RAW_VARIABLES}

        for part in monthly_parts:
            if month not in part:
                continue
            info = part[month]
            n_files_with_rows += int(info.get("n_files_with_rows", 0))
            n_raw_rows += int(info.get("n_raw_rows", 0))
            stations.update(info.get("stations", set()))  # type: ignore[arg-type]
            for variable in RAW_VARIABLES:
                key = f"{variable}_numeric"
                variable_counts[key] += int(info.get(key, 0))

        rows.append(
            MonthlyCountRow(
                month=month,
                n_files_with_rows=n_files_with_rows,
                n_stations_with_rows=len(stations),
                n_raw_rows=n_raw_rows,
                temperature_numeric=variable_counts["temperature_numeric"],
                dew_point_temperature_numeric=variable_counts["dew_point_temperature_numeric"],
                relative_humidity_numeric=variable_counts["relative_humidity_numeric"],
                wind_speed_numeric=variable_counts["wind_speed_numeric"],
                station_level_pressure_numeric=variable_counts["station_level_pressure_numeric"],
                precipitation_numeric=variable_counts["precipitation_numeric"],
            )
        )

    return pd.DataFrame([row.__dict__ for row in rows])


def write_summary_markdown(
    *,
    output_path: Path,
    raw_parquet_dir: Path,
    file_inventory: pd.DataFrame,
    monthly_counts: pd.DataFrame,
    station_variable_counts: pd.DataFrame,
    maria_start: pd.Timestamp,
    maria_end: pd.Timestamp,
) -> None:
    """Write a compact human-readable diagnostic summary."""
    n_files = int(len(file_inventory))
    n_files_ok = int((file_inventory["read_status"] == "ok").sum()) if not file_inventory.empty else 0
    n_files_failed = n_files - n_files_ok
    maria_rows = int(file_inventory["n_rows_maria_window"].sum()) if not file_inventory.empty else 0
    maria_files = int(file_inventory["has_maria_window_rows"].sum()) if not file_inventory.empty else 0

    maria_var = (
        station_variable_counts.groupby("variable", as_index=False)["n_numeric_maria_window"].sum()
        if not station_variable_counts.empty
        else pd.DataFrame(columns=["variable", "n_numeric_maria_window"])
    )

    if maria_rows == 0:
        conclusion = (
            "No raw rows were found in the Hurricane Maria analysis window. "
            "Stop at the raw-data stage before auditing the clean core."
        )
    else:
        conclusion = (
            "Raw rows were found in the Hurricane Maria analysis window. "
            "A follow-up diagnostic should compare raw records against the clean core "
            "and cleaning-decision logs."
        )

    lines: list[str] = []
    lines.append("# GHCNh raw 2017 Hurricane Maria window diagnostic")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("This diagnostic inspects local raw GHCNh Parquet files only.")
    lines.append("")
    lines.append(f"- Raw Parquet directory: `{raw_parquet_dir}`")
    lines.append(f"- Maria analysis window: `{maria_start}` <= DATE < `{maria_end}`")
    lines.append("- Comparison months: 2017-08, 2017-09, 2017-10, 2017-11")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append(f"- Local raw Parquet files inspected: {n_files}")
    lines.append(f"- Files read successfully: {n_files_ok}")
    lines.append(f"- Files with read errors: {n_files_failed}")
    lines.append(f"- Files with rows in Maria window: {maria_files}")
    lines.append(f"- Raw rows in Maria window: {maria_rows}")
    lines.append("")
    lines.append(f"**Conclusion:** {conclusion}")
    lines.append("")
    lines.append("## Monthly row counts")
    lines.append("")
    if monthly_counts.empty:
        lines.append("No monthly counts were generated.")
    else:
        lines.append(monthly_counts.to_string(index=False))
    lines.append("")
    lines.append("## Numeric variable counts inside Maria window")
    lines.append("")
    if maria_var.empty:
        lines.append("No variable counts were generated.")
    else:
        lines.append(maria_var.to_string(index=False))
    lines.append("")
    lines.append("## Files written")
    lines.append("")
    lines.append("- `ghcnh_raw_2017_file_inventory.csv`")
    lines.append("- `ghcnh_raw_2017_monthly_counts.csv`")
    lines.append("- `ghcnh_raw_2017_station_variable_counts.csv`")
    lines.append("- `ghcnh_raw_2017_maria_window_summary.md`")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether local raw GHCNh 2017 Parquet files contain records in the Hurricane Maria analysis window."
    )
    parser.add_argument(
        "--raw-parquet-dir",
        default="data_raw/noaa/ghcnh/hourly/by_year/2017/parquet",
        help="Directory containing local raw GHCNh 2017 Parquet files.",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/diagnostics/ghcnh_hourly/raw_2017_maria_window",
        help="Output directory for diagnostic tables and markdown summary.",
    )
    parser.add_argument(
        "--maria-start",
        default="2017-09-01",
        help="Inclusive start date for the Maria analysis window.",
    )
    parser.add_argument(
        "--maria-end",
        default="2017-11-01",
        help="Exclusive end date for the Maria analysis window.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path.cwd())

    raw_parquet_dir = Path(args.raw_parquet_dir)
    if not raw_parquet_dir.is_absolute():
        raw_parquet_dir = repo_root / raw_parquet_dir

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = repo_root / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    maria_start = pd.Timestamp(args.maria_start)
    maria_end = pd.Timestamp(args.maria_end)
    if maria_end <= maria_start:
        raise ValueError("--maria-end must be later than --maria-start")

    files = sorted(raw_parquet_dir.glob("GHCNh_*_2017.parquet"))

    print("GHCNh raw 2017 Hurricane Maria window diagnostic")
    print(f"Repository root: {repo_root}")
    print(f"Raw Parquet directory: {raw_parquet_dir}")
    print(f"Output directory: {outdir}")
    print(f"Maria analysis window: {maria_start} <= DATE < {maria_end}")
    print(f"Local raw 2017 Parquet files found: {len(files)}")

    file_rows: list[FileInventoryRow] = []
    variable_rows: list[StationVariableCountRow] = []
    monthly_parts: list[dict[str, dict[str, int | set[str]]]] = []

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] Inspecting {path.name}", flush=True)
        file_row, file_variable_rows, monthly_contrib = inspect_one_file(
            path,
            maria_start=maria_start,
            maria_end=maria_end,
        )
        file_rows.append(file_row)
        variable_rows.extend(file_variable_rows)
        if monthly_contrib:
            monthly_parts.append(monthly_contrib)

    file_inventory = pd.DataFrame([row.__dict__ for row in file_rows])
    station_variable_counts = pd.DataFrame([row.__dict__ for row in variable_rows])
    monthly_counts = combine_monthly_counts(monthly_parts)

    file_inventory_path = outdir / "ghcnh_raw_2017_file_inventory.csv"
    monthly_counts_path = outdir / "ghcnh_raw_2017_monthly_counts.csv"
    station_variable_counts_path = outdir / "ghcnh_raw_2017_station_variable_counts.csv"
    summary_path = outdir / "ghcnh_raw_2017_maria_window_summary.md"

    file_inventory.to_csv(file_inventory_path, index=False)
    monthly_counts.to_csv(monthly_counts_path, index=False)
    station_variable_counts.to_csv(station_variable_counts_path, index=False)

    write_summary_markdown(
        output_path=summary_path,
        raw_parquet_dir=raw_parquet_dir,
        file_inventory=file_inventory,
        monthly_counts=monthly_counts,
        station_variable_counts=station_variable_counts,
        maria_start=maria_start,
        maria_end=maria_end,
    )

    maria_rows = int(file_inventory["n_rows_maria_window"].sum()) if not file_inventory.empty else 0
    maria_files = int(file_inventory["has_maria_window_rows"].sum()) if not file_inventory.empty else 0

    print("Diagnostic complete.")
    print(f"Files with rows in Maria window: {maria_files}")
    print(f"Raw rows in Maria window: {maria_rows}")
    print("Outputs:")
    print(f"  {file_inventory_path.relative_to(repo_root)}")
    print(f"  {monthly_counts_path.relative_to(repo_root)}")
    print(f"  {station_variable_counts_path.relative_to(repo_root)}")
    print(f"  {summary_path.relative_to(repo_root)}")

    if maria_rows == 0:
        print("No raw rows found in the Maria window. Stop at raw-data stage.")
    else:
        print("Raw rows found in the Maria window. Next step: compare raw vs clean core if needed.")


if __name__ == "__main__":
    main()
