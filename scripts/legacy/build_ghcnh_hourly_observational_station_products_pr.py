#!/usr/bin/env python3
"""
build_ghcnh_hourly_observational_station_products_pr.py

Build base observational station products from the Puerto Rico GHCNh hourly
clean core for the PR-ngVLA weather characterization project.

Purpose
-------
This is a report-production/infrastructure script for Phase 2A. It summarizes
which clean-core GHCNh hourly stations and variables are available before any
station-level weather-condition maps or threshold products are produced.

The script intentionally does NOT interpolate station observations, does NOT
merge ERA5/reanalysis data, and does NOT compute PWV. It only uses the cleaned
GHCNh hourly observational table and produces station/coverage products needed
for later scientific interpretation.

Inputs
------
- data_interim/noaa/ghcnh_hourly/clean_core/
  ghcnh_hourly_clean_core_2004_2023.parquet

Outputs
-------
Tables:
- outputs/tables/ghcnh_hourly_observational/
  ghcnh_hourly_station_inventory_observational.csv
- outputs/tables/ghcnh_hourly_observational/
  ghcnh_hourly_station_variable_availability.csv
- outputs/tables/ghcnh_hourly_observational/
  ghcnh_hourly_variable_coverage_summary.csv

Figures/maps:
- outputs/maps/ghcnh_hourly_observational/
  pr_ghcnh_hourly_all_stations_map.png
- outputs/maps/ghcnh_hourly_observational/
  pr_ghcnh_hourly_all_stations_map_excluding_hurricane_maria_window.png
- outputs/figures/ghcnh_hourly_observational/
  pr_ghcnh_hourly_station_variable_availability_matrix.png

Usage
-----
Run from the repository root:

    python scripts/build_ghcnh_hourly_observational_station_products_pr.py

Notes
-----
- The station maps use the established project map style from
  pr_ngvla.visualization.maps. This keeps Phase 2A station products visually
  consistent with the existing NOAA/GHCNh station inventory maps.
- A second station map is created after applying the centralized Hurricane
  Maria observational-disruption time exclusion from
  pr_ngvla.data.time_filters. This is a sensitivity check on station
  availability, not a replacement for the complete clean core.
- Wind direction is not included unless a clean-core direction column is added
  in a later phase. This Phase 2A script only uses variables that are known to
  exist in the current GHCNh clean core.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import sys

import numpy as np
import pandas as pd

# Use a non-interactive backend so the script works on remote/HPC sessions.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pr_ngvla.config as cfg
from pr_ngvla.data.spatial import load_vector_data
from pr_ngvla.data.time_filters import (
    HURRICANE_MARIA_OBSERVATIONAL_DISRUPTION_WINDOW,
    apply_hurricane_maria_exclusion,
)
from pr_ngvla.visualization.maps import (
    add_north_arrow,
    finalize_station_inventory_figure,
    mask_ocean,
    plot_base_map,
    style_station_inventory_axes,
)


# -----------------------------------------------------------------------------
# Project constants
# -----------------------------------------------------------------------------

PERIOD_START = pd.Timestamp("2004-01-01 00:00:00")
PERIOD_END = pd.Timestamp("2023-12-31 23:00:00")
EXPECTED_HOURS_FULL_PERIOD = int(
    (PERIOD_END - PERIOD_START) / pd.Timedelta(hours=1)
) + 1

@dataclass(frozen=True)
class VariableSpec:
    """Definition of a clean-core observational variable."""

    column: str
    short_name: str
    report_name: str
    unit: str


VARIABLES: tuple[VariableSpec, ...] = (
    VariableSpec(
        column="temperature_c",
        short_name="T",
        report_name="Air temperature",
        unit="deg C",
    ),
    VariableSpec(
        column="dew_point_temperature_c",
        short_name="Td",
        report_name="Dew point temperature",
        unit="deg C",
    ),
    VariableSpec(
        column="relative_humidity_pct",
        short_name="RH",
        report_name="Relative humidity",
        unit="%",
    ),
    VariableSpec(
        column="wind_speed_m_s",
        short_name="Wind speed",
        report_name="Wind speed",
        unit="m s-1",
    ),
    VariableSpec(
        column="station_level_pressure_hpa",
        short_name="Pressure",
        report_name="Station-level pressure",
        unit="hPa",
    ),
    VariableSpec(
        column="precipitation_mm",
        short_name="Precipitation",
        report_name="Hourly precipitation",
        unit="mm h-1",
    ),
)

REQUIRED_BASE_COLUMNS = (
    "station_id",
    "station_name",
    "lat",
    "lon",
    "elevation_m",
    "datetime_hour",
    "year",
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def find_repo_root(start: Path) -> Path:
    """Return the repository root by walking upward from *start*."""
    start = start.resolve()
    candidates = [start] + list(start.parents)
    for candidate in candidates:
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError(
        "Could not locate repository root. Run this script from inside the "
        "PR-ngVLA repository."
    )


def cfg_path(name: str, fallback: str | Path) -> Path:
    """
    Return a project path from pr_ngvla.config with a local fallback.

    This keeps the script compatible with the existing project configuration
    while still providing a clear fallback for the expected repository layout.
    """
    return Path(getattr(cfg, name, fallback))


def require_columns(df: pd.DataFrame, columns: Iterable[str], context: str) -> None:
    """Raise a clear error if required columns are missing."""
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {context}: {', '.join(missing)}"
        )


def ensure_output_dirs(repo_root: Path) -> dict[str, Path]:
    """Create and return Phase 2A output directories."""
    dirs = {
        "tables": repo_root / "outputs" / "tables" / "ghcnh_hourly_observational",
        "figures": repo_root / "outputs" / "figures" / "ghcnh_hourly_observational",
        "maps": repo_root / "outputs" / "maps" / "ghcnh_hourly_observational",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def first_non_null(series: pd.Series):
    """Return the first non-null value from a Series, or NA if none exist."""
    valid = series.dropna()
    if valid.empty:
        return pd.NA
    return valid.iloc[0]


def summarize_station_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one row per station using stable station metadata.

    Median coordinates are used defensively in case a station has tiny metadata
    variations across source files. The unique-count fields document whether
    coordinate/name metadata were stable in the clean core.
    """
    grouped = df.groupby("station_id", sort=True)
    station_inventory = grouped.agg(
        station_name=("station_name", first_non_null),
        lat=("lat", "median"),
        lon=("lon", "median"),
        elevation_m=("elevation_m", "median"),
        n_station_name_values=("station_name", lambda s: s.dropna().nunique()),
        n_lat_values=("lat", lambda s: s.dropna().nunique()),
        n_lon_values=("lon", lambda s: s.dropna().nunique()),
        n_elevation_values=("elevation_m", lambda s: s.dropna().nunique()),
        first_datetime_hour=("datetime_hour", "min"),
        last_datetime_hour=("datetime_hour", "max"),
        n_station_hour_rows=("datetime_hour", "count"),
    ).reset_index()

    station_inventory["first_datetime_hour"] = station_inventory[
        "first_datetime_hour"
    ].dt.strftime("%Y-%m-%d %H:%M:%S")
    station_inventory["last_datetime_hour"] = station_inventory[
        "last_datetime_hour"
    ].dt.strftime("%Y-%m-%d %H:%M:%S")
    return station_inventory


def build_station_variable_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Return long-format station-variable availability metrics."""
    records: list[dict[str, object]] = []

    metadata = summarize_station_coordinates(df).set_index("station_id")

    for station_id, station_df in df.groupby("station_id", sort=True):
        station_meta = metadata.loc[station_id]
        for var in VARIABLES:
            valid = station_df[var.column].notna()
            valid_df = station_df.loc[valid, ["datetime_hour", "year", var.column]]
            n_valid_hours = int(valid.sum())
            years_with_data = int(valid_df["year"].nunique()) if n_valid_hours else 0
            first_time = (
                valid_df["datetime_hour"].min().strftime("%Y-%m-%d %H:%M:%S")
                if n_valid_hours
                else pd.NA
            )
            last_time = (
                valid_df["datetime_hour"].max().strftime("%Y-%m-%d %H:%M:%S")
                if n_valid_hours
                else pd.NA
            )

            records.append(
                {
                    "station_id": station_id,
                    "station_name": station_meta["station_name"],
                    "lat": station_meta["lat"],
                    "lon": station_meta["lon"],
                    "elevation_m": station_meta["elevation_m"],
                    "variable_column": var.column,
                    "variable_short_name": var.short_name,
                    "variable_report_name": var.report_name,
                    "unit": var.unit,
                    "has_data": bool(n_valid_hours > 0),
                    "n_valid_hours": n_valid_hours,
                    "years_with_data": years_with_data,
                    "first_datetime_hour": first_time,
                    "last_datetime_hour": last_time,
                    "fraction_of_full_2004_2023_hours": n_valid_hours
                    / EXPECTED_HOURS_FULL_PERIOD,
                }
            )

    return pd.DataFrame.from_records(records)


def build_station_inventory(
    df: pd.DataFrame, station_variable: pd.DataFrame
) -> pd.DataFrame:
    """Return one row per station with variable availability flags."""
    station_inventory = summarize_station_coordinates(df)

    station_var_wide = (
        station_variable.pivot(
            index="station_id", columns="variable_column", values="has_data"
        )
        .fillna(False)
        .astype(bool)
    )
    station_var_wide = station_var_wide.rename(
        columns={var.column: f"has_{var.column}" for var in VARIABLES}
    )

    valid_hour_wide = station_variable.pivot(
        index="station_id", columns="variable_column", values="n_valid_hours"
    ).fillna(0)
    valid_hour_wide = valid_hour_wide.rename(
        columns={var.column: f"n_valid_hours_{var.column}" for var in VARIABLES}
    )

    station_inventory = station_inventory.merge(
        station_var_wide.reset_index(), on="station_id", how="left"
    ).merge(valid_hour_wide.reset_index(), on="station_id", how="left")

    has_columns = [f"has_{var.column}" for var in VARIABLES]
    station_inventory[has_columns] = station_inventory[has_columns].fillna(False)
    station_inventory["n_variables_available"] = station_inventory[has_columns].sum(axis=1)

    def available_variable_list(row: pd.Series) -> str:
        names = [
            var.short_name
            for var in VARIABLES
            if bool(row.get(f"has_{var.column}", False))
        ]
        return ", ".join(names)

    station_inventory["variables_available"] = station_inventory.apply(
        available_variable_list, axis=1
    )

    return station_inventory.sort_values(["station_id"]).reset_index(drop=True)


def build_variable_coverage_summary(
    df: pd.DataFrame, station_variable: pd.DataFrame
) -> pd.DataFrame:
    """Return one row per observational variable with coverage metrics."""
    records: list[dict[str, object]] = []

    for var in VARIABLES:
        valid = df[var.column].notna()
        valid_df = df.loc[valid, ["station_id", "datetime_hour", "year", var.column]]
        n_valid = int(valid.sum())

        if n_valid:
            station_years = valid_df[["station_id", "year"]].drop_duplicates().shape[0]
            records.append(
                {
                    "variable_column": var.column,
                    "variable_short_name": var.short_name,
                    "variable_report_name": var.report_name,
                    "unit": var.unit,
                    "n_valid_hours": n_valid,
                    "n_stations_with_data": int(valid_df["station_id"].nunique()),
                    "station_years_with_data": int(station_years),
                    "first_datetime_hour": valid_df["datetime_hour"]
                    .min()
                    .strftime("%Y-%m-%d %H:%M:%S"),
                    "last_datetime_hour": valid_df["datetime_hour"]
                    .max()
                    .strftime("%Y-%m-%d %H:%M:%S"),
                    "min_value": float(valid_df[var.column].min()),
                    "mean_value": float(valid_df[var.column].mean()),
                    "median_value": float(valid_df[var.column].median()),
                    "max_value": float(valid_df[var.column].max()),
                    "fraction_of_full_2004_2023_station_hours": n_valid
                    / (EXPECTED_HOURS_FULL_PERIOD * df["station_id"].nunique()),
                }
            )
        else:
            records.append(
                {
                    "variable_column": var.column,
                    "variable_short_name": var.short_name,
                    "variable_report_name": var.report_name,
                    "unit": var.unit,
                    "n_valid_hours": 0,
                    "n_stations_with_data": 0,
                    "station_years_with_data": 0,
                    "first_datetime_hour": pd.NA,
                    "last_datetime_hour": pd.NA,
                    "min_value": np.nan,
                    "mean_value": np.nan,
                    "median_value": np.nan,
                    "max_value": np.nan,
                    "fraction_of_full_2004_2023_station_hours": 0.0,
                }
            )

    summary = pd.DataFrame.from_records(records)

    # Add a coverage rank that is useful for interpretation without imposing any
    # science-weighted index or site decision.
    summary = summary.sort_values("n_valid_hours", ascending=False).reset_index(drop=True)
    summary.insert(0, "coverage_rank_by_valid_hours", np.arange(1, len(summary) + 1))
    return summary


# -----------------------------------------------------------------------------
# Plotting
# -----------------------------------------------------------------------------


def plot_station_map(
    station_inventory: pd.DataFrame,
    repo_root: Path,
    out_path: Path,
    *,
    title: str,
) -> None:
    """
    Create a project-style map of all GHCNh clean-core station locations.

    The map intentionally reuses the same shared Puerto Rico basemap helpers used
    by scripts/map_ghcnh_station_inventory_pr.py and
    scripts/map_noaa_station_inventory_pr.py. Station IDs are not printed on the
    map because labels overlap at this station density; station identification is
    handled by the accompanying CSV inventory table.
    """
    coast_shp = cfg_path(
        "COAST_SHP",
        repo_root / "data_raw" / "shapefiles" / "GSHHS_h_L1.shp",
    )
    muni_shp = cfg_path(
        "MUNI_SHP",
        repo_root
        / "data_raw"
        / "shapefiles"
        / "tl_2024_us_county"
        / "tl_2024_us_county.shp",
    )

    muni_clip, coast_union, muni_land_union = load_vector_data(coast_shp, muni_shp)

    fig, ax = plt.subplots(figsize=(14, 4.5), dpi=150)

    # Use the established PR-ngVLA station-map basemap style.
    mask_ocean(ax, muni_land_union)
    plot_base_map(ax, coast_union=coast_union, muni_clip=muni_clip)

    ax.scatter(
        station_inventory["lon"],
        station_inventory["lat"],
        s=22,
        marker="o",
        color="#1f77b4",
        edgecolors="white",
        linewidths=0.4,
        zorder=10,
        label="ghcnh",
    )

    ax.legend(title="source", loc="lower left", frameon=True)
    style_station_inventory_axes(ax, title=title)
    add_north_arrow(ax)

    finalize_station_inventory_figure(fig, out_path)
    plt.close(fig)


def plot_station_variable_matrix(
    station_variable: pd.DataFrame, station_inventory: pd.DataFrame, out_path: Path
) -> None:
    """Create a station-by-variable availability matrix figure."""
    ordered_stations = station_inventory.sort_values(
        ["n_variables_available", "station_id"], ascending=[False, True]
    )["station_id"].tolist()
    ordered_variables = [var.column for var in VARIABLES]
    variable_labels = [var.short_name for var in VARIABLES]

    matrix = (
        station_variable.pivot(
            index="station_id", columns="variable_column", values="has_data"
        )
        .reindex(index=ordered_stations, columns=ordered_variables)
        .fillna(False)
        .astype(int)
    )

    fig_height = max(7.0, 0.22 * len(matrix.index) + 2.5)
    fig, ax = plt.subplots(figsize=(8.5, fig_height))
    ax.imshow(matrix.values, aspect="auto", interpolation="nearest", cmap="Greys")

    ax.set_xticks(np.arange(len(variable_labels)))
    ax.set_xticklabels(variable_labels, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=7)
    ax.set_title("GHCNh hourly clean-core variable availability by station")

    # Draw cell grid lines for readability.
    ax.set_xticks(np.arange(-0.5, len(variable_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(matrix.index), 1), minor=True)
    ax.grid(which="minor", linewidth=0.4)
    ax.tick_params(which="minor", bottom=False, left=False)

    fig.text(
        0.01,
        0.01,
        "Filled cells indicate at least one valid clean-core hourly observation for the variable.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Main workflow
# -----------------------------------------------------------------------------


def main() -> int:
    repo_root = find_repo_root(Path.cwd())
    output_dirs = ensure_output_dirs(repo_root)

    clean_core_path = (
        repo_root
        / "data_interim"
        / "noaa"
        / "ghcnh_hourly"
        / "clean_core"
        / "ghcnh_hourly_clean_core_2004_2023.parquet"
    )
    if not clean_core_path.exists():
        raise FileNotFoundError(f"Clean-core parquet not found: {clean_core_path}")

    variable_columns = [var.column for var in VARIABLES]
    columns_to_read = list(REQUIRED_BASE_COLUMNS) + variable_columns

    print("Reading GHCNh hourly clean core...")
    print(f"Input: {clean_core_path}")
    df = pd.read_parquet(clean_core_path, columns=columns_to_read)
    require_columns(df, columns_to_read, "GHCNh hourly clean-core parquet")

    df["datetime_hour"] = pd.to_datetime(df["datetime_hour"], errors="raise")
    df["year"] = df["year"].astype(int)

    # A defensive check: this script is designed for the fixed 2004-2023 clean
    # core. A warning is printed rather than mutating/filtering the data.
    observed_start = df["datetime_hour"].min()
    observed_end = df["datetime_hour"].max()
    if observed_start < PERIOD_START or observed_end > PERIOD_END:
        print(
            "WARNING: Clean-core time span extends outside 2004-2023. "
            f"Observed span: {observed_start} to {observed_end}",
            file=sys.stderr,
        )

    # Keep the complete clean core as the primary analysis table. The filtered
    # table below is used only to test whether the station inventory map changes
    # after excluding the Hurricane Maria observational-disruption window.
    df_excluding_maria = apply_hurricane_maria_exclusion(
        df,
        datetime_column="datetime_hour",
        copy=True,
    )
    maria_window = HURRICANE_MARIA_OBSERVATIONAL_DISRUPTION_WINDOW
    rows_excluded_by_maria_window = len(df) - len(df_excluding_maria)

    print("Building station-variable availability table...")
    station_variable = build_station_variable_availability(df)

    print("Building station inventory table...")
    station_inventory = build_station_inventory(df, station_variable)

    print("Building station inventory table excluding Hurricane Maria window...")
    station_inventory_excluding_maria = summarize_station_coordinates(df_excluding_maria)

    print("Building variable coverage summary...")
    variable_summary = build_variable_coverage_summary(df, station_variable)

    station_inventory_path = (
        output_dirs["tables"] / "ghcnh_hourly_station_inventory_observational.csv"
    )
    station_variable_path = (
        output_dirs["tables"] / "ghcnh_hourly_station_variable_availability.csv"
    )
    variable_summary_path = (
        output_dirs["tables"] / "ghcnh_hourly_variable_coverage_summary.csv"
    )

    station_inventory.to_csv(station_inventory_path, index=False)
    station_variable.to_csv(station_variable_path, index=False)
    variable_summary.to_csv(variable_summary_path, index=False)

    station_map_path = output_dirs["maps"] / "pr_ghcnh_hourly_all_stations_map.png"
    station_map_excluding_maria_path = (
        output_dirs["maps"]
        / "pr_ghcnh_hourly_all_stations_map_excluding_hurricane_maria_window.png"
    )
    matrix_path = (
        output_dirs["figures"]
        / "pr_ghcnh_hourly_station_variable_availability_matrix.png"
    )

    print("Creating all-stations map...")
    plot_station_map(
        station_inventory,
        repo_root,
        station_map_path,
        title="Puerto Rico GHCNh hourly clean-core station inventory (2004–2023)",
    )

    print("Creating all-stations map excluding Hurricane Maria window...")
    plot_station_map(
        station_inventory_excluding_maria,
        repo_root,
        station_map_excluding_maria_path,
        title=(
            "Puerto Rico GHCNh hourly clean-core station inventory — "
            "excluding Hurricane Maria window"
        ),
    )

    print("Creating station-variable availability matrix...")
    plot_station_variable_matrix(station_variable, station_inventory, matrix_path)

    print("GHCNh hourly observational station products complete.")
    print(f"Repository root: {repo_root}")
    print(f"Stations: {len(station_inventory)}")
    print(
        "Stations after excluding Hurricane Maria window: "
        f"{len(station_inventory_excluding_maria)}"
    )
    print(
        "Hurricane Maria exclusion window: "
        f"{maria_window.start} <= datetime_hour < {maria_window.end}"
    )
    print(f"Rows excluded by Hurricane Maria window: {rows_excluded_by_maria_window}")
    print("Variables:")
    for var in VARIABLES:
        row = variable_summary.loc[variable_summary["variable_column"] == var.column].iloc[0]
        print(
            f"  {var.short_name}: {int(row['n_stations_with_data'])} stations, "
            f"{int(row['n_valid_hours'])} valid hours"
        )
    print("Outputs:")
    print(f"  {station_inventory_path.relative_to(repo_root)}")
    print(f"  {station_variable_path.relative_to(repo_root)}")
    print(f"  {variable_summary_path.relative_to(repo_root)}")
    print(f"  {station_map_path.relative_to(repo_root)}")
    print(f"  {station_map_excluding_maria_path.relative_to(repo_root)}")
    print(f"  {matrix_path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
