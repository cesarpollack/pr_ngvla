#!/usr/bin/env python3
"""
download_ghcnh_hourly_station_year_pr.py

Descarga archivos horarios GHCNh para Puerto Rico usando el inventario maestro
ya construido en una etapa previa del proyecto.

Objetivo de esta etapa
----------------------
- Descargar TODO lo que exista para las estaciones del inventario maestro.
- No filtrar por variable.
- No limpiar datos.
- No decidir todavía qué estación sirve o no sirve.
- Registrar cada intento de descarga en un archivo log CSV.

Estrategia
----------
Unidad de descarga:

    1 archivo = 1 estación × 1 año

Por ejemplo:

    GHCNh_RQC00660061_2004.parquet
    GHCNh_RQC00660061_2005.parquet
    ...

Por qué así:
- Evita archivos gigantes.
- Permite reanudar el proceso si se cae la conexión.
- Permite repetir solo los años o estaciones que fallen.
- Permite diagnosticar cobertura real después.

Notas importantes
-----------------
- Este script usa descarga directa HTTPS de NOAA/NCEI.
- No usa token CDO.
- Por defecto intenta descargar Parquet primero.
- Si Parquet no existe, intenta descargar PSV.
- Si ambos fallan con 404, registra "missing_404".
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


# ---------------------------------------------------------------------------
# Configuración base
# ---------------------------------------------------------------------------

# URL base oficial de archivos GHCNh.
# El patrón usado es:
#   .../hourly/access/by-year/<YEAR>/<FORMAT>/GHCNh_<STATION>_<YEAR>.<FORMAT>
BASE_URL = (
    "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/"
    "hourly/access/by-year"
)

# Formatos que intentaremos en orden cuando mode="auto".
# Parquet es preferido porque es más eficiente para análisis posterior.
DEFAULT_FORMAT_ORDER = ("parquet", "psv")


# ---------------------------------------------------------------------------
# Estructuras de datos simples
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DownloadTask:
    """
    Representa una unidad lógica de trabajo: estación × año.

    Esta clase NO descarga nada por sí misma. Solo guarda los metadatos
    necesarios para construir las URLs y registrar el log.
    """

    station_id: str
    station_name: str
    lat: float | None
    lon: float | None
    elevation_m: float | None
    inventory_start_year: int | None
    inventory_end_year: int | None
    inventory_years_with_data: int | None
    year: int


@dataclass(frozen=True)
class AttemptResult:
    """
    Resultado de un intento específico de descarga.

    Importante:
    - Una tarea estación × año puede tener más de un intento.
      Ejemplo: primero Parquet, luego PSV si Parquet no existe.
    """

    station_id: str
    station_name: str
    lat: float | None
    lon: float | None
    elevation_m: float | None
    inventory_start_year: int | None
    inventory_end_year: int | None
    inventory_years_with_data: int | None
    year: int
    file_format: str
    url: str
    raw_path: str
    status: str
    http_status: int | None
    bytes_written: int
    sha256: str | None
    attempted_at_utc: str
    elapsed_seconds: float
    error_message: str | None


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """
    Devuelve la hora actual en UTC con formato ISO.

    Esto ayuda a saber cuándo se hizo cada intento de descarga.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_int(value) -> int | None:
    """
    Convierte un valor a entero si es posible.

    Se usa porque algunas columnas pueden venir como NaN.
    """
    if pd.isna(value):
        return None
    return int(value)


def safe_float(value) -> float | None:
    """
    Convierte un valor a float si es posible.

    Se usa para latitud, longitud y elevación.
    """
    if pd.isna(value):
        return None
    return float(value)


def build_url(station_id: str, year: int, file_format: str) -> str:
    """
    Construye la URL oficial del archivo estación-año.

    Ejemplo:
    https://www.ncei.noaa.gov/.../hourly/access/by-year/2023/parquet/GHCNh_RQC00660061_2023.parquet
    """
    filename = f"GHCNh_{station_id}_{year}.{file_format}"
    return f"{BASE_URL}/{year}/{file_format}/{filename}"


def build_raw_path(raw_root: Path, station_id: str, year: int, file_format: str) -> Path:
    """
    Construye la ruta local donde se guardará el archivo descargado.

    Estructura local:
        data_raw/noaa/ghcnh/hourly/by_year/<YEAR>/<FORMAT>/GHCNh_<station>_<year>.<format>
    """
    filename = f"GHCNh_{station_id}_{year}.{file_format}"
    return raw_root / "by_year" / str(year) / file_format / filename


def sha256_file(path: Path) -> str:
    """
    Calcula SHA256 del archivo descargado.

    Esto permite verificar que el archivo no cambió entre corridas.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inventory(inventory_path: Path) -> pd.DataFrame:
    """
    Lee el inventario maestro GHCNh de Puerto Rico.

    Requisito mínimo:
        station_id

    No filtramos por prelim_usable.
    Usamos todas las estaciones presentes en el inventario maestro.
    """
    if not inventory_path.exists():
        raise FileNotFoundError(f"No existe el inventario: {inventory_path}")

    df = pd.read_parquet(inventory_path)

    if "station_id" not in df.columns:
        raise ValueError(
            f"El inventario no tiene columna 'station_id'. Columnas disponibles: {df.columns.tolist()}"
        )

    # Evita duplicados accidentales.
    df = df.drop_duplicates(subset=["station_id"]).copy()

    # Orden estable para que las descargas sean reproducibles.
    df = df.sort_values("station_id").reset_index(drop=True)

    return df


def build_tasks(df: pd.DataFrame, start_year: int, end_year: int) -> list[DownloadTask]:
    """
    Construye todas las tareas estación × año.

    Importante:
    - No se filtra por start_year/end_year del inventario.
    - Si una estación no tiene archivo para cierto año, NOAA responderá 404.
    - Ese 404 se registra en el log.
    """
    tasks: list[DownloadTask] = []

    for _, row in df.iterrows():
        for year in range(start_year, end_year + 1):
            tasks.append(
                DownloadTask(
                    station_id=str(row["station_id"]),
                    station_name=str(row.get("station_name", "")),
                    lat=safe_float(row.get("lat")),
                    lon=safe_float(row.get("lon")),
                    elevation_m=safe_float(row.get("elevation_m")),
                    inventory_start_year=safe_int(row.get("start_year")),
                    inventory_end_year=safe_int(row.get("end_year")),
                    inventory_years_with_data=safe_int(row.get("years_with_data")),
                    year=year,
                )
            )

    return tasks


def ensure_log_header(log_path: Path) -> None:
    """
    Crea el archivo log con encabezado si todavía no existe.

    Si ya existe, no lo borra. Esto permite reanudar procesos largos.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if log_path.exists():
        return

    fieldnames = list(AttemptResult.__dataclass_fields__.keys())

    with log_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def append_log(log_path: Path, result: AttemptResult) -> None:
    """
    Añade una fila al log CSV inmediatamente después de cada intento.

    Esto es importante porque si el servidor tumba el job, el log conserva
    el progreso hasta el último intento terminado.
    """
    fieldnames = list(AttemptResult.__dataclass_fields__.keys())

    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(result.__dict__)


def download_one(
    task: DownloadTask,
    file_format: str,
    raw_root: Path,
    *,
    force: bool,
    timeout: int,
) -> AttemptResult:
    """
    Intenta descargar un archivo específico para una tarea y un formato.

    Estados posibles:
    - downloaded: archivo descargado correctamente.
    - skipped_existing: el archivo ya existe y no se usó --force.
    - missing_404: NOAA respondió 404; el archivo no existe para esa estación/año/formato.
    - failed: error de red u otro error no controlado.
    """
    url = build_url(task.station_id, task.year, file_format)
    raw_path = build_raw_path(raw_root, task.station_id, task.year, file_format)
    attempted_at = utc_now_iso()
    t0 = time.time()

    # Si el archivo ya existe, no se vuelve a descargar a menos que el usuario pida --force.
    if raw_path.exists() and raw_path.stat().st_size > 0 and not force:
        elapsed = time.time() - t0
        return AttemptResult(
            station_id=task.station_id,
            station_name=task.station_name,
            lat=task.lat,
            lon=task.lon,
            elevation_m=task.elevation_m,
            inventory_start_year=task.inventory_start_year,
            inventory_end_year=task.inventory_end_year,
            inventory_years_with_data=task.inventory_years_with_data,
            year=task.year,
            file_format=file_format,
            url=url,
            raw_path=str(raw_path),
            status="skipped_existing",
            http_status=None,
            bytes_written=raw_path.stat().st_size,
            sha256=sha256_file(raw_path),
            attempted_at_utc=attempted_at,
            elapsed_seconds=round(elapsed, 3),
            error_message=None,
        )

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = raw_path.with_suffix(raw_path.suffix + ".part")

    # Si quedó un archivo parcial de una corrida interrumpida, se reemplaza.
    if part_path.exists():
        part_path.unlink()

    try:
        req = Request(
            url,
            headers={
                "User-Agent": "pr_ngvla-ghcnh-downloader/1.0",
            },
        )

        with urlopen(req, timeout=timeout) as response:
            http_status = getattr(response, "status", None)

            with part_path.open("wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

        # Renombrar al final evita dejar un archivo final incompleto.
        part_path.replace(raw_path)

        bytes_written = raw_path.stat().st_size
        checksum = sha256_file(raw_path)
        elapsed = time.time() - t0

        return AttemptResult(
            station_id=task.station_id,
            station_name=task.station_name,
            lat=task.lat,
            lon=task.lon,
            elevation_m=task.elevation_m,
            inventory_start_year=task.inventory_start_year,
            inventory_end_year=task.inventory_end_year,
            inventory_years_with_data=task.inventory_years_with_data,
            year=task.year,
            file_format=file_format,
            url=url,
            raw_path=str(raw_path),
            status="downloaded",
            http_status=http_status,
            bytes_written=bytes_written,
            sha256=checksum,
            attempted_at_utc=attempted_at,
            elapsed_seconds=round(elapsed, 3),
            error_message=None,
        )

    except HTTPError as e:
        elapsed = time.time() - t0

        # 404 significa que ese archivo no existe en NOAA para esa estación/año/formato.
        if e.code == 404:
            status = "missing_404"
        else:
            status = "failed"

        return AttemptResult(
            station_id=task.station_id,
            station_name=task.station_name,
            lat=task.lat,
            lon=task.lon,
            elevation_m=task.elevation_m,
            inventory_start_year=task.inventory_start_year,
            inventory_end_year=task.inventory_end_year,
            inventory_years_with_data=task.inventory_years_with_data,
            year=task.year,
            file_format=file_format,
            url=url,
            raw_path=str(raw_path),
            status=status,
            http_status=e.code,
            bytes_written=0,
            sha256=None,
            attempted_at_utc=attempted_at,
            elapsed_seconds=round(elapsed, 3),
            error_message=str(e),
        )

    except (URLError, TimeoutError, OSError) as e:
        elapsed = time.time() - t0

        return AttemptResult(
            station_id=task.station_id,
            station_name=task.station_name,
            lat=task.lat,
            lon=task.lon,
            elevation_m=task.elevation_m,
            inventory_start_year=task.inventory_start_year,
            inventory_end_year=task.inventory_end_year,
            inventory_years_with_data=task.inventory_years_with_data,
            year=task.year,
            file_format=file_format,
            url=url,
            raw_path=str(raw_path),
            status="failed",
            http_status=None,
            bytes_written=0,
            sha256=None,
            attempted_at_utc=attempted_at,
            elapsed_seconds=round(elapsed, 3),
            error_message=str(e),
        )

    finally:
        # Si ocurrió un error, no queremos dejar basura parcial.
        if part_path.exists():
            part_path.unlink()


def run_downloads(
    tasks: Iterable[DownloadTask],
    *,
    raw_root: Path,
    log_path: Path,
    file_mode: str,
    force: bool,
    timeout: int,
    sleep_seconds: float,
) -> None:
    """
    Ejecuta las descargas.

    file_mode:
    - auto: intenta parquet; si parquet no existe, intenta psv.
    - parquet: solo intenta parquet.
    - psv: solo intenta psv.
    """
    ensure_log_header(log_path)

    if file_mode == "auto":
        format_order = DEFAULT_FORMAT_ORDER
    else:
        format_order = (file_mode,)

    total_tasks = 0

    for task in tasks:
        total_tasks += 1
        print(f"\n=== {task.station_id} | {task.year} ===", flush=True)

        station_year_done = False

        for file_format in format_order:
            result = download_one(
                task,
                file_format,
                raw_root,
                force=force,
                timeout=timeout,
            )

            append_log(log_path, result)

            print(
                f"{result.status:>16} | {file_format:7s} | "
                f"bytes={result.bytes_written} | {result.raw_path}",
                flush=True,
            )

            # Si descargó o ya existía Parquet/PSV, no hace falta intentar el otro formato.
            if result.status in {"downloaded", "skipped_existing"}:
                station_year_done = True
                break

            # Si Parquet no existe y estamos en auto, seguimos a PSV.
            # Si fue otro error, también dejamos que el modo auto intente el siguiente formato,
            # pero el error queda registrado en el log.
            time.sleep(sleep_seconds)

        if not station_year_done:
            print("No se obtuvo archivo para esta estación-año.", flush=True)

        time.sleep(sleep_seconds)

    print(f"\nProceso terminado. Tareas estación-año procesadas: {total_tasks}")
    print(f"Log escrito en: {log_path}")


def parse_args() -> argparse.Namespace:
    """
    Define argumentos de línea de comando.

    Los defaults están ajustados para el proyecto pr_ngvla.
    """
    parser = argparse.ArgumentParser(
        description="Descargar archivos GHCNh por estación × año para Puerto Rico."
    )

    parser.add_argument(
        "--inventory",
        default="data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet",
        help="Inventario maestro GHCNh de Puerto Rico en formato Parquet.",
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2004,
        help="Primer año a descargar.",
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=2023,
        help="Último año a descargar.",
    )

    parser.add_argument(
        "--raw-root",
        default="data_raw/noaa/ghcnh/hourly",
        help="Directorio raíz para guardar archivos crudos descargados.",
    )

    parser.add_argument(
        "--log",
        default="data_raw/noaa/ghcnh/hourly/logs/ghcnh_hourly_download_log_2004_2023.csv",
        help="Archivo CSV donde se registra cada intento de descarga.",
    )

    parser.add_argument(
        "--file-mode",
        choices=["auto", "parquet", "psv"],
        default="auto",
        help="Formato a descargar. auto intenta Parquet y luego PSV si hace falta.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Volver a descargar aunque el archivo ya exista localmente.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Timeout por intento de descarga, en segundos.",
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Pausa entre intentos para no golpear el servidor de NOAA.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No descarga. Solo muestra cuántas tareas se construirían y algunos ejemplos.",
    )

    parser.add_argument(
        "--max-station-years",
        type=int,
        default=None,
        help="Límite opcional para pruebas. Ejemplo: 3 procesa solo 3 estación-año.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    inventory_path = Path(args.inventory)
    raw_root = Path(args.raw_root)
    log_path = Path(args.log)

    df_inventory = load_inventory(inventory_path)
    tasks = build_tasks(df_inventory, args.start_year, args.end_year)

    if args.max_station_years is not None:
        tasks = tasks[: args.max_station_years]

    print("Inventario cargado:")
    print(f"  estaciones: {len(df_inventory)}")
    print(f"  años: {args.start_year}-{args.end_year}")
    print(f"  tareas estación-año: {len(tasks)}")
    print(f"  modo de archivo: {args.file_mode}")
    print(f"  raw root: {raw_root}")
    print(f"  log: {log_path}")

    if args.dry_run:
        print("\nDRY RUN: no se descargará nada.")
        print("\nPrimeras tareas:")
        for task in tasks[:5]:
            print(
                f"  {task.station_id} | {task.year} | "
                f"{build_url(task.station_id, task.year, 'parquet')}"
            )
        return

    run_downloads(
        tasks,
        raw_root=raw_root,
        log_path=log_path,
        file_mode=args.file_mode,
        force=args.force,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
