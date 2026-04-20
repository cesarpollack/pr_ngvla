"""
pr_ngvla.data.noaa
==================

Utilities for NOAA station metadata and inventory handling.

Scope of this first implementation
----------------------------------
This module handles metadata only:
- authoritative ISD / Global Hourly station history
- authoritative GHCN-Daily station metadata
- authoritative GHCN-Daily inventory metadata
- Puerto Rico bounding-box filtering
- study-period overlap filtering
- assembly of a standardized master inventory table

This module does NOT yet:
- download station time series
- parse hourly station observations
- match stations to ERA5 grid cells
- compute validation metrics

Design rules
------------
- Keep source-specific parsing here.
- Return clean pandas DataFrames with a standard schema.
- Keep plotting and file-output orchestration out of this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# Fixed-width specifications for authoritative GHCN-Daily metadata files
# ---------------------------------------------------------------------------
# NOAA distributes ghcnd-stations.txt as a fixed-width text file.
GHCND_STATION_COLSPECS = [
    (0, 11),   # station id
    (12, 20),  # latitude
    (21, 30),  # longitude
    (31, 37),  # elevation
    (38, 40),  # state
    (41, 71),  # station name
    (72, 75),  # GSN flag
    (76, 79),  # HCN/CRN flag
    (80, 85),  # WMO id
]

GHCND_STATION_NAMES = [
    "station_id",
    "latitude",
    "longitude",
    "elevation_m",
    "state_code",
    "station_name",
    "gsn_flag",
    "hcn_crn_flag",
    "wmo_id",
]

# NOAA distributes ghcnd-inventory.txt as a fixed-width text file.
GHCND_INVENTORY_COLSPECS = [
    (0, 11),   # station id
    (12, 20),  # latitude
    (21, 30),  # longitude
    (31, 35),  # element
    (36, 40),  # first year
    (41, 45),  # last year
]

GHCND_INVENTORY_NAMES = [
    "station_id",
    "latitude",
    "longitude",
    "element",
    "first_year",
    "last_year",
]


# ---------------------------------------------------------------------------
# Standard output schema used by the inventory builder
# ---------------------------------------------------------------------------
STANDARD_METADATA_COLUMNS = [
    "source",
    "source_subtype",
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "elevation_m",
    "country_code",
    "state_code",
    "icao",
    "usaf",
    "wban",
    "begin_date",
    "end_date",
    "begin_year",
    "end_year",
    "in_pr_bbox",
    "overlaps_study_period",
    "has_metadata_issue",
    "notes",
]


# ---------------------------------------------------------------------------
# Generic normalization helpers
# ---------------------------------------------------------------------------
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of `df` with normalized column names.

    Normalization rules
    -------------------
    - strip leading/trailing whitespace
    - lowercase
    - replace spaces, slashes, hyphens, and parentheses
    - collapse repeated underscores

    This keeps source-specific loaders simpler and more robust.
    """
    out = df.copy()

    normalized = []
    for column in out.columns:
        name = str(column).strip().lower()
        name = name.replace("(", "_")
        name = name.replace(")", "")
        name = name.replace("/", "_")
        name = name.replace("-", "_")
        name = name.replace(" ", "_")

        while "__" in name:
            name = name.replace("__", "_")

        normalized.append(name.strip("_"))

    out.columns = normalized
    return out

def coerce_date_column(series: pd.Series) -> pd.Series:
    """
    Parse a date-like series into pandas datetime values.

    Supported common formats
    ------------------------
    - YYYYMMDD   (e.g. NOAA ISD history files)
    - YYYY-MM-DD (e.g. project-derived CSVs)

    Unparseable values become NaT.
    """
    cleaned = (
        series.astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )

    # Pass 1: compact NOAA format YYYYMMDD
    parsed = pd.to_datetime(cleaned, format="%Y%m%d", errors="coerce")

    # Pass 2: ISO-style YYYY-MM-DD only where still missing
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            cleaned.loc[missing],
            format="%Y-%m-%d",
            errors="coerce",
        )

    # Pass 3: generic fallback for anything else
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            cleaned.loc[missing],
            errors="coerce",
        )

    return parsed



def derive_year_column(series: pd.Series) -> pd.Series:
    """
    Extract year from a datetime-like series as nullable Int64.
    """
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.year.astype("Int64")


def _empty_standard_dataframe() -> pd.DataFrame:
    """
    Create an empty standardized inventory DataFrame.
    """
    return pd.DataFrame(columns=STANDARD_METADATA_COLUMNS)


def _combine_isd_station_id(usaf: pd.Series, wban: pd.Series) -> pd.Series:
    """
    Build the canonical ISD station identifier: USAF-WBAN.

    Leading zeros are preserved by padding to the standard widths:
    - USAF: 6 digits
    - WBAN: 5 digits
    """
    usaf_str = usaf.astype("string").str.strip().str.zfill(6)
    wban_str = wban.astype("string").str.strip().str.zfill(5)
    return usaf_str + "-" + wban_str


# ---------------------------------------------------------------------------
# Source-specific metadata loaders
# ---------------------------------------------------------------------------
def load_isd_history(path: Path) -> pd.DataFrame:
    """
    Load NOAA ISD / Global Hourly station-history metadata.

    Parameters
    ----------
    path : Path
        Path to authoritative isd-history.csv.

    Returns
    -------
    DataFrame
        Normalized metadata table.
    """
    df = pd.read_csv(path, dtype=str)
    return normalize_column_names(df)


def load_isd_inventory(path: Path) -> pd.DataFrame:
    """
    Load NOAA ISD inventory metadata.

    This file is not yet used directly in the first-pass master inventory,
    but it is staged now because it will be useful for later completeness
    and year-by-year availability analyses.

    Parameters
    ----------
    path : Path
        Path to authoritative isd-inventory.csv.

    Returns
    -------
    DataFrame
        Normalized inventory table.
    """
    df = pd.read_csv(path, dtype=str, low_memory=False)
    return normalize_column_names(df)


def load_ghcnd_stations(path: Path) -> pd.DataFrame:
    """
    Load authoritative GHCN-Daily station metadata from ghcnd-stations.txt.

    Parameters
    ----------
    path : Path
        Path to ghcnd-stations.txt.

    Returns
    -------
    DataFrame
        Parsed fixed-width metadata table.
    """
    df = pd.read_fwf(
        path,
        colspecs=GHCND_STATION_COLSPECS,
        names=GHCND_STATION_NAMES,
    )
    return normalize_column_names(df)


def load_ghcnd_inventory(path: Path) -> pd.DataFrame:
    """
    Load authoritative GHCN-Daily inventory metadata from ghcnd-inventory.txt.

    Parameters
    ----------
    path : Path
        Path to ghcnd-inventory.txt.

    Returns
    -------
    DataFrame
        Parsed fixed-width inventory table.
    """
    df = pd.read_fwf(
        path,
        colspecs=GHCND_INVENTORY_COLSPECS,
        names=GHCND_INVENTORY_NAMES,
    )
    return normalize_column_names(df)


# ---------------------------------------------------------------------------
# Inventory summarization helpers
# ---------------------------------------------------------------------------
def summarize_ghcnd_inventory_period(df_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce GHCN-Daily inventory rows to one row per station.

    The authoritative inventory is element-specific (e.g. TMAX, TMIN, PRCP).
    For the first-pass station inventory, we summarize each station by the
    earliest and latest year available in the inventory.

    Parameters
    ----------
    df_inventory : DataFrame
        Parsed GHCN-Daily inventory table.

    Returns
    -------
    DataFrame
        Columns:
        - station_id
        - begin_year
        - end_year
    """
    inventory = df_inventory.copy()

    inventory["first_year"] = pd.to_numeric(inventory["first_year"], errors="coerce")
    inventory["last_year"] = pd.to_numeric(inventory["last_year"], errors="coerce")

    summary = (
        inventory.groupby("station_id", as_index=False)
        .agg(
            begin_year=("first_year", "min"),
            end_year=("last_year", "max"),
        )
    )

    summary["begin_year"] = summary["begin_year"].astype("Int64")
    summary["end_year"] = summary["end_year"].astype("Int64")

    return summary


# ---------------------------------------------------------------------------
# Standardization functions
# ---------------------------------------------------------------------------
def standardize_isd_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map NOAA ISD history metadata into the project-standard schema.
    """
    required_columns = [
        "usaf",
        "wban",
        "station_name",
        "ctry",
        "state",
        "icao",
        "lat",
        "lon",
        "elev_m",
        "begin",
        "end",
    ]

    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"ISD history file is missing required columns: {missing}")

    out = pd.DataFrame(index=df.index.copy())

    out["source"] = "isd"
    out["source_subtype"] = "isd_history"
    out["station_id"] = _combine_isd_station_id(df["usaf"], df["wban"])
    out["station_name"] = df["station_name"].astype("string").str.strip()

    out["latitude"] = pd.to_numeric(df["lat"], errors="coerce")
    out["longitude"] = pd.to_numeric(df["lon"], errors="coerce")
    out["elevation_m"] = pd.to_numeric(df["elev_m"], errors="coerce")

    out["country_code"] = df["ctry"].astype("string").str.strip()
    out["state_code"] = df["state"].astype("string").str.strip()
    out["icao"] = df["icao"].astype("string").str.strip()
    out["usaf"] = df["usaf"].astype("string").str.strip()
    out["wban"] = df["wban"].astype("string").str.strip()

    out["begin_date"] = coerce_date_column(df["begin"])
    out["end_date"] = coerce_date_column(df["end"])
    out["begin_year"] = derive_year_column(out["begin_date"])
    out["end_year"] = derive_year_column(out["end_date"])

    out["in_pr_bbox"] = False
    out["overlaps_study_period"] = False

    out["has_metadata_issue"] = (
        out["station_id"].isna()
        | out["latitude"].isna()
        | out["longitude"].isna()
    )

    out["notes"] = pd.NA

    return out[STANDARD_METADATA_COLUMNS]


def standardize_ghcnd_stations(
    df_stations: pd.DataFrame,
    df_inventory: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Map GHCN-Daily station metadata into the project-standard schema.

    If inventory is available, derive station begin/end years from it.
    """
    required_columns = [
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "elevation_m",
        "state_code",
    ]

    missing = [column for column in required_columns if column not in df_stations.columns]
    if missing:
        raise ValueError(f"GHCND station file is missing required columns: {missing}")

    stations = df_stations.copy()

    inventory_summary = None
    if df_inventory is not None:
        inventory_summary = summarize_ghcnd_inventory_period(df_inventory)

    out = pd.DataFrame(index=stations.index.copy())

    out["source"] = "ghcnd"
    out["source_subtype"] = "ghcnd_stations"
    out["station_id"] = stations["station_id"].astype("string").str.strip()
    out["station_name"] = stations["station_name"].astype("string").str.strip()

    out["latitude"] = pd.to_numeric(stations["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(stations["longitude"], errors="coerce")
    out["elevation_m"] = pd.to_numeric(stations["elevation_m"], errors="coerce")

    # GHCND station metadata does not provide a separate country code field here.
    out["country_code"] = pd.NA
    out["state_code"] = stations["state_code"].astype("string").str.strip()
    out["icao"] = pd.NA
    out["usaf"] = pd.NA
    out["wban"] = pd.NA

    out["begin_date"] = pd.NaT
    out["end_date"] = pd.NaT
    out["begin_year"] = pd.Series(pd.NA, index=stations.index, dtype="Int64")
    out["end_year"] = pd.Series(pd.NA, index=stations.index, dtype="Int64")

    if inventory_summary is not None:
        merged_years = out[["station_id"]].merge(
            inventory_summary,
            on="station_id",
            how="left",
        )

        out["begin_year"] = merged_years["begin_year"].astype("Int64")
        out["end_year"] = merged_years["end_year"].astype("Int64")

        # Convert summarized years into conservative station-wide date bounds.
        out["begin_date"] = pd.to_datetime(
            out["begin_year"].astype("string") + "-01-01",
            errors="coerce",
        )
        out["end_date"] = pd.to_datetime(
            out["end_year"].astype("string") + "-12-31",
            errors="coerce",
        )

    out["in_pr_bbox"] = False
    out["overlaps_study_period"] = False

    out["has_metadata_issue"] = (
        out["station_id"].isna()
        | out["latitude"].isna()
        | out["longitude"].isna()
    )

    out["notes"] = pd.NA

    return out[STANDARD_METADATA_COLUMNS]


# ---------------------------------------------------------------------------
# Filtering / flagging helpers
# ---------------------------------------------------------------------------
def flag_stations_in_bbox(
    df: pd.DataFrame,
    south: float,
    west: float,
    north: float,
    east: float,
) -> pd.DataFrame:
    """
    Add or overwrite the boolean `in_pr_bbox` flag using an inclusive bbox.
    """
    out = df.copy()

    out["in_pr_bbox"] = (
        out["latitude"].between(south, north, inclusive="both")
        & out["longitude"].between(west, east, inclusive="both")
    )

    return out


def flag_stations_overlapping_period(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Add or overwrite the boolean `overlaps_study_period` flag.

    Overlap rule
    ------------
    A station overlaps the study period if:
    - station begin date <= study end date
    - station end date   >= study start date

    Missing begin/end dates are treated as non-overlap for this first pass.
    """
    out = df.copy()

    study_start = pd.Timestamp(start_date)
    study_end = pd.Timestamp(end_date)

    out["overlaps_study_period"] = (
        out["begin_date"].notna()
        & out["end_date"].notna()
        & (out["begin_date"] <= study_end)
        & (out["end_date"] >= study_start)
    )

    return out


def filter_candidate_pr_stations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return stations already flagged as inside the Puerto Rico bounding box.
    """
    return df.loc[df["in_pr_bbox"]].copy()


def filter_overlap_stations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return stations already flagged as overlapping the study period.
    """
    return df.loc[df["overlaps_study_period"]].copy()

def filter_pr_territory_stations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a stricter Puerto Rico territorial subset from an already
    bbox-filtered inventory.

    Territorial rule for Pass 1
    ---------------------------
    - GHCND: keep only rows with state_code == "PR"
    - ISD:   keep rows with state_code == "PR" OR country_code == "RQ"

    Rationale
    ---------
    The bounding box intentionally includes Mona, Vieques, and Culebra, but
    it can also admit nearby non-Puerto Rico stations (for example USVI rows).
    This stricter rule keeps Puerto Rico territorial stations while removing
    the obvious geographic spillover.
    """
    out = df.copy()

    ghcnd_mask = (
        (out["source"] == "ghcnd")
        & (out["state_code"] == "PR")
    )

    isd_mask = (
        (out["source"] == "isd")
        & (
            (out["state_code"] == "PR")
            | (out["country_code"] == "RQ")
        )
    )

    return out.loc[ghcnd_mask | isd_mask].copy()


def build_station_inventory_summary_by_subset(
    df_all_in_bbox: pd.DataFrame,
    df_pr_territory: pd.DataFrame,
    df_master: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a compact summary table across the three inventory stages.

    Stages
    ------
    - all_in_bbox : coarse geographic filter only
    - pr_territory: stricter Puerto Rico territorial filter
    - master      : pr_territory subset overlapping 2004-2023
    """
    rows = []

    for label, frame in [
        ("all_in_bbox", df_all_in_bbox),
        ("pr_territory", df_pr_territory),
        ("master", df_master),
    ]:
        if frame.empty:
            continue

        grouped = (
            frame.groupby("source", as_index=False)
            .agg(
                n_total=("station_id", "size"),
                min_begin_year=("begin_year", "min"),
                max_end_year=("end_year", "max"),
            )
        )

        grouped.insert(0, "subset", label)
        rows.append(grouped)

    if not rows:
        return pd.DataFrame(
            columns=[
                "subset",
                "source",
                "n_total",
                "min_begin_year",
                "max_end_year",
            ]
        )

    return pd.concat(rows, ignore_index=True)

# ---------------------------------------------------------------------------
# Inventory assembly helpers
# ---------------------------------------------------------------------------
def build_master_station_inventory(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """
    Concatenate standardized metadata tables into one inventory.

    Deduplication policy for Pass 1
    -------------------------------
    Deduplicate only within the same source using:
    - source
    - station_id

    Cross-source matching is deliberately postponed to a later phase.
    """
    usable = [frame.copy() for frame in frames if frame is not None and not frame.empty]

    if not usable:
        return _empty_standard_dataframe()

    inventory = pd.concat(usable, axis=0, ignore_index=True)

    # Reindex defensively in case future source adapters add extra columns.
    inventory = inventory.reindex(columns=STANDARD_METADATA_COLUMNS)

    inventory = inventory.drop_duplicates(subset=["source", "station_id"]).copy()

    inventory = inventory.sort_values(
        by=["source", "station_id"],
        kind="stable",
    ).reset_index(drop=True)

    return inventory


def build_station_inventory_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a compact grouped summary from a standardized inventory table.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "source",
                "n_total",
                "n_in_pr_bbox",
                "n_overlap_2004_2023",
                "min_begin_year",
                "max_end_year",
            ]
        )

    summary = (
        df.groupby("source", as_index=False)
        .agg(
            n_total=("station_id", "size"),
            n_in_pr_bbox=("in_pr_bbox", "sum"),
            n_overlap_2004_2023=("overlaps_study_period", "sum"),
            min_begin_year=("begin_year", "min"),
            max_end_year=("end_year", "max"),
        )
    )

    return summary
