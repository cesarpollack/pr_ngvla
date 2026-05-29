#!/usr/bin/env python3
"""
download_coops_pr.py — NOAA CO-OPS/NOS metadata and observational downloads for PR-ngVLA.

Scope
-----
This script is intentionally limited to NOAA CO-OPS / NOAA NOS coastal water-level
and meteorological station discovery/downloads. It does not process ERA5, make maps,
or perform scientific analysis.

Workflow
--------
1) init             Create the expected directory structure.
2) metadata         Download official CO-OPS station lists and build a Puerto Rico candidate table.
3) station-details  Download expanded station metadata: details, sensors, products, datums.
4) targets          Build station/product targets from installed sensors.
5) availability     Probe CO-OPS Data API by station/product/year and write availability CSV.
6) download         Download selected products by station/year or station/month chunks.

Outputs
-------
data_raw/noaa/coops/metadata/
  coops_stations_<type>_metric.json
  coops_pr_candidate_stations.csv
  station_details/<station_id>_details_sensors_products_datums_metric.json
  coops_pr_station_sensor_inventory.csv
  coops_pr_station_product_inventory.csv
  coops_pr_station_datum_inventory.csv
  coops_pr_variable_scope_notes.csv

data_raw/noaa/coops/raw/<product>/<station_id>/
  COOPS_<station_id>_<product>_<begin>_<end>_<timezone>_<units>.csv

data_raw/noaa/coops/metadata/coops_download_manifest.csv
logs/noaa/coops/

Design notes
------------
- Uses only Python standard library to keep the workflow portable.
- Uses official NOAA CO-OPS Metadata API and Data API endpoints.
- Includes variable-scope notes so the physical meaning of each product is documented.
- Requires an explicit datum when downloading water-level products.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MDAPI_BASE = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
DATA_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

DEFAULT_STATION_TYPES = [
    "waterlevelsandmet",
    "waterlevels",
    "historicwl",
    "met",
    "watertemp",
    "cond",
    "physocean",
    "visibility",
]

# Conservative Puerto Rico bounding box used only as fallback when state metadata is missing.
PR_BBOX = {
    "lat_min": 17.50,
    "lat_max": 18.60,
    "lon_min": -68.20,
    "lon_max": -65.00,
}

WATER_LEVEL_PRODUCTS = {
    "water_level",
    "hourly_height",
    "high_low",
    "monthly_mean",
    "one_minute_water_level",
    "predictions",
    "daily_max_min",
}

MET_HOURLY_PRODUCTS = {
    "air_temperature",
    "water_temperature",
    "wind",
    "air_pressure",
    "conductivity",
    "visibility",
    "humidity",
    "salinity",
}

# Strict Puerto Rico operational subset used for the main PR-ngVLA dataset.
# It includes Puerto Rico main island, Vieques, Culebra, and Mona Island,
# while excluding the nearby U.S. Virgin Islands stations that CO-OPS may label
# within the same regional/state grouping.
PR_STRICT_BBOX = {
    "lat_min": 17.85,
    "lat_max": 18.60,
    "lon_min": -68.20,
    "lon_max": -65.00,
}

SENSOR_TO_API_PRODUCT = {
    "Air Temperature": "air_temperature",
    "Water Temperature": "water_temperature",
    "Wind": "wind",
    "Barometric Pressure": "air_pressure",
    "Relative Humidity": "humidity",
    "Visibility": "visibility",
    "Conductivity": "conductivity",
    "Salinity": "salinity",
}

# These notes are intentionally methodological, not analytical.
VARIABLE_SCOPE_NOTES = {
    "air_temperature": {
        "measured_quantity": "Air temperature",
        "api_information": "time, value, flags",
        "physical_scope": "Point measurement at the coastal station air-temperature sensor.",
        "spatial_representativeness": "Station latitude/longitude only; coastal/port local environment.",
        "interpretation_for_pr_ngvla": "Useful as observed coastal meteorological context; not an island-wide or inland land-temperature field.",
    },
    "water_temperature": {
        "measured_quantity": "Water temperature",
        "api_information": "time, value, flags",
        "physical_scope": "Point measurement at the station water-temperature sensor, usually in harbor/coastal water.",
        "spatial_representativeness": "Station latitude/longitude and sensor depth/elevation metadata if available.",
        "interpretation_for_pr_ngvla": "Useful for marine/coastal thermal context; not air temperature and not directly inland meteorology.",
    },
    "wind": {
        "measured_quantity": "Wind speed, direction, and gust",
        "api_information": "time, speed, direction, direction text, gust, flags",
        "physical_scope": "Point measurement at the coastal station anemometer.",
        "spatial_representativeness": "Local exposure depends on station siting, nearby structures, bay geometry, and coastline orientation.",
        "interpretation_for_pr_ngvla": "Useful for coastal wind regime; not automatically representative of mountainous or inland sites.",
    },
    "air_pressure": {
        "measured_quantity": "Barometric pressure",
        "api_information": "time, value, flags",
        "physical_scope": "Point measurement at the coastal station barometer.",
        "spatial_representativeness": "Station latitude/longitude and station elevation context.",
        "interpretation_for_pr_ngvla": "Useful for synoptic/local coastal pressure context; compare carefully across elevations.",
    },
    "humidity": {
        "measured_quantity": "Relative humidity",
        "api_information": "time, value, flags",
        "physical_scope": "Point measurement at the coastal station humidity sensor.",
        "spatial_representativeness": "Coastal point environment; strong marine influence possible.",
        "interpretation_for_pr_ngvla": "Useful for observed coastal humidity context; not a direct proxy for inland humidity gradients.",
    },
    "visibility": {
        "measured_quantity": "Horizontal visibility / atmospheric clarity",
        "api_information": "time, value, flags",
        "physical_scope": "Point measurement at station visibility sensor where available.",
        "spatial_representativeness": "Local coastal/port environment; may be affected by rain, mist, aerosol, salt spray, or local obstructions.",
        "interpretation_for_pr_ngvla": "Potentially useful for coastal visibility/fog/mist context; availability may be sparse.",
    },
    "hourly_height": {
        "measured_quantity": "Verified hourly water level height",
        "api_information": "time, height relative to requested datum, flags/metadata depending on response",
        "physical_scope": "Water level at the tide/water-level station relative to an explicit datum.",
        "spatial_representativeness": "Station tide gauge location only; harbor/bay/coastal hydrodynamic setting.",
        "interpretation_for_pr_ngvla": "Coastal/oceanographic context. It does not measure atmospheric meteorology and does not characterize inland telescope-site weather.",
    },
    "water_level": {
        "measured_quantity": "6-minute water level",
        "api_information": "time, height relative to requested datum, sigma/flags/QA depending on response",
        "physical_scope": "Water level at the tide/water-level station relative to an explicit datum.",
        "spatial_representativeness": "Station tide gauge location only; harbor/bay/coastal hydrodynamic setting.",
        "interpretation_for_pr_ngvla": "High-frequency coastal water-level context; not an atmospheric variable.",
    },
}


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "data_raw" / "noaa" / "coops" / "metadata"

    @property
    def raw(self) -> Path:
        return self.root / "data_raw" / "noaa" / "coops" / "raw"

    @property
    def station_details(self) -> Path:
        return self.metadata / "station_details"

    @property
    def logs(self) -> Path:
        return self.root / "logs" / "noaa" / "coops"

    @property
    def candidate_csv(self) -> Path:
        return self.metadata / "coops_pr_candidate_stations.csv"

    @property
    def manifest_csv(self) -> Path:
        return self.metadata / "coops_download_manifest.csv"


def ensure_dirs(paths: Paths) -> None:
    for d in [paths.metadata, paths.raw, paths.station_details, paths.logs]:
        d.mkdir(parents=True, exist_ok=True)


def log(paths: Paths, message: str) -> None:
    stamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{stamp}] {message}"
    print(line)
    paths.logs.mkdir(parents=True, exist_ok=True)
    with (paths.logs / "download_coops_pr.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_bytes(url: str, params: dict[str, Any], *, timeout: int = 90, retries: int = 3, sleep: float = 1.0) -> tuple[bytes, str]:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    full_url = f"{url}?{query}" if query else url
    req = Request(full_url, headers={"User-Agent": "PR-ngVLA-COOPS-download/1.0"})
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read(), full_url
        except (HTTPError, URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(sleep * attempt)
            else:
                break
    raise RuntimeError(f"Failed after {retries} attempts: {full_url}\n{last_err}")


def fetch_json(url: str, params: dict[str, Any], out_path: Path, paths: Paths) -> dict[str, Any]:
    payload, full_url = fetch_bytes(url, params)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    try:
        obj = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Response is not valid JSON for URL: {full_url}\nSaved to: {out_path}") from exc
    log(paths, f"Saved JSON: {out_path}  URL: {full_url}")
    return obj


def list_from_any(obj: dict[str, Any], keys: Iterable[str]) -> list[dict[str, Any]]:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def station_list(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return list_from_any(obj, ["stationList", "stations"])


def nested_list(obj: dict[str, Any], container_key: str, list_keys: Iterable[str]) -> list[dict[str, Any]]:
    container = obj.get(container_key)
    if isinstance(container, dict):
        found = list_from_any(container, list_keys)
        if found:
            return found
    return list_from_any(obj, list_keys)


def coops_record_list(value: Any) -> list[dict[str, Any]]:
    """Return a list of dictionaries from CO-OPS JSON values that may be lists or wrapped collections."""
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def coops_collection(obj: dict[str, Any], container_key: str, list_keys: Iterable[str]) -> list[dict[str, Any]]:
    """
    Extract collections robustly from MDAPI JSON.

    NOAA examples/documentation show more than one JSON shape depending on the resource:
      - expanded: {"sensors": {"sensorList": [...]}}
      - resource JSON: {"sensors": [...]} or {"sensorList": [...]}
      - occasionally a direct list may appear under the container key.
    """
    container = obj.get(container_key)

    if isinstance(container, list):
        return coops_record_list(container)

    if isinstance(container, dict):
        for key in list_keys:
            rows = coops_record_list(container.get(key))
            if rows:
                return rows

    for key in list_keys:
        rows = coops_record_list(obj.get(key))
        if rows:
            return rows

    return []


def station_record(obj: dict[str, Any]) -> dict[str, Any]:
    """Return the actual station record whether the API returns it directly or inside a collection."""
    for key in ("stations", "stationList"):
        rows = coops_record_list(obj.get(key))
        if rows:
            return rows[0]
    return obj


def fetch_json_optional(url: str, params: dict[str, Any], out_path: Path, paths: Paths) -> dict[str, Any] | None:
    """Fetch JSON but return None for station resources that are unavailable for a station."""
    try:
        return fetch_json(url, params, out_path, paths)
    except Exception as exc:
        log(paths, f"WARNING: optional MDAPI resource not available: {url} params={params} error={exc}")
        return None


def in_pr_bbox(lat: Any, lon: Any) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    return (
        PR_BBOX["lat_min"] <= lat_f <= PR_BBOX["lat_max"]
        and PR_BBOX["lon_min"] <= lon_f <= PR_BBOX["lon_max"]
    )


def is_pr_station(st: dict[str, Any]) -> bool:
    state = str(st.get("state", "")).strip().upper()
    if state == "PR":
        return True
    return in_pr_bbox(st.get("lat"), st.get("lng"))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def in_bbox_row(row: dict[str, Any], bbox: dict[str, float]) -> bool:
    try:
        lat = float(row.get("lat", ""))
        lon = float(row.get("lng", row.get("lon", "")))
    except (TypeError, ValueError):
        return False
    return bbox["lat_min"] <= lat <= bbox["lat_max"] and bbox["lon_min"] <= lon <= bbox["lon_max"]


def row_area_ok(row: dict[str, Any], area: str) -> bool:
    if area == "all_candidates":
        return True
    if area == "pr_strict":
        return in_bbox_row(row, PR_STRICT_BBOX)
    raise ValueError(f"Unsupported area: {area}")


def scope_note_for_product(product: str, key: str) -> str:
    return VARIABLE_SCOPE_NOTES.get(product, {}).get(key, "")


def build_sensor_product_targets(
    paths: Paths,
    *,
    area: str,
    station_filter: set[str] | None = None,
    product_filter: set[str] | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Build station/product targets from installed sensor metadata.

    This intentionally uses sensor inventory rather than MDAPI product links because
    the station product inventory contains page/product links, not guaranteed Data
    API time-series availability.
    """
    sensor_path = paths.metadata / "coops_pr_station_sensor_inventory.csv"
    if not sensor_path.exists():
        raise RuntimeError(f"Missing sensor inventory: {sensor_path}. Run station-details first.")

    rows = read_csv(sensor_path)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        sid = str(row.get("station_id", "")).strip()
        if not sid:
            continue
        if station_filter and sid not in station_filter:
            continue
        if not row_area_ok(row, area):
            continue
        if active_only and str(row.get("status", "")).strip() not in {"1", "1.0", "true", "True"}:
            continue

        sensor_name = str(row.get("sensor_name", "")).strip()
        product = SENSOR_TO_API_PRODUCT.get(sensor_name)
        if not product:
            continue
        if product_filter and product not in product_filter:
            continue

        key = (sid, product)
        rec = grouped.setdefault(
            key,
            {
                "station_id": sid,
                "station_name": row.get("station_name", ""),
                "lat": row.get("lat", ""),
                "lng": row.get("lng", ""),
                "state": row.get("state", ""),
                "source_types": row.get("source_types", ""),
                "product": product,
                "sensor_names": [],
                "sensor_ids": [],
                "sensor_refdatums": [],
                "sensor_elevations": [],
                "physical_scope": scope_note_for_product(product, "physical_scope"),
                "spatial_representativeness": scope_note_for_product(product, "spatial_representativeness"),
                "interpretation_for_pr_ngvla": scope_note_for_product(product, "interpretation_for_pr_ngvla"),
            },
        )
        rec["sensor_names"].append(sensor_name)
        rec["sensor_ids"].append(str(row.get("sensor_id", "")))
        rec["sensor_refdatums"].append(str(row.get("refdatum", "")))
        rec["sensor_elevations"].append(str(row.get("elevation", "")))

    out: list[dict[str, Any]] = []
    for rec in grouped.values():
        for key in ["sensor_names", "sensor_ids", "sensor_refdatums", "sensor_elevations"]:
            rec[key] = ";".join(sorted({x for x in rec[key] if x != ""}))
        out.append(rec)

    return sorted(out, key=lambda r: (r["station_id"], r["product"]))


def cmd_init(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)
    log(paths, "Initialized NOAA CO-OPS directory structure.")


def cmd_metadata(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    types = args.types.split(",") if args.types else DEFAULT_STATION_TYPES
    by_id: dict[str, dict[str, Any]] = {}

    for station_type in types:
        station_type = station_type.strip()
        if not station_type:
            continue
        out = paths.metadata / f"coops_stations_{station_type}_metric.json"
        obj = fetch_json(
            f"{MDAPI_BASE}/stations.json",
            {"type": station_type, "units": "metric"},
            out,
            paths,
        )
        stations = station_list(obj)
        pr_stations = [st for st in stations if is_pr_station(st)]
        log(paths, f"Station type {station_type}: total={len(stations)} PR_candidates={len(pr_stations)}")

        for st in pr_stations:
            sid = str(st.get("id", "")).strip()
            if not sid:
                continue
            rec = by_id.setdefault(
                sid,
                {
                    "id": sid,
                    "name": st.get("name", ""),
                    "lat": st.get("lat", ""),
                    "lng": st.get("lng", ""),
                    "state": st.get("state", ""),
                    "affiliations": st.get("affiliations", ""),
                    "source_types": set(),
                    "self": st.get("self", ""),
                },
            )
            rec["source_types"].add(station_type)

    rows: list[dict[str, Any]] = []
    for rec in sorted(by_id.values(), key=lambda r: r["id"]):
        out = dict(rec)
        out["source_types"] = ";".join(sorted(rec["source_types"]))
        out["physical_scope"] = "CO-OPS coastal/port station point location; not island-wide spatial coverage."
        rows.append(out)

    write_csv(
        paths.candidate_csv,
        rows,
        ["id", "name", "lat", "lng", "state", "affiliations", "source_types", "self", "physical_scope"],
    )
    log(paths, f"Wrote PR candidate stations: {paths.candidate_csv} rows={len(rows)}")


def cmd_station_details(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    candidates = read_csv(paths.candidate_csv)
    candidate_by_id = {r.get("id", ""): r for r in candidates if r.get("id")}
    station_ids = [r["id"] for r in candidates if r.get("id")]
    if args.stations:
        wanted = {x.strip() for x in args.stations.split(",") if x.strip()}
        station_ids = [sid for sid in station_ids if sid in wanted]

    sensor_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    datum_rows: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []

    for sid in station_ids:
        cand = candidate_by_id.get(sid, {})

        # First try the official expanded station record.
        expanded_out = paths.station_details / f"{sid}_details_sensors_products_datums_metric.json"
        expanded_obj = fetch_json_optional(
            f"{MDAPI_BASE}/stations/{sid}.json",
            {"expand": "details,sensors,products,datums", "units": "metric"},
            expanded_out,
            paths,
        )

        st_obj: dict[str, Any] = station_record(expanded_obj) if expanded_obj else {}

        # Fallback to individual resource endpoints.  This prevents an empty inventory
        # when the expanded representation omits or wraps resources differently.
        sensors = coops_collection(st_obj, "sensors", ["sensorList", "sensors"])
        if not sensors:
            obj = fetch_json_optional(
                f"{MDAPI_BASE}/stations/{sid}/sensors.json",
                {"units": "metric"},
                paths.station_details / f"{sid}_sensors_metric.json",
                paths,
            )
            if obj:
                sensors = coops_collection(obj, "sensors", ["sensorList", "sensors"])

        products = coops_collection(st_obj, "products", ["productList", "products"])
        if not products:
            obj = fetch_json_optional(
                f"{MDAPI_BASE}/stations/{sid}/products.json",
                {},
                paths.station_details / f"{sid}_products.json",
                paths,
            )
            if obj:
                products = coops_collection(obj, "products", ["productList", "products"])

        datums = coops_collection(st_obj, "datums", ["datumList", "datums"])
        if not datums:
            obj = fetch_json_optional(
                f"{MDAPI_BASE}/stations/{sid}/datums.json",
                {"units": "metric"},
                paths.station_details / f"{sid}_datums_metric.json",
                paths,
            )
            if obj:
                datums = coops_collection(obj, "datums", ["datumList", "datums"])

        station_name = st_obj.get("name") or cand.get("name", "")
        lat = st_obj.get("lat") or cand.get("lat", "")
        lng = st_obj.get("lng") or cand.get("lng", "")
        state = st_obj.get("state") or cand.get("state", "")
        source_types = cand.get("source_types", "")

        for s in sensors:
            sensor_rows.append(
                {
                    "station_id": sid,
                    "station_name": station_name,
                    "lat": lat,
                    "lng": lng,
                    "state": state,
                    "source_types": source_types,
                    "sensor_id": s.get("sensorID", s.get("id", "")),
                    "sensor_name": s.get("name", ""),
                    "status": s.get("status", ""),
                    "refdatum": s.get("refdatum", ""),
                    "elevation": s.get("elevation", ""),
                    "dcp": s.get("dcp", ""),
                    "message": s.get("message", ""),
                    "physical_scope_note": "Sensor metadata describes point instrumentation at the station; use sensor elevation/refdatum where provided.",
                }
            )

        for p in products:
            product_rows.append(
                {
                    "station_id": sid,
                    "station_name": station_name,
                    "lat": lat,
                    "lng": lng,
                    "state": state,
                    "source_types": source_types,
                    "product_name": p.get("name", ""),
                    "product_value": p.get("value", ""),
                    "physical_scope_note": "MDAPI product links/information are station-specific; they do not imply spatial coverage beyond the station location.",
                }
            )

        for d in datums:
            datum_rows.append(
                {
                    "station_id": sid,
                    "station_name": station_name,
                    "lat": lat,
                    "lng": lng,
                    "state": state,
                    "source_types": source_types,
                    "datum_name": d.get("name", d.get("datum", "")),
                    "datum_value": d.get("value", ""),
                    "datum_description": d.get("description", ""),
                    "physical_scope_note": "Datum metadata is local to the water-level station; water-level products must be interpreted relative to the requested datum.",
                }
            )

        # Add standardized scope notes.  These are methodological notes, not proof of data availability.
        for product, note in VARIABLE_SCOPE_NOTES.items():
            scope_rows.append(
                {
                    "station_id": sid,
                    "station_name": station_name,
                    "lat": lat,
                    "lng": lng,
                    "source_types": source_types,
                    "product": product,
                    "availability_basis": "scope_note_only_not_download_availability",
                    **note,
                }
            )
        time.sleep(args.sleep)

    write_csv(
        paths.metadata / "coops_pr_station_sensor_inventory.csv",
        sensor_rows,
        [
            "station_id",
            "station_name",
            "lat",
            "lng",
            "state",
            "source_types",
            "sensor_id",
            "sensor_name",
            "status",
            "refdatum",
            "elevation",
            "dcp",
            "message",
            "physical_scope_note",
        ],
    )
    write_csv(
        paths.metadata / "coops_pr_station_product_inventory.csv",
        product_rows,
        ["station_id", "station_name", "lat", "lng", "state", "source_types", "product_name", "product_value", "physical_scope_note"],
    )
    write_csv(
        paths.metadata / "coops_pr_station_datum_inventory.csv",
        datum_rows,
        ["station_id", "station_name", "lat", "lng", "state", "source_types", "datum_name", "datum_value", "datum_description", "physical_scope_note"],
    )
    write_csv(
        paths.metadata / "coops_pr_variable_scope_notes.csv",
        scope_rows,
        [
            "station_id",
            "station_name",
            "lat",
            "lng",
            "source_types",
            "product",
            "availability_basis",
            "measured_quantity",
            "api_information",
            "physical_scope",
            "spatial_representativeness",
            "interpretation_for_pr_ngvla",
        ],
    )
    log(paths, f"Wrote sensor rows={len(sensor_rows)}, product rows={len(product_rows)}, datum rows={len(datum_rows)}, scope rows={len(scope_rows)}")


def parse_date_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def date_chunks(start: date, end: date, product: str) -> list[tuple[date, date]]:
    """Return inclusive chunks that respect CO-OPS length constraints for selected products."""
    chunks: list[tuple[date, date]] = []
    cur = start

    # 6-minute water_level is limited to about one month; use calendar-month chunks.
    if product in {"water_level", "one_minute_water_level"}:
        while cur <= end:
            if product == "one_minute_water_level":
                nxt = min(cur + timedelta(days=3), end)  # 4-day limit, inclusive chunk.
            else:
                next_month = date(cur.year + (cur.month == 12), 1 if cur.month == 12 else cur.month + 1, 1)
                nxt = min(next_month - timedelta(days=1), end)
            chunks.append((cur, nxt))
            cur = nxt + timedelta(days=1)
        return chunks

    # Hourly met and hourly_height are safe as annual chunks.
    while cur <= end:
        nxt = min(date(cur.year, 12, 31), end)
        chunks.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return chunks


def response_status(text: str) -> tuple[str, int, str]:
    """Classify a CO-OPS Data API response.

    CO-OPS can return HTTP 200 and a CSV-looking payload even when there is
    no data, for example a normal header followed by an ``Error: No data was
    found...`` row.  Treat those as ``no_data`` rather than ``ok`` so
    availability/download manifests do not overstate coverage.
    """
    stripped = text.strip()
    if not stripped:
        return "empty", 0, "empty response"

    lower = stripped.lower()
    if "no data was found" in lower:
        msg = next((ln.strip() for ln in stripped.splitlines() if "no data was found" in ln.lower()), stripped)
        return "no_data", 0, msg[:300].replace("\n", " ")
    if "<error" in lower or '"error"' in lower:
        return "api_error", 0, stripped[:300].replace("\n", " ")

    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    for ln in lines[:5]:
        if ln.lstrip().lower().startswith("error"):
            return "api_error", 0, ln.strip()[:300].replace("\n", " ")

    # CSV row count approximation: subtract one header row if present.
    n_data = max(0, len(lines) - 1)
    return "ok", n_data, ""

def product_params(product: str, args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {
        "product": product,
        "time_zone": args.time_zone,
        "units": args.units,
        "application": args.application,
        "format": "csv",
    }
    if product in MET_HOURLY_PRODUCTS and args.met_interval:
        params["interval"] = args.met_interval
    if product in WATER_LEVEL_PRODUCTS:
        if not args.datum:
            raise ValueError(
                f"Product '{product}' is a water-level/tide product and requires --datum. "
                "Do not download water-level data without an explicit datum choice."
            )
        params["datum"] = args.datum
    return params


def append_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "station_id",
        "product",
        "begin_date",
        "end_date",
        "units",
        "time_zone",
        "datum",
        "interval",
        "status",
        "n_data_rows_approx",
        "output_path",
        "url",
        "message",
    ]
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


TARGET_FIELDNAMES = [
    "station_id",
    "station_name",
    "lat",
    "lng",
    "state",
    "source_types",
    "product",
    "sensor_names",
    "sensor_ids",
    "sensor_refdatums",
    "sensor_elevations",
    "physical_scope",
    "spatial_representativeness",
    "interpretation_for_pr_ngvla",
]


def cmd_targets(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    station_filter = {x.strip() for x in args.stations.split(",") if x.strip()} if args.stations else None
    product_filter = {x.strip() for x in args.products.split(",") if x.strip()} if args.products else None
    rows = build_sensor_product_targets(
        paths,
        area=args.area,
        station_filter=station_filter,
        product_filter=product_filter,
        active_only=not args.include_inactive,
    )
    out = paths.metadata / "coops_pr_station_product_targets_from_sensors.csv"
    write_csv(out, rows, TARGET_FIELDNAMES)
    log(paths, f"Wrote sensor-derived station/product targets: {out} rows={len(rows)} area={args.area}")


def cmd_availability(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    station_filter = {x.strip() for x in args.stations.split(",") if x.strip()} if args.stations else None
    product_filter = {x.strip() for x in args.products.split(",") if x.strip()} if args.products else None

    targets = build_sensor_product_targets(
        paths,
        area=args.area,
        station_filter=station_filter,
        product_filter=product_filter,
        active_only=not args.include_inactive,
    )
    if not targets:
        raise RuntimeError("No station/product targets from sensor inventory. Run station-details and/or adjust filters.")

    start = parse_date_ymd(args.start)
    end = parse_date_ymd(args.end)
    if end < start:
        raise ValueError("--end must be >= --start")

    rows: list[dict[str, Any]] = []
    for t in targets:
        sid = t["station_id"]
        product = t["product"]
        base_params = product_params(product, args)
        for b, e in date_chunks(start, end, product):
            params = dict(base_params)
            params.update({"station": sid, "begin_date": ymd(b), "end_date": ymd(e)})
            try:
                payload, url = fetch_bytes(DATA_API_BASE, params, timeout=args.timeout, retries=args.retries, sleep=args.sleep)
                text = payload.decode("utf-8", errors="replace")
                status, nrows, message = response_status(text)
            except Exception as exc:
                url = f"{DATA_API_BASE}?{urlencode({k: v for k, v in params.items() if v is not None})}"
                status, nrows, message = "request_failed", 0, str(exc)[:300].replace("\n", " ")

            rows.append(
                {
                    **{k: t.get(k, "") for k in TARGET_FIELDNAMES},
                    "begin_date": ymd(b),
                    "end_date": ymd(e),
                    "units": args.units,
                    "time_zone": args.time_zone,
                    "datum": args.datum or "",
                    "interval": base_params.get("interval", ""),
                    "status": status,
                    "n_data_rows_approx": nrows,
                    "url": url,
                    "message": message,
                }
            )
            log(paths, f"AVAILABILITY {sid} {product} {ymd(b)}-{ymd(e)} status={status} rows~{nrows}")
            time.sleep(args.sleep)

    out = paths.metadata / f"coops_pr_data_api_availability_{start.year}_{end.year}.csv"
    fieldnames = TARGET_FIELDNAMES + [
        "begin_date",
        "end_date",
        "units",
        "time_zone",
        "datum",
        "interval",
        "status",
        "n_data_rows_approx",
        "url",
        "message",
    ]
    write_csv(out, rows, fieldnames)

    summary: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        key = (str(r["station_id"]), str(r["station_name"]), str(r["product"]))
        rec = summary.setdefault(
            key,
            {
                "station_id": r["station_id"],
                "station_name": r["station_name"],
                "lat": r["lat"],
                "lng": r["lng"],
                "product": r["product"],
                "n_chunks": 0,
                "n_ok_chunks": 0,
                "n_error_chunks": 0,
                "total_data_rows_approx": 0,
                "first_ok_begin_date": "",
                "last_ok_end_date": "",
                "interpretation_for_pr_ngvla": r.get("interpretation_for_pr_ngvla", ""),
            },
        )
        rec["n_chunks"] += 1
        if r["status"] == "ok" and int(r.get("n_data_rows_approx") or 0) > 0:
            rec["n_ok_chunks"] += 1
            rec["total_data_rows_approx"] += int(r.get("n_data_rows_approx") or 0)
            if not rec["first_ok_begin_date"]:
                rec["first_ok_begin_date"] = r["begin_date"]
            rec["last_ok_end_date"] = r["end_date"]
        elif r["status"] != "ok":
            rec["n_error_chunks"] += 1

    summary_rows = sorted(summary.values(), key=lambda r: (r["station_id"], r["product"]))
    summary_out = paths.metadata / f"coops_pr_data_api_availability_summary_{start.year}_{end.year}.csv"
    write_csv(
        summary_out,
        summary_rows,
        [
            "station_id",
            "station_name",
            "lat",
            "lng",
            "product",
            "n_chunks",
            "n_ok_chunks",
            "n_error_chunks",
            "total_data_rows_approx",
            "first_ok_begin_date",
            "last_ok_end_date",
            "interpretation_for_pr_ngvla",
        ],
    )
    log(paths, f"Wrote availability rows={len(rows)} to {out}")
    log(paths, f"Wrote availability summary rows={len(summary_rows)} to {summary_out}")


def cmd_download(args: argparse.Namespace) -> None:
    """Download CO-OPS Data API products using the validated sensor-derived target table.

    Important: this intentionally mirrors the availability target logic.  It does
    not default to all MDAPI PR candidates, because that would mix historical
    water-level-only stations and nearby regional stations into the meteorology
    download.
    """
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    if getattr(args, "fresh_manifest", False) and paths.manifest_csv.exists():
        backup = paths.manifest_csv.with_suffix(paths.manifest_csv.suffix + ".bak")
        paths.manifest_csv.replace(backup)
        log(paths, f"Moved existing manifest to backup before fresh download manifest: {backup}")

    station_filter = {x.strip() for x in args.stations.split(",") if x.strip()} if args.stations else None
    product_filter = {x.strip() for x in args.products.split(",") if x.strip()} if args.products else None
    if not product_filter:
        raise RuntimeError("download requires --products with one or more Data API products")

    targets = build_sensor_product_targets(
        paths,
        area=args.area,
        station_filter=station_filter,
        product_filter=product_filter,
        active_only=not args.include_inactive,
    )
    if not targets:
        raise RuntimeError(
            "No station/product targets selected from sensor inventory. "
            "Run station-details/targets first, or adjust --area/--stations/--products/--include-inactive."
        )

    # Safety check: for the meteorological download stage, only download products
    # that were present in the validated sensor-derived targets. Water-level data
    # should be handled separately after choosing an explicit datum and station set.
    target_products = sorted({t["product"] for t in targets})
    requested_products = sorted(product_filter)
    missing = [p for p in requested_products if p not in target_products]
    if missing:
        log(paths, f"WARNING requested products with no selected sensor-derived targets: {','.join(missing)}")

    start = parse_date_ymd(args.start)
    end = parse_date_ymd(args.end)
    if end < start:
        raise ValueError("--end must be >= --start")

    manifest_batch: list[dict[str, Any]] = []
    total_chunks = sum(len(date_chunks(start, end, t["product"])) for t in targets)
    done_chunks = 0
    log(
        paths,
        f"Starting download from sensor-derived targets: targets={len(targets)} chunks={total_chunks} "
        f"area={args.area} products={','.join(requested_products)} include_inactive={args.include_inactive}",
    )

    for t in targets:
        sid = t["station_id"]
        product = t["product"]
        base_params = product_params(product, args)
        chunks = date_chunks(start, end, product)
        for b, e in chunks:
            params = dict(base_params)
            params.update({"station": sid, "begin_date": ymd(b), "end_date": ymd(e)})
            filename = f"COOPS_{sid}_{product}_{ymd(b)}_{ymd(e)}_{args.time_zone}_{args.units}.csv"
            out = paths.raw / product / sid / filename
            out.parent.mkdir(parents=True, exist_ok=True)

            if out.exists() and not args.overwrite:
                status, nrows, message = "exists", -1, "already exists; skipped"
                url = ""
            else:
                try:
                    payload, url = fetch_bytes(DATA_API_BASE, params, timeout=args.timeout, retries=args.retries, sleep=args.sleep)
                    text = payload.decode("utf-8", errors="replace")
                    out.write_text(text, encoding="utf-8")
                    status, nrows, message = response_status(text)
                except Exception as exc:
                    url = f"{DATA_API_BASE}?{urlencode({k: v for k, v in params.items() if v is not None})}"
                    status, nrows, message = "request_failed", 0, str(exc)[:300].replace("\n", " ")
                time.sleep(args.sleep)

            done_chunks += 1
            manifest_batch.append(
                {
                    "station_id": sid,
                    "product": product,
                    "begin_date": ymd(b),
                    "end_date": ymd(e),
                    "units": args.units,
                    "time_zone": args.time_zone,
                    "datum": args.datum or "",
                    "interval": base_params.get("interval", ""),
                    "status": status,
                    "n_data_rows_approx": nrows,
                    "output_path": str(out.relative_to(paths.root)),
                    "url": url,
                    "message": message,
                }
            )
            log(paths, f"DOWNLOAD {done_chunks}/{total_chunks} {sid} {product} {ymd(b)}-{ymd(e)} status={status} rows~{nrows}")

            # Incremental manifest checkpoint so a connection loss does not erase
            # the record of completed chunks.
            if len(manifest_batch) >= 10:
                append_manifest(paths.manifest_csv, manifest_batch)
                manifest_batch.clear()

    if manifest_batch:
        append_manifest(paths.manifest_csv, manifest_batch)
    log(paths, f"Updated manifest: {paths.manifest_csv}")


def safe_float(value: str) -> float | None:
    """Return float(value) for normal numeric CO-OPS cells, otherwise None."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.upper() in {"NA", "N/A", "NULL", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def value_range_for_product_column(product: str, column: str) -> tuple[float, float] | None:
    """Broad physical sanity ranges for raw CO-OPS metric downloads.

    These are not scientific QC thresholds. They are deliberately broad checks to
    catch parsing/unit/API mistakes before any analysis.
    """
    c = column.lower()
    if product == "humidity" and "humidity" in c:
        return (0.0, 100.0)
    if product == "air_pressure" and ("pressure" in c or "barometric" in c):
        return (850.0, 1100.0)
    if product == "air_temperature" and "temperature" in c:
        return (-10.0, 50.0)
    if product == "water_temperature" and "temperature" in c:
        return (0.0, 40.0)
    if product == "wind":
        if "direction" in c:
            return (0.0, 360.0)
        if "speed" in c or "gust" in c:
            return (0.0, 100.0)
    return None


def is_non_data_column(column: str) -> bool:
    c = column.strip().lower()
    return (
        c in {"date time", "time", "date", "i", "f", "r", "q", "qc", "flags"}
        or "flag" in c
        or c.endswith(" qc")
        or c.endswith(" quality")
    )


def audit_csv_file(path: Path, product: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Audit one downloaded CO-OPS CSV file without transforming the raw file."""
    base: dict[str, Any] = {
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "n_csv_rows": 0,
        "header": "",
        "read_status": "missing" if not path.exists() else "ok",
        "message": "",
    }
    numeric: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return base, []

    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                base["read_status"] = "empty_or_no_header"
                return base, []
            base["header"] = "|".join(reader.fieldnames)
            for row in reader:
                # CO-OPS sometimes returns a CSV header plus a single row whose
                # first field is an error message.  That is not an observed data row.
                joined = " ".join(str(v) for v in row.values() if v is not None).strip()
                if "no data was found" in joined.lower():
                    base["read_status"] = "api_no_data"
                    base["message"] = joined[:300].replace("\n", " ")
                    continue
                if joined.lower().startswith("error"):
                    base["read_status"] = "api_error_payload"
                    base["message"] = joined[:300].replace("\n", " ")
                    continue

                base["n_csv_rows"] += 1
                for col, raw_val in row.items():
                    if col is None or is_non_data_column(col):
                        continue
                    clean_col = col.strip()
                    val = safe_float(raw_val)
                    if val is None:
                        continue
                    stats = numeric.setdefault(
                        clean_col,
                        {"count": 0, "min": val, "max": val, "outside_broad_range_count": 0},
                    )
                    stats["count"] += 1
                    stats["min"] = min(stats["min"], val)
                    stats["max"] = max(stats["max"], val)
                    broad = value_range_for_product_column(product, clean_col)
                    if broad is not None and not (broad[0] <= val <= broad[1]):
                        stats["outside_broad_range_count"] += 1
    except Exception as exc:  # defensive audit path
        base["read_status"] = "read_failed"
        base["message"] = str(exc)[:300].replace("\n", " ")

    long_rows = []
    for col, stats in sorted(numeric.items()):
        broad = value_range_for_product_column(product, col)
        long_rows.append(
            {
                "numeric_column": col,
                "numeric_count": stats["count"],
                "numeric_min": stats["min"],
                "numeric_max": stats["max"],
                "broad_range_min": "" if broad is None else broad[0],
                "broad_range_max": "" if broad is None else broad[1],
                "outside_broad_range_count": stats["outside_broad_range_count"],
            }
        )
    return base, long_rows


def cmd_audit_raw(args: argparse.Namespace) -> None:
    """Audit downloaded raw CO-OPS CSV files for integrity and broad physical sanity."""
    paths = Paths(Path(args.repo_root).resolve())
    ensure_dirs(paths)

    manifest_path = Path(args.manifest) if args.manifest else paths.manifest_csv
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    file_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for m in reader:
            rel = m.get("output_path", "")
            raw_path = paths.root / rel
            product = m.get("product", "")
            audit, nums = audit_csv_file(raw_path, product)
            base_row = {
                "station_id": m.get("station_id", ""),
                "product": product,
                "begin_date": m.get("begin_date", ""),
                "end_date": m.get("end_date", ""),
                "manifest_status": m.get("status", ""),
                "manifest_rows_approx": m.get("n_data_rows_approx", ""),
                "output_path": rel,
                **audit,
            }
            file_rows.append(base_row)
            for nr in nums:
                numeric_rows.append({**base_row, **nr})

    file_out = paths.metadata / "coops_raw_file_audit.csv"
    numeric_out = paths.metadata / "coops_raw_numeric_range_audit.csv"
    write_csv(
        file_out,
        file_rows,
        [
            "station_id",
            "product",
            "begin_date",
            "end_date",
            "manifest_status",
            "manifest_rows_approx",
            "output_path",
            "exists",
            "size_bytes",
            "n_csv_rows",
            "header",
            "read_status",
            "message",
        ],
    )
    write_csv(
        numeric_out,
        numeric_rows,
        [
            "station_id",
            "product",
            "begin_date",
            "end_date",
            "output_path",
            "numeric_column",
            "numeric_count",
            "numeric_min",
            "numeric_max",
            "broad_range_min",
            "broad_range_max",
            "outside_broad_range_count",
            "read_status",
        ],
    )
    log(paths, f"Wrote raw file audit rows={len(file_rows)} to {file_out}")
    log(paths, f"Wrote raw numeric audit rows={len(numeric_rows)} to {numeric_out}")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NOAA CO-OPS/NOS download workflow for PR-ngVLA")
    parser.add_argument("--repo-root", default=".", help="Repository root. Default: current directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Create output directories")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("metadata", help="Download official CO-OPS station lists and build PR candidate table")
    p.add_argument("--types", default=",".join(DEFAULT_STATION_TYPES), help="Comma-separated MDAPI station types")
    p.set_defaults(func=cmd_metadata)

    p = sub.add_parser("station-details", help="Download station details, sensors, products, datums for PR candidates")
    p.add_argument("--stations", default="", help="Optional comma-separated station IDs")
    p.add_argument("--sleep", type=float, default=0.4, help="Seconds between MDAPI station requests")
    p.set_defaults(func=cmd_station_details)

    p = sub.add_parser("targets", help="Build station/product targets from active installed sensors")
    p.add_argument("--area", default="pr_strict", choices=["pr_strict", "all_candidates"], help="Spatial subset for targets")
    p.add_argument("--stations", default="", help="Optional comma-separated station IDs")
    p.add_argument("--products", default="", help="Optional comma-separated API products; default all mapped sensor products")
    p.add_argument("--include-inactive", action="store_true", help="Include sensors not marked as status=1")
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("availability", help="Probe Data API availability by station/product/year using sensor-derived targets")
    p.add_argument("--area", default="pr_strict", choices=["pr_strict", "all_candidates"], help="Spatial subset for availability")
    p.add_argument("--stations", default="", help="Optional comma-separated station IDs")
    p.add_argument("--products", default="", help="Optional comma-separated API products; default all mapped sensor products")
    p.add_argument("--start", default="2004-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default="2023-12-31", help="End date YYYY-MM-DD")
    p.add_argument("--units", default="metric", choices=["metric", "english"], help="CO-OPS API units")
    p.add_argument("--time-zone", default="gmt", choices=["gmt", "lst", "lst_ldt"], help="CO-OPS API time_zone")
    p.add_argument("--met-interval", default="h", help="Meteorological interval. Use h for hourly. Empty string for default 6-min.")
    p.add_argument("--datum", default="", help="Required only if probing water-level/tide products")
    p.add_argument("--application", default="PR_ngVLA_COOPS", help="CO-OPS application identifier")
    p.add_argument("--sleep", type=float, default=0.6, help="Seconds between Data API requests")
    p.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    p.add_argument("--retries", type=int, default=3, help="Request retry count")
    p.add_argument("--include-inactive", action="store_true", help="Include sensors not marked as status=1")
    p.set_defaults(func=cmd_availability)

    p = sub.add_parser("download", help="Download selected CO-OPS products from sensor-derived targets")
    p.add_argument("--area", default="pr_strict", choices=["pr_strict", "all_candidates"], help="Spatial subset for download targets")
    p.add_argument("--stations", default="", help="Optional comma-separated station IDs")
    p.add_argument("--products", required=True, help="Comma-separated products, e.g. air_temperature,wind,air_pressure")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--units", default="metric", choices=["metric", "english"], help="CO-OPS API units")
    p.add_argument("--time-zone", default="gmt", choices=["gmt", "lst", "lst_ldt"], help="CO-OPS API time_zone")
    p.add_argument("--met-interval", default="h", help="Meteorological interval. Use h for hourly. Empty string for default 6-min.")
    p.add_argument("--datum", default="", help="Required for water-level/tide products, e.g. MSL, MLLW, STND")
    p.add_argument("--application", default="PR_ngVLA_COOPS", help="CO-OPS application identifier")
    p.add_argument("--sleep", type=float, default=0.6, help="Seconds between Data API requests")
    p.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    p.add_argument("--retries", type=int, default=3, help="Request retry count")
    p.add_argument("--include-inactive", action="store_true", help="Include sensors not marked as status=1, matching historical availability workflow")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing raw files")
    p.add_argument("--fresh-manifest", action="store_true", help="Move any existing manifest to .bak before writing a new manifest")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("audit-raw", help="Audit downloaded raw CO-OPS CSV files for integrity and broad physical sanity")
    p.add_argument("--manifest", default="", help="Optional manifest path; default data_raw/noaa/coops/metadata/coops_download_manifest.csv")
    p.set_defaults(func=cmd_audit_raw)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
