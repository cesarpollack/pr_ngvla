#!/usr/bin/env python3
"""
build_ghcnh_hourly_variable_coverage_pr.py

Construye diagnósticos de cobertura real para los archivos horarios GHCNh
descargados previamente para Puerto Rico.

Este script NO descarga datos.
Este script NO limpia datos para comparación final.
Este script NO decide todavía qué estación es "buena" o "mala".

Objetivo
--------
Leer los archivos crudos Parquet descargados desde GHCNh y responder:

1. ¿Qué archivos existen físicamente?
2. ¿Qué columnas trae cada archivo?
3. ¿Cuántos registros hay por estación-año?
4. ¿Cuántos valores no nulos hay por variable?
5. ¿Cuántos valores numéricos válidos hay por variable?
6. ¿Cuántas horas únicas tienen al menos un dato para cada variable?
7. ¿Cómo se distribuye la cobertura por mes?

Por qué contamos horas únicas
-----------------------------
Aunque GHCNh es un producto horario/sinóptico, algunos archivos tienen
registros sub-horarios, por ejemplo 12:15, 12:30, 12:45.

Para comparar después con ERA5, probablemente necesitaremos trabajar a escala
horaria. Por eso este diagnóstico distingue entre:

- n_rows: cantidad de filas observadas
- n_timestamps: cantidad de timestamps exactos únicos
- n_hours: cantidad de horas únicas presentes al redondear hacia abajo

Ejemplo:
    2004-01-01T12:15
    2004-01-01T12:30
    2004-01-01T12:45

son 3 timestamps, pero pertenecen a 1 hora única: 2004-01-01 12:00.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Variables que queremos diagnosticar en esta etapa
# ---------------------------------------------------------------------------

# Variables directamente relacionadas con el proyecto.
# PWV no aparece aquí porque GHCNh no provee PWV.
CORE_STUDY_VARIABLES = [
    "temperature",
    "dew_point_temperature",
    "relative_humidity",
    "wind_speed",
    "station_level_pressure",
    "precipitation",
]

# Variables adicionales útiles para contexto o diagnóstico futuro.
# No necesariamente entran al análisis principal, pero conviene saber si existen.
OPTIONAL_DIAGNOSTIC_VARIABLES = [
    "sea_level_pressure",
    "wind_direction",
    "wind_gust",
    "wet_bulb_temperature",
    "altimeter",
    "visibility",
    "precipitation_5_minute",
    "precipitation_15_minute",
    "precipitation_3_hour",
    "precipitation_6_hour",
    "precipitation_9_hour",
    "precipitation_12_hour",
    "precipitation_15_hour",
    "precipitation_18_hour",
    "precipitation_21_hour",
    "precipitation_24_hour",
]

VARIABLES_TO_CHECK = CORE_STUDY_VARIABLES + OPTIONAL_DIAGNOSTIC_VARIABLES


# ---------------------------------------------------------------------------
# Estructuras de salida
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileInventoryRow:
    """
    Una fila por archivo Parquet encontrado.

    Esto permite verificar qué archivos físicos existen antes de hacer cualquier
    análisis de cobertura por variable.
    """

    station_id: str | None
    station_name: str | None
    year: int | None
    path: str
    n_rows: int
    n_columns: int
    first_timestamp: str | None
    last_timestamp: str | None
    n_timestamps: int
    n_hours: int
    has_parseable_dates: bool
    read_status: str
    error_message: str | None


@dataclass(frozen=True)
class CoverageRow:
    """
    Una fila por estación-año-variable o estación-año-mes-variable.

    Se usa tanto para cobertura anual como mensual.
    """

    station_id: str | None
    station_name: str | None
    year: int | None
    month: int | None
    variable: str
    variable_group: str
    variable_present_as_column: bool
    qc_column_present: bool
    n_rows_in_period: int
    n_timestamps_in_period: int
    n_hours_in_period: int
    n_non_null_values: int
    n_numeric_values: int
    n_non_missing_hours: int
    numeric_min: float | None
    numeric_max: float | None
    numeric_mean: float | None
    n_quality_code_non_null: int
    unique_quality_codes: str | None


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def variable_group(variable: str) -> str:
    """
    Clasifica la variable para que los CSV sean fáciles de leer.
    """
    if variable in CORE_STUDY_VARIABLES:
        return "core_study_variable"
    return "optional_diagnostic_variable"


def safe_first_value(df: pd.DataFrame, column: str) -> str | None:
    """
    Devuelve el primer valor no nulo de una columna si existe.

    Se usa para STATION y Station_name.
    """
    if column not in df.columns:
        return None

    values = df[column].dropna()
    if values.empty:
        return None

    return str(values.iloc[0])


def safe_int_from_path(path: Path) -> int | None:
    """
    Intenta obtener el año desde la ruta.

    La estructura esperada es:
        data_raw/noaa/ghcnh/hourly/by_year/2004/parquet/archivo.parquet
    """
    parts = path.parts
    for part in parts:
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def parse_datetime_column(df: pd.DataFrame) -> pd.Series:
    """
    Convierte la columna DATE a datetime.

    Nota metodológica:
    - Aquí no se hace cambio de zona horaria local.
    - Para diagnóstico de cobertura, tratamos DATE como timestamp UTC/naive.
    - La comparación con ERA5 se hará en otra etapa con una decisión explícita
      sobre zona horaria y alineación temporal.
    """
    if "DATE" not in df.columns:
        return pd.Series(pd.NaT, index=df.index)

    return pd.to_datetime(df["DATE"], errors="coerce")


def numeric_series(df: pd.DataFrame, variable: str) -> pd.Series:
    """
    Convierte una columna de variable a numérica.

    Los Parquet leídos muestran muchas columnas como dtype object.
    Por eso convertimos con errors='coerce':
    - valores numéricos válidos -> número
    - texto, blancos o códigos no numéricos -> NaN

    Esto NO modifica los datos crudos.
    Solo se usa para contar disponibilidad numérica real.
    """
    if variable not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")

    return pd.to_numeric(df[variable], errors="coerce")


def summarize_qc_codes(df: pd.DataFrame, variable: str) -> tuple[bool, int, str | None]:
    """
    Resume la columna de código de calidad asociada a una variable.

    Ejemplo:
        temperature -> temperature_Quality_Code

    En esta etapa NO filtramos por calidad.
    Solo registramos qué códigos aparecen para revisarlos después.
    """
    qc_col = f"{variable}_Quality_Code"

    if qc_col not in df.columns:
        return False, 0, None

    qc = df[qc_col].dropna().astype(str).str.strip()
    qc = qc[qc != ""]

    if qc.empty:
        return True, 0, None

    unique_codes = sorted(qc.unique().tolist())
    return True, int(qc.shape[0]), "|".join(unique_codes)


def summarize_period(
    *,
    df: pd.DataFrame,
    dt: pd.Series,
    station_id: str | None,
    station_name: str | None,
    year: int | None,
    month: int | None,
    variable: str,
) -> CoverageRow:
    """
    Calcula cobertura para una variable dentro de un periodo.

    El periodo puede ser:
    - todo el año del archivo
    - un mes específico dentro del archivo
    """
    variable_present = variable in df.columns
    qc_present, n_qc_non_null, qc_codes = summarize_qc_codes(df, variable)

    n_rows = int(len(df))

    valid_dt = dt.dropna()
    n_timestamps = int(valid_dt.nunique())

    if valid_dt.empty:
        hour_bins_all = pd.Series([], dtype="datetime64[ns]")
        n_hours = 0
    else:
        hour_bins_all = valid_dt.dt.floor("h")
        n_hours = int(hour_bins_all.nunique())

    if variable_present:
        values_num = numeric_series(df, variable)
        values_raw = df[variable]
        non_null_mask = values_raw.notna()
        numeric_mask = values_num.notna()

        n_non_null = int(non_null_mask.sum())
        n_numeric = int(numeric_mask.sum())

        if n_numeric > 0:
            numeric_min = float(values_num[numeric_mask].min())
            numeric_max = float(values_num[numeric_mask].max())
            numeric_mean = float(values_num[numeric_mask].mean())

            # Horas con al menos un valor numérico para esta variable.
            dt_numeric = dt[numeric_mask & dt.notna()]
            n_non_missing_hours = int(dt_numeric.dt.floor("h").nunique())
        else:
            numeric_min = None
            numeric_max = None
            numeric_mean = None
            n_non_missing_hours = 0
    else:
        n_non_null = 0
        n_numeric = 0
        numeric_min = None
        numeric_max = None
        numeric_mean = None
        n_non_missing_hours = 0

    return CoverageRow(
        station_id=station_id,
        station_name=station_name,
        year=year,
        month=month,
        variable=variable,
        variable_group=variable_group(variable),
        variable_present_as_column=variable_present,
        qc_column_present=qc_present,
        n_rows_in_period=n_rows,
        n_timestamps_in_period=n_timestamps,
        n_hours_in_period=n_hours,
        n_non_null_values=n_non_null,
        n_numeric_values=n_numeric,
        n_non_missing_hours=n_non_missing_hours,
        numeric_min=numeric_min,
        numeric_max=numeric_max,
        numeric_mean=numeric_mean,
        n_quality_code_non_null=n_qc_non_null,
        unique_quality_codes=qc_codes,
    )


def read_one_file(path: Path) -> tuple[pd.DataFrame | None, FileInventoryRow]:
    """
    Lee un archivo Parquet y produce una fila de inventario de archivo.

    Si el archivo falla, devuelve df=None y una fila con read_status='failed'.
    """
    try:
        df = pd.read_parquet(path)
        dt = parse_datetime_column(df)

        station_id = safe_first_value(df, "STATION")
        station_name = safe_first_value(df, "Station_name")
        year = safe_int_from_path(path)

        valid_dt = dt.dropna()

        if valid_dt.empty:
            first_timestamp = None
            last_timestamp = None
            n_timestamps = 0
            n_hours = 0
            has_parseable_dates = False
        else:
            first_timestamp = valid_dt.min().isoformat()
            last_timestamp = valid_dt.max().isoformat()
            n_timestamps = int(valid_dt.nunique())
            n_hours = int(valid_dt.dt.floor("h").nunique())
            has_parseable_dates = True

        row = FileInventoryRow(
            station_id=station_id,
            station_name=station_name,
            year=year,
            path=str(path),
            n_rows=int(df.shape[0]),
            n_columns=int(df.shape[1]),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            n_timestamps=n_timestamps,
            n_hours=n_hours,
            has_parseable_dates=has_parseable_dates,
            read_status="ok",
            error_message=None,
        )

        return df, row

    except Exception as exc:
        row = FileInventoryRow(
            station_id=None,
            station_name=None,
            year=safe_int_from_path(path),
            path=str(path),
            n_rows=0,
            n_columns=0,
            first_timestamp=None,
            last_timestamp=None,
            n_timestamps=0,
            n_hours=0,
            has_parseable_dates=False,
            read_status="failed",
            error_message=str(exc),
        )

        return None, row


def write_dataframe(df: pd.DataFrame, csv_path: Path, parquet_path: Path) -> None:
    """
    Escribe una tabla tanto en CSV como en Parquet.

    CSV:
        útil para inspección rápida con head, less, Excel, etc.

    Parquet:
        útil para análisis posterior con pandas/xarray/dask.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------

def build_diagnostics(raw_root: Path, outdir: Path) -> None:
    """
    Recorre todos los Parquet descargados y genera diagnósticos.
    """
    files = sorted(raw_root.glob("by_year/*/parquet/*.parquet"))

    if not files:
        raise FileNotFoundError(f"No encontré archivos Parquet en: {raw_root}")

    print(f"Archivos Parquet encontrados: {len(files)}")

    file_inventory_rows: list[FileInventoryRow] = []
    station_year_rows: list[CoverageRow] = []
    station_month_rows: list[CoverageRow] = []

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] Leyendo {path}", flush=True)

        df, file_row = read_one_file(path)
        file_inventory_rows.append(file_row)

        if df is None:
            continue

        dt = parse_datetime_column(df)
        station_id = file_row.station_id
        station_name = file_row.station_name
        year = file_row.year

        # -------------------------------
        # Cobertura por estación-año
        # -------------------------------
        for variable in VARIABLES_TO_CHECK:
            row = summarize_period(
                df=df,
                dt=dt,
                station_id=station_id,
                station_name=station_name,
                year=year,
                month=None,
                variable=variable,
            )
            station_year_rows.append(row)

        # -------------------------------
        # Cobertura por estación-año-mes
        # -------------------------------
        if dt.notna().any():
            month_series = dt.dt.month

            for month in range(1, 13):
                mask = month_series == month

                if not mask.any():
                    # Si no hay filas para ese mes en ese archivo, no generamos fila.
                    # La ausencia quedará implícita y se puede reconstruir después.
                    continue

                df_m = df.loc[mask].copy()
                dt_m = dt.loc[mask]

                for variable in VARIABLES_TO_CHECK:
                    row = summarize_period(
                        df=df_m,
                        dt=dt_m,
                        station_id=station_id,
                        station_name=station_name,
                        year=year,
                        month=month,
                        variable=variable,
                    )
                    station_month_rows.append(row)

    # Convertir listas de dataclasses a DataFrames.
    file_inventory = pd.DataFrame([r.__dict__ for r in file_inventory_rows])
    station_year = pd.DataFrame([r.__dict__ for r in station_year_rows])
    station_month = pd.DataFrame([r.__dict__ for r in station_month_rows])

    # Resumen compacto por variable.
    # Aquí sumamos solo cobertura anual, no mensual, para evitar doble conteo.
    summary = (
        station_year
        .groupby(["variable_group", "variable"], as_index=False)
        .agg(
            station_year_rows=("variable", "size"),
            files_with_column=("variable_present_as_column", "sum"),
            total_rows=("n_rows_in_period", "sum"),
            total_timestamps=("n_timestamps_in_period", "sum"),
            total_hours=("n_hours_in_period", "sum"),
            total_non_null_values=("n_non_null_values", "sum"),
            total_numeric_values=("n_numeric_values", "sum"),
            total_non_missing_hours=("n_non_missing_hours", "sum"),
            min_value=("numeric_min", "min"),
            max_value=("numeric_max", "max"),
            mean_of_file_means=("numeric_mean", "mean"),
        )
        .sort_values(["variable_group", "variable"])
        .reset_index(drop=True)
    )

    # Salidas.
    write_dataframe(
        file_inventory,
        outdir / "ghcnh_hourly_file_inventory_2004_2023.csv",
        outdir / "ghcnh_hourly_file_inventory_2004_2023.parquet",
    )

    write_dataframe(
        station_year,
        outdir / "ghcnh_hourly_variable_coverage_station_year.csv",
        outdir / "ghcnh_hourly_variable_coverage_station_year.parquet",
    )

    write_dataframe(
        station_month,
        outdir / "ghcnh_hourly_variable_coverage_station_month.csv",
        outdir / "ghcnh_hourly_variable_coverage_station_month.parquet",
    )

    write_dataframe(
        summary,
        outdir / "ghcnh_hourly_variable_coverage_summary.csv",
        outdir / "ghcnh_hourly_variable_coverage_summary.parquet",
    )

    print("\nListo. Archivos escritos en:")
    print(f"  {outdir}")
    print("\nResumen por variable:")
    print(summary.to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construir diagnóstico de cobertura real por variable para GHCNh PR."
    )

    parser.add_argument(
        "--raw-root",
        default="data_raw/noaa/ghcnh/hourly",
        help="Raíz donde están los Parquet crudos descargados.",
    )

    parser.add_argument(
        "--outdir",
        default="data_interim/noaa/ghcnh_hourly/coverage_diagnostics",
        help="Directorio de salida para tablas de diagnóstico.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    raw_root = Path(args.raw_root)
    outdir = Path(args.outdir)

    build_diagnostics(raw_root=raw_root, outdir=outdir)


if __name__ == "__main__":
    main()
