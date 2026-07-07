#!/usr/bin/env python3
"""
check_ghcnh_hourly_clean_core_readiness_pr.py

Classification:
    Diagnostic / exploratory project script.
    This script is not a report-production script. It verifies whether the
    existing GHCNh hourly clean-core dataset and coverage tables are ready to
    support reproducible observational products for the PR-ngVLA technical
    report.

Purpose:
    Inspect the GHCNh hourly clean-core dataset for Puerto Rico (2004-2023)
    and verify the presence, structure, temporal coverage, station coverage,
    variable coverage, and consistency of the no-threshold coverage tables.

Inputs:
    data_interim/noaa/ghcnh_hourly/clean_core/
        ghcnh_hourly_clean_core_2004_2023.parquet
        coverage_no_thresholds/
            ghcnh_hourly_clean_core_variable_summary_no_thresholds.csv
            ghcnh_hourly_clean_core_station_variable_summary_no_thresholds.csv
            ghcnh_hourly_clean_core_station_year_variable_coverage_no_thresholds.csv
            ghcnh_hourly_clean_core_station_year_coverage_wide_no_thresholds.csv

Outputs:
    outputs/diagnostics/ghcnh_hourly/
        ghcnh_hourly_clean_core_readiness_checks.csv
        ghcnh_hourly_clean_core_variable_readiness_summary.csv
        ghcnh_hourly_clean_core_temporal_readiness_summary.csv
        ghcnh_hourly_clean_core_readiness_report.md

Notes:
    - This script does not modify raw data or interim data.
    - This script does not generate report figures.
    - This script does not interpolate observational data.
    - This script does not touch ERA5/ERA5-Land products.
    - It is intended to be run before report-production scripts.
    - It avoids optional Markdown dependencies such as tabulate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_PERIOD_START = 2004
PROJECT_PERIOD_END = 2023

VARIABLE_COLUMNS = [
    "temperature_c",
    "dew_point_temperature_c",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "station_level_pressure_hpa",
    "precipitation_mm",
]

REQUIRED_COLUMNS = [
    "station_id",
    "station_name",
    "lat",
    "lon",
    "elevation_m",
    "datetime_hour",
    "year",
    "month",
    "day",
    "hour",
    "n_raw_records_in_hour",
    *VARIABLE_COLUMNS,
]


@dataclass
class CheckResult:
    check: str
    status: str
    details: str


def find_repo_root() -> Path:
    """Find the repository root from this script location or the current directory."""
    candidates: list[Path] = []

    try:
        here = Path(__file__).resolve()
        candidates.extend([here.parent, *here.parents])
    except NameError:
        pass

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / ".git").exists() and (candidate / "data_interim").exists():
            return candidate

    raise RuntimeError(
        "Could not locate the repository root. Run this script from inside the "
        "pr_ngvla repository or place it under the repository scripts directory."
    )


def file_size_label(path: Path) -> str:
    """Return a compact file size label."""
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size >= 1024**3:
        return f"{size / 1024**3:.2f} GiB"
    if size >= 1024**2:
        return f"{size / 1024**2:.2f} MiB"
    if size >= 1024:
        return f"{size / 1024:.2f} KiB"
    return f"{size} bytes"


def add_check(results: list[CheckResult], check: str, condition: bool, details: str) -> None:
    """Append a pass/fail check result."""
    results.append(CheckResult(check=check, status="PASS" if condition else "FAIL", details=details))


def add_info(results: list[CheckResult], check: str, details: str) -> None:
    """Append an informational result."""
    results.append(CheckResult(check=check, status="INFO", details=details))


def expected_project_hours(start_year: int, end_year: int) -> int:
    """Return the number of hourly timestamps in the inclusive project period."""
    start = pd.Timestamp(year=start_year, month=1, day=1, hour=0)
    end_exclusive = pd.Timestamp(year=end_year + 1, month=1, day=1, hour=0)
    return int((end_exclusive - start) / pd.Timedelta(hours=1))


def summarize_variable(df: pd.DataFrame, variable: str) -> dict[str, object]:
    """Compute a compact readiness summary for one clean variable."""
    valid_mask = df[variable].notna()
    valid_values = df.loc[valid_mask, variable]

    if valid_values.empty:
        return {
            "variable": variable,
            "total_valid_hours": 0,
            "stations_with_any_data": 0,
            "station_years_with_any_data": 0,
            "first_datetime_hour": pd.NaT,
            "last_datetime_hour": pd.NaT,
            "min_clean_value": pd.NA,
            "max_clean_value": pd.NA,
            "mean_clean_value": pd.NA,
        }

    station_years = (
        df.loc[valid_mask, ["station_id", "year"]]
        .drop_duplicates()
        .shape[0]
    )

    return {
        "variable": variable,
        "total_valid_hours": int(valid_mask.sum()),
        "stations_with_any_data": int(df.loc[valid_mask, "station_id"].nunique()),
        "station_years_with_any_data": int(station_years),
        "first_datetime_hour": df.loc[valid_mask, "datetime_hour"].min(),
        "last_datetime_hour": df.loc[valid_mask, "datetime_hour"].max(),
        "min_clean_value": float(valid_values.min()),
        "max_clean_value": float(valid_values.max()),
        "mean_clean_value": float(valid_values.mean()),
    }


def validate_required_columns(columns: Iterable[str]) -> tuple[bool, list[str]]:
    """Check whether required columns are present."""
    column_set = set(columns)
    missing = [col for col in REQUIRED_COLUMNS if col not in column_set]
    return len(missing) == 0, missing



def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """
    Convert a small DataFrame to a GitHub-flavored Markdown table without
    relying on pandas.to_markdown() or the optional tabulate package.

    This keeps the diagnostic script self-contained inside the existing
    PR-ngVLA conda environment.
    """
    if df.empty:
        return "_No rows._"

    table = df.copy()

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    headers = [str(col) for col in table.columns]
    rows = [[fmt(value) for value in row] for row in table.itertuples(index=False, name=None)]

    # Escape pipe characters so Markdown table structure is not broken.
    headers = [cell.replace("|", r"\|") for cell in headers]
    rows = [[cell.replace("|", r"\|") for cell in row] for row in rows]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def compare_variable_counts(
    computed_summary: pd.DataFrame,
    existing_variable_summary: pd.DataFrame | None,
) -> tuple[bool | None, str]:
    """
    Compare computed valid counts against an existing variable summary table.

    Returns:
        (None, message) when the existing table does not contain comparable
        columns; otherwise (True/False, message).
    """
    if existing_variable_summary is None:
        return None, "Existing variable summary table was not loaded."

    if "variable" not in existing_variable_summary.columns:
        return None, "Existing variable summary table has no 'variable' column."

    candidate_count_columns = [
        "total_valid_hours",
        "n_valid",
        "valid_hours",
        "n_hours_valid",
    ]

    count_column = None
    for col in candidate_count_columns:
        if col in existing_variable_summary.columns:
            count_column = col
            break

    if count_column is None:
        return None, (
            "Existing variable summary table has no comparable count column "
            f"among {candidate_count_columns}."
        )

    left = computed_summary[["variable", "total_valid_hours"]].copy()
    right = existing_variable_summary[["variable", count_column]].copy()
    right = right.rename(columns={count_column: "existing_total_valid_hours"})

    merged = left.merge(right, on="variable", how="outer")
    merged["count_difference"] = (
        merged["total_valid_hours"].fillna(-1).astype("int64")
        - merged["existing_total_valid_hours"].fillna(-1).astype("int64")
    )

    mismatches = merged.loc[merged["count_difference"] != 0]
    if mismatches.empty:
        return True, f"Computed counts match existing '{count_column}' counts for all variables."

    mismatch_text = mismatches.to_dict(orient="records")
    return False, f"Count mismatches detected: {mismatch_text}"


def main() -> int:
    repo_root = find_repo_root()

    clean_core_dir = repo_root / "data_interim" / "noaa" / "ghcnh_hourly" / "clean_core"
    coverage_dir = clean_core_dir / "coverage_no_thresholds"
    output_dir = repo_root / "outputs" / "diagnostics" / "ghcnh_hourly"
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_core_file = clean_core_dir / "ghcnh_hourly_clean_core_2004_2023.parquet"
    variable_summary_file = coverage_dir / "ghcnh_hourly_clean_core_variable_summary_no_thresholds.csv"
    station_variable_summary_file = coverage_dir / "ghcnh_hourly_clean_core_station_variable_summary_no_thresholds.csv"
    station_year_variable_file = coverage_dir / "ghcnh_hourly_clean_core_station_year_variable_coverage_no_thresholds.csv"
    station_year_wide_file = coverage_dir / "ghcnh_hourly_clean_core_station_year_coverage_wide_no_thresholds.csv"

    required_files = [
        clean_core_file,
        variable_summary_file,
        station_variable_summary_file,
        station_year_variable_file,
        station_year_wide_file,
    ]

    checks: list[CheckResult] = []
    add_info(checks, "repository_root", str(repo_root))

    for path in required_files:
        add_check(
            checks,
            f"file_exists::{path.relative_to(repo_root)}",
            path.exists(),
            file_size_label(path),
        )

    if not clean_core_file.exists():
        checks_df = pd.DataFrame([r.__dict__ for r in checks])
        checks_df.to_csv(output_dir / "ghcnh_hourly_clean_core_readiness_checks.csv", index=False)
        print("FAIL: clean-core parquet file is missing. See readiness checks CSV.")
        return 1

    df = pd.read_parquet(clean_core_file)

    has_required_columns, missing_columns = validate_required_columns(df.columns)
    add_check(
        checks,
        "required_columns_present",
        has_required_columns,
        "All required columns present." if has_required_columns else f"Missing columns: {missing_columns}",
    )

    add_check(
        checks,
        "datetime_hour_column_present",
        "datetime_hour" in df.columns,
        "datetime_hour is the official clean-core timestamp column.",
    )

    if "datetime_hour" not in df.columns:
        checks_df = pd.DataFrame([r.__dict__ for r in checks])
        checks_df.to_csv(output_dir / "ghcnh_hourly_clean_core_readiness_checks.csv", index=False)
        print("FAIL: datetime_hour column is missing. See readiness checks CSV.")
        return 1

    df["datetime_hour"] = pd.to_datetime(df["datetime_hour"], errors="coerce")

    n_rows = len(df)
    n_columns = len(df.columns)
    n_stations = int(df["station_id"].nunique()) if "station_id" in df.columns else 0
    years = sorted(df["year"].dropna().astype(int).unique().tolist()) if "year" in df.columns else []
    expected_years = list(range(PROJECT_PERIOD_START, PROJECT_PERIOD_END + 1))

    add_info(checks, "clean_core_rows", str(n_rows))
    add_info(checks, "clean_core_columns", str(n_columns))
    add_info(checks, "unique_stations", str(n_stations))

    add_check(
        checks,
        "project_years_complete",
        years == expected_years,
        f"Observed years: {years}; expected years: {expected_years}",
    )

    start_time = df["datetime_hour"].min()
    end_time = df["datetime_hour"].max()
    unique_hours = int(df["datetime_hour"].nunique())
    expected_hours = expected_project_hours(PROJECT_PERIOD_START, PROJECT_PERIOD_END)

    temporal_summary = pd.DataFrame(
        [
            {
                "project_period_start_year": PROJECT_PERIOD_START,
                "project_period_end_year": PROJECT_PERIOD_END,
                "first_datetime_hour": start_time,
                "last_datetime_hour": end_time,
                "unique_datetime_hours_present": unique_hours,
                "expected_hours_in_project_period": expected_hours,
                "fraction_of_project_hours_present_in_any_station": unique_hours / expected_hours,
            }
        ]
    )

    add_check(
        checks,
        "time_span_start",
        start_time == pd.Timestamp("2004-01-01 00:00:00"),
        f"First datetime_hour: {start_time}",
    )
    add_check(
        checks,
        "time_span_end",
        end_time == pd.Timestamp("2023-12-31 23:00:00"),
        f"Last datetime_hour: {end_time}",
    )
    add_info(checks, "unique_datetime_hours", f"{unique_hours} of {expected_hours}")

    variable_summary = pd.DataFrame([summarize_variable(df, variable) for variable in VARIABLE_COLUMNS])

    existing_variable_summary = None
    if variable_summary_file.exists():
        existing_variable_summary = pd.read_csv(variable_summary_file)

    compare_status, compare_message = compare_variable_counts(variable_summary, existing_variable_summary)
    if compare_status is None:
        add_info(checks, "variable_count_consistency", compare_message)
    else:
        add_check(checks, "variable_count_consistency", compare_status, compare_message)

    if station_variable_summary_file.exists():
        station_variable_summary = pd.read_csv(station_variable_summary_file)
        add_info(checks, "station_variable_summary_rows", str(len(station_variable_summary)))
        if "variable" in station_variable_summary.columns:
            add_info(
                checks,
                "station_variable_summary_variables",
                ", ".join(sorted(station_variable_summary["variable"].dropna().astype(str).unique())),
            )

    if station_year_variable_file.exists():
        station_year_variable = pd.read_csv(station_year_variable_file)
        add_info(checks, "station_year_variable_coverage_rows", str(len(station_year_variable)))

    if station_year_wide_file.exists():
        station_year_wide = pd.read_csv(station_year_wide_file)
        add_info(checks, "station_year_wide_coverage_rows", str(len(station_year_wide)))

    checks_df = pd.DataFrame([r.__dict__ for r in checks])

    checks_output = output_dir / "ghcnh_hourly_clean_core_readiness_checks.csv"
    variable_output = output_dir / "ghcnh_hourly_clean_core_variable_readiness_summary.csv"
    temporal_output = output_dir / "ghcnh_hourly_clean_core_temporal_readiness_summary.csv"
    report_output = output_dir / "ghcnh_hourly_clean_core_readiness_report.md"

    checks_df.to_csv(checks_output, index=False)
    variable_summary.to_csv(variable_output, index=False)
    temporal_summary.to_csv(temporal_output, index=False)

    n_fail = int((checks_df["status"] == "FAIL").sum())
    n_pass = int((checks_df["status"] == "PASS").sum())
    n_info = int((checks_df["status"] == "INFO").sum())

    report_lines = [
        "# GHCNh hourly clean-core readiness diagnostic",
        "",
        "## Classification",
        "",
        "Diagnostic / exploratory project script. This output verifies readiness before report-production scripts are run.",
        "",
        "## Scope",
        "",
        "- Source: GHCNh hourly clean core for Puerto Rico.",
        "- Period: 2004-2023.",
        "- This diagnostic does not modify raw or interim data.",
        "- This diagnostic does not interpolate observational data.",
        "- This diagnostic does not touch ERA5 or ERA5-Land products.",
        "",
        "## Summary",
        "",
        f"- PASS checks: {n_pass}",
        f"- FAIL checks: {n_fail}",
        f"- INFO entries: {n_info}",
        f"- Clean-core rows: {n_rows:,}",
        f"- Clean-core columns: {n_columns:,}",
        f"- Unique stations: {n_stations:,}",
        f"- First datetime_hour: {start_time}",
        f"- Last datetime_hour: {end_time}",
        f"- Unique project hours present in at least one station: {unique_hours:,} of {expected_hours:,}",
        "",
        "## Variable readiness summary",
        "",
        dataframe_to_markdown(variable_summary),
        "",
        "## Readiness checks",
        "",
        dataframe_to_markdown(checks_df),
        "",
        "## Output files",
        "",
        f"- `{checks_output.relative_to(repo_root)}`",
        f"- `{variable_output.relative_to(repo_root)}`",
        f"- `{temporal_output.relative_to(repo_root)}`",
        f"- `{report_output.relative_to(repo_root)}`",
        "",
    ]

    report_output.write_text("\n".join(report_lines), encoding="utf-8")

    print("GHCNh hourly clean-core readiness diagnostic complete.")
    print(f"Repository root: {repo_root}")
    print(f"PASS checks: {n_pass}")
    print(f"FAIL checks: {n_fail}")
    print(f"INFO entries: {n_info}")
    print("Outputs:")
    print(f"  {checks_output.relative_to(repo_root)}")
    print(f"  {variable_output.relative_to(repo_root)}")
    print(f"  {temporal_output.relative_to(repo_root)}")
    print(f"  {report_output.relative_to(repo_root)}")

    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
