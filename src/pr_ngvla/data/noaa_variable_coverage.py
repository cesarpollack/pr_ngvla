from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd

from pr_ngvla.config import STUDY_YEAR_END, STUDY_YEAR_START
from pr_ngvla.data.noaa import _combine_isd_station_id

# ---------------------------------------------------------------------------
# Canonical variables
# ---------------------------------------------------------------------------

CANONICAL_VARIABLES: tuple[str, ...] = (
    "temperature",
    "dewpoint_rh",
    "wind",
    "precipitation",
)


# ---------------------------------------------------------------------------
# Native-to-canonical mapping specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VariableCoverageSpec:
    """
    Mapping from one source's native inventory keys to one canonical variable.
    """
    variable: str
    source: str
    native_keys: tuple[str, ...]
    native_timescale: str


# GHCND inventory is yearly by element.
# Conservative mapping only.
GHCND_SPECS: tuple[VariableCoverageSpec, ...] = (
    VariableCoverageSpec(
        variable="temperature",
        source="ghcnd",
        native_keys=("TMIN", "TMAX", "TAVG"),
        native_timescale="daily",
    ),
    VariableCoverageSpec(
        variable="wind",
        source="ghcnd",
        native_keys=("AWND",),
        native_timescale="daily",
    ),
    VariableCoverageSpec(
        variable="precipitation",
        source="ghcnd",
        native_keys=("PRCP",),
        native_timescale="daily",
    ),
)

# ISD inventory is station-year observation coverage, not variable-level metadata.
# We use it conservatively as a temporal-coverage proxy for core hourly meteorology.
ISD_SPECS: tuple[VariableCoverageSpec, ...] = (
    VariableCoverageSpec(
        variable="temperature",
        source="isd",
        native_keys=("station_year_obs_count",),
        native_timescale="hourly",
    ),
    VariableCoverageSpec(
        variable="dewpoint_rh",
        source="isd",
        native_keys=("station_year_obs_count",),
        native_timescale="hourly",
    ),
    VariableCoverageSpec(
        variable="wind",
        source="isd",
        native_keys=("station_year_obs_count",),
        native_timescale="hourly",
    ),
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

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
    Raise a clear error if any required columns are missing.
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

    Example:
      station span 2010-2012, study span 2004-2023 -> 3
      station span 1990-2003, study span 2004-2023 -> 0
    """
    clipped_start = start_year.clip(lower=study_start_year)
    clipped_end = end_year.clip(upper=study_end_year)

    years = clipped_end - clipped_start + 1
    years = years.where(start_year.notna() & end_year.notna(), pd.NA)
    years = years.where(years > 0, 0)

    return years.astype("Int64")


def long_form_columns() -> list[str]:
    """
    Standard output schema for the long-form coverage table.
    """
    return [
        "station_id",
        "source",
        "variable",
        "native_datatype",
        "native_timescale",
        "start_year",
        "end_year",
        "years_with_data",
        "study_overlap",
        "prelim_usable",
        "notes",
    ]


# ---------------------------------------------------------------------------
# ISD-specific helpers
# ---------------------------------------------------------------------------

MONTH_COLS: tuple[str, ...] = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)

def combine_isd_station_id(usaf: pd.Series, wban: pd.Series) -> pd.Series:
    """
    Build the canonical ISD station identifier using the same helper
    used by the NOAA module, to avoid station-id drift.
    """
    return _combine_isd_station_id(usaf, wban).astype(str).str.strip()


# ---------------------------------------------------------------------------
# Standardizers
# ---------------------------------------------------------------------------

def standardize_master_inventory(master_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize the validation-ready master station inventory.

    Required logical fields:
    - station id
    - source

    Accepted station id aliases:
    - station_id
    - id

    Accepted source aliases:
    - source
    """
    df = normalize_columns(master_inventory)

    station_id_col = pick_first_present(
        df,
        ("station_id", "id"),
        context="master inventory station id",
    )
    source_col = pick_first_present(
        df,
        ("source",),
        context="master inventory source",
    )

    out = df.rename(
        columns={
            station_id_col: "station_id",
            source_col: "source",
        }
    ).copy()

    out["station_id"] = out["station_id"].astype(str).str.strip()
    out["source"] = out["source"].astype(str).str.strip().str.lower()

    return (
        out[["station_id", "source"]]
        .drop_duplicates()
        .sort_values(["source", "station_id"], kind="stable")
        .reset_index(drop=True)
    )


def standardize_ghcnd_inventory(ghcnd_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize GHCND inventory metadata to:
      station_id, element, start_year, end_year, source

    Accepted aliases:
    - station_id / id
    - element
    - first_year / start_year / year_start
    - last_year / end_year / year_end
    """
    df = normalize_columns(ghcnd_inventory)

    station_id_col = pick_first_present(
        df,
        ("station_id", "id"),
        context="GHCND inventory station id",
    )
    element_col = pick_first_present(
        df,
        ("element",),
        context="GHCND inventory element",
    )
    start_year_col = pick_first_present(
        df,
        ("first_year", "start_year", "year_start"),
        context="GHCND inventory start year",
    )
    end_year_col = pick_first_present(
        df,
        ("last_year", "end_year", "year_end"),
        context="GHCND inventory end year",
    )

    out = df.rename(
        columns={
            station_id_col: "station_id",
            element_col: "element",
            start_year_col: "start_year",
            end_year_col: "end_year",
        }
    ).copy()

    out["station_id"] = out["station_id"].astype(str).str.strip()
    out["element"] = out["element"].astype(str).str.strip().str.upper()
    out["start_year"] = coerce_nullable_int(out["start_year"])
    out["end_year"] = coerce_nullable_int(out["end_year"])
    out["source"] = "ghcnd"

    return out[["station_id", "element", "start_year", "end_year", "source"]]


def standardize_isd_inventory(isd_inventory: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize ISD inventory metadata to station-year observation coverage.

    Expected logical fields from NOAA ISD inventory:
    - usaf
    - wban
    - year
    - jan ... dec

    Important
    ---------
    NOAA's ISD inventory is not variable-level metadata. It reports the number
    of observations available by station, year, and month. We therefore use it
    as a station-year coverage proxy for core hourly ISD meteorology, not as
    proof of variable-specific availability.
    """
    df = normalize_columns(isd_inventory)

    require_columns(
        df,
        required={"usaf", "wban", "year", *MONTH_COLS},
        context="ISD inventory",
    )

    out = df.copy()
    out["station_id"] = combine_isd_station_id(out["usaf"], out["wban"])
    out["year"] = coerce_nullable_int(out["year"])

    for col in MONTH_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["annual_obs_count"] = out[list(MONTH_COLS)].sum(axis=1)
    out["source"] = "isd"

    return out[["station_id", "year", "annual_obs_count", "source"]]


# ---------------------------------------------------------------------------
# Source-specific builders
# ---------------------------------------------------------------------------

def build_ghcnd_variable_coverage(
    master_inventory: pd.DataFrame,
    ghcnd_inventory: pd.DataFrame,
    *,
    study_start_year: int = STUDY_YEAR_START,
    study_end_year: int = STUDY_YEAR_END,
    specs: tuple[VariableCoverageSpec, ...] = GHCND_SPECS,
) -> pd.DataFrame:
    """
    Build long-form variable coverage rows for GHCND master stations.
    """
    master = standardize_master_inventory(master_inventory)
    master = master[master["source"] == "ghcnd"].copy()

    inv = standardize_ghcnd_inventory(ghcnd_inventory)

    rows: list[pd.DataFrame] = []

    for spec in specs:
        sub = inv[inv["element"].isin(spec.native_keys)].copy()
        if sub.empty:
            continue

        grouped = (
            sub.groupby(["source", "station_id"], as_index=False)
            .agg(
                native_datatype=("element", lambda s: "|".join(sorted(set(map(str, s))))),
                start_year=("start_year", "min"),
                end_year=("end_year", "max"),
            )
        )

        grouped["variable"] = spec.variable
        grouped["native_timescale"] = spec.native_timescale
        grouped["study_overlap"] = has_year_overlap(
            grouped["start_year"],
            grouped["end_year"],
            study_start_year=study_start_year,
            study_end_year=study_end_year,
        )
        grouped["years_with_data"] = overlap_year_count(
            grouped["start_year"],
            grouped["end_year"],
            study_start_year=study_start_year,
            study_end_year=study_end_year,
        )
        grouped["prelim_usable"] = grouped["study_overlap"]
        grouped["notes"] = pd.NA

        rows.append(grouped)

    if not rows:
        return pd.DataFrame(columns=long_form_columns())

    out = pd.concat(rows, ignore_index=True)
    out = master.merge(out, on=["source", "station_id"], how="left")
    out = out.dropna(subset=["variable"]).reset_index(drop=True)

    return out[long_form_columns()]


def build_isd_variable_coverage(
    master_inventory: pd.DataFrame,
    isd_inventory: pd.DataFrame,
    *,
    study_start_year: int = STUDY_YEAR_START,
    study_end_year: int = STUDY_YEAR_END,
    specs: tuple[VariableCoverageSpec, ...] = ISD_SPECS,
) -> pd.DataFrame:
    """
    Build long-form variable coverage rows for ISD master stations.

    Notes
    -----
    The NOAA ISD inventory is station-year observation metadata, not
    variable-level metadata. Here we use positive station-year observation
    counts as a conservative temporal-coverage proxy for the core hourly ISD
    meteorological variables:
      - temperature
      - dewpoint_rh
      - wind

    Precipitation is not inferred from ISD inventory at this stage because the
    inventory does not encode variable-specific presence.
    """
    master = standardize_master_inventory(master_inventory)
    master = master[master["source"] == "isd"].copy()

    inv = standardize_isd_inventory(isd_inventory)
    inv = inv[inv["annual_obs_count"] > 0].copy()

    if inv.empty:
        return pd.DataFrame(columns=long_form_columns())

    grouped = (
        inv.groupby(["source", "station_id"], as_index=False)
        .agg(
            start_year=("year", "min"),
            end_year=("year", "max"),
        )
    )

    rows: list[pd.DataFrame] = []

    for spec in specs:
        tmp = grouped.copy()
        tmp["variable"] = spec.variable
        tmp["native_datatype"] = "station_year_obs_count"
        tmp["native_timescale"] = spec.native_timescale
        tmp["study_overlap"] = has_year_overlap(
            tmp["start_year"],
            tmp["end_year"],
            study_start_year=study_start_year,
            study_end_year=study_end_year,
        )
        tmp["years_with_data"] = overlap_year_count(
            tmp["start_year"],
            tmp["end_year"],
            study_start_year=study_start_year,
            study_end_year=study_end_year,
        )
        tmp["prelim_usable"] = tmp["study_overlap"]
        tmp["notes"] = (
            "ISD inventory is station-year observation coverage, not "
            "variable-level metadata; used here as a proxy for core hourly "
            "ISD meteorology."
        )
        rows.append(tmp)

    out = pd.concat(rows, ignore_index=True)
    out = master.merge(out, on=["source", "station_id"], how="left")
    out = out.dropna(subset=["variable"]).reset_index(drop=True)

    return out[long_form_columns()]


# ---------------------------------------------------------------------------
# Combined public builders
# ---------------------------------------------------------------------------

def build_noaa_variable_coverage_long(
    master_inventory: pd.DataFrame,
    ghcnd_inventory: pd.DataFrame,
    isd_inventory: pd.DataFrame,
    *,
    study_start_year: int = STUDY_YEAR_START,
    study_end_year: int = STUDY_YEAR_END,
) -> pd.DataFrame:
    """
    Build the combined long-form NOAA variable coverage table.

    Returns one row per station-source-variable combination.
    """
    ghcnd_cov = build_ghcnd_variable_coverage(
        master_inventory=master_inventory,
        ghcnd_inventory=ghcnd_inventory,
        study_start_year=study_start_year,
        study_end_year=study_end_year,
    )
    isd_cov = build_isd_variable_coverage(
        master_inventory=master_inventory,
        isd_inventory=isd_inventory,
        study_start_year=study_start_year,
        study_end_year=study_end_year,
    )

    out = pd.concat([ghcnd_cov, isd_cov], ignore_index=True)

    return (
        out.sort_values(
            ["source", "station_id", "variable", "start_year", "end_year"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_noaa_variable_coverage_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the long-form coverage table to one row per station-source pair.

    Output fields:
    - <variable>_available
    - <variable>_start_year
    - <variable>_end_year
    - n_variables_available
    """
    df = normalize_columns(long_df)

    require_columns(
        df,
        required={
            "station_id",
            "source",
            "variable",
            "start_year",
            "end_year",
            "prelim_usable",
        },
        context="NOAA variable coverage long table",
    )

    availability = (
        df.groupby(["source", "station_id", "variable"], as_index=False)
        .agg(
            available=("prelim_usable", "max"),
            start_year=("start_year", "min"),
            end_year=("end_year", "max"),
        )
    )

    base = availability[["source", "station_id"]].drop_duplicates().reset_index(drop=True)

    for variable in CANONICAL_VARIABLES:
        sub = availability[availability["variable"] == variable].copy()
        if sub.empty:
            continue

        sub = sub.rename(
            columns={
                "available": f"{variable}_available",
                "start_year": f"{variable}_start_year",
                "end_year": f"{variable}_end_year",
            }
        )

        base = base.merge(
            sub[
                [
                    "source",
                    "station_id",
                    f"{variable}_available",
                    f"{variable}_start_year",
                    f"{variable}_end_year",
                ]
            ],
            on=["source", "station_id"],
            how="left",
        )

    for variable in CANONICAL_VARIABLES:
        avail_col = f"{variable}_available"
        if avail_col not in base.columns:
            base[avail_col] = False
        else:
            base[avail_col] = base[avail_col].fillna(False)

    base["n_variables_available"] = (
        base[[f"{v}_available" for v in CANONICAL_VARIABLES]]
        .astype(int)
        .sum(axis=1)
    )

    return (
        base.sort_values(["source", "station_id"], kind="stable")
        .reset_index(drop=True)
    )


def summarize_variable_coverage(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple summary table for quick QC.

    Returns one row per source-variable with:
    - n_station_variable_rows
    - n_prelim_usable
    """
    df = normalize_columns(long_df)

    require_columns(
        df,
        required={"source", "variable", "prelim_usable"},
        context="NOAA variable coverage summary",
    )

    return (
        df.groupby(["source", "variable"], as_index=False)
        .agg(
            n_station_variable_rows=("station_id", "count"),
            n_prelim_usable=("prelim_usable", "sum"),
        )
        .sort_values(["source", "variable"], kind="stable")
        .reset_index(drop=True)
    )
