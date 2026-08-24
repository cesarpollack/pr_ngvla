#!/usr/bin/env python3
"""
download_usgs_nwis_pr.py — USGS NWIS metadata/inventory acquisition for PR-ngVLA.

Scope
-----
This script is intentionally limited to USGS NWIS station/parameter discovery
and availability inventory for Puerto Rico. It does not clean data, compare with
ERA5/ERA5-Land, make maps, or produce scientific conclusions.

Workflow
--------
1) init
   Create the expected directory structure and write candidate parameter scope notes.

2) sites
   Query the official USGS NWIS Site Service for Puerto Rico sites with selected
   candidate parameters and IV/DV period-of-record metadata overlapping the project
   window.

3) summary
   Rebuild compact station and parameter summary tables from the parsed Site Service
   output.

4) probe-precip-uv
   Make small USGS IV requests for precipitation (parameter 00045) to verify
   whether historical unit-value observations are accessible and what timestamp
   spacing they use. This is a verification probe, not a mass scientific download.

5) download-precip-uv
   Download raw USGS IV/unit-value precipitation (parameter 00045) for selected
   sites with hourly-or-finer probe cadence. The download is chunked by time
   interval, writes raw RDB files, and writes a manifest/audit CSV. It does not
   clean, aggregate, gap-fill, compare, or interpret the data scientifically.

Outputs
-------
data_raw/usgs/nwis/metadata/
  usgs_nwis_candidate_parameter_scope_notes.csv
  usgs_nwis_pr_site_series_catalog_<START>_<END>_candidate_params.rdb
  usgs_nwis_pr_site_series_catalog_<START>_<END>_candidate_params.csv
  usgs_nwis_pr_sites_<START>_<END>_candidate_params.csv
  usgs_nwis_pr_parameter_inventory_<START>_<END>_candidate_params.csv
  usgs_nwis_pr_availability_summary_<START>_<END>_candidate_params.csv
  usgs_nwis_pr_precipitation_uv_probe_<START>_<END>.csv
  usgs_nwis_pr_precipitation_uv_download_manifest_<START>_<END>.csv

data_raw/usgs/nwis/raw/precipitation_uv/
  <site_no>/<year>/raw USGS IV RDB chunks

logs/usgs/nwis/
  download_usgs_nwis_pr.log

Design notes
------------
- Uses only Python standard library to keep the workflow portable.
- Uses the official USGS Water Services Site Service endpoint.
- Treats all NWIS observations as point observations at site latitude/longitude.
- Candidate parameter labels in this script are methodological hints only.
  The authoritative parameter names/units must be read from USGS output columns
  such as parm_cd, parm_nm, parm_units when available.
"""

from __future__ import annotations

import argparse
import csv
import json
import datetime as dt
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SITE_SERVICE_URL = "https://waterservices.usgs.gov/nwis/site/"
IV_SERVICE_URL = "https://nwis.waterservices.usgs.gov/nwis/iv/"

DEFAULT_START = "2004-01-01"
DEFAULT_END = "2023-12-31"
DEFAULT_STATE_CD = "PR"
DEFAULT_TIMEOUT = 120
DEFAULT_SLEEP_SECONDS = 0.5

# Candidate parameters for discovery only. Do not treat the labels below as a
# replacement for the official USGS parameter metadata returned by the service.
DEFAULT_PARAMETER_CODES = [
    "00045",  # precipitation
    "00060",  # discharge
    "00065",  # gage height / stage
    "00010",  # water temperature
    "00020",  # air temperature
    "00052",  # relative humidity, if present in NWIS
    "75969",  # barometric pressure, if present in NWIS
]

PARAMETER_SCOPE_NOTES: dict[str, dict[str, str]] = {
    "00045": {
        "candidate_label": "Precipitation",
        "physical_scope": "Point precipitation measurement at the monitoring location if available.",
        "use_for_pr_ngvla": "Potential partial comparison for precipitation, depending on temporal coverage and units.",
        "caution": "Verify availability, units, sensor/instrument metadata, and whether values are IV or DV before scientific use.",
    },
    "00060": {
        "candidate_label": "Discharge / streamflow",
        "physical_scope": "Hydrologic flow at a stream/river site; usually derived from stage-discharge relation.",
        "use_for_pr_ngvla": "Hydrologic context only; not direct validation of atmospheric precipitation, wind, RH, temperature, or PWV.",
        "caution": "Do not interpret discharge as local rainfall without watershed-response analysis.",
    },
    "00065": {
        "candidate_label": "Gage height / stage",
        "physical_scope": "Water level height at the streamgage or hydrologic monitoring site.",
        "use_for_pr_ngvla": "Hydrologic/flood-response context only.",
        "caution": "Not an atmospheric variable and not spatially representative beyond the site/water body.",
    },
    "00010": {
        "candidate_label": "Water temperature",
        "physical_scope": "Water temperature at the hydrologic monitoring location.",
        "use_for_pr_ngvla": "Environmental/hydrologic context only; not air temperature.",
        "caution": "Do not use as a substitute for near-surface air temperature.",
    },
    "00020": {
        "candidate_label": "Air temperature",
        "physical_scope": "Point air-temperature observation at the monitoring location if available.",
        "use_for_pr_ngvla": "Potential partial comparison for local air temperature if coverage is adequate.",
        "caution": "Verify station exposure, temporal resolution, units, and period of record.",
    },
    "00052": {
        "candidate_label": "Relative humidity",
        "physical_scope": "Point relative-humidity observation if available in NWIS.",
        "use_for_pr_ngvla": "Potential partial comparison/context for humidity if coverage is adequate.",
        "caution": "Verify parameter name and units from official USGS metadata before use.",
    },
    "75969": {
        "candidate_label": "Barometric pressure",
        "physical_scope": "Point barometric-pressure observation if available in NWIS.",
        "use_for_pr_ngvla": "Potential synoptic/local pressure context if coverage is adequate.",
        "caution": "Verify parameter name, units, elevation, and station metadata before use.",
    },
}


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    start_label: str
    end_label: str

    @property
    def base_dir(self) -> Path:
        return self.repo_root / "data_raw" / "usgs" / "nwis"

    @property
    def metadata_dir(self) -> Path:
        return self.base_dir / "metadata"

    @property
    def raw_dir(self) -> Path:
        return self.base_dir / "raw"

    @property
    def logs_dir(self) -> Path:
        return self.repo_root / "logs" / "usgs" / "nwis"

    @property
    def log_path(self) -> Path:
        return self.logs_dir / "download_usgs_nwis_pr.log"

    @property
    def scope_notes_csv(self) -> Path:
        return self.metadata_dir / "usgs_nwis_candidate_parameter_scope_notes.csv"

    @property
    def site_catalog_rdb(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_site_series_catalog_{self.start_label}_{self.end_label}_candidate_params.rdb"

    @property
    def site_catalog_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_site_series_catalog_{self.start_label}_{self.end_label}_candidate_params.csv"

    @property
    def sites_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_sites_{self.start_label}_{self.end_label}_candidate_params.csv"

    @property
    def parameter_inventory_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_parameter_inventory_{self.start_label}_{self.end_label}_candidate_params.csv"

    @property
    def availability_summary_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_availability_summary_{self.start_label}_{self.end_label}_candidate_params.csv"

    @property
    def precip_uv_probe_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_precipitation_uv_probe_{self.start_label}_{self.end_label}.csv"

    @property
    def precip_uv_raw_dir(self) -> Path:
        return self.raw_dir / "precipitation_uv"

    @property
    def precip_uv_download_manifest_csv(self) -> Path:
        return self.metadata_dir / f"usgs_nwis_pr_precipitation_uv_download_manifest_{self.start_label}_{self.end_label}.csv"


def label_from_date(date_text: str) -> str:
    return date_text.replace("-", "")


def ensure_directories(paths: Paths) -> None:
    for directory in [paths.metadata_dir, paths.raw_dir, paths.logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(paths: Paths, message: str) -> None:
    ensure_directories(paths)
    line = f"[{utc_now_iso()}] {message}"
    print(line)
    with paths.log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_scope_notes(paths: Paths) -> None:
    rows = []
    for code in DEFAULT_PARAMETER_CODES:
        note = PARAMETER_SCOPE_NOTES.get(code, {})
        rows.append(
            {
                "parameter_cd": code,
                "candidate_label": note.get("candidate_label", ""),
                "physical_scope": note.get("physical_scope", ""),
                "use_for_pr_ngvla": note.get("use_for_pr_ngvla", ""),
                "caution": note.get("caution", ""),
                "authority_note": "Candidate label only; verify official USGS parameter name/units in service output before scientific use.",
            }
        )

    write_csv(
        paths.scope_notes_csv,
        rows,
        [
            "parameter_cd",
            "candidate_label",
            "physical_scope",
            "use_for_pr_ngvla",
            "caution",
            "authority_note",
        ],
    )


def fetch_text(url: str, params: dict[str, Any], *, timeout: int, retries: int = 3, sleep: float = 1.0) -> tuple[str, str]:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    full_url = f"{url}?{query}" if query else url
    request = Request(
        full_url,
        headers={
            "User-Agent": "PR-ngVLA-USGS-NWIS-inventory/1.0 (+https://github.com/cesarpollack/pr_ngvla)",
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                text = raw.decode("utf-8", errors="replace")
                return text, full_url
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(sleep * attempt)
            else:
                break

    raise RuntimeError(f"Failed after {retries} attempts: {full_url}\n{last_error}")


def parse_rdb(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """
    Parse USGS RDB text.

    RDB files contain comment lines beginning with '#', followed by a header row,
    followed by a column-format row such as '5s 15s 10d ...'. This parser skips
    comments and the format row, then returns rows as dictionaries.
    """
    data_lines = [line.rstrip("\n") for line in text.splitlines() if line and not line.startswith("#")]

    if len(data_lines) < 2:
        return [], []

    header = data_lines[0].split("\t")
    rows: list[dict[str, str]] = []

    for line in data_lines[1:]:
        cols = line.split("\t")

        # Skip the RDB column-width/type row.
        if len(cols) == len(header) and all(_looks_like_rdb_type_token(c) for c in cols):
            continue

        padded = cols + [""] * max(0, len(header) - len(cols))
        rows.append(dict(zip(header, padded[: len(header)])))

    return header, rows


def _looks_like_rdb_type_token(token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    # Examples: 5s, 15s, 10d, 6n
    if len(token) < 2:
        return False
    return token[:-1].replace(".", "", 1).isdigit() and token[-1].lower() in {"s", "d", "n"}


def cmd_init(args: argparse.Namespace, paths: Paths) -> None:
    ensure_directories(paths)
    write_scope_notes(paths)
    log(paths, "Initialized USGS NWIS directory structure and candidate parameter scope notes.")
    print(f"Metadata directory: {paths.metadata_dir}")
    print(f"Raw directory:      {paths.raw_dir}")
    print(f"Logs directory:     {paths.logs_dir}")


def cmd_sites(args: argparse.Namespace, paths: Paths) -> None:
    ensure_directories(paths)
    write_scope_notes(paths)

    params = {
        "format": "rdb",
        "stateCd": args.state_cd,
        "siteStatus": "all",
        "seriesCatalogOutput": "true",
        "outputDataTypeCd": "iv,dv",
        "parameterCd": args.parameter_codes,
        "startDt": args.start,
        "endDt": args.end,
    }

    text, full_url = fetch_text(SITE_SERVICE_URL, params, timeout=args.timeout, sleep=args.sleep)
    paths.site_catalog_rdb.write_text(text, encoding="utf-8")
    log(paths, f"Saved USGS NWIS Site Service RDB: {paths.site_catalog_rdb}")
    log(paths, f"Site Service URL: {full_url}")

    header, rows = parse_rdb(text)
    if not rows:
        raise RuntimeError(
            "USGS Site Service returned no parsed rows. "
            f"Inspect raw RDB file: {paths.site_catalog_rdb}"
        )

    write_csv(paths.site_catalog_csv, rows, header)
    log(paths, f"Wrote parsed site-series catalog CSV: {paths.site_catalog_csv} rows={len(rows)}")

    build_summaries(paths, rows)
    print_summary(paths)


def build_summaries(paths: Paths, rows: list[dict[str, str]]) -> None:
    site_rows = build_site_summary(rows)
    parameter_rows = build_parameter_inventory(rows)
    availability_rows = build_availability_summary(rows)

    write_csv(paths.sites_csv, site_rows, site_fieldnames())
    write_csv(paths.parameter_inventory_csv, parameter_rows, parameter_inventory_fieldnames())
    write_csv(paths.availability_summary_csv, availability_rows, availability_fieldnames())

    log(paths, f"Wrote site summary: {paths.sites_csv} rows={len(site_rows)}")
    log(paths, f"Wrote parameter inventory: {paths.parameter_inventory_csv} rows={len(parameter_rows)}")
    log(paths, f"Wrote availability summary: {paths.availability_summary_csv} rows={len(availability_rows)}")


def first_present(row: dict[str, str], candidates: Iterable[str]) -> str:
    for key in candidates:
        value = row.get(key, "")
        if value not in ("", None):
            return value
    return ""


def min_date(values: Iterable[str]) -> str:
    clean = sorted(v for v in values if v)
    return clean[0] if clean else ""


def max_date(values: Iterable[str]) -> str:
    clean = sorted(v for v in values if v)
    return clean[-1] if clean else ""


def build_site_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        site_no = row.get("site_no", "")
        if not site_no:
            continue

        rec = grouped.setdefault(
            site_no,
            {
                "agency_cd": row.get("agency_cd", ""),
                "site_no": site_no,
                "station_nm": row.get("station_nm", ""),
                "site_tp_cd": row.get("site_tp_cd", ""),
                "dec_lat_va": row.get("dec_lat_va", ""),
                "dec_long_va": row.get("dec_long_va", ""),
                "coord_datum_cd": first_present(row, ["dec_coord_datum_cd", "coord_datum_cd"]),
                "alt_va": row.get("alt_va", ""),
                "alt_datum_cd": row.get("alt_datum_cd", ""),
                "huc_cd": row.get("huc_cd", ""),
                "data_type_cds": set(),
                "parameter_cds": set(),
                "stat_cds": set(),
                "begin_dates": [],
                "end_dates": [],
                "physical_scope": "USGS NWIS point monitoring location; not a regional gridded field.",
            },
        )

        for key, field in [
            ("data_type_cd", "data_type_cds"),
            ("parm_cd", "parameter_cds"),
            ("stat_cd", "stat_cds"),
        ]:
            if row.get(key):
                rec[field].add(row[key])

        if row.get("begin_date"):
            rec["begin_dates"].append(row["begin_date"])
        if row.get("end_date"):
            rec["end_dates"].append(row["end_date"])

    out: list[dict[str, str]] = []
    for rec in grouped.values():
        out.append(
            {
                "agency_cd": rec["agency_cd"],
                "site_no": rec["site_no"],
                "station_nm": rec["station_nm"],
                "site_tp_cd": rec["site_tp_cd"],
                "dec_lat_va": rec["dec_lat_va"],
                "dec_long_va": rec["dec_long_va"],
                "coord_datum_cd": rec["coord_datum_cd"],
                "alt_va": rec["alt_va"],
                "alt_datum_cd": rec["alt_datum_cd"],
                "huc_cd": rec["huc_cd"],
                "data_type_cds": ";".join(sorted(rec["data_type_cds"])),
                "parameter_cds": ";".join(sorted(rec["parameter_cds"])),
                "stat_cds": ";".join(sorted(rec["stat_cds"])),
                "earliest_begin_date": min_date(rec["begin_dates"]),
                "latest_end_date": max_date(rec["end_dates"]),
                "physical_scope": rec["physical_scope"],
            }
        )

    return sorted(out, key=lambda r: r["site_no"])


def site_fieldnames() -> list[str]:
    return [
        "agency_cd",
        "site_no",
        "station_nm",
        "site_tp_cd",
        "dec_lat_va",
        "dec_long_va",
        "coord_datum_cd",
        "alt_va",
        "alt_datum_cd",
        "huc_cd",
        "data_type_cds",
        "parameter_cds",
        "stat_cds",
        "earliest_begin_date",
        "latest_end_date",
        "physical_scope",
    ]


def build_parameter_inventory(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in rows:
        parm_cd = row.get("parm_cd", "")
        if not parm_cd:
            continue

        data_type_cd = row.get("data_type_cd", "")
        stat_cd = row.get("stat_cd", "")
        key = (parm_cd, data_type_cd, stat_cd)

        rec = grouped.setdefault(
            key,
            {
                "parm_cd": parm_cd,
                "data_type_cd": data_type_cd,
                "stat_cd": stat_cd,
                "parm_nm": first_present(row, ["parm_nm", "parm_name", "parameter_nm"]),
                "parm_units": first_present(row, ["parm_units", "parameter_units"]),
                "sites": set(),
                "site_type_codes": set(),
                "begin_dates": [],
                "end_dates": [],
                "total_count_nu": 0,
                "candidate_label": PARAMETER_SCOPE_NOTES.get(parm_cd, {}).get("candidate_label", ""),
                "methodological_note": PARAMETER_SCOPE_NOTES.get(parm_cd, {}).get("use_for_pr_ngvla", ""),
                "caution": PARAMETER_SCOPE_NOTES.get(parm_cd, {}).get("caution", ""),
            },
        )

        if not rec["parm_nm"]:
            rec["parm_nm"] = first_present(row, ["parm_nm", "parm_name", "parameter_nm"])
        if not rec["parm_units"]:
            rec["parm_units"] = first_present(row, ["parm_units", "parameter_units"])
        if row.get("site_no"):
            rec["sites"].add(row["site_no"])
        if row.get("site_tp_cd"):
            rec["site_type_codes"].add(row["site_tp_cd"])
        if row.get("begin_date"):
            rec["begin_dates"].append(row["begin_date"])
        if row.get("end_date"):
            rec["end_dates"].append(row["end_date"])
        rec["total_count_nu"] += safe_int(row.get("count_nu", ""))

    out: list[dict[str, str]] = []
    for rec in grouped.values():
        out.append(
            {
                "parm_cd": rec["parm_cd"],
                "candidate_label": rec["candidate_label"],
                "official_parm_nm": rec["parm_nm"],
                "official_parm_units": rec["parm_units"],
                "data_type_cd": rec["data_type_cd"],
                "stat_cd": rec["stat_cd"],
                "n_sites": str(len(rec["sites"])),
                "site_type_codes": ";".join(sorted(rec["site_type_codes"])),
                "earliest_begin_date": min_date(rec["begin_dates"]),
                "latest_end_date": max_date(rec["end_dates"]),
                "total_count_nu": str(rec["total_count_nu"]),
                "methodological_note": rec["methodological_note"],
                "caution": rec["caution"],
            }
        )

    return sorted(out, key=lambda r: (r["parm_cd"], r["data_type_cd"], r["stat_cd"]))


def parameter_inventory_fieldnames() -> list[str]:
    return [
        "parm_cd",
        "candidate_label",
        "official_parm_nm",
        "official_parm_units",
        "data_type_cd",
        "stat_cd",
        "n_sites",
        "site_type_codes",
        "earliest_begin_date",
        "latest_end_date",
        "total_count_nu",
        "methodological_note",
        "caution",
    ]


def build_availability_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    for row in rows:
        site_no = row.get("site_no", "")
        parm_cd = row.get("parm_cd", "")
        if not site_no or not parm_cd:
            continue

        out.append(
            {
                "site_no": site_no,
                "station_nm": row.get("station_nm", ""),
                "site_tp_cd": row.get("site_tp_cd", ""),
                "dec_lat_va": row.get("dec_lat_va", ""),
                "dec_long_va": row.get("dec_long_va", ""),
                "parm_cd": parm_cd,
                "candidate_label": PARAMETER_SCOPE_NOTES.get(parm_cd, {}).get("candidate_label", ""),
                "official_parm_nm": first_present(row, ["parm_nm", "parm_name", "parameter_nm"]),
                "official_parm_units": first_present(row, ["parm_units", "parameter_units"]),
                "data_type_cd": row.get("data_type_cd", ""),
                "stat_cd": row.get("stat_cd", ""),
                "begin_date": row.get("begin_date", ""),
                "end_date": row.get("end_date", ""),
                "count_nu": row.get("count_nu", ""),
                "physical_scope": "Point observation at USGS NWIS monitoring location.",
            }
        )

    return sorted(out, key=lambda r: (r["parm_cd"], r["site_no"], r["data_type_cd"], r["stat_cd"]))


def availability_fieldnames() -> list[str]:
    return [
        "site_no",
        "station_nm",
        "site_tp_cd",
        "dec_lat_va",
        "dec_long_va",
        "parm_cd",
        "candidate_label",
        "official_parm_nm",
        "official_parm_units",
        "data_type_cd",
        "stat_cd",
        "begin_date",
        "end_date",
        "count_nu",
        "physical_scope",
    ]


def safe_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0




def parse_usgs_datetime(value: str) -> dt.datetime | None:
    """Parse common USGS datetime strings with timezone offsets."""
    value = (value or "").strip()
    if not value:
        return None
    # USGS RDB commonly returns ISO-like strings such as:
    # 2016-10-01 00:00 EDT, 2016-10-01T00:00:00.000-04:00,
    # or 2016-10-01 00:00:00-04:00 depending on service/output.
    candidates = [
        value.replace("Z", "+00:00"),
        value.replace(" ", "T", 1).replace("Z", "+00:00"),
    ]
    for candidate in candidates:
        try:
            return dt.datetime.fromisoformat(candidate)
        except ValueError:
            pass
    # Fallback: strip timezone abbreviations such as AST/EDT and parse naive.
    parts = value.split()
    for n in (2, 1):
        if len(parts) >= n:
            candidate = " ".join(parts[:n])
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return dt.datetime.strptime(candidate, fmt)
                except ValueError:
                    pass
    return None


def find_datetime_column(fieldnames: list[str]) -> str:
    for name in fieldnames:
        low = name.lower()
        if low in {"datetime", "date_time", "datetime_utc"}:
            return name
        if "datetime" in low or "date_time" in low:
            return name
    return ""


def median(values: list[float]) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def infer_step_minutes(rows: list[dict[str, str]], datetime_col: str) -> dict[str, str]:
    times = []
    for row in rows:
        parsed = parse_usgs_datetime(row.get(datetime_col, ""))
        if parsed is not None:
            times.append(parsed)
    times = sorted(set(times))
    diffs = []
    for a, b in zip(times, times[1:]):
        minutes = (b - a).total_seconds() / 60.0
        if minutes > 0:
            diffs.append(minutes)

    unique = sorted(set(round(x, 6) for x in diffs))
    med = median(diffs)
    min_step = min(diffs) if diffs else None
    max_step = max(diffs) if diffs else None

    def fmt(x: float | None) -> str:
        if x is None:
            return ""
        if abs(x - round(x)) < 1e-6:
            return str(int(round(x)))
        return f"{x:.3f}"

    return {
        "first_datetime": times[0].isoformat() if times else "",
        "last_datetime": times[-1].isoformat() if times else "",
        "n_unique_datetimes": str(len(times)),
        "min_step_minutes": fmt(min_step),
        "median_step_minutes": fmt(med),
        "max_step_minutes": fmt(max_step),
        "unique_step_minutes_first20": ";".join(fmt(x) for x in unique[:20]),
        "likely_subdaily": "yes" if med is not None and med < 1440 else "no" if med is not None else "unknown",
        "likely_hourly_or_finer": "yes" if med is not None and med <= 60 else "no" if med is not None else "unknown",
        "likely_15min_or_finer": "yes" if med is not None and med <= 15 else "no" if med is not None else "unknown",
    }


def select_precip_uv_sites(paths: Paths, *, max_sites: int, start: str, end: str) -> list[dict[str, str]]:
    if not paths.availability_summary_csv.exists():
        raise FileNotFoundError(
            f"Availability summary not found: {paths.availability_summary_csv}\n"
            "Run: python scripts/download_usgs_nwis_pr.py sites"
        )

    rows = read_csv(paths.availability_summary_csv)
    candidates = []
    for row in rows:
        if row.get("parm_cd") != "00045":
            continue
        if row.get("data_type_cd") not in {"uv", "iv"}:
            continue
        begin = row.get("begin_date", "")
        finish = row.get("end_date", "")
        # Keep series that overlap the requested project window.
        if finish and finish < start:
            continue
        if begin and begin > end:
            continue
        candidates.append(row)

    def sort_key(row: dict[str, str]) -> tuple[int, str, str]:
        # Prefer atmospheric rain gages first, then long records.
        site_type = row.get("site_tp_cd", "")
        rank = 0 if site_type == "AT" else 1 if site_type in {"ST", "LK"} else 2
        return (rank, row.get("begin_date", "9999-99-99"), row.get("site_no", ""))

    return sorted(candidates, key=sort_key)[:max_sites]


def cmd_probe_precip_uv(args: argparse.Namespace, paths: Paths) -> None:
    """Probe USGS instantaneous/unit-value precipitation availability and cadence."""
    ensure_directories(paths)
    sites = select_precip_uv_sites(paths, max_sites=args.max_sites, start=args.start, end=args.end)
    if not sites:
        raise RuntimeError("No precipitation UV series found in availability summary.")

    probe_rows: list[dict[str, str]] = []
    log(paths, f"Starting precipitation UV probe: sites={len(sites)} probe_days={args.probe_days}")

    for idx, site in enumerate(sites, start=1):
        begin = site.get("begin_date", "") or args.start
        probe_start = max(begin, args.start)
        try:
            start_date = dt.date.fromisoformat(probe_start)
        except ValueError:
            start_date = dt.date.fromisoformat(args.start)
        end_date = min(start_date + dt.timedelta(days=args.probe_days), dt.date.fromisoformat(args.end))
        if end_date < start_date:
            end_date = start_date

        params = {
            "format": "rdb",
            "sites": site["site_no"],
            "parameterCd": "00045",
            "startDT": start_date.isoformat(),
            "endDT": end_date.isoformat(),
            "siteStatus": "all",
        }

        out: dict[str, str] = {
            "site_no": site.get("site_no", ""),
            "station_nm": site.get("station_nm", ""),
            "site_tp_cd": site.get("site_tp_cd", ""),
            "dec_lat_va": site.get("dec_lat_va", ""),
            "dec_long_va": site.get("dec_long_va", ""),
            "series_begin_date": site.get("begin_date", ""),
            "series_end_date": site.get("end_date", ""),
            "probe_start": start_date.isoformat(),
            "probe_end": end_date.isoformat(),
            "status": "",
            "url": "",
            "n_rows": "0",
            "datetime_column": "",
            "first_datetime": "",
            "last_datetime": "",
            "n_unique_datetimes": "0",
            "min_step_minutes": "",
            "median_step_minutes": "",
            "max_step_minutes": "",
            "unique_step_minutes_first20": "",
            "likely_subdaily": "unknown",
            "likely_hourly_or_finer": "unknown",
            "likely_15min_or_finer": "unknown",
            "error": "",
        }

        try:
            text, full_url = fetch_text(IV_SERVICE_URL, params, timeout=args.timeout, sleep=args.sleep)
            out["url"] = full_url
            header, rows = parse_rdb(text)
            out["n_rows"] = str(len(rows))
            out["datetime_column"] = find_datetime_column(header)
            if rows and out["datetime_column"]:
                out.update(infer_step_minutes(rows, out["datetime_column"]))
                out["status"] = "ok"
            elif rows:
                out["status"] = "rows_no_datetime_column"
            else:
                out["status"] = "no_rows"
            log(paths, f"Probe {idx}/{len(sites)} site={site['site_no']} rows={out['n_rows']} status={out['status']}")
        except Exception as exc:
            out["status"] = "error"
            out["error"] = str(exc).replace("\n", " | ")[:1000]
            log(paths, f"Probe {idx}/{len(sites)} site={site.get('site_no','')} ERROR: {out['error']}")

        probe_rows.append(out)
        time.sleep(args.sleep)

    fieldnames = [
        "site_no",
        "station_nm",
        "site_tp_cd",
        "dec_lat_va",
        "dec_long_va",
        "series_begin_date",
        "series_end_date",
        "probe_start",
        "probe_end",
        "status",
        "n_rows",
        "datetime_column",
        "first_datetime",
        "last_datetime",
        "n_unique_datetimes",
        "min_step_minutes",
        "median_step_minutes",
        "max_step_minutes",
        "unique_step_minutes_first20",
        "likely_subdaily",
        "likely_hourly_or_finer",
        "likely_15min_or_finer",
        "url",
        "error",
    ]
    write_csv(paths.precip_uv_probe_csv, probe_rows, fieldnames)
    log(paths, f"Wrote precipitation UV probe summary: {paths.precip_uv_probe_csv} rows={len(probe_rows)}")

    ok = sum(1 for r in probe_rows if r["status"] == "ok")
    hourly = sum(1 for r in probe_rows if r["likely_hourly_or_finer"] == "yes")
    subdaily = sum(1 for r in probe_rows if r["likely_subdaily"] == "yes")
    print("\nUSGS NWIS precipitation UV probe summary")
    print("-----------------------------------------")
    print(f"Probed sites:           {len(probe_rows)}")
    print(f"Sites with rows:        {ok}")
    print(f"Subdaily cadence:       {subdaily}")
    print(f"Hourly or finer cadence:{hourly}")
    print(f"Output:                 {paths.precip_uv_probe_csv}")


def load_probe_usable_sites(
    paths: Paths,
    *,
    probe_csv: Path,
    include_unknown: bool,
    max_sites: int | None,
    site_filter: set[str] | None,
) -> list[dict[str, str]]:
    """Load precipitation UV probe rows and keep sites suitable for hourly-threshold work.

    The probe file is intentionally independent from the download window.
    For smoke tests, the download may request a short period such as 2016-10-01
    to 2016-10-31, while the probe inventory was generated for the full
    project discovery window, usually 2004-01-01 to 2023-12-31.
    """
    if not probe_csv.exists():
        raise FileNotFoundError(
            f"Precipitation UV probe file not found: {probe_csv}\n"
            "Run: python scripts/download_usgs_nwis_pr.py probe-precip-uv --max-sites 999"
        )

    rows = read_csv(probe_csv)
    usable = []
    for row in rows:
        if site_filter is not None and row.get("site_no", "") not in site_filter:
            continue
        status_ok = row.get("status") == "ok"
        hourly = row.get("likely_hourly_or_finer") == "yes"
        unknown_allowed = include_unknown and row.get("likely_hourly_or_finer") == "unknown"
        if status_ok and (hourly or unknown_allowed):
            usable.append(row)

    def sort_key(row: dict[str, str]) -> tuple[int, str, str]:
        site_type = row.get("site_tp_cd", "")
        rank = 0 if site_type == "AT" else 1 if site_type in {"ST", "LK"} else 2
        return (rank, row.get("series_begin_date", "9999-99-99"), row.get("site_no", ""))

    usable = sorted(usable, key=sort_key)
    if max_sites is not None and max_sites > 0:
        usable = usable[:max_sites]
    return usable


def iter_date_chunks(start_date: dt.date, end_date: dt.date, chunk_days: int) -> Iterable[tuple[dt.date, dt.date]]:
    """Yield inclusive date chunks for USGS startDT/endDT requests."""
    current = start_date
    while current <= end_date:
        chunk_end = min(current + dt.timedelta(days=chunk_days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + dt.timedelta(days=1)


def raw_precip_uv_chunk_path(paths: Paths, site_no: str, start_date: dt.date, end_date: dt.date) -> Path:
    year_dir = paths.precip_uv_raw_dir / site_no / f"{start_date.year:04d}"
    return year_dir / f"usgs_nwis_pr_precipitation_uv_{site_no}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.rdb"


def raw_precip_uv_json_chunk_path(paths: Paths, site_no: str, start_date: dt.date, end_date: dt.date) -> Path:
    year_dir = paths.precip_uv_raw_dir / site_no / f"{start_date.year:04d}"
    return year_dir / f"usgs_nwis_pr_precipitation_uv_{site_no}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.json"


def _parse_iso_datetime_for_manifest(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_minutes(value: float) -> str:
    return f"{value:g}"


def summarize_iv_json(text: str) -> dict[str, str]:
    """Summarize USGS IV JSON values for raw-acquisition manifest metadata."""
    data = json.loads(text)
    values: list[str] = []

    for series in data.get("value", {}).get("timeSeries", []):
        for group in series.get("values", []):
            for item in group.get("value", []):
                date_time = item.get("dateTime", "")
                if date_time:
                    values.append(date_time)

    out = {
        "n_rows": str(len(values)),
        "datetime_column": "dateTime",
        "first_datetime": "",
        "last_datetime": "",
        "n_unique_datetimes": str(len(set(values))),
        "min_step_minutes": "",
        "median_step_minutes": "",
        "max_step_minutes": "",
    }

    parsed = [(value, _parse_iso_datetime_for_manifest(value)) for value in values]
    parsed = [(value, parsed_dt) for value, parsed_dt in parsed if parsed_dt is not None]

    if not parsed:
        return out

    parsed.sort(key=lambda item: item[1])
    out["first_datetime"] = parsed[0][0]
    out["last_datetime"] = parsed[-1][0]

    unique_times = sorted({parsed_dt for _, parsed_dt in parsed})
    if len(unique_times) >= 2:
        diffs = [
            (b - a).total_seconds() / 60.0
            for a, b in zip(unique_times[:-1], unique_times[1:])
        ]
        diffs_sorted = sorted(diffs)
        mid = len(diffs_sorted) // 2
        if len(diffs_sorted) % 2:
            median = diffs_sorted[mid]
        else:
            median = 0.5 * (diffs_sorted[mid - 1] + diffs_sorted[mid])

        out["min_step_minutes"] = _format_minutes(min(diffs))
        out["median_step_minutes"] = _format_minutes(median)
        out["max_step_minutes"] = _format_minutes(max(diffs))

    return out


def cmd_download_precip_uv(args: argparse.Namespace, paths: Paths) -> None:
    """
    Download raw USGS NWIS instantaneous/unit-value precipitation chunks.

    This mode is intentionally raw-data acquisition only. It does not aggregate
    to hourly values, clean provisional flags, fill gaps, compare with ERA5, or
    generate science tables/figures.
    """
    ensure_directories(paths)
    paths.precip_uv_raw_dir.mkdir(parents=True, exist_ok=True)

    site_filter = set(args.sites.split(",")) if args.sites else None
    max_sites = args.max_sites if args.max_sites and args.max_sites > 0 else None

    if args.probe_file:
        probe_csv = Path(args.probe_file)
        if not probe_csv.is_absolute():
            probe_csv = (paths.repo_root / probe_csv).resolve()
    else:
        probe_paths = Paths(
            repo_root=paths.repo_root,
            start_label=label_from_date(args.probe_start),
            end_label=label_from_date(args.probe_end),
        )
        probe_csv = probe_paths.precip_uv_probe_csv

    sites = load_probe_usable_sites(
        paths,
        probe_csv=probe_csv,
        include_unknown=args.include_unknown,
        max_sites=max_sites,
        site_filter=site_filter,
    )
    if not sites:
        raise RuntimeError("No usable precipitation UV sites selected from probe file.")

    project_start = dt.date.fromisoformat(args.start)
    project_end = dt.date.fromisoformat(args.end)
    manifest_rows: list[dict[str, str]] = []
    total_chunks = 0
    ok_chunks = 0
    skipped_chunks = 0
    error_chunks = 0

    log(
        paths,
        "Starting raw precipitation UV download: "
        f"sites={len(sites)} start={args.start} end={args.end} "
        f"chunk_days={args.chunk_days} resume={args.resume} probe_csv={probe_csv}",
    )

    for site_index, site in enumerate(sites, start=1):
        site_no = site.get("site_no", "")
        if not site_no:
            continue

        begin_text = site.get("series_begin_date", "") or args.start
        end_text = site.get("series_end_date", "") or args.end
        try:
            series_start = dt.date.fromisoformat(begin_text)
        except ValueError:
            series_start = project_start
        try:
            series_end = dt.date.fromisoformat(end_text)
        except ValueError:
            series_end = project_end

        request_start = max(project_start, series_start)
        request_end = min(project_end, series_end)
        if request_end < request_start:
            log(paths, f"Site {site_index}/{len(sites)} site={site_no}: no overlap with requested project window.")
            continue

        chunks = list(iter_date_chunks(request_start, request_end, args.chunk_days))
        log(
            paths,
            f"Site {site_index}/{len(sites)} site={site_no} chunks={len(chunks)} "
            f"window={request_start}..{request_end} station={site.get('station_nm','')}",
        )

        for chunk_index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            total_chunks += 1
            out_path = raw_precip_uv_chunk_path(paths, site_no, chunk_start, chunk_end)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            row: dict[str, str] = {
                "site_no": site_no,
                "station_nm": site.get("station_nm", ""),
                "site_tp_cd": site.get("site_tp_cd", ""),
                "dec_lat_va": site.get("dec_lat_va", ""),
                "dec_long_va": site.get("dec_long_va", ""),
                "series_begin_date": site.get("series_begin_date", ""),
                "series_end_date": site.get("series_end_date", ""),
                "probe_median_step_minutes": site.get("median_step_minutes", ""),
                "likely_hourly_or_finer": site.get("likely_hourly_or_finer", ""),
                "chunk_start": chunk_start.isoformat(),
                "chunk_end": chunk_end.isoformat(),
                "status": "",
                "n_rows": "0",
                "datetime_column": "",
                "first_datetime": "",
                "last_datetime": "",
                "n_unique_datetimes": "0",
                "min_step_minutes": "",
                "median_step_minutes": "",
                "max_step_minutes": "",
                "raw_path": str(out_path.relative_to(paths.repo_root)),
                "url": "",
                "error": "",
            }

            if args.resume and out_path.exists() and out_path.stat().st_size > 0:
                text = out_path.read_text(encoding="utf-8", errors="replace")
                header, parsed_rows = parse_rdb(text)
                row["status"] = "skipped_existing"
                row["n_rows"] = str(len(parsed_rows))
                row["datetime_column"] = find_datetime_column(header)
                if parsed_rows and row["datetime_column"]:
                    row.update(infer_step_minutes(parsed_rows, row["datetime_column"]))
                skipped_chunks += 1
                manifest_rows.append(row)
                continue

            params = {
                "format": "rdb",
                "sites": site_no,
                "parameterCd": "00045",
                "startDT": chunk_start.isoformat(),
                "endDT": chunk_end.isoformat(),
                "siteStatus": "all",
            }

            try:
                text, full_url = fetch_text(
                    IV_SERVICE_URL,
                    params,
                    timeout=args.timeout,
                    sleep=args.sleep,
                    retries=args.retries,
                )
                out_path.write_text(text, encoding="utf-8")
                row["url"] = full_url
                header, parsed_rows = parse_rdb(text)
                row["n_rows"] = str(len(parsed_rows))
                row["datetime_column"] = find_datetime_column(header)
                if parsed_rows and row["datetime_column"]:
                    row.update(infer_step_minutes(parsed_rows, row["datetime_column"]))
                    row["status"] = "ok"
                    ok_chunks += 1
                elif parsed_rows:
                    row["status"] = "rows_no_datetime_column"
                    ok_chunks += 1
                else:
                    row["status"] = "no_rows"
                    ok_chunks += 1

                if total_chunks % args.progress_every == 0:
                    log(
                        paths,
                        f"Download progress chunks={total_chunks} ok={ok_chunks} "
                        f"skipped={skipped_chunks} errors={error_chunks} latest_site={site_no}",
                    )
            except Exception as rdb_exc:
                if args.json_fallback:
                    json_path = raw_precip_uv_json_chunk_path(paths, site_no, chunk_start, chunk_end)
                    json_path.parent.mkdir(parents=True, exist_ok=True)

                    json_params = dict(params)
                    json_params["format"] = "json"

                    try:
                        json_text, json_full_url = fetch_text(
                            IV_SERVICE_URL,
                            json_params,
                            timeout=args.timeout,
                            sleep=args.sleep,
                            retries=args.retries,
                        )
                        json_path.write_text(json_text, encoding="utf-8")

                        row["raw_path"] = str(json_path.relative_to(paths.repo_root))
                        row["url"] = json_full_url
                        row.update(summarize_iv_json(json_text))

                        if row["n_rows"] != "0":
                            row["status"] = "json_fallback_ok"
                        else:
                            row["status"] = "json_fallback_no_rows"

                        row["error"] = (
                            "RDB failed; JSON fallback succeeded. "
                            f"rdb_error={str(rdb_exc).replace(chr(10), ' | ')[:700]}"
                        )
                        ok_chunks += 1
                        log(
                            paths,
                            f"Download JSON FALLBACK site={site_no} chunk={chunk_start}..{chunk_end}: "
                            f"status={row['status']} rows={row['n_rows']}",
                        )
                    except Exception as json_exc:
                        row["status"] = "error"
                        row["error"] = (
                            "RDB failed and JSON fallback failed. "
                            f"rdb_error={str(rdb_exc).replace(chr(10), ' | ')[:450]} | "
                            f"json_error={str(json_exc).replace(chr(10), ' | ')[:450]}"
                        )[:1000]
                        error_chunks += 1
                        log(
                            paths,
                            f"Download ERROR site={site_no} chunk={chunk_start}..{chunk_end}: {row['error']}",
                        )
                else:
                    row["status"] = "error"
                    row["error"] = str(rdb_exc).replace("\n", " | ")[:1000]
                    error_chunks += 1
                    log(
                        paths,
                        f"Download ERROR site={site_no} chunk={chunk_start}..{chunk_end}: {row['error']}",
                    )

            manifest_rows.append(row)
            time.sleep(args.sleep)

            # Write an incremental manifest so the audit is preserved if the run is interrupted.
            write_csv(paths.precip_uv_download_manifest_csv, manifest_rows, precip_uv_manifest_fieldnames())

    write_csv(paths.precip_uv_download_manifest_csv, manifest_rows, precip_uv_manifest_fieldnames())
    log(
        paths,
        f"Finished raw precipitation UV download manifest={paths.precip_uv_download_manifest_csv} "
        f"rows={len(manifest_rows)} chunks={total_chunks} ok={ok_chunks} "
        f"skipped={skipped_chunks} errors={error_chunks}",
    )

    print("\nUSGS NWIS raw precipitation UV download summary")
    print("------------------------------------------------")
    print(f"Selected sites:     {len(sites)}")
    print(f"Chunks attempted:   {total_chunks}")
    print(f"OK chunks:          {ok_chunks}")
    print(f"Skipped chunks:     {skipped_chunks}")
    print(f"Error chunks:       {error_chunks}")
    print(f"Raw directory:      {paths.precip_uv_raw_dir}")
    print(f"Manifest:           {paths.precip_uv_download_manifest_csv}")



def precip_uv_retry_errors_manifest_csv(paths: Paths) -> Path:
    return paths.metadata_dir / (
        f"usgs_nwis_pr_precipitation_uv_retry_errors_manifest_"
        f"{paths.start_label}_{paths.end_label}.csv"
    )


def _manifest_chunk_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("site_no", ""),
        row.get("chunk_start", ""),
        row.get("chunk_end", ""),
    )


def _successful_precip_uv_status(status: str) -> bool:
    return status in {
        "ok",
        "rows_no_datetime_column",
        "no_rows",
        "skipped_existing",
        "json_fallback_ok",
        "json_fallback_no_rows",
    }


def _resolve_repo_relative_path(paths: Paths, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (paths.repo_root / path).resolve()


def cmd_retry_errors(args: argparse.Namespace, paths: Paths) -> None:
    """
    Retry only rows with status=error from an existing precipitation UV download manifest.

    This mode is intentionally raw-data acquisition only. It does not process,
    clean, aggregate, interpolate, map, or compare data. It writes a separate
    recovery manifest and never overwrites the canonical download manifest.
    """
    ensure_directories(paths)
    paths.precip_uv_raw_dir.mkdir(parents=True, exist_ok=True)

    canonical_manifest = (
        _resolve_repo_relative_path(paths, args.canonical_manifest)
        if args.canonical_manifest
        else paths.precip_uv_download_manifest_csv
    )
    recovery_manifest = (
        _resolve_repo_relative_path(paths, args.recovery_manifest)
        if args.recovery_manifest
        else precip_uv_retry_errors_manifest_csv(paths)
    )

    if not canonical_manifest.exists():
        raise FileNotFoundError(f"Canonical manifest not found: {canonical_manifest}")

    canonical_rows = read_csv(canonical_manifest)
    error_rows = [row for row in canonical_rows if row.get("status", "") == "error"]

    manifest_rows: list[dict[str, str]] = []
    completed_keys: set[tuple[str, str, str]] = set()
    if recovery_manifest.exists():
        manifest_rows = read_csv(recovery_manifest)
        completed_keys = {
            _manifest_chunk_key(row)
            for row in manifest_rows
            if _successful_precip_uv_status(row.get("status", ""))
        }

    pending_rows = [
        row for row in error_rows
        if _manifest_chunk_key(row) not in completed_keys
    ]

    total_chunks = 0
    ok_chunks = 0
    skipped_chunks = len(error_rows) - len(pending_rows)
    error_chunks = 0

    log(
        paths,
        "Starting precipitation UV retry-errors: "
        f"canonical_manifest={canonical_manifest} "
        f"recovery_manifest={recovery_manifest} "
        f"canonical_error_rows={len(error_rows)} "
        f"already_recovered={skipped_chunks} "
        f"pending={len(pending_rows)} "
        f"json_fallback={args.json_fallback}",
    )

    if not error_rows:
        print("\nUSGS NWIS precipitation UV retry-errors summary")
        print("------------------------------------------------")
        print(f"Canonical manifest: {canonical_manifest}")
        print("Canonical error rows: 0")
        print(f"Recovery manifest:  {recovery_manifest}")
        return

    for attempt_index, source_row in enumerate(pending_rows, start=1):
        total_chunks += 1
        site_no = source_row.get("site_no", "")
        chunk_start_text = source_row.get("chunk_start", "")
        chunk_end_text = source_row.get("chunk_end", "")

        row: dict[str, str] = {
            field: source_row.get(field, "")
            for field in precip_uv_manifest_fieldnames()
        }
        row.update({
            "status": "",
            "n_rows": "0",
            "datetime_column": "",
            "first_datetime": "",
            "last_datetime": "",
            "n_unique_datetimes": "0",
            "min_step_minutes": "",
            "median_step_minutes": "",
            "max_step_minutes": "",
            "url": "",
            "error": "",
        })

        try:
            chunk_start = dt.date.fromisoformat(chunk_start_text)
            chunk_end = dt.date.fromisoformat(chunk_end_text)
        except ValueError as exc:
            row["status"] = "error"
            row["error"] = f"Invalid chunk_start/chunk_end in canonical manifest: {exc}"
            error_chunks += 1
            manifest_rows.append(row)
            write_csv(recovery_manifest, manifest_rows, precip_uv_manifest_fieldnames())
            continue

        out_path = raw_precip_uv_chunk_path(paths, site_no, chunk_start, chunk_end)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        row["raw_path"] = str(out_path.relative_to(paths.repo_root))

        params = {
            "format": "rdb",
            "sites": site_no,
            "parameterCd": "00045",
            "startDT": chunk_start.isoformat(),
            "endDT": chunk_end.isoformat(),
            "siteStatus": "all",
        }

        try:
            text, full_url = fetch_text(
                IV_SERVICE_URL,
                params,
                timeout=args.timeout,
                sleep=args.sleep,
                retries=args.retries,
            )
            out_path.write_text(text, encoding="utf-8")
            row["url"] = full_url

            header, parsed_rows = parse_rdb(text)
            row["n_rows"] = str(len(parsed_rows))
            row["datetime_column"] = find_datetime_column(header)

            if parsed_rows and row["datetime_column"]:
                row.update(infer_step_minutes(parsed_rows, row["datetime_column"]))
                row["status"] = "ok"
            elif parsed_rows:
                row["status"] = "rows_no_datetime_column"
            else:
                row["status"] = "no_rows"

            ok_chunks += 1
        except Exception as rdb_exc:
            if args.json_fallback:
                json_path = raw_precip_uv_json_chunk_path(paths, site_no, chunk_start, chunk_end)
                json_path.parent.mkdir(parents=True, exist_ok=True)

                json_params = dict(params)
                json_params["format"] = "json"

                try:
                    json_text, json_full_url = fetch_text(
                        IV_SERVICE_URL,
                        json_params,
                        timeout=args.timeout,
                        sleep=args.sleep,
                        retries=args.retries,
                    )
                    json_path.write_text(json_text, encoding="utf-8")

                    row["raw_path"] = str(json_path.relative_to(paths.repo_root))
                    row["url"] = json_full_url
                    row.update(summarize_iv_json(json_text))

                    if row["n_rows"] != "0":
                        row["status"] = "json_fallback_ok"
                    else:
                        row["status"] = "json_fallback_no_rows"

                    row["error"] = (
                        "RDB failed; JSON fallback succeeded. "
                        f"rdb_error={str(rdb_exc).replace(chr(10), ' | ')[:700]}"
                    )
                    ok_chunks += 1
                    log(
                        paths,
                        f"Retry JSON FALLBACK site={site_no} chunk={chunk_start}..{chunk_end}: "
                        f"status={row['status']} rows={row['n_rows']}",
                    )
                except Exception as json_exc:
                    row["status"] = "error"
                    row["error"] = (
                        "RDB failed and JSON fallback failed. "
                        f"rdb_error={str(rdb_exc).replace(chr(10), ' | ')[:450]} | "
                        f"json_error={str(json_exc).replace(chr(10), ' | ')[:450]}"
                    )[:1000]
                    error_chunks += 1
                    log(
                        paths,
                        f"Retry ERROR site={site_no} chunk={chunk_start}..{chunk_end}: {row['error']}",
                    )
            else:
                row["status"] = "error"
                row["error"] = str(rdb_exc).replace("\n", " | ")[:1000]
                error_chunks += 1
                log(
                    paths,
                    f"Retry ERROR site={site_no} chunk={chunk_start}..{chunk_end}: {row['error']}",
                )

        manifest_rows.append(row)
        write_csv(recovery_manifest, manifest_rows, precip_uv_manifest_fieldnames())

        if attempt_index % args.progress_every == 0:
            log(
                paths,
                f"Retry progress attempted={total_chunks} ok={ok_chunks} "
                f"errors={error_chunks} already_recovered={skipped_chunks} latest_site={site_no}",
            )

        time.sleep(args.sleep)

    write_csv(recovery_manifest, manifest_rows, precip_uv_manifest_fieldnames())
    log(
        paths,
        f"Finished precipitation UV retry-errors recovery_manifest={recovery_manifest} "
        f"canonical_error_rows={len(error_rows)} attempted={total_chunks} "
        f"already_recovered={skipped_chunks} ok={ok_chunks} errors={error_chunks}",
    )

    print("\nUSGS NWIS precipitation UV retry-errors summary")
    print("------------------------------------------------")
    print(f"Canonical manifest:     {canonical_manifest}")
    print(f"Canonical error rows:   {len(error_rows)}")
    print(f"Already recovered:      {skipped_chunks}")
    print(f"Retry chunks attempted: {total_chunks}")
    print(f"OK chunks:              {ok_chunks}")
    print(f"Error chunks:           {error_chunks}")
    print(f"Raw directory:          {paths.precip_uv_raw_dir}")
    print(f"Recovery manifest:      {recovery_manifest}")

def precip_uv_manifest_fieldnames() -> list[str]:
    return [
        "site_no",
        "station_nm",
        "site_tp_cd",
        "dec_lat_va",
        "dec_long_va",
        "series_begin_date",
        "series_end_date",
        "probe_median_step_minutes",
        "likely_hourly_or_finer",
        "chunk_start",
        "chunk_end",
        "status",
        "n_rows",
        "datetime_column",
        "first_datetime",
        "last_datetime",
        "n_unique_datetimes",
        "min_step_minutes",
        "median_step_minutes",
        "max_step_minutes",
        "raw_path",
        "url",
        "error",
    ]

def cmd_summary(paths: Paths) -> None:
    if not paths.site_catalog_csv.exists():
        raise FileNotFoundError(
            f"Parsed site catalog not found: {paths.site_catalog_csv}\n"
            "Run: python scripts/download_usgs_nwis_pr.py sites"
        )

    rows = read_csv(paths.site_catalog_csv)
    build_summaries(paths, rows)
    print_summary(paths)


def print_summary(paths: Paths) -> None:
    site_rows = read_csv(paths.sites_csv)
    param_rows = read_csv(paths.parameter_inventory_csv)
    avail_rows = read_csv(paths.availability_summary_csv)

    print("\nUSGS NWIS inventory summary")
    print("---------------------------")
    print(f"Sites:                 {len(site_rows)}")
    print(f"Parameter rows:        {len(param_rows)}")
    print(f"Site-parameter series: {len(avail_rows)}")
    print(f"\nFiles:")
    print(f"  {paths.site_catalog_rdb}")
    print(f"  {paths.site_catalog_csv}")
    print(f"  {paths.sites_csv}")
    print(f"  {paths.parameter_inventory_csv}")
    print(f"  {paths.availability_summary_csv}")
    print(f"  {paths.scope_notes_csv}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire USGS NWIS station/parameter inventory for Puerto Rico.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=["init", "sites", "summary", "probe-precip-uv", "download-precip-uv", "retry-errors"],
        help="Workflow stage to run.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to current working directory.",
    )
    parser.add_argument("--state-cd", default=DEFAULT_STATE_CD, help="USGS state code filter.")
    parser.add_argument("--start", default=DEFAULT_START, help="Project start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=DEFAULT_END, help="Project end date, YYYY-MM-DD.")
    parser.add_argument(
        "--probe-start",
        default=DEFAULT_START,
        help="Start date label for the precipitation UV probe file used by download-precip-uv.",
    )
    parser.add_argument(
        "--probe-end",
        default=DEFAULT_END,
        help="End date label for the precipitation UV probe file used by download-precip-uv.",
    )
    parser.add_argument(
        "--probe-file",
        default="",
        help="Optional explicit path to a precipitation UV probe CSV. Overrides --probe-start/--probe-end.",
    )
    parser.add_argument(
        "--parameter-codes",
        default=",".join(DEFAULT_PARAMETER_CODES),
        help="Comma-separated USGS parameter codes for discovery.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--max-sites", type=int, default=20, help="Maximum number of sites to probe or download. Use 0 for all selected sites in download mode.")
    parser.add_argument("--probe-days", type=int, default=7, help="Number of days per site to request for probe-precip-uv.")
    parser.add_argument("--chunk-days", type=int, default=31, help="Number of days per raw IV download chunk for download-precip-uv.")
    parser.add_argument("--sites", default="", help="Optional comma-separated site numbers to download in download-precip-uv mode.")
    parser.add_argument("--include-unknown", action="store_true", help="Include probe rows with unknown cadence in download-precip-uv mode.")
    parser.add_argument("--resume", action="store_true", help="Skip existing non-empty raw chunk files in download-precip-uv mode and include them in the manifest.")
    parser.add_argument("--json-fallback", action="store_true", help="If an RDB precipitation UV chunk fails, retry the same chunk as raw JSON and record json_fallback_* status in the manifest.")
    parser.add_argument("--canonical-manifest", default="", help="Existing precipitation UV manifest to read status=error rows from in retry-errors mode.")
    parser.add_argument("--recovery-manifest", default="", help="Separate recovery manifest to write in retry-errors mode. Defaults to metadata/usgs_nwis_pr_precipitation_uv_retry_errors_manifest_<START>_<END>.csv.")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retries for USGS service requests.")
    parser.add_argument("--progress-every", type=int, default=25, help="Log progress after this many chunks during download-precip-uv.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        start_dt = dt.date.fromisoformat(args.start)
        end_dt = dt.date.fromisoformat(args.end)
    except ValueError as exc:
        print(f"ERROR: --start and --end must be ISO dates YYYY-MM-DD: {exc}", file=sys.stderr)
        return 2

    if end_dt < start_dt:
        print("ERROR: --end must be greater than or equal to --start", file=sys.stderr)
        return 2

    try:
        probe_start_dt = dt.date.fromisoformat(args.probe_start)
        probe_end_dt = dt.date.fromisoformat(args.probe_end)
    except ValueError as exc:
        print(f"ERROR: --probe-start and --probe-end must be ISO dates YYYY-MM-DD: {exc}", file=sys.stderr)
        return 2

    if probe_end_dt < probe_start_dt:
        print("ERROR: --probe-end must be greater than or equal to --probe-start", file=sys.stderr)
        return 2

    if args.chunk_days < 1:
        print("ERROR: --chunk-days must be >= 1", file=sys.stderr)
        return 2

    if args.progress_every < 1:
        print("ERROR: --progress-every must be >= 1", file=sys.stderr)
        return 2

    paths = Paths(
        repo_root=args.repo_root.resolve(),
        start_label=label_from_date(args.start),
        end_label=label_from_date(args.end),
    )

    try:
        if args.mode == "init":
            cmd_init(args, paths)
        elif args.mode == "sites":
            cmd_sites(args, paths)
        elif args.mode == "summary":
            cmd_summary(paths)
        elif args.mode == "probe-precip-uv":
            cmd_probe_precip_uv(args, paths)
        elif args.mode == "download-precip-uv":
            cmd_download_precip_uv(args, paths)
        elif args.mode == "retry-errors":
            cmd_retry_errors(args, paths)
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
