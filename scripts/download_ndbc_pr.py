#!/usr/bin/env python3
"""
download_ndbc_pr.py

Acquire NOAA/NDBC metadata and historical standard meteorological (stdmet)
files for Puerto Rico and nearby coastal/marine candidate stations.

This script is intentionally limited to acquisition and verification. It does
not parse, clean, validate physical values, or produce scientific comparisons.

Recommended usage from the repository root, inside tmux:

    python scripts/download_ndbc_pr.py metadata
    python scripts/download_ndbc_pr.py availability
    python scripts/download_ndbc_pr.py summary
    python scripts/download_ndbc_pr.py download

Outputs
-------
- Candidate station list:
  data_raw/noaa/ndbc/metadata/ndbc_pr_candidate_stations.txt

- Official metadata snapshots / station pages:
  data_raw/noaa/ndbc/metadata/activestations.xml
  data_raw/noaa/ndbc/metadata/stationmetadata.xml
  data_raw/noaa/ndbc/raw/station_pages/<STATION>_station_page.html
  data_raw/noaa/ndbc/raw/station_pages/<STATION>_station_history.html

- Availability table:
  data_raw/noaa/ndbc/metadata/ndbc_stdmet_availability_2004_2023.csv

- Downloaded historical stdmet files:
  data_raw/noaa/ndbc/raw/stdmet/<station_lower>h<year>.txt.gz

- Logs:
  logs/ndbc_*.log

Notes
-----
- Raw data under data_raw/ should not be committed to Git.
- Historical stdmet files use NDBC naming convention:
  https://www.ndbc.noaa.gov/data/historical/stdmet/<station_lower>h<year>.txt.gz
- Time in NDBC historical files should be treated as UTC. Confirm units from
  NDBC measurement descriptions before processing.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Optional


DEFAULT_STATIONS = [
    # Numeric buoys / coastal stations near Puerto Rico and the northeast Caribbean.
    # This is a candidate list, not the final scientific selection.
    "41043",
    "41053",
    "41056",
    "42085",
    "41115",
    "41121",
    # Alphanumeric coastal stations historically relevant around Puerto Rico.
    "SJNP4",
    "FRDP4",
    "AROP4",
    "VQSP4",
    "MGIP4",
    "LPRP4",
    "JOXP4",
]

NDBC_BASE = "https://www.ndbc.noaa.gov"
STD_MET_BASE = f"{NDBC_BASE}/data/historical/stdmet"
ACTIVE_STATIONS_URL = f"{NDBC_BASE}/activestations.xml"
STATION_METADATA_URL = f"{NDBC_BASE}/metadata/stationmetadata.xml"

DEFAULT_START_YEAR = 2004
DEFAULT_END_YEAR = 2023
DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.15


@dataclass(frozen=True)
class Paths:
    repo_root: pathlib.Path
    base_dir: pathlib.Path
    metadata_dir: pathlib.Path
    raw_dir: pathlib.Path
    stdmet_dir: pathlib.Path
    station_page_dir: pathlib.Path
    logs_dir: pathlib.Path
    station_list: pathlib.Path
    availability_csv: pathlib.Path
    summary_csv: pathlib.Path
    metadata_log: pathlib.Path
    availability_log: pathlib.Path
    download_log: pathlib.Path


def make_paths(repo_root: pathlib.Path, start_year: int, end_year: int) -> Paths:
    base_dir = repo_root / "data_raw" / "noaa" / "ndbc"
    metadata_dir = base_dir / "metadata"
    raw_dir = base_dir / "raw"
    stdmet_dir = raw_dir / "stdmet"
    station_page_dir = raw_dir / "station_pages"
    logs_dir = repo_root / "logs"

    return Paths(
        repo_root=repo_root,
        base_dir=base_dir,
        metadata_dir=metadata_dir,
        raw_dir=raw_dir,
        stdmet_dir=stdmet_dir,
        station_page_dir=station_page_dir,
        logs_dir=logs_dir,
        station_list=metadata_dir / "ndbc_pr_candidate_stations.txt",
        availability_csv=metadata_dir / f"ndbc_stdmet_availability_{start_year}_{end_year}.csv",
        summary_csv=metadata_dir / f"ndbc_stdmet_availability_summary_{start_year}_{end_year}.csv",
        metadata_log=logs_dir / f"ndbc_metadata_{start_year}_{end_year}.log",
        availability_log=logs_dir / f"ndbc_stdmet_availability_{start_year}_{end_year}.log",
        download_log=logs_dir / f"ndbc_stdmet_download_{start_year}_{end_year}.log",
    )


def ensure_directories(paths: Paths) -> None:
    for directory in [
        paths.metadata_dir,
        paths.raw_dir,
        paths.stdmet_dir,
        paths.station_page_dir,
        paths.logs_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log_line(path: pathlib.Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{utc_now_iso()}] {message}\n")


def station_for_url(station: str) -> str:
    """NDBC historical filenames for alphanumeric stations are lower-case."""
    return station.strip().lower()


def read_stations(station_list: pathlib.Path) -> list[str]:
    stations: list[str] = []
    with station_list.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            stations.append(line.upper())
    return stations


def write_default_station_list(paths: Paths, overwrite: bool = False) -> None:
    if paths.station_list.exists() and not overwrite:
        print(f"Station list already exists: {paths.station_list}")
        return

    paths.station_list.parent.mkdir(parents=True, exist_ok=True)
    with paths.station_list.open("w", encoding="utf-8") as fh:
        fh.write("# NOAA/NDBC Puerto Rico and nearby candidate stations\n")
        fh.write("# Candidate list only; final scientific selection must be verified later.\n")
        fh.write("# One station ID per line. Lines beginning with # are ignored.\n")
        for station in DEFAULT_STATIONS:
            fh.write(f"{station}\n")

    print(f"Wrote station list: {paths.station_list}")


def build_stdmet_url(station: str, year: int) -> str:
    st = station_for_url(station)
    return f"{STD_MET_BASE}/{st}h{year}.txt.gz"


def build_station_page_url(station: str) -> str:
    return f"{NDBC_BASE}/station_page.php?station={station_for_url(station)}"


def build_station_history_url(station: str) -> str:
    return f"{NDBC_BASE}/station_history.php?station={station_for_url(station)}"


def open_url(url: str, timeout: int) -> urllib.response.addinfourl:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pr-ngvla-ndbc-downloader/1.0 (+https://github.com/cesarpollack/pr_ngvla)",
        },
    )
    return urllib.request.urlopen(request, timeout=timeout)


def url_exists(url: str, timeout: int) -> tuple[bool, Optional[int], str]:
    """
    Return (exists, content_length, message).

    Uses a minimal GET rather than HEAD because some simple directory servers are
    more reliable with GET. The file is not downloaded here; only headers are read.
    """
    try:
        with open_url(url, timeout=timeout) as response:
            status = getattr(response, "status", None)
            content_length_raw = response.headers.get("Content-Length")
            content_length = int(content_length_raw) if content_length_raw else None
            if status is None or 200 <= int(status) < 300:
                return True, content_length, "OK"
            return False, content_length, f"HTTP_STATUS_{status}"
    except urllib.error.HTTPError as exc:
        return False, None, f"HTTP_ERROR_{exc.code}"
    except urllib.error.URLError as exc:
        return False, None, f"URL_ERROR_{exc.reason}"
    except TimeoutError:
        return False, None, "TIMEOUT"


def download_file(
    url: str,
    output_path: pathlib.Path,
    *,
    timeout: int,
    overwrite: bool = False,
) -> tuple[bool, str, int]:
    """Download URL to output_path via a .part file. Returns success, message, bytes."""
    if output_path.exists() and output_path.stat().st_size > 0 and not overwrite:
        return True, "SKIPPED_EXISTS", output_path.stat().st_size

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")

    try:
        with open_url(url, timeout=timeout) as response, tmp_path.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
        tmp_path.replace(output_path)
        return True, "DOWNLOADED", total
    except urllib.error.HTTPError as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, f"HTTP_ERROR_{exc.code}", 0
    except urllib.error.URLError as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, f"URL_ERROR_{exc.reason}", 0
    except TimeoutError:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, "TIMEOUT", 0


def mode_init(paths: Paths, overwrite_station_list: bool) -> None:
    ensure_directories(paths)
    write_default_station_list(paths, overwrite=overwrite_station_list)
    print("Initialized NDBC acquisition directories.")
    print(f"Base directory: {paths.base_dir}")


def mode_metadata(args: argparse.Namespace, paths: Paths) -> None:
    ensure_directories(paths)
    write_default_station_list(paths, overwrite=args.overwrite_station_list)
    paths.metadata_log.write_text("", encoding="utf-8")

    downloads = [
        (ACTIVE_STATIONS_URL, paths.metadata_dir / "activestations.xml"),
        (STATION_METADATA_URL, paths.metadata_dir / "stationmetadata.xml"),
    ]

    for url, out in downloads:
        ok, message, nbytes = download_file(url, out, timeout=args.timeout, overwrite=args.overwrite)
        print(f"{message:16s} {nbytes:10d} {out}")
        log_line(paths.metadata_log, f"{message} bytes={nbytes} url={url} output={out}")
        time.sleep(args.sleep)

    stations = read_stations(paths.station_list)
    for station in stations:
        page_url = build_station_page_url(station)
        hist_url = build_station_history_url(station)
        page_out = paths.station_page_dir / f"{station}_station_page.html"
        hist_out = paths.station_page_dir / f"{station}_station_history.html"

        for url, out in [(page_url, page_out), (hist_url, hist_out)]:
            ok, message, nbytes = download_file(url, out, timeout=args.timeout, overwrite=args.overwrite)
            print(f"{station:8s} {message:16s} {nbytes:10d} {out}")
            log_line(paths.metadata_log, f"station={station} {message} bytes={nbytes} url={url} output={out}")
            time.sleep(args.sleep)

    print("\nMetadata acquisition complete.")
    print(f"Station list: {paths.station_list}")
    print(f"Metadata log: {paths.metadata_log}")


def mode_availability(args: argparse.Namespace, paths: Paths) -> None:
    ensure_directories(paths)
    write_default_station_list(paths, overwrite=args.overwrite_station_list)
    stations = read_stations(paths.station_list)

    paths.availability_log.write_text("", encoding="utf-8")

    fieldnames = [
        "station",
        "year",
        "status",
        "message",
        "content_length_bytes",
        "url",
        "local_path",
    ]

    with paths.availability_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for station in stations:
            for year in range(args.start_year, args.end_year + 1):
                url = build_stdmet_url(station, year)
                local_path = paths.stdmet_dir / f"{station_for_url(station)}h{year}.txt.gz"
                exists, content_length, message = url_exists(url, timeout=args.timeout)
                status = "OK" if exists else "MISSING"

                writer.writerow(
                    {
                        "station": station,
                        "year": year,
                        "status": status,
                        "message": message,
                        "content_length_bytes": content_length if content_length is not None else "",
                        "url": url,
                        "local_path": str(local_path),
                    }
                )

                line = f"{station} {year} {status} {message} {url}"
                print(line)
                log_line(paths.availability_log, line)
                time.sleep(args.sleep)

    print("\nAvailability check complete.")
    print(f"Availability CSV: {paths.availability_csv}")
    print(f"Availability log: {paths.availability_log}")
    print_availability_summary(paths.availability_csv)


def read_availability_rows(path: pathlib.Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Availability CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def summarize_availability(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        station = row["station"]
        status = row["status"]
        counts.setdefault(station, {"OK": 0, "MISSING": 0})
        if status in counts[station]:
            counts[station][status] += 1

    summary = []
    for station in sorted(counts):
        summary.append(
            {
                "station": station,
                "available_years": str(counts[station]["OK"]),
                "missing_years": str(counts[station]["MISSING"]),
            }
        )
    return summary


def print_availability_summary(availability_csv: pathlib.Path) -> None:
    rows = read_availability_rows(availability_csv)
    total_ok = sum(1 for row in rows if row["status"] == "OK")
    total_missing = sum(1 for row in rows if row["status"] == "MISSING")

    print("\nAvailability summary")
    print("--------------------")
    print(f"OK files:      {total_ok}")
    print(f"Missing files: {total_missing}")
    print("\nAvailable years by station:")

    for item in summarize_availability(rows):
        print(f"{int(item['available_years']):5d}  {item['station']}")


def mode_summary(paths: Paths) -> None:
    rows = read_availability_rows(paths.availability_csv)
    summary = summarize_availability(rows)

    with paths.summary_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["station", "available_years", "missing_years"])
        writer.writeheader()
        writer.writerows(summary)

    print_availability_summary(paths.availability_csv)
    print(f"\nWrote summary CSV: {paths.summary_csv}")


def mode_download(args: argparse.Namespace, paths: Paths) -> None:
    ensure_directories(paths)
    rows = read_availability_rows(paths.availability_csv)
    ok_rows = [row for row in rows if row["status"] == "OK"]

    paths.download_log.write_text("", encoding="utf-8")

    n_downloaded = 0
    n_skipped = 0
    n_failed = 0

    for row in ok_rows:
        station = row["station"]
        year = row["year"]
        url = row["url"]
        local_path = pathlib.Path(row["local_path"])

        if not local_path.is_absolute():
            local_path = paths.repo_root / local_path

        success, message, nbytes = download_file(
            url,
            local_path,
            timeout=args.timeout,
            overwrite=args.overwrite,
        )

        if success and message == "DOWNLOADED":
            n_downloaded += 1
        elif success and message == "SKIPPED_EXISTS":
            n_skipped += 1
        else:
            n_failed += 1

        line = f"station={station} year={year} {message} bytes={nbytes} url={url} output={local_path}"
        print(line)
        log_line(paths.download_log, line)
        time.sleep(args.sleep)

    print("\nDownload complete.")
    print(f"Downloaded: {n_downloaded}")
    print(f"Skipped existing: {n_skipped}")
    print(f"Failed: {n_failed}")
    print(f"Download log: {paths.download_log}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire NOAA/NDBC metadata and historical stdmet files for PR-ngVLA.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=["init", "metadata", "availability", "summary", "download"],
        help="Workflow stage to run.",
    )
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Repository root. Defaults to current working directory.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite downloaded metadata/raw files if they already exist.",
    )
    parser.add_argument(
        "--overwrite-station-list",
        action="store_true",
        help="Overwrite the candidate station list with the script defaults.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.end_year < args.start_year:
        print("ERROR: --end-year must be greater than or equal to --start-year", file=sys.stderr)
        return 2

    repo_root = args.repo_root.resolve()
    paths = make_paths(repo_root, args.start_year, args.end_year)

    try:
        if args.mode == "init":
            mode_init(paths, overwrite_station_list=args.overwrite_station_list)
        elif args.mode == "metadata":
            mode_metadata(args, paths)
        elif args.mode == "availability":
            mode_availability(args, paths)
        elif args.mode == "summary":
            mode_summary(paths)
        elif args.mode == "download":
            mode_download(args, paths)
        else:
            raise RuntimeError(f"Unhandled mode: {args.mode}")
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
