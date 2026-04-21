"""
src/pr_ngvla/data/ghcnh.py
=========================

Helpers for the NOAA GHCNh metadata stage used in the Puerto Rico ngVLA
validation workflow.

Purpose
-------
Build a Puerto Rico GHCNh station inventory from NOAA official metadata:

- ghcnh-station-list(.csv or .txt)
- ghcnh-inventory.txt

This stage is metadata-only. It does NOT download hourly observations.
It is used to:
1. map GHCNh stations in Puerto Rico,
2. define the validation-ready hourly candidate subset for 2004-2023.

Design
------
- Pure library logic; no file writing here.
- Scripts should orchestrate loading, calling these functions, and saving.
- Column handling is deliberately defensive because NOAA metadata files may
  be provided in multiple plain-text formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


MONTH_COLS: tuple[str, ...] = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)

STATION_LIST_FWF_WIDTHS: list[int] = [11, 1, 8, 1, 9, 1, 6, 1, 2, 1, 30, 1, 3, 1, 3, 1, 5, 1, 4]
STATION_LIST_FWF_NAMES: list[str] = [
    "id", "_1", "latitude", "_2", "longitude", "_3", "elevation",
    "_4", "state", "_5", "name", "_6", "gsn_flag", "_7",
    "hcn_crn_flag", "_8", "wmo_id", "_9", "icao"
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy with stripped, lower-case column names.
    """
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def require_columns(
    df: pd.DataFrame,
    required: Iterable[str],
    *,
    context: str = "",
) -> None:
    """
    Raise a clear error if required columns are missing.
    """
    missing = sorted(set(required) - set(df.columns))
    if missing:
        ctx = f" for {context}" if context else ""
        raise ValueError(
            f"Missing columns{ctx}: {missing}. "
            f"Available: {sorted(df.columns)}"
        )


def pick_first_present(
    df: pd.DataFrame,
    candidates: Sequence[str],
    *,
    context: str,
) -> str:
    """
    Return the first candidate column present in the DataFrame.
    """
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(
        f"None of the candidate columns were found for {context}: "
        f"{list(candidates)}. Available: {sorted(df.columns)}"
    )


def coerce_nullable_int(series: pd.Series) -> pd.Series:
    """
    Convert to pandas nullable Int64.
    """
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def coerce_float(series: pd.Series) -> pd.Series:
    """
    Convert to float with NaN on errors.
    """
    return pd.to_numeric(series, errors="coerce")


def has_year_overlap(
    start_year: pd.Series,
    end_year: pd.Series,
    *,
    study_start_year: int,
    study_end_year: int,
) -> pd.Series:
    """
    Return True when [start_year, end_year] overlaps the study window.
    """
    return (
        start_year.notna()
        & end_year.notna()
        & (end_year >= study_start_year)
        & (start_year <= study_end_year)
    )


def overlap_year_count(
    start_year: pd.Series,
    end_year: pd.Series,
    *,
    study_start_year: int,
    study_end_year: int,
) -> pd.Series:
    """
    Inclusive count of overlapping years with the study window.
    """
    clipped_start = start_year.clip(lower=study_start_year)
    clipped_end = end_year.clip(upper=study_end_year)

    years = clipped_end - clipped_start + 1
    years = years.where(start_year.notna() & end_year.notna(), pd.NA)
    years = years.where(years > 0, 0)

    return years.astype("Int64")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_ghcnh_station_list(path: Path) -> pd.DataFrame:
    """
    Load NOAA GHCNh station-list metadata.

    Supports:
    - ghcnh-station-list.csv
    - ghcnh-station-list.txt (fixed width)

    Returns a raw DataFrame that is standardized later.
    """
    path = Path(path)

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        return df

    # Fixed-width fallback using the official field layout from NOAA docs.
    df = pd.read_fwf(
        path,
        widths=STATION_LIST_FWF_WIDTHS,
        names=STATION_LIST_FWF_NAMES,
        dtype=str,
    )
    keep_cols = [c for c in df.columns if not c.startswith("_")]
    return df[keep_cols].copy()


def load_ghcnh_inventory(path: Path) -> pd.DataFrame:
    """
    Load NOAA GHCNh inventory metadata.

    Based on the file observed in this project, ghcnh-inventory.txt has a
    whitespace-delimited header row like:

        GHCNh_ID YEAR JAN FEB ... DEC

    This loader tries:
    1. normal CSV parsing,
    2. whitespace-delimited parsing with header row.

    If neither yields the expected structure, it raises a clear error.
    """
    path = Path(path)

    # Try regular CSV first.
    try:
        df_csv = pd.read_csv(path)
        df_csv = normalize_columns(df_csv)
        if {"ghcnh_id", "year", *MONTH_COLS}.issubset(df_csv.columns):
            return df_csv
        if {"id", "year", *MONTH_COLS}.issubset(df_csv.columns):
            return df_csv
    except Exception:
        pass

    # Fallback: whitespace-delimited with header row present.
    try:
        df_ws = pd.read_csv(
            path,
            sep=r"\s+",
            header=0,
            dtype=str,
            engine="python",
        )
        df_ws = normalize_columns(df_ws)

        if {"ghcnh_id", "year", *MONTH_COLS}.issubset(df_ws.columns):
            return df_ws
        if {"id", "year", *MONTH_COLS}.issubset(df_ws.columns):
            return df_ws

        raise ValueError(
            f"Unexpected GHCNh inventory columns: {sorted(df_ws.columns)}"
        )
    except Exception as exc:
        raise ValueError(
            "Could not parse GHCNh inventory file with the expected structure."
        ) from exc


# ---------------------------------------------------------------------------
# Standardizers
# ---------------------------------------------------------------------------

def standardize_ghcnh_station_list(df_station_list: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize the GHCNh station list to the project schema.

    The downloaded CSV in this project uses `ghcn_id` as the station id field.
    """
    df = normalize_columns(df_station_list)

    id_col = pick_first_present(
        df,
        ("id", "ghcnh_id", "ghcn_id"),
        context="GHCNh station list id",
    )
    lat_col = pick_first_present(
        df,
        ("latitude", "lat"),
        context="GHCNh station list latitude",
    )
    lon_col = pick_first_present(
        df,
        ("longitude", "lon"),
        context="GHCNh station list longitude",
    )
    elev_col = pick_first_present(
        df,
        ("elevation", "elevation_m"),
        context="GHCNh station list elevation",
    )
    name_col = pick_first_present(
        df,
        ("name", "station_name"),
        context="GHCNh station list name",
    )

    out = df.copy()
    out["station_id"] = out[id_col].astype(str).str.strip()
    out["lat"] = coerce_float(out[lat_col])
    out["lon"] = coerce_float(out[lon_col])
    out["elevation_m"] = coerce_float(out[elev_col])
    out["station_name"] = out[name_col].astype(str).str.strip()

    out["state"] = out["state"].astype(str).str.strip() if "state" in out.columns else ""
    out["wmo_id"] = out["wmo_id"].astype(str).str.strip() if "wmo_id" in out.columns else ""
    out["icao"] = out["icao"].astype(str).str.strip() if "icao" in out.columns else ""

    out["source"] = "ghcnh"

    return out[
        [
            "station_id",
            "station_name",
            "lat",
            "lon",
            "elevation_m",
            "state",
            "wmo_id",
            "icao",
            "source",
        ]
    ].copy()


def standardize_ghcnh_inventory(df_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize the GHCNh inventory to station-year monthly record counts.
    """
    df = normalize_columns(df_inventory)

    id_col = pick_first_present(
        df,
        ("id", "ghcnh_id", "ghcn_id"),
        context="GHCNh inventory id",
    )

    require_columns(
        df,
        required={id_col, "year", *MONTH_COLS},
        context="GHCNh inventory",
    )

    out = df.copy()
    out["station_id"] = out[id_col].astype(str).str.strip()
    out["year"] = coerce_nullable_int(out["year"])

    for col in MONTH_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["annual_obs_count"] = out[list(MONTH_COLS)].sum(axis=1)
    out["source"] = "ghcnh"

    return out[["station_id", "year", *MONTH_COLS, "annual_obs_count", "source"]].copy()


def summarize_ghcnh_inventory_period(df_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize GHCNh inventory to one row per station with start/end year and
    number of years with positive records.
    """
    df = standardize_ghcnh_inventory(df_inventory)
    df = df[df["annual_obs_count"] > 0].copy()

    if df.empty:
        return pd.DataFrame(
            columns=["station_id", "source", "start_year", "end_year", "n_years_positive"]
        )

    out = (
        df.groupby(["source", "station_id"], as_index=False)
        .agg(
            start_year=("year", "min"),
            end_year=("year", "max"),
            n_years_positive=("year", "nunique"),
        )
    )
    return out


# ---------------------------------------------------------------------------
# Spatial filters
# ---------------------------------------------------------------------------

def filter_to_bbox(
    df_stations: pd.DataFrame,
    *,
    south: float,
    west: float,
    north: float,
    east: float,
) -> pd.DataFrame:
    """
    Apply the project bounding box filter to station coordinates.
    """
    df = df_stations.copy()
    mask = (
        df["lat"].between(south, north, inclusive="both")
        & df["lon"].between(west, east, inclusive="both")
    )
    return df.loc[mask].copy().reset_index(drop=True)


def stations_to_gdf(df_stations: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert a station table with lon/lat to a GeoDataFrame in EPSG:4326.
    """
    df = df_stations.copy()
    geometry = [Point(xy) for xy in zip(df["lon"], df["lat"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def filter_to_pr_territory(
    df_stations: pd.DataFrame,
    *,
    land_union,
) -> pd.DataFrame:
    """
    Keep only stations intersecting the strict Puerto Rico territory geometry.

    Uses the dissolved municipality land polygon, consistent with the project
    coastline/masking strategy.
    """
    gdf = stations_to_gdf(df_stations)
    mask = gdf.geometry.intersects(land_union)
    return pd.DataFrame(gdf.loc[mask].drop(columns="geometry")).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Inventory builders
# ---------------------------------------------------------------------------

def build_ghcnh_master_inventory(
    df_station_list: pd.DataFrame,
    df_inventory_summary: pd.DataFrame,
    *,
    study_start_year: int,
    study_end_year: int,
) -> pd.DataFrame:
    """
    Merge GHCNh station metadata with summarized inventory period and keep only
    validation-ready stations that overlap the study window.

    This function accepts either:
    1. a raw GHCNh station-list table, or
    2. an already standardized station table.
    """
    station_df = normalize_columns(df_station_list)

    # Accept either raw or already-standardized station metadata.
    standardized_cols = {
        "station_id",
        "station_name",
        "lat",
        "lon",
        "elevation_m",
        "source",
    }

    if standardized_cols.issubset(station_df.columns):
        stations = station_df.copy()
    else:
        stations = standardize_ghcnh_station_list(df_station_list)

    inv = df_inventory_summary.copy()

    out = stations.merge(inv, on=["source", "station_id"], how="left")

    out["study_overlap"] = has_year_overlap(
        out["start_year"],
        out["end_year"],
        study_start_year=study_start_year,
        study_end_year=study_end_year,
    )
    out["years_with_data"] = overlap_year_count(
        out["start_year"],
        out["end_year"],
        study_start_year=study_start_year,
        study_end_year=study_end_year,
    )
    out["prelim_usable"] = out["study_overlap"]

    out = out[out["study_overlap"]].copy().reset_index(drop=True)
    return out


def build_station_inventory_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a minimal one-table summary for station inventory subsets.
    """
    if df.empty:
        return pd.DataFrame(
            [{"source": "ghcnh", "n_stations": 0, "min_start_year": pd.NA, "max_end_year": pd.NA}]
        )

    min_start = pd.to_numeric(df["start_year"], errors="coerce").min() if "start_year" in df.columns else pd.NA
    max_end = pd.to_numeric(df["end_year"], errors="coerce").max() if "end_year" in df.columns else pd.NA

    return pd.DataFrame(
        [
            {
                "source": "ghcnh",
                "n_stations": int(len(df)),
                "min_start_year": min_start,
                "max_end_year": max_end,
            }
        ]
    )
