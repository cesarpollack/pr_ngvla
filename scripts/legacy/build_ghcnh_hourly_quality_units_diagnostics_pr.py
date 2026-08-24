#!/usr/bin/env python3
"""
build_ghcnh_hourly_quality_units_diagnostics_pr.py

Diagnóstico de unidades, códigos de calidad y valores extremos para GHCNh
horario en Puerto Rico.

Este script NO descarga datos.
Este script NO elimina datos.
Este script NO corrige unidades automáticamente.
Este script NO genera todavía la tabla limpia para comparar contra ERA5.

Objetivo de esta etapa
----------------------
Después de descargar y diagnosticar cobertura real, vimos que las variables core
sí existen, pero algunas tienen valores extremos físicamente sospechosos.

Ejemplos observados en el resumen previo:
    temperature max              = 928
    dew_point_temperature max    = 285
    relative_humidity max        = 464408
    wind_speed max               = 389.2
    station_level_pressure min   = 101.4

La meta de este script es localizar esos valores y entender si están asociados
con:
    - códigos de calidad
    - códigos de medición
    - report type
    - source code
    - estaciones específicas
    - años o meses específicos
    - valores sentinela/missing/overflow

Decisión metodológica importante
--------------------------------
Aunque documentación de GHCNh/legacy puede mencionar décimas para algunas
variables, en los Parquet descargados los valores promedio de temperatura y
dew point ya parecen estar en unidades físicas razonables para Puerto Rico.
Por eso este script NO divide automáticamente por 10.

En lugar de eso, produce diagnósticos con:
    - valor bruto leído desde Parquet
    - valor hipotético dividido entre 10
    - rango físico amplio esperado
    - códigos asociados

Luego, con evidencia, se define la limpieza final en otro script.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Variables core del proyecto
# ---------------------------------------------------------------------------

CORE_VARIABLES = [
    "temperature",
    "dew_point_temperature",
    "relative_humidity",
    "wind_speed",
    "station_level_pressure",
    "precipitation",
]


# ---------------------------------------------------------------------------
# Rangos físicos amplios para diagnóstico inicial
# ---------------------------------------------------------------------------
#
# Estos NO son reglas finales de limpieza.
# Son rangos conservadores para encontrar valores que necesitan revisión.
#
# Para Puerto Rico, algunos rangos son deliberadamente amplios.
# Por ejemplo, wind_speed <= 75 m/s es mucho más alto que condiciones normales,
# pero ayuda a detectar solo valores extremadamente sospechosos.

BROAD_RANGES = {
    "temperature": {
        "unit": "degC",
        "min": -10.0,
        "max": 45.0,
        "notes": "Broad diagnostic range for air temperature in Puerto Rico.",
    },
    "dew_point_temperature": {
        "unit": "degC",
        "min": -20.0,
        "max": 35.0,
        "notes": "Broad diagnostic range for dew point temperature in Puerto Rico.",
    },
    "relative_humidity": {
        "unit": "percent",
        "min": 0.0,
        "max": 100.0,
        "notes": "Physical range for relative humidity percentage.",
    },
    "wind_speed": {
        "unit": "m/s",
        "min": 0.0,
        "max": 75.0,
        "notes": "Very broad diagnostic range; values above this require review.",
    },
    "station_level_pressure": {
        "unit": "hPa",
        "min": 850.0,
        "max": 1050.0,
        "notes": "Broad range for surface/station pressure in Puerto Rico elevations.",
    },
    "precipitation": {
        "unit": "mm",
        "min": 0.0,
        "max": 500.0,
        "notes": "Broad diagnostic range for precipitation per reported interval.",
    },
}


# ---------------------------------------------------------------------------
# Column suffixes used by GHCNh files
# ---------------------------------------------------------------------------

RELATED_SUFFIXES = {
    "measurement_code": "_Measurement_Code",
    "quality_code": "_Quality_Code",
    "report_type": "_Report_Type",
    "source_code": "_Source_Code",
    "source_station_id": "_Source_Station_ID",
}


# ---------------------------------------------------------------------------
# Dataclasses for tabular outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitsReferenceRow:
    """
    Human-readable reference table for expected units and how we treat them
    in this diagnostic stage.
    """

    variable: str
    expected_unit: str
    broad_min: float
    broad_max: float
    scale_applied_in_this_script: float
    value_used_for_diagnostics: str
    notes: str


@dataclass(frozen=True)
class OutOfRangeCountRow:
    """
    Counts by station-year-month-variable.

    This is the main table to identify where suspicious values are concentrated.
    """

    station_id: str | None
    station_name: str | None
    year: int | None
    month: int | None
    variable: str
    expected_unit: str
    broad_min: float
    broad_max: float
    n_rows: int
    n_numeric: int
    n_inside_range: int
    n_below_range: int
    n_above_range: int
    n_out_of_range: int
    fraction_out_of_range: float | None
    min_value: float | None
    max_value: float | None
    mean_value: float | None


@dataclass(frozen=True)
class CodeSummaryRow:
    """
    Aggregated summary for quality/measurement/source/report codes.
    """

    variable: str
    code_type: str
    code_value: str
    n_rows: int
    n_numeric: int
    n_out_of_range: int
    fraction_out_of_range: float | None
    min_value: float | None
    max_value: float | None
    station_count: int
    year_count: int


@dataclass(frozen=True)
class ExtremeExampleRow:
    """
    Example rows for suspicious values.

    This table is intentionally not meant to include every bad value.
    It stores representative examples and global extremes.
    """

    reason: str
    station_id: str | None
    station_name: str | None
    datetime: str | None
    year: int | None
    month: int | None
    variable: str
    raw_value: float | None
    value_divided_by_10: float | None
    expected_unit: str
    broad_min: float
    broad_max: float
    measurement_code: str | None
    quality_code: str | None
    report_type: str | None
    source_code: str | None
    source_station_id: str | None
    raw_file: str


@dataclass(frozen=True)
class ScaleSanityRow:
    """
    Quantile table to check whether a global scale factor appears plausible.

    We compute quantiles for the raw values and for raw/10.
    This does not apply scaling; it just helps decide later.
    """

    variable: str
    interpretation: str
    n_numeric: int
    q00_min: float | None
    q01: float | None
    q05: float | None
    q50_median: float | None
    q95: float | None
    q99: float | None
    q100_max: float | None


@dataclass(frozen=True)
class PreliminaryRecommendationRow:
    """
    Preliminary recommendation for later cleaning.

    This is NOT enforced by this script.
    """

    variable: str
    recommendation_type: str
    recommendation: str
    rationale: str


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def parse_datetime_column(df: pd.DataFrame) -> pd.Series:
    """
    Parse DATE column safely.

    We keep this as a naive datetime for now. Time-zone alignment for ERA5
    comparison is a separate stage.
    """
    if "DATE" not in df.columns:
        return pd.Series(pd.NaT, index=df.index)

    return pd.to_datetime(df["DATE"], errors="coerce")


def safe_first_value(df: pd.DataFrame, column: str) -> str | None:
    """
    Return first non-null value from a column.
    """
    if column not in df.columns:
        return None

    values = df[column].dropna()
    if values.empty:
        return None

    return str(values.iloc[0])


def safe_year_from_path(path: Path) -> int | None:
    """
    Extract year from path components.
    """
    for part in path.parts:
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def numeric_series(df: pd.DataFrame, variable: str) -> pd.Series:
    """
    Convert variable to numeric for diagnostics.

    This does not modify raw files.
    """
    if variable not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")

    return pd.to_numeric(df[variable], errors="coerce")


def get_related_column(df: pd.DataFrame, variable: str, suffix_key: str) -> pd.Series:
    """
    Return a related metadata/code column for a variable.

    Example:
        variable='temperature', suffix_key='quality_code'
        -> temperature_Quality_Code

    If the column does not exist, return an NA series.
    """
    suffix = RELATED_SUFFIXES[suffix_key]
    column = f"{variable}{suffix}"

    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="object")

    return df[column]


def clean_code_value(value: Any) -> str:
    """
    Normalize a code value for grouping.

    Blank or missing values become '<blank>'.
    """
    if pd.isna(value):
        return "<blank>"

    s = str(value).strip()
    if s == "":
        return "<blank>"

    return s


def broad_range_for(variable: str) -> tuple[float, float, str]:
    """
    Return broad min, max and unit for a variable.
    """
    info = BROAD_RANGES[variable]
    return float(info["min"]), float(info["max"]), str(info["unit"])


def out_of_range_masks(values: pd.Series, variable: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Build boolean masks:
        below range
        above range
        outside range

    Missing/non-numeric values are not counted as below/above.
    """
    vmin, vmax, _ = broad_range_for(variable)

    numeric_mask = values.notna()
    below = numeric_mask & (values < vmin)
    above = numeric_mask & (values > vmax)
    outside = below | above

    return below, above, outside


def none_if_nan(value: Any) -> float | None:
    """
    Convert NaN-like scalar to None for cleaner CSV/Parquet outputs.
    """
    if pd.isna(value):
        return None
    return float(value)


def value_at(series: pd.Series, idx: Any) -> str | None:
    """
    Safely extract a string value at an index.
    """
    try:
        value = series.loc[idx]
    except Exception:
        return None

    if pd.isna(value):
        return None

    s = str(value).strip()
    if s == "":
        return None

    return s


# ---------------------------------------------------------------------------
# Units reference and recommendations
# ---------------------------------------------------------------------------

def build_units_reference() -> pd.DataFrame:
    """
    Create a simple units reference table.

    The important point is that this diagnostic script applies scale factor 1.0.
    """
    rows: list[UnitsReferenceRow] = []

    for variable in CORE_VARIABLES:
        info = BROAD_RANGES[variable]
        rows.append(
            UnitsReferenceRow(
                variable=variable,
                expected_unit=str(info["unit"]),
                broad_min=float(info["min"]),
                broad_max=float(info["max"]),
                scale_applied_in_this_script=1.0,
                value_used_for_diagnostics="raw numeric value read from Parquet",
                notes=str(info["notes"]),
            )
        )

    return pd.DataFrame([r.__dict__ for r in rows])


def build_preliminary_recommendations() -> pd.DataFrame:
    """
    Human-readable recommendations for the next cleaning stage.

    These are intentionally conservative.
    """
    rows = [
        PreliminaryRecommendationRow(
            variable="temperature",
            recommendation_type="scale",
            recommendation="Do not apply global division by 10 until confirmed by station-level distributions.",
            rationale="Puerto Rico mean temperature from raw Parquet values appears physically plausible; isolated extremes require quality review.",
        ),
        PreliminaryRecommendationRow(
            variable="dew_point_temperature",
            recommendation_type="scale",
            recommendation="Do not apply global division by 10 until confirmed by station-level distributions.",
            rationale="Puerto Rico mean dew point from raw Parquet values appears physically plausible; isolated extremes require quality review.",
        ),
        PreliminaryRecommendationRow(
            variable="relative_humidity",
            recommendation_type="physical_range",
            recommendation="Treat numeric values outside 0–100% as invalid for physical comparison unless a documented correction is identified.",
            rationale="Relative humidity is a percentage; values far above 100 indicate quality/source/sentinel issues.",
        ),
        PreliminaryRecommendationRow(
            variable="wind_speed",
            recommendation_type="physical_range",
            recommendation="Flag very large wind speeds and inspect Quality_Code and Source_Code before cleaning.",
            rationale="Extremely high values are not physically plausible for station wind speed and may reflect source-specific issues.",
        ),
        PreliminaryRecommendationRow(
            variable="station_level_pressure",
            recommendation_type="physical_range",
            recommendation="Flag pressure values outside the broad hPa range and inspect associated codes.",
            rationale="Station pressure should be broadly near surface pressure; very low values suggest invalid or miscoded observations.",
        ),
        PreliminaryRecommendationRow(
            variable="precipitation",
            recommendation_type="interval_definition",
            recommendation="Do not compare precipitation to ERA5 until the reported accumulation interval is clarified.",
            rationale="GHCNh includes multiple precipitation interval fields; the main precipitation column must be interpreted carefully.",
        ),
        PreliminaryRecommendationRow(
            variable="all",
            recommendation_type="quality_codes",
            recommendation="Before ERA5 comparison, define which Quality_Code values are acceptable for each variable.",
            rationale="GHCNh preserves source-specific and general quality flags; invalid values should not enter RMSE/MBE/correlation.",
        ),
    ]

    return pd.DataFrame([r.__dict__ for r in rows])


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def summarize_out_of_range_for_period(
    *,
    station_id: str | None,
    station_name: str | None,
    year: int | None,
    month: int | None,
    variable: str,
    values: pd.Series,
) -> OutOfRangeCountRow:
    """
    Count out-of-range values for one station-year or station-year-month.
    """
    vmin, vmax, unit = broad_range_for(variable)

    numeric_mask = values.notna()
    below, above, outside = out_of_range_masks(values, variable)

    n_rows = int(len(values))
    n_numeric = int(numeric_mask.sum())
    n_below = int(below.sum())
    n_above = int(above.sum())
    n_outside = int(outside.sum())
    n_inside = int((numeric_mask & ~outside).sum())

    if n_numeric > 0:
        fraction = n_outside / n_numeric
        min_value = float(values[numeric_mask].min())
        max_value = float(values[numeric_mask].max())
        mean_value = float(values[numeric_mask].mean())
    else:
        fraction = None
        min_value = None
        max_value = None
        mean_value = None

    return OutOfRangeCountRow(
        station_id=station_id,
        station_name=station_name,
        year=year,
        month=month,
        variable=variable,
        expected_unit=unit,
        broad_min=vmin,
        broad_max=vmax,
        n_rows=n_rows,
        n_numeric=n_numeric,
        n_inside_range=n_inside,
        n_below_range=n_below,
        n_above_range=n_above,
        n_out_of_range=n_outside,
        fraction_out_of_range=fraction,
        min_value=min_value,
        max_value=max_value,
        mean_value=mean_value,
    )


def add_code_summary_rows(
    *,
    rows: list[CodeSummaryRow],
    df: pd.DataFrame,
    station_id: str | None,
    year: int | None,
    variable: str,
    values: pd.Series,
    code_type: str,
) -> None:
    """
    Append code summary rows for a variable.

    Code types:
        quality_code
        measurement_code
        source_code
        report_type
    """
    if code_type == "quality_code":
        code_series = get_related_column(df, variable, "quality_code")
    elif code_type == "measurement_code":
        code_series = get_related_column(df, variable, "measurement_code")
    elif code_type == "source_code":
        code_series = get_related_column(df, variable, "source_code")
    elif code_type == "report_type":
        code_series = get_related_column(df, variable, "report_type")
    else:
        raise ValueError(f"Unknown code_type: {code_type}")

    below, above, outside = out_of_range_masks(values, variable)
    numeric_mask = values.notna()

    tmp = pd.DataFrame(
        {
            "code_value": code_series.map(clean_code_value),
            "value": values,
            "numeric": numeric_mask,
            "out_of_range": outside,
            "station_id": station_id,
            "year": year,
        }
    )

    grouped = tmp.groupby("code_value", dropna=False)

    for code_value, g in grouped:
        n_rows = int(len(g))
        n_numeric = int(g["numeric"].sum())
        n_out = int(g["out_of_range"].sum())

        if n_numeric > 0:
            numeric_values = g.loc[g["numeric"], "value"]
            min_value = float(numeric_values.min())
            max_value = float(numeric_values.max())
            fraction_out = n_out / n_numeric
        else:
            min_value = None
            max_value = None
            fraction_out = None

        rows.append(
            CodeSummaryRow(
                variable=variable,
                code_type=code_type,
                code_value=str(code_value),
                n_rows=n_rows,
                n_numeric=n_numeric,
                n_out_of_range=n_out,
                fraction_out_of_range=fraction_out,
                min_value=min_value,
                max_value=max_value,
                station_count=1 if station_id is not None else 0,
                year_count=1 if year is not None else 0,
            )
        )


def build_extreme_example_rows(
    *,
    df: pd.DataFrame,
    dt: pd.Series,
    path: Path,
    station_id: str | None,
    station_name: str | None,
    year: int | None,
    variable: str,
    values: pd.Series,
    max_examples_per_reason: int,
) -> list[ExtremeExampleRow]:
    """
    Build example rows for suspicious/extreme values.

    Reasons:
        below_broad_range
        above_broad_range
        global_low_candidate
        global_high_candidate

    The global candidates are collected per file first; after all files are read,
    the script will reduce them to global extremes.
    """
    vmin, vmax, unit = broad_range_for(variable)
    below, above, outside = out_of_range_masks(values, variable)

    measurement = get_related_column(df, variable, "measurement_code")
    quality = get_related_column(df, variable, "quality_code")
    report = get_related_column(df, variable, "report_type")
    source = get_related_column(df, variable, "source_code")
    source_station = get_related_column(df, variable, "source_station_id")

    rows: list[ExtremeExampleRow] = []

    def make_row(reason: str, idx: Any) -> ExtremeExampleRow:
        raw_val = none_if_nan(values.loc[idx])
        div10 = None if raw_val is None else raw_val / 10.0

        dt_value = dt.loc[idx] if idx in dt.index else pd.NaT
        if pd.isna(dt_value):
            datetime_str = None
            month_value = None
        else:
            datetime_str = pd.Timestamp(dt_value).isoformat()
            month_value = int(pd.Timestamp(dt_value).month)

        return ExtremeExampleRow(
            reason=reason,
            station_id=station_id,
            station_name=station_name,
            datetime=datetime_str,
            year=year,
            month=month_value,
            variable=variable,
            raw_value=raw_val,
            value_divided_by_10=div10,
            expected_unit=unit,
            broad_min=vmin,
            broad_max=vmax,
            measurement_code=value_at(measurement, idx),
            quality_code=value_at(quality, idx),
            report_type=value_at(report, idx),
            source_code=value_at(source, idx),
            source_station_id=value_at(source_station, idx),
            raw_file=str(path),
        )

    # Examples below range.
    below_idx = values[below].head(max_examples_per_reason).index
    for idx in below_idx:
        rows.append(make_row("below_broad_range", idx))

    # Examples above range.
    above_idx = values[above].head(max_examples_per_reason).index
    for idx in above_idx:
        rows.append(make_row("above_broad_range", idx))

    # Per-file candidates for global low/high.
    numeric_values = values.dropna()

    if not numeric_values.empty:
        low_idx = numeric_values.nsmallest(max_examples_per_reason).index
        high_idx = numeric_values.nlargest(max_examples_per_reason).index

        for idx in low_idx:
            rows.append(make_row("global_low_candidate", idx))

        for idx in high_idx:
            rows.append(make_row("global_high_candidate", idx))

    return rows


def reduce_code_summary(rows: list[CodeSummaryRow]) -> pd.DataFrame:
    """
    Aggregate code summary rows across files.

    The first pass creates one row per file-variable-code.
    This function collapses them into one row per variable-code_type-code_value.
    """
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([r.__dict__ for r in rows])

    # station_count and year_count in raw rows are not unique counts yet.
    # For this diagnostic table, we want counts over contributing file groups.
    # We keep them as approximate file-group counts via summation.
    out = (
        df.groupby(["variable", "code_type", "code_value"], as_index=False)
        .agg(
            n_rows=("n_rows", "sum"),
            n_numeric=("n_numeric", "sum"),
            n_out_of_range=("n_out_of_range", "sum"),
            min_value=("min_value", "min"),
            max_value=("max_value", "max"),
            station_file_groups=("station_count", "sum"),
            year_file_groups=("year_count", "sum"),
        )
        .sort_values(["variable", "code_type", "n_rows"], ascending=[True, True, False])
        .reset_index(drop=True)
    )

    out["fraction_out_of_range"] = out.apply(
        lambda r: None if r["n_numeric"] == 0 else r["n_out_of_range"] / r["n_numeric"],
        axis=1,
    )

    # Put fraction near counts.
    cols = [
        "variable",
        "code_type",
        "code_value",
        "n_rows",
        "n_numeric",
        "n_out_of_range",
        "fraction_out_of_range",
        "min_value",
        "max_value",
        "station_file_groups",
        "year_file_groups",
    ]

    return out[cols]


def reduce_extreme_examples(rows: list[ExtremeExampleRow], max_global_examples: int) -> pd.DataFrame:
    """
    Reduce extreme examples to a manageable table.

    Keeps:
        - all below/above broad range examples already sampled per file
        - global lowest/highest values per variable
    """
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([r.__dict__ for r in rows])

    keep_parts = []

    # Keep sampled broad-range violations.
    direct = df[df["reason"].isin(["below_broad_range", "above_broad_range"])].copy()
    keep_parts.append(direct)

    # Reduce global low candidates.
    low = df[df["reason"] == "global_low_candidate"].copy()
    if not low.empty:
        low = (
            low.sort_values(["variable", "raw_value"], ascending=[True, True])
            .groupby("variable", as_index=False)
            .head(max_global_examples)
        )
        keep_parts.append(low)

    # Reduce global high candidates.
    high = df[df["reason"] == "global_high_candidate"].copy()
    if not high.empty:
        high = (
            high.sort_values(["variable", "raw_value"], ascending=[True, False])
            .groupby("variable", as_index=False)
            .head(max_global_examples)
        )
        keep_parts.append(high)

    out = pd.concat(keep_parts, ignore_index=True)

    # Remove exact duplicate rows if a value was both an above-range example
    # and a global-high candidate.
    out = out.drop_duplicates(
        subset=[
            "reason",
            "station_id",
            "datetime",
            "variable",
            "raw_value",
            "raw_file",
        ]
    )

    return out.sort_values(["variable", "reason", "raw_value"]).reset_index(drop=True)


def update_scale_samples(samples: dict[str, list[pd.Series]], variable: str, values: pd.Series) -> None:
    """
    Store numeric values for later quantile summaries.

    Dataset size here is manageable (~10 million rows total), but to be safe
    we store one series per file-variable and concatenate at the end.
    """
    numeric = values.dropna()
    if numeric.empty:
        return

    samples[variable].append(numeric.astype("float64"))


def build_scale_sanity_summary(samples: dict[str, list[pd.Series]]) -> pd.DataFrame:
    """
    Build quantiles for raw values and raw/10 values.
    """
    rows: list[ScaleSanityRow] = []

    for variable in CORE_VARIABLES:
        series_list = samples.get(variable, [])

        if not series_list:
            for interpretation in ["raw", "raw_divided_by_10"]:
                rows.append(
                    ScaleSanityRow(
                        variable=variable,
                        interpretation=interpretation,
                        n_numeric=0,
                        q00_min=None,
                        q01=None,
                        q05=None,
                        q50_median=None,
                        q95=None,
                        q99=None,
                        q100_max=None,
                    )
                )
            continue

        values = pd.concat(series_list, ignore_index=True)

        for interpretation, transformed in [
            ("raw", values),
            ("raw_divided_by_10", values / 10.0),
        ]:
            q = transformed.quantile([0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0])

            rows.append(
                ScaleSanityRow(
                    variable=variable,
                    interpretation=interpretation,
                    n_numeric=int(transformed.notna().sum()),
                    q00_min=float(q.loc[0.0]),
                    q01=float(q.loc[0.01]),
                    q05=float(q.loc[0.05]),
                    q50_median=float(q.loc[0.5]),
                    q95=float(q.loc[0.95]),
                    q99=float(q.loc[0.99]),
                    q100_max=float(q.loc[1.0]),
                )
            )

    return pd.DataFrame([r.__dict__ for r in rows])


def write_table(df: pd.DataFrame, csv_path: Path, parquet_path: Path) -> None:
    """
    Write both CSV and Parquet.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)


# ---------------------------------------------------------------------------
# Main diagnostic loop
# ---------------------------------------------------------------------------

def build_quality_units_diagnostics(
    *,
    raw_root: Path,
    outdir: Path,
    max_examples_per_file_variable: int,
    max_global_examples: int,
) -> None:
    """
    Read all downloaded GHCNh Parquet files and build diagnostic tables.
    """
    files = sorted(raw_root.glob("by_year/*/parquet/*.parquet"))

    if not files:
        raise FileNotFoundError(f"No encontré Parquet en: {raw_root}")

    print(f"Archivos Parquet encontrados: {len(files)}")

    out_of_range_year_rows: list[OutOfRangeCountRow] = []
    out_of_range_month_rows: list[OutOfRangeCountRow] = []
    code_rows: list[CodeSummaryRow] = []
    extreme_rows: list[ExtremeExampleRow] = []

    scale_samples: dict[str, list[pd.Series]] = defaultdict(list)

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] Revisando {path}", flush=True)

        try:
            df = pd.read_parquet(path)
        except Exception as exc:
            print(f"  WARNING: no pude leer {path}: {exc}", flush=True)
            continue

        dt = parse_datetime_column(df)
        station_id = safe_first_value(df, "STATION")
        station_name = safe_first_value(df, "Station_name")
        year = safe_year_from_path(path)

        for variable in CORE_VARIABLES:
            values = numeric_series(df, variable)

            # Save samples for raw vs raw/10 quantile sanity checks.
            update_scale_samples(scale_samples, variable, values)

            # Annual/file-level range counts.
            out_of_range_year_rows.append(
                summarize_out_of_range_for_period(
                    station_id=station_id,
                    station_name=station_name,
                    year=year,
                    month=None,
                    variable=variable,
                    values=values,
                )
            )

            # Monthly range counts.
            if dt.notna().any():
                months = dt.dt.month

                for month in range(1, 13):
                    mask = months == month
                    if not mask.any():
                        continue

                    out_of_range_month_rows.append(
                        summarize_out_of_range_for_period(
                            station_id=station_id,
                            station_name=station_name,
                            year=year,
                            month=month,
                            variable=variable,
                            values=values.loc[mask],
                        )
                    )

            # Code summaries.
            for code_type in ["quality_code", "measurement_code", "source_code", "report_type"]:
                add_code_summary_rows(
                    rows=code_rows,
                    df=df,
                    station_id=station_id,
                    year=year,
                    variable=variable,
                    values=values,
                    code_type=code_type,
                )

            # Examples and global extreme candidates.
            extreme_rows.extend(
                build_extreme_example_rows(
                    df=df,
                    dt=dt,
                    path=path,
                    station_id=station_id,
                    station_name=station_name,
                    year=year,
                    variable=variable,
                    values=values,
                    max_examples_per_reason=max_examples_per_file_variable,
                )
            )

    # Build final tables.
    units_reference = build_units_reference()
    recommendations = build_preliminary_recommendations()

    out_of_range_year = pd.DataFrame([r.__dict__ for r in out_of_range_year_rows])
    out_of_range_month = pd.DataFrame([r.__dict__ for r in out_of_range_month_rows])

    code_summary = reduce_code_summary(code_rows)

    # Split code summary into separate files for easier inspection.
    quality_code_summary = code_summary[code_summary["code_type"] == "quality_code"].copy()
    measurement_code_summary = code_summary[code_summary["code_type"] == "measurement_code"].copy()
    source_code_summary = code_summary[code_summary["code_type"] == "source_code"].copy()
    report_type_summary = code_summary[code_summary["code_type"] == "report_type"].copy()

    extreme_examples = reduce_extreme_examples(
        extreme_rows,
        max_global_examples=max_global_examples,
    )

    scale_sanity = build_scale_sanity_summary(scale_samples)

    # Write outputs.
    write_table(
        units_reference,
        outdir / "ghcnh_hourly_core_units_reference.csv",
        outdir / "ghcnh_hourly_core_units_reference.parquet",
    )

    write_table(
        recommendations,
        outdir / "ghcnh_hourly_core_cleaning_recommendations_preliminary.csv",
        outdir / "ghcnh_hourly_core_cleaning_recommendations_preliminary.parquet",
    )

    write_table(
        out_of_range_year,
        outdir / "ghcnh_hourly_core_out_of_range_counts_station_year.csv",
        outdir / "ghcnh_hourly_core_out_of_range_counts_station_year.parquet",
    )

    write_table(
        out_of_range_month,
        outdir / "ghcnh_hourly_core_out_of_range_counts_station_month.csv",
        outdir / "ghcnh_hourly_core_out_of_range_counts_station_month.parquet",
    )

    write_table(
        quality_code_summary,
        outdir / "ghcnh_hourly_core_quality_code_summary.csv",
        outdir / "ghcnh_hourly_core_quality_code_summary.parquet",
    )

    write_table(
        measurement_code_summary,
        outdir / "ghcnh_hourly_core_measurement_code_summary.csv",
        outdir / "ghcnh_hourly_core_measurement_code_summary.parquet",
    )

    write_table(
        source_code_summary,
        outdir / "ghcnh_hourly_core_source_code_summary.csv",
        outdir / "ghcnh_hourly_core_source_code_summary.parquet",
    )

    write_table(
        report_type_summary,
        outdir / "ghcnh_hourly_core_report_type_summary.csv",
        outdir / "ghcnh_hourly_core_report_type_summary.parquet",
    )

    write_table(
        extreme_examples,
        outdir / "ghcnh_hourly_core_extreme_values_examples.csv",
        outdir / "ghcnh_hourly_core_extreme_values_examples.parquet",
    )

    write_table(
        scale_sanity,
        outdir / "ghcnh_hourly_core_scale_sanity_summary.csv",
        outdir / "ghcnh_hourly_core_scale_sanity_summary.parquet",
    )

    print("\nListo. Archivos escritos en:")
    print(f"  {outdir}")

    print("\nResumen: valores fuera de rango por variable")
    if not out_of_range_year.empty:
        summary = (
            out_of_range_year
            .groupby("variable", as_index=False)
            .agg(
                n_numeric=("n_numeric", "sum"),
                n_out_of_range=("n_out_of_range", "sum"),
                n_below_range=("n_below_range", "sum"),
                n_above_range=("n_above_range", "sum"),
                min_value=("min_value", "min"),
                max_value=("max_value", "max"),
            )
        )
        summary["fraction_out_of_range"] = summary["n_out_of_range"] / summary["n_numeric"]
        print(summary.to_string(index=False))

    print("\nResumen: escala raw vs raw/10")
    print(scale_sanity.to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnóstico de unidades, calidad y extremos para GHCNh PR."
    )

    parser.add_argument(
        "--raw-root",
        default="data_raw/noaa/ghcnh/hourly",
        help="Raíz de archivos crudos GHCNh descargados.",
    )

    parser.add_argument(
        "--outdir",
        default="data_interim/noaa/ghcnh_hourly/quality_diagnostics",
        help="Directorio de salida para diagnósticos de calidad y unidades.",
    )

    parser.add_argument(
        "--max-examples-per-file-variable",
        type=int,
        default=5,
        help="Máximo de ejemplos por archivo-variable para cada razón de extremo.",
    )

    parser.add_argument(
        "--max-global-examples",
        type=int,
        default=100,
        help="Máximo de extremos globales bajos/altos por variable.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    build_quality_units_diagnostics(
        raw_root=Path(args.raw_root),
        outdir=Path(args.outdir),
        max_examples_per_file_variable=args.max_examples_per_file_variable,
        max_global_examples=args.max_global_examples,
    )


if __name__ == "__main__":
    main()
