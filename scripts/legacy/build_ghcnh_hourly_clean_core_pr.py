#!/usr/bin/env python3
"""
build_ghcnh_hourly_clean_core_pr.py

Construye una tabla horaria limpia/candidata de variables core GHCNh
para Puerto Rico, 2004–2023.

Este script parte de los archivos Parquet crudos descargados en:

    data_raw/noaa/ghcnh/hourly/by_year/<YEAR>/parquet/*.parquet

Y produce una tabla horaria en:

    data_interim/noaa/ghcnh_hourly/clean_core/

Objetivo
--------
Crear un dataset candidato para comparación futura contra ERA5, aplicando
reglas explícitas y trazables de calidad, unidades, rangos físicos y
agregación horaria.

Importante
----------
- Este script NO modifica los datos crudos.
- Este script NO compara contra ERA5.
- Este script NO resuelve PWV.
- Este script NO debe interpretarse como la versión científica final sin
  revisar las tablas de decisiones generadas.

Variables core
--------------
- temperature
- dew_point_temperature
- relative_humidity
- wind_speed
- station_level_pressure
- precipitation

Decisiones principales
----------------------
1. Si el valor raw está dentro del rango físico definido para PR/proyecto,
   se conserva.
2. Para temperature y dew_point_temperature, solo se permite corrección /10
   cuando el raw parece claramente codificado en décimas: abs(raw) >= 100.
   Esto evita convertir valores cercanos pero sospechosos, como 42.2 °C,
   en 4.22 °C.
3. Para station_level_pressure, si raw está fuera de rango pero raw*10 cae
   dentro de rango, se corrige multiplicando por 10.
4. relative_humidity, wind_speed y precipitation NO se reescalan por defecto.
5. Valores con códigos de calidad de error fuerte se descartan.
6. Valores marcados como suspect/review QC NO se conservan en la tabla
   limpia final para ninguna variable. Quedan trazados en el log de decisiones.
7. Valores fuera de rango que no tienen una corrección justificada se descartan.
8. Para precipitación horaria limpia se excluyen reportes no horarios o
   marcados por QC, especialmente Source 382 / 4-DSI-3240 y Source 382 con
   cualquier quality code no vacío.
9. Precipitación se agrega por hora usando el último reporte válido dentro
   de la hora, no la suma ciega de reportes subhorarios, porque en GHCNh/METAR
   puede representar un running total dentro de la hora.

Por qué no dividir todo entre 10
--------------------------------
El diagnóstico previo mostró que las distribuciones raw globales ya son
físicamente plausibles para Puerto Rico, por ejemplo:

- temperature raw median ≈ 26.9 °C
- dew_point raw median ≈ 22.2 °C
- pressure raw median ≈ 1014.9 hPa
- RH raw median ≈ 77 %
- wind raw median ≈ 2.6 m/s

Por lo tanto, el problema no es una escala global incorrecta, sino valores
puntuales o patrones específicos de fuente/código.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Variables y nombres finales
# ---------------------------------------------------------------------------

CORE_VARIABLES = [
    "temperature",
    "dew_point_temperature",
    "relative_humidity",
    "wind_speed",
    "station_level_pressure",
    "precipitation",
]

OUTPUT_NAMES = {
    "temperature": "temperature_c",
    "dew_point_temperature": "dew_point_temperature_c",
    "relative_humidity": "relative_humidity_pct",
    "wind_speed": "wind_speed_m_s",
    "station_level_pressure": "station_level_pressure_hpa",
    "precipitation": "precipitation_mm",
}

# Cómo agregar cada variable a escala horaria.
# Para variables de estado usamos promedio.
# Para precipitación NO sumamos reportes subhorarios: usamos el último reporte
# válido dentro de la hora.
HOURLY_AGG_METHOD = {
    "temperature": "mean",
    "dew_point_temperature": "mean",
    "relative_humidity": "mean",
    "wind_speed": "mean",
    "station_level_pressure": "mean",
    "precipitation": "last_valid_report_in_hour",
}


# ---------------------------------------------------------------------------
# Rangos físicos para limpieza candidata
# ---------------------------------------------------------------------------
#
# Estos rangos no son una climatología fina. Son límites operacionales para
# remover valores claramente problemáticos antes de construir el dataset limpio.
#
# Cambio importante de esta versión:
# - temperature usa 4–41 °C para Puerto Rico.
# - Valores T < 4 °C se descartan como fuera de rango para esta etapa.
# - Valores T > 41 °C se descartan como fuera de rango para esta etapa.
#
# Si en el futuro se quiere defender un valor fuera de ese rango, debe hacerse
# con una revisión puntual por estación/fecha/fuente/código, no desde el flujo
# automático general.

BROAD_RANGES = {
    "temperature": {
        "unit": "degC",
        "min": 4.0,
        "max": 41.0,
    },
    "dew_point_temperature": {
        "unit": "degC",
        "min": -20.0,
        "max": 35.0,
    },
    "relative_humidity": {
        "unit": "percent",
        "min": 0.0,
        "max": 100.0,
    },
    "wind_speed": {
        "unit": "m/s",
        "min": 0.0,
        "max": 50.0,
    },
    "station_level_pressure": {
        "unit": "hPa",
        "min": 850.0,
        "max": 1050.0,
    },
    "precipitation": {
        "unit": "mm",
        "min": 0.0,
        "max": 500.0,
    },
}


# ---------------------------------------------------------------------------
# Quality code logic
# ---------------------------------------------------------------------------
#
# GHCNh preserva códigos de calidad de varias fuentes. Por eso la
# interpretación depende de source_code.
#
# Clasificación conservadora usada aquí:
#
# Fuentes 313/314/315/322/335/343/344/346:
#   3 = erroneous
#   7 = erroneous from NCEI source
#   2 = suspect
#   6 = suspect from NCEI source
#   5 = passed QC from NCEI source
#
# Fuentes 220/221/222/223/347/348:
#   3 = erroneous
#   5 = removed
#   2 = suspect
#
# Source 345 para relative_humidity y wind_speed:
#   1 = field-length overflow / issue
#   3 = error
#
# Relative humidity:
#   o = out of physical range
#   f = one or more input variables had suspect/error flags
#
# Blank y 9 no se tratan como error fuerte.
# El código 9 representa ausencia de quality code, no un fallo físico.

LEGACY_NCEI_SOURCES = {"313", "314", "315", "322", "335", "343", "344", "346"}
LEGACY_OTHER_SOURCES = {"220", "221", "222", "223", "347", "348"}
GENERAL_REVIEW_FLAGS = {"L", "o", "O", "W", "C", "T", "S", "h", "w", "p", "N", "H"}


# ---------------------------------------------------------------------------
# Dataclasses para salidas trazables
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CleaningRuleRow:
    variable: str
    output_column: str
    expected_unit: str
    broad_min: float
    broad_max: float
    hourly_aggregation: str
    scaling_rule: str
    quality_rule: str


@dataclass(frozen=True)
class DecisionSummaryRow:
    station_id: str | None
    station_name: str | None
    year: int | None
    variable: str
    decision: str
    n_rows: int
    n_raw_numeric: int
    n_clean_numeric: int
    raw_min: float | None
    raw_max: float | None
    clean_min: float | None
    clean_max: float | None


@dataclass(frozen=True)
class CleaningExampleRow:
    station_id: str | None
    station_name: str | None
    datetime: str | None
    year: int | None
    month: int | None
    variable: str
    decision: str
    raw_value: float | None
    clean_value: float | None
    value_divided_by_10: float | None
    value_times_10: float | None
    quality_code: str | None
    measurement_code: str | None
    source_code: str | None
    report_type: str | None
    source_station_id: str | None
    raw_file: str


# ---------------------------------------------------------------------------
# Helpers básicos
# ---------------------------------------------------------------------------

def normalize_code(value: Any) -> str:
    """
    Normaliza códigos para comparación robusta.

    Ejemplos:
    - NaN -> ""
    - "" -> ""
    - 343.0 -> "343"
    - " 5 " -> "5"
    """
    if pd.isna(value):
        return ""

    s = str(value).strip()
    if s == "":
        return ""

    # Evita problemas si pandas leyera códigos numéricos como 343.0.
    if s.endswith(".0") and s.replace(".0", "").isdigit():
        s = s.replace(".0", "")

    return s


def parse_datetime_column(df: pd.DataFrame) -> pd.Series:
    """
    Convierte DATE a datetime.

    En esta etapa no se cambia zona horaria. La alineación temporal con ERA5
    se hará explícitamente en la etapa de comparación.
    """
    if "DATE" not in df.columns:
        return pd.Series(pd.NaT, index=df.index)

    return pd.to_datetime(df["DATE"], errors="coerce")


def safe_first_value(df: pd.DataFrame, column: str) -> str | None:
    """Devuelve el primer valor no nulo de una columna."""
    if column not in df.columns:
        return None

    values = df[column].dropna()
    if values.empty:
        return None

    return str(values.iloc[0])


def safe_year_from_path(path: Path) -> int | None:
    """
    Extrae el año desde una ruta tipo:

        .../by_year/2023/parquet/GHCNh_..._2023.parquet
    """
    for part in path.parts:
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def numeric_series(df: pd.DataFrame, variable: str) -> pd.Series:
    """
    Convierte una variable a numérica.

    No modifica el Parquet crudo. Solo crea una serie numérica para limpieza.
    """
    if variable not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")

    return pd.to_numeric(df[variable], errors="coerce")


def related_code(df: pd.DataFrame, variable: str, suffix: str) -> pd.Series:
    """
    Obtiene columnas asociadas a una variable.

    Ejemplo:
        temperature + "_Quality_Code"
    """
    col = f"{variable}_{suffix}"
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="object")

    return df[col].map(normalize_code)


def broad_range(variable: str) -> tuple[float, float]:
    info = BROAD_RANGES[variable]
    return float(info["min"]), float(info["max"])


def unit_for(variable: str) -> str:
    return str(BROAD_RANGES[variable]["unit"])


def inside_range(values: pd.Series, variable: str) -> pd.Series:
    """Boolean mask: valor numérico dentro del rango definido."""
    vmin, vmax = broad_range(variable)
    return values.notna() & (values >= vmin) & (values <= vmax)


def none_if_nan(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def value_at(series: pd.Series, idx: Any) -> str | None:
    if idx not in series.index:
        return None

    value = series.loc[idx]
    if pd.isna(value):
        return None

    s = str(value).strip()
    if s == "":
        return None

    return s


# ---------------------------------------------------------------------------
# Quality classification
# ---------------------------------------------------------------------------

def classify_quality_masks(
    *,
    variable: str,
    quality_code: pd.Series,
    source_code: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """
    Devuelve dos máscaras booleanas:

    strong_error:
        Se descarta directamente.

    suspect:
        Se descarta de la tabla limpia final. El valor queda trazado como
        dropped_suspect_quality_code.
    """
    qc = quality_code.map(normalize_code)
    src = source_code.map(normalize_code)

    strong_error = pd.Series(False, index=qc.index)
    suspect = pd.Series(False, index=qc.index)

    # Legacy NCEI sources.
    mask_legacy_ncei = src.isin(LEGACY_NCEI_SOURCES)
    strong_error |= mask_legacy_ncei & qc.isin({"3", "7"})
    suspect |= mask_legacy_ncei & qc.isin({"2", "6"})

    # Other legacy sources.
    mask_legacy_other = src.isin(LEGACY_OTHER_SOURCES)
    strong_error |= mask_legacy_other & qc.isin({"3", "5"})
    suspect |= mask_legacy_other & qc.isin({"2"})

    # Source 345 special issue for RH and wind speed.
    if variable in {"relative_humidity", "wind_speed"}:
        mask_345 = src.eq("345")
        strong_error |= mask_345 & qc.isin({"1", "3"})
        suspect |= mask_345 & qc.isin({"2"})

    # Relative humidity derived flags.
    if variable == "relative_humidity":
        strong_error |= qc.eq("o")
        suspect |= qc.eq("f")

    # General review flags: do not keep in the clean final table.
    suspect |= qc.isin(GENERAL_REVIEW_FLAGS)

    # Para Source 382 en precipitación, cualquier quality code no vacío indica
    # que el valor requiere interpretación adicional. En particular, A marca
    # acumulación sobre un período mayor de una hora, no lluvia horaria limpia.
    if variable == "precipitation":
        mask_382 = src.eq("382")
        suspect |= mask_382 & ~qc.isin({"", "9"})

    # Blank and 9 are not treated as errors.
    strong_error &= ~qc.isin({"", "9"})
    suspect &= ~qc.isin({"", "9"})

    return strong_error, suspect


# ---------------------------------------------------------------------------
# Limpieza variable por variable
# ---------------------------------------------------------------------------

def clean_variable(
    *,
    df: pd.DataFrame,
    variable: str,
) -> tuple[pd.Series, pd.Series]:
    """
    Limpia una variable y devuelve:

    clean_values, decisions

    Decisiones trazables:
    - non_numeric
    - dropped_strong_quality_code
    - dropped_suspect_quality_code
    - dropped_non_hourly_precipitation_report
    - kept_raw
    - rescaled_divide_by_10
    - rescaled_multiply_by_10
    - dropped_out_of_range

    Regla central de esta versión:
    ningún valor marcado como suspect QC se conserva en la tabla limpia final.
    """
    raw = numeric_series(df, variable)
    quality_code = related_code(df, variable, "Quality_Code")
    source_code = related_code(df, variable, "Source_Code")
    measurement_code = related_code(df, variable, "Measurement_Code")
    report_type = related_code(df, variable, "Report_Type")

    strong_error, suspect = classify_quality_masks(
        variable=variable,
        quality_code=quality_code,
        source_code=source_code,
    )

    clean = pd.Series(np.nan, index=df.index, dtype="float64")
    decision = pd.Series("non_numeric", index=df.index, dtype="object")

    numeric = raw.notna()

    # 1. Error fuerte de quality code.
    mask_strong = numeric & strong_error
    decision.loc[mask_strong] = "dropped_strong_quality_code"

    # 2. Suspect/review QC: no se conserva para ninguna variable.
    mask_suspect = numeric & ~strong_error & suspect
    decision.loc[mask_suspect] = "dropped_suspect_quality_code"

    # 3. Regla adicional para precipitación horaria limpia.
    # Source 382 / 4-DSI-3240 corresponde a reportes que no se deben
    # interpretar como lluvia horaria limpia en este workflow. Además,
    # Measurement_Code no vacío en Source 382 suele indicar período de
    # acumulación. Estos valores pueden ser útiles para estudios diarios o
    # mensuales, pero no entran en precipitation_mm horario limpio.
    mask_non_hourly = pd.Series(False, index=df.index)
    if variable == "precipitation":
        src = source_code.map(normalize_code)
        rpt = report_type.map(normalize_code)
        meas = measurement_code.map(normalize_code)
        mask_non_hourly = (
            numeric
            & ~strong_error
            & ~suspect
            & src.eq("382")
            & (rpt.eq("4-DSI-3240") | meas.ne(""))
        )
        decision.loc[mask_non_hourly] = "dropped_non_hourly_precipitation_report"

    valid_qc = numeric & ~strong_error & ~suspect & ~mask_non_hourly

    # 4. Mantener raw si está dentro de rango.
    raw_inside = valid_qc & inside_range(raw, variable)
    clean.loc[raw_inside] = raw.loc[raw_inside]
    decision.loc[raw_inside] = "kept_raw"

    # 5. Reescalar temperature y dew point con /10 solo cuando el raw parece
    # claramente codificado en décimas. Esto evita convertir 42.2 °C -> 4.22 °C.
    if variable in {"temperature", "dew_point_temperature"}:
        candidate = raw / 10.0
        encoded_tenths_like = raw.abs() >= 100.0
        rescale_ok = (
            valid_qc
            & ~raw_inside
            & encoded_tenths_like
            & inside_range(candidate, variable)
        )
        clean.loc[rescale_ok] = candidate.loc[rescale_ok]
        decision.loc[rescale_ok] = "rescaled_divide_by_10"

    # 6. Reescalar presión con *10 si raw está fuera de rango, pero raw*10
    # entra al rango físico amplio.
    if variable == "station_level_pressure":
        candidate = raw * 10.0
        rescale_ok = valid_qc & ~raw_inside & inside_range(candidate, variable)
        clean.loc[rescale_ok] = candidate.loc[rescale_ok]
        decision.loc[rescale_ok] = "rescaled_multiply_by_10"

    # 7. Todo lo numérico restante que no se limpió queda fuera de rango.
    unresolved = numeric & clean.isna() & ~strong_error & ~suspect & ~mask_non_hourly
    decision.loc[unresolved] = "dropped_out_of_range"

    return clean, decision


# ---------------------------------------------------------------------------
# Salidas auxiliares
# ---------------------------------------------------------------------------

def build_cleaning_rules_reference() -> pd.DataFrame:
    rows: list[CleaningRuleRow] = []

    for variable in CORE_VARIABLES:
        vmin, vmax = broad_range(variable)

        if variable in {"temperature", "dew_point_temperature"}:
            scaling_rule = (
                "Keep raw if plausible; if raw is outside range, raw looks encoded "
                "in tenths (abs(raw) >= 100), and raw/10 is plausible, use raw/10."
            )
        elif variable == "station_level_pressure":
            scaling_rule = "Keep raw if plausible; if raw is outside range and raw*10 is plausible, use raw*10."
        else:
            scaling_rule = "Keep raw if plausible; no automatic scaling."

        rows.append(
            CleaningRuleRow(
                variable=variable,
                output_column=OUTPUT_NAMES[variable],
                expected_unit=unit_for(variable),
                broad_min=vmin,
                broad_max=vmax,
                hourly_aggregation=HOURLY_AGG_METHOD[variable],
                scaling_rule=scaling_rule,
                quality_rule="Drop strong QC errors and all suspect/review QC; no suspect QC values are retained in clean final output.",
            )
        )

    return pd.DataFrame([r.__dict__ for r in rows])


def summarize_decisions(
    *,
    station_id: str | None,
    station_name: str | None,
    year: int | None,
    variable: str,
    raw: pd.Series,
    clean: pd.Series,
    decision: pd.Series,
) -> pd.DataFrame:
    """Crea resumen por estación-año-variable-decisión."""
    tmp = pd.DataFrame(
        {
            "raw": raw,
            "clean": clean,
            "decision": decision,
        }
    )

    rows: list[DecisionSummaryRow] = []

    for dec, g in tmp.groupby("decision", dropna=False):
        raw_numeric = g["raw"].dropna()
        clean_numeric = g["clean"].dropna()

        rows.append(
            DecisionSummaryRow(
                station_id=station_id,
                station_name=station_name,
                year=year,
                variable=variable,
                decision=str(dec),
                n_rows=int(len(g)),
                n_raw_numeric=int(raw_numeric.shape[0]),
                n_clean_numeric=int(clean_numeric.shape[0]),
                raw_min=none_if_nan(raw_numeric.min()) if not raw_numeric.empty else None,
                raw_max=none_if_nan(raw_numeric.max()) if not raw_numeric.empty else None,
                clean_min=none_if_nan(clean_numeric.min()) if not clean_numeric.empty else None,
                clean_max=none_if_nan(clean_numeric.max()) if not clean_numeric.empty else None,
            )
        )

    return pd.DataFrame([r.__dict__ for r in rows])


def sample_cleaning_examples(
    *,
    df: pd.DataFrame,
    dt: pd.Series,
    path: Path,
    station_id: str | None,
    station_name: str | None,
    year: int | None,
    variable: str,
    raw: pd.Series,
    clean: pd.Series,
    decision: pd.Series,
    max_examples_per_decision: int,
) -> pd.DataFrame:
    """
    Guarda ejemplos de decisiones que requieren revisión.

    No guardamos ejemplos de kept_raw para evitar archivos enormes.
    """
    quality_code = related_code(df, variable, "Quality_Code")
    measurement_code = related_code(df, variable, "Measurement_Code")
    source_code = related_code(df, variable, "Source_Code")
    report_type = related_code(df, variable, "Report_Type")
    source_station_id = related_code(df, variable, "Source_Station_ID")

    rows: list[CleaningExampleRow] = []
    decisions_to_sample = [
        "rescaled_divide_by_10",
        "rescaled_multiply_by_10",
        "dropped_strong_quality_code",
        "dropped_suspect_quality_code",
        "dropped_non_hourly_precipitation_report",
        "dropped_dew_point_gt_temperature",
        "dropped_out_of_range",
    ]

    for dec in decisions_to_sample:
        idxs = decision[decision == dec].head(max_examples_per_decision).index

        for idx in idxs:
            raw_val = none_if_nan(raw.loc[idx])
            clean_val = none_if_nan(clean.loc[idx])
            dt_value = dt.loc[idx] if idx in dt.index else pd.NaT

            if pd.isna(dt_value):
                datetime_str = None
                month_value = None
            else:
                ts = pd.Timestamp(dt_value)
                datetime_str = ts.isoformat()
                month_value = int(ts.month)

            rows.append(
                CleaningExampleRow(
                    station_id=station_id,
                    station_name=station_name,
                    datetime=datetime_str,
                    year=year,
                    month=month_value,
                    variable=variable,
                    decision=dec,
                    raw_value=raw_val,
                    clean_value=clean_val,
                    value_divided_by_10=None if raw_val is None else raw_val / 10.0,
                    value_times_10=None if raw_val is None else raw_val * 10.0,
                    quality_code=value_at(quality_code, idx),
                    measurement_code=value_at(measurement_code, idx),
                    source_code=value_at(source_code, idx),
                    report_type=value_at(report_type, idx),
                    source_station_id=value_at(source_station_id, idx),
                    raw_file=str(path),
                )
            )

    return pd.DataFrame([r.__dict__ for r in rows])



def apply_record_level_consistency(
    *,
    clean_by_variable: dict[str, pd.Series],
    decision_by_variable: dict[str, pd.Series],
) -> None:
    """
    Aplica consistencia física mínima entre temperatura y punto de rocío.

    El punto de rocío no debe exceder la temperatura del aire por más de una
    tolerancia pequeña. Cuando ocurre, se eliminan ambas mediciones de ese
    registro porque no se puede decidir automáticamente cuál es responsable.
    """
    if "temperature" not in clean_by_variable or "dew_point_temperature" not in clean_by_variable:
        return

    temp = clean_by_variable["temperature"]
    dew = clean_by_variable["dew_point_temperature"]

    bad = temp.notna() & dew.notna() & (dew > temp + 0.5)
    if not bad.any():
        return

    clean_by_variable["temperature"].loc[bad] = np.nan
    clean_by_variable["dew_point_temperature"].loc[bad] = np.nan
    decision_by_variable["temperature"].loc[bad] = "dropped_dew_point_gt_temperature"
    decision_by_variable["dew_point_temperature"].loc[bad] = "dropped_dew_point_gt_temperature"

    if "relative_humidity" in clean_by_variable:
        clean_by_variable["relative_humidity"].loc[bad] = np.nan
        decision_by_variable["relative_humidity"].loc[bad] = "dropped_dew_point_gt_temperature"

def aggregate_hourly(work: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega datos limpios a escala horaria.

    Para variables de estado:
        promedio horario.

    Para precipitación:
        último reporte válido dentro de la hora.
    """
    # Importante para que .last() represente el último reporte temporal de la hora.
    work = work.sort_values(["station_id", "datetime"]).copy()

    group_cols = ["station_id", "datetime_hour"]
    grouped = work.groupby(group_cols, dropna=False)

    hourly = grouped.agg(
        station_name=("station_name", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
        elevation_m=("elevation_m", "first"),
        n_raw_records_in_hour=("datetime", "size"),
    ).reset_index()

    for variable in CORE_VARIABLES:
        out_col = OUTPUT_NAMES[variable]
        clean_col = f"{variable}_clean"
        count_col = f"{out_col}_n_valid"

        method = HOURLY_AGG_METHOD[variable]

        if method == "mean":
            agg = grouped[clean_col].mean().rename(out_col).reset_index()
        elif method == "sum":
            agg = grouped[clean_col].sum(min_count=1).rename(out_col).reset_index()
        elif method == "last_valid_report_in_hour":
            # Because work is sorted by datetime, this returns the last non-null
            # clean value in the hour. If all values are NaN, result is NaN.
            agg = grouped[clean_col].last().rename(out_col).reset_index()
        else:
            raise ValueError(f"Unknown aggregation method for {variable}: {method}")

        cnt = grouped[clean_col].count().rename(count_col).reset_index()

        hourly = hourly.merge(agg, on=group_cols, how="left")
        hourly = hourly.merge(cnt, on=group_cols, how="left")

    # Remover horas donde no quedó ningún dato limpio en ninguna variable core.
    count_cols = [f"{OUTPUT_NAMES[v]}_n_valid" for v in CORE_VARIABLES]
    hourly = hourly[hourly[count_cols].sum(axis=1) > 0].copy()

    # Consistencia física posagregación: si el promedio horario produce
    # Td > T por mezcla de reportes dentro de una hora, removemos T, Td y RH
    # de esa hora para evitar contradicciones físicas en la tabla final.
    thermo_bad = (
        hourly["temperature_c"].notna()
        & hourly["dew_point_temperature_c"].notna()
        & (hourly["dew_point_temperature_c"] > hourly["temperature_c"] + 0.5)
    )
    if thermo_bad.any():
        for col in ["temperature_c", "dew_point_temperature_c", "relative_humidity_pct"]:
            if col in hourly.columns:
                hourly.loc[thermo_bad, col] = np.nan
        for col in ["temperature_c_n_valid", "dew_point_temperature_c_n_valid", "relative_humidity_pct_n_valid"]:
            if col in hourly.columns:
                hourly.loc[thermo_bad, col] = 0

    # Campos temporales derivados de la hora.
    hourly["year"] = hourly["datetime_hour"].dt.year
    hourly["month"] = hourly["datetime_hour"].dt.month
    hourly["day"] = hourly["datetime_hour"].dt.day
    hourly["hour"] = hourly["datetime_hour"].dt.hour

    ordered = [
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
    ]

    for variable in CORE_VARIABLES:
        out_col = OUTPUT_NAMES[variable]
        ordered.append(out_col)
        ordered.append(f"{out_col}_n_valid")

    return hourly[ordered].sort_values(["station_id", "datetime_hour"]).reset_index(drop=True)


def build_station_year_summary(hourly: pd.DataFrame) -> pd.DataFrame:
    """Resume cobertura limpia por estación-año."""
    group_cols = ["station_id", "station_name", "year"]

    summary = (
        hourly.groupby(group_cols, dropna=False)
        .agg(
            n_clean_hours=("datetime_hour", "nunique"),
            n_raw_records=("n_raw_records_in_hour", "sum"),
            first_hour=("datetime_hour", "min"),
            last_hour=("datetime_hour", "max"),
        )
        .reset_index()
    )

    for variable in CORE_VARIABLES:
        out_col = OUTPUT_NAMES[variable]
        count_col = f"{out_col}_n_valid"
        tmp = (
            hourly.groupby(group_cols, dropna=False)
            .agg(
                **{
                    f"{out_col}_hours_with_data": (out_col, lambda s: int(s.notna().sum())),
                    f"{out_col}_total_valid_obs": (count_col, "sum"),
                    f"{out_col}_min": (out_col, "min"),
                    f"{out_col}_max": (out_col, "max"),
                    f"{out_col}_mean": (out_col, "mean"),
                }
            )
            .reset_index()
        )
        summary = summary.merge(tmp, on=group_cols, how="left")

    return summary.sort_values(["station_id", "year"]).reset_index(drop=True)


def write_table(df: pd.DataFrame, csv_path: Path | None, parquet_path: Path | None) -> None:
    """Escribe tabla en CSV y/o Parquet."""
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)

    if parquet_path is not None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------

def build_clean_core(
    *,
    raw_root: Path,
    outdir: Path,
    max_examples_per_decision: int,
    max_files: int | None = None,
) -> None:
    files = sorted(raw_root.glob("by_year/*/parquet/*.parquet"))
    if max_files is not None:
        files = files[:max_files]

    if not files:
        raise FileNotFoundError(f"No encontré Parquet en: {raw_root}")

    print(f"Archivos Parquet encontrados: {len(files)}")

    hourly_parts: list[pd.DataFrame] = []
    decision_parts: list[pd.DataFrame] = []
    example_parts: list[pd.DataFrame] = []

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] Limpiando {path}", flush=True)

        df = pd.read_parquet(path)
        dt = parse_datetime_column(df)

        station_id = safe_first_value(df, "STATION")
        station_name = safe_first_value(df, "Station_name")
        year = safe_year_from_path(path)

        work = pd.DataFrame(
            {
                "station_id": station_id,
                "station_name": station_name,
                "datetime": dt,
                "datetime_hour": dt.dt.floor("h"),
                "lat": pd.to_numeric(df.get("LATITUDE", np.nan), errors="coerce"),
                "lon": pd.to_numeric(df.get("LONGITUDE", np.nan), errors="coerce"),
                "elevation_m": pd.to_numeric(df.get("ELEVATION", np.nan), errors="coerce"),
            }
        )

        # Si no hay fechas parseables, no se puede agregar a hora.
        if work["datetime_hour"].isna().all():
            print(f"  WARNING: sin DATE parseable en {path}", flush=True)
            continue

        raw_by_variable: dict[str, pd.Series] = {}
        clean_by_variable: dict[str, pd.Series] = {}
        decision_by_variable: dict[str, pd.Series] = {}

        for variable in CORE_VARIABLES:
            raw = numeric_series(df, variable)
            clean, decision = clean_variable(df=df, variable=variable)
            raw_by_variable[variable] = raw
            clean_by_variable[variable] = clean
            decision_by_variable[variable] = decision

        apply_record_level_consistency(
            clean_by_variable=clean_by_variable,
            decision_by_variable=decision_by_variable,
        )

        for variable in CORE_VARIABLES:
            raw = raw_by_variable[variable]
            clean = clean_by_variable[variable]
            decision = decision_by_variable[variable]
            work[f"{variable}_clean"] = clean

            decision_parts.append(
                summarize_decisions(
                    station_id=station_id,
                    station_name=station_name,
                    year=year,
                    variable=variable,
                    raw=raw,
                    clean=clean,
                    decision=decision,
                )
            )

            examples = sample_cleaning_examples(
                df=df,
                dt=dt,
                path=path,
                station_id=station_id,
                station_name=station_name,
                year=year,
                variable=variable,
                raw=raw,
                clean=clean,
                decision=decision,
                max_examples_per_decision=max_examples_per_decision,
            )

            if not examples.empty:
                example_parts.append(examples)

        hourly = aggregate_hourly(work.dropna(subset=["datetime_hour"]))
        hourly_parts.append(hourly)

    clean_hourly = pd.concat(hourly_parts, ignore_index=True)
    decisions = pd.concat(decision_parts, ignore_index=True)
    examples = pd.concat(example_parts, ignore_index=True) if example_parts else pd.DataFrame()
    rules = build_cleaning_rules_reference()
    station_year_summary = build_station_year_summary(clean_hourly)

    outdir.mkdir(parents=True, exist_ok=True)

    # Tabla principal: Parquet solamente para evitar CSV enorme.
    write_table(
        clean_hourly,
        csv_path=None,
        parquet_path=outdir / "ghcnh_hourly_clean_core_2004_2023.parquet",
    )

    write_table(
        decisions,
        csv_path=outdir / "ghcnh_hourly_cleaning_decisions_log.csv",
        parquet_path=outdir / "ghcnh_hourly_cleaning_decisions_log.parquet",
    )

    write_table(
        examples,
        csv_path=outdir / "ghcnh_hourly_cleaning_examples.csv",
        parquet_path=outdir / "ghcnh_hourly_cleaning_examples.parquet",
    )

    write_table(
        rules,
        csv_path=outdir / "ghcnh_hourly_cleaning_rules_reference.csv",
        parquet_path=outdir / "ghcnh_hourly_cleaning_rules_reference.parquet",
    )

    write_table(
        station_year_summary,
        csv_path=outdir / "ghcnh_hourly_clean_core_station_year_summary.csv",
        parquet_path=outdir / "ghcnh_hourly_clean_core_station_year_summary.parquet",
    )

    print("\nListo. Archivos escritos en:")
    print(f"  {outdir}")
    print("\nTabla horaria limpia:")
    print(f"  filas: {len(clean_hourly):,}")
    print(f"  estaciones: {clean_hourly['station_id'].nunique()}")
    print(f"  rango temporal: {clean_hourly['datetime_hour'].min()} a {clean_hourly['datetime_hour'].max()}")

    print("\nResumen de decisiones:")
    decision_summary = (
        decisions.groupby(["variable", "decision"], as_index=False)
        .agg(
            n_rows=("n_rows", "sum"),
            n_raw_numeric=("n_raw_numeric", "sum"),
            n_clean_numeric=("n_clean_numeric", "sum"),
            raw_min=("raw_min", "min"),
            raw_max=("raw_max", "max"),
            clean_min=("clean_min", "min"),
            clean_max=("clean_max", "max"),
        )
        .sort_values(["variable", "decision"])
    )
    print(decision_summary.to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construir tabla horaria limpia/candidata GHCNh core para PR."
    )
    parser.add_argument(
        "--raw-root",
        default="data_raw/noaa/ghcnh/hourly",
        help="Raíz de archivos crudos GHCNh descargados.",
    )
    parser.add_argument(
        "--outdir",
        default="data_interim/noaa/ghcnh_hourly/clean_core",
        help="Directorio de salida para tabla limpia y logs.",
    )
    parser.add_argument(
        "--max-examples-per-decision",
        type=int,
        default=5,
        help="Máximo de ejemplos por decisión, variable y archivo.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Opcional: procesar solo los primeros N archivos para prueba rápida.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_clean_core(
        raw_root=Path(args.raw_root),
        outdir=Path(args.outdir),
        max_examples_per_decision=args.max_examples_per_decision,
        max_files=args.max_files,
    )


if __name__ == "__main__":
    main()
