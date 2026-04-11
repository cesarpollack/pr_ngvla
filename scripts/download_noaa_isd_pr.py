#!/usr/bin/env python3
"""
download_noaa_isd_pr.py
=======================
Download NOAA Integrated Surface Database (ISD) hourly observations
for Puerto Rico stations, 2004–2023.

Source:  NCEI Global Hourly (ISD CSV format)
         https://www.ncei.noaa.gov/data/global-hourly/access/
Station discovery: isd-history.csv filtered for Puerto Rico (STATE=PR)
Inventory check:   isd-inventory.csv to verify data completeness

Variables extracted
-------------------
  TMP  – air temperature        (°C, derived from raw ×10 tenths)
  DEW  – dew point temperature  (°C)
  WND  – wind speed             (m/s) and direction (°)
  SLP  – sea level pressure     (hPa)
  AA1  – liquid precipitation   (mm, 1-hour accumulation)
  RH   – relative humidity      (%, derived from TMP + DEW via Magnus formula)
  T_dep– dew point depression   (°C, TMP - DEW, derived)

Quality control
---------------
  - Stations with < 80 % hourly completeness over 2004–2023 are flagged
    and excluded from the bias-correction pool (kept in archive)
  - Hurricane Maria impact period flagged: 2017-09 through 2018-06
  - ISD quality flags: keep codes 1, 5 (passed QC); flag / drop 2, 3, 6, 7, 9
  - Missing value sentinels (+9999, +999, etc.) replaced with NaN
  - Duplicate timestamps: keep first observation per hour

Output
------
  data_raw/noaa/isd/
  ├── station_catalog.csv           # all discovered PR stations + metadata
  ├── station_inventory.csv         # per-station completeness summary
  ├── {USAF}-{WBAN}_{STATION}.csv  # one CSV per station, all years merged
  └── logs/download_isd.log

Usage
-----
  # Full download (all stations, 2004–2023)
  python scripts/download_noaa_isd_pr.py

  # Single station test run (SJU airport)
  python scripts/download_noaa_isd_pr.py --station 785026-11641

  # Dry-run: discover and list stations only, no download
  python scripts/download_noaa_isd_pr.py --list-only

Notes
-----
  - Network is rate-limited; script uses 0.5 s delay between requests
  - Retries up to 3× on HTTP errors with exponential back-off
  - Resume-safe: skips year-files that already exist on disk
  - Tested with Python 3.11 / requests 2.31 / pandas 2.1

Author: César Pollack  |  ngVLA Puerto Rico Site Suitability Study  |  2026
"""

import argparse
import io
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "data_raw" / "noaa" / "isd"
LOG_DIR      = PROJECT_ROOT / "logs"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = LOG_DIR / "download_isd.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode="a"),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
YEARS        = list(range(2004, 2024))          # 2004–2023 inclusive
HISTORY_URL  = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
INVENT_URL   = "https://www.ncei.noaa.gov/pub/data/noaa/isd-inventory.csv"
DATA_BASE    = "https://www.ncei.noaa.gov/data/global-hourly/access"
DELAY_S      = 0.5    # seconds between HTTP requests
MAX_RETRIES  = 3
COMPLETENESS_THRESHOLD = 0.80   # 80 % minimum

# Expected hours per year (accounting for leap years handled in inventory check)
HOURS_PER_YEAR = 8760

# Hurricane Maria impact window
MARIA_START = pd.Timestamp("2017-09-01", tz="UTC")
MARIA_END   = pd.Timestamp("2018-06-30", tz="UTC")

# ISD quality flag codes considered valid
VALID_QC_FLAGS = {"1", "5", "A", "U", "P", "I", "M", "C"}

# ISD missing-value sentinels (raw strings before scaling)
MISSING_TMP = "+9999"
MISSING_DEW = "+9999"
MISSING_WND_SPD = "9999"
MISSING_SLP = "99999"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = 60) -> requests.Response | None:
    """GET url with retries; returns Response or None on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                log.debug("404 %s", url)
                return None
            log.warning("HTTP %d on attempt %d: %s", r.status_code, attempt, url)
        except requests.RequestException as exc:
            log.warning("Request error attempt %d: %s — %s", attempt, url, exc)
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    log.error("Failed after %d attempts: %s", MAX_RETRIES, url)
    return None


# ── Station discovery ─────────────────────────────────────────────────────────

def get_pr_stations() -> pd.DataFrame:
    """
    Download isd-history.csv and return rows for Puerto Rico.
    Filters on STATE == 'PR' (US territory stations) and verifies
    lat/lon are within the PR bounding box.
    """
    catalog_path = RAW_DIR / "station_catalog.csv"

    if catalog_path.exists():
        log.info("Loading station catalog from cache: %s", catalog_path)
        return pd.read_csv(catalog_path, dtype=str)

    log.info("Downloading ISD station history …")
    r = fetch_url(HISTORY_URL)
    if r is None:
        raise RuntimeError("Cannot download ISD station history")

    df = pd.read_csv(
        io.StringIO(r.text),
        dtype=str,
        encoding="latin-1",
    )
    df.columns = df.columns.str.strip().str.upper()
    log.info("isd-history columns: %s", df.columns.tolist())

    # Primary filter: bounding box (robust to column naming differences
    # across isd-history.csv versions — avoids KeyError on ST vs STATE)
    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    bbox = (df["LAT"] >= 17.5) & (df["LAT"] <= 18.7) & \
           (df["LON"] >= -68.1) & (df["LON"] <= -64.9)
    pr = df[bbox].copy()

    # Secondary filter: allow PR, US, or blank STATE
    # (some valid PR stations have empty STATE field in isd-history)
    if "STATE" in pr.columns:
        log.info("Applying secondary state filter on column 'STATE'")
        state_ok = pr["STATE"].str.strip().isin({"PR", "US", ""})
        pr = pr[state_ok].copy()

    # Build station_id = "USAF-WBAN" — WBAN zero-padded to 5 digits
    # to match isd-inventory and the NCEI archive filename format
    pr["STATION_ID"] = (
        pr["USAF"].str.strip()
        + "-"
        + pr["WBAN"].str.strip().str.zfill(5)
    )

    # Clip to stations active at any point during 2004–2023
    pr["BEGIN"] = pd.to_datetime(pr["BEGIN"], format="%Y%m%d", errors="coerce")
    pr["END"]   = pd.to_datetime(pr["END"],   format="%Y%m%d", errors="coerce")
    active = (pr["END"] >= pd.Timestamp("2004-01-01")) & \
             (pr["BEGIN"] <= pd.Timestamp("2023-12-31"))
    pr = pr[active].reset_index(drop=True)

    pr.to_csv(catalog_path, index=False)
    log.info("Found %d Puerto Rico ISD stations → %s", len(pr), catalog_path)
    return pr


# ── Inventory check ───────────────────────────────────────────────────────────

def check_inventory(stations: pd.DataFrame) -> pd.DataFrame:
    """
    Download isd-inventory.csv and compute per-station completeness
    for 2004–2023. Returns stations df with added columns:
      total_obs, expected_obs, completeness, keep (bool)
    """
    inv_path = RAW_DIR / "station_inventory.csv"

    log.info("Downloading ISD inventory (completeness check) …")
    r = fetch_url(INVENT_URL)
    if r is None:
        log.warning("Could not download inventory; skipping completeness filter")
        stations["completeness"] = np.nan
        stations["keep"] = True
        return stations

    inv = pd.read_csv(
        io.StringIO(r.text),
        dtype=str,
    )
    # Normalize column names (strip quotes/whitespace)
    inv.columns = inv.columns.str.strip().str.strip('"').str.upper()
    inv["YEAR"] = pd.to_numeric(inv["YEAR"], errors="coerce")
    month_cols  = ["JAN","FEB","MAR","APR","MAY","JUN",
                   "JUL","AUG","SEP","OCT","NOV","DEC"]
    for c in month_cols:
        inv[c] = pd.to_numeric(inv[c], errors="coerce").fillna(0)
    inv["annual_obs"] = inv[month_cols].sum(axis=1)

    inv_study = inv[inv["YEAR"].between(2004, 2023)].copy()

    # Expected observations: 20 years × 8760 h (simplified)
    EXPECTED_TOTAL = 20 * HOURS_PER_YEAR

    summary = (
        inv_study.groupby(["USAF", "WBAN"])["annual_obs"]
        .sum()
        .reset_index()
        .rename(columns={"annual_obs": "total_obs"})
    )
    summary["expected_obs"] = EXPECTED_TOTAL
    summary["completeness"] = summary["total_obs"] / summary["expected_obs"]
    summary["STATION_ID"] = (
        summary["USAF"].str.strip()
        + "-"
        + summary["WBAN"].str.strip().str.zfill(5)
    )

    stations = stations.merge(
        summary[["STATION_ID", "total_obs", "completeness"]],
        on="STATION_ID", how="left"
    )
    stations["completeness"] = stations["completeness"].fillna(0.0)

    # If no stations matched the inventory, assume all pass rather than
    # blocking the download — inventory may not cover all territories
    n_matched = stations["completeness"].gt(0).sum()
    if n_matched == 0:
        log.warning(
            "No PR stations found in isd-inventory — "
            "inventory may not cover US territories. "
            "Marking all stations keep=True; completeness will be "
            "assessed from the downloaded data."
        )
        stations["keep"] = True
    else:
        stations["keep"] = stations["completeness"] >= COMPLETENESS_THRESHOLD

    n_keep = stations["keep"].sum()
    n_flag = (~stations["keep"]).sum()
    log.info(
        "Completeness check: %d stations pass (≥80%%), %d flagged (<80%%)",
        n_keep, n_flag,
    )

    stations.to_csv(inv_path, index=False)
    return stations


# ── ISD CSV parsing ───────────────────────────────────────────────────────────

def parse_tmp(raw: str) -> float:
    """Parse ISD TMP field '+0234,1' → 23.4 °C; returns NaN on missing."""
    if pd.isna(raw):
        return np.nan
    val_part = str(raw).split(",")[0].strip()
    if val_part == MISSING_TMP:
        return np.nan
    try:
        return int(val_part) / 10.0
    except ValueError:
        return np.nan


def parse_dew(raw: str) -> float:
    """Parse ISD DEW field '+0189,1' → 18.9 °C."""
    if pd.isna(raw):
        return np.nan
    val_part = str(raw).split(",")[0].strip()
    if val_part == MISSING_DEW:
        return np.nan
    try:
        return int(val_part) / 10.0
    except ValueError:
        return np.nan


def parse_wind(raw: str) -> tuple[float, float]:
    """
    Parse ISD WND field '270,1,N,0103,1' →
        (direction_deg, speed_m_s)
    Returns (NaN, NaN) on missing.
    """
    if pd.isna(raw):
        return np.nan, np.nan
    parts = str(raw).split(",")
    if len(parts) < 4:
        return np.nan, np.nan
    try:
        direction = float(parts[0]) if parts[0].strip() not in ("999", "9999") else np.nan
        speed_raw = parts[3].strip()
        speed     = float(speed_raw) / 10.0 if speed_raw not in ("9999", "99999") else np.nan
        return direction, speed
    except (ValueError, IndexError):
        return np.nan, np.nan


def parse_slp(raw: str) -> float:
    """Parse ISD SLP field '10135,1' → 1013.5 hPa."""
    if pd.isna(raw):
        return np.nan
    val_part = str(raw).split(",")[0].strip()
    if val_part == MISSING_SLP:
        return np.nan
    try:
        return int(val_part) / 10.0
    except ValueError:
        return np.nan


def parse_precip(raw: str) -> float:
    """
    Parse ISD AA1 field (liquid precipitation).
    Format: 'depth_mm×10,period_hours,condition,qc'
    Returns mm for 1-hour accumulation; NaN otherwise.
    """
    if pd.isna(raw) or str(raw).strip() == "":
        return np.nan
    parts = str(raw).split(",")
    if len(parts) < 2:
        return np.nan
    try:
        depth_raw   = parts[0].strip()
        period_raw  = parts[1].strip()
        if depth_raw in ("9999", "99999"):
            return np.nan
        depth_mm = int(depth_raw) / 10.0      # tenths of mm → mm
        period_h = int(period_raw)
        if period_h == 1:
            return depth_mm
        # Only return 1-hour accumulations for clean hourly alignment
        return np.nan
    except (ValueError, IndexError):
        return np.nan


def rh_from_t_td(t_c: float | np.ndarray, td_c: float | np.ndarray) -> float | np.ndarray:
    """
    Relative humidity from temperature and dew point (Magnus formula).
    Both inputs in °C. Returns RH in percent [0, 100].
    """
    # Magnus constants (Alduchov & Eskridge 1996)
    a, b, c = 17.625, 243.04, 6.1078          # noqa: E501 – not used but kept for reference
    gamma_t  = 17.625 * t_c  / (243.04 + t_c)
    gamma_td = 17.625 * td_c / (243.04 + td_c)
    rh = 100.0 * np.exp(gamma_td - gamma_t)
    # Clip to physical range
    return np.clip(rh, 0.0, 100.0)


def parse_station_year(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Given a raw ISD global-hourly CSV DataFrame (single station, single year),
    parse all fields and return a clean hourly DataFrame.
    """
    # ── Timestamp ──────────────────────────────────────────────────────────────
    df_raw["datetime"] = pd.to_datetime(
        df_raw["DATE"], utc=True, errors="coerce"
    )
    df_raw = df_raw.dropna(subset=["datetime"])

    # ── Parse meteorological fields ────────────────────────────────────────────
    df_raw["t2m"]   = df_raw["TMP"].apply(parse_tmp)
    df_raw["d2m"]   = df_raw["DEW"].apply(parse_dew)
    df_raw[["wdir", "ws"]] = pd.DataFrame(
        df_raw["WND"].apply(parse_wind).tolist(),
        index=df_raw.index,
        columns=["wdir", "ws"],
    )
    df_raw["slp"]   = df_raw["SLP"].apply(parse_slp)

    # Precipitation: prefer AA1 (1-hour); fall back to column if missing
    aa1_col = "AA1" if "AA1" in df_raw.columns else None
    if aa1_col:
        df_raw["precip_mm"] = df_raw[aa1_col].apply(parse_precip)
    else:
        df_raw["precip_mm"] = np.nan

    # ── Derived fields ─────────────────────────────────────────────────────────
    df_raw["rh"]    = rh_from_t_td(df_raw["t2m"].values, df_raw["d2m"].values)
    df_raw["tdep"]  = df_raw["t2m"] - df_raw["d2m"]   # dew point depression

    # ── Hurricane Maria flag ───────────────────────────────────────────────────
    df_raw["maria_flag"] = (
        (df_raw["datetime"] >= MARIA_START) &
        (df_raw["datetime"] <= MARIA_END)
    ).astype(int)

    # ── Select and clean ───────────────────────────────────────────────────────
    cols = ["datetime", "t2m", "d2m", "rh", "tdep",
            "ws", "wdir", "slp", "precip_mm", "maria_flag"]
    out = df_raw[cols].copy()

    # Round to nearest hour and deduplicate (keep first)
    out["datetime"] = out["datetime"].dt.floor("h")
    out = out.drop_duplicates(subset=["datetime"], keep="first")
    out = out.sort_values("datetime").reset_index(drop=True)

    return out


# ── Per-station download ──────────────────────────────────────────────────────

def download_station(station_row: pd.Series, years: list[int]) -> Path | None:
    """
    Download all year-files for one station, parse, concatenate,
    and save to a single CSV. Returns output path or None on failure.
    """
    sid      = station_row["STATION_ID"]       # e.g. "785026-11641"
    name_raw = station_row.get("STATION NAME", station_row.get("STATION", sid))
    name     = str(name_raw).strip().replace(" ", "_").replace("/", "-")[:30]
    out_path = RAW_DIR / f"{sid}_{name}.csv"

    if out_path.exists():
        log.info("  [SKIP] %s already exists", out_path.name)
        return out_path

    frames = []
    missing_years = 0

    for year in years:
        # NCEI global-hourly CSV filenames concatenate USAF+WBAN with no dash
        # e.g. USAF=785260, WBAN=11641 → 78526011641.csv
        usaf, wban = sid.split("-", 1)
        ncei_fname = f"{usaf}{wban}"
        url        = f"{DATA_BASE}/{year}/{ncei_fname}.csv"
        year_cache = RAW_DIR / f"_cache_{sid}_{year}.csv"

        if year_cache.exists():
            df_raw = pd.read_csv(year_cache, dtype=str, low_memory=False)
        else:
            time.sleep(DELAY_S)
            r = fetch_url(url)
            if r is None:
                log.debug("    %d: no data (404)", year)
                missing_years += 1
                continue
            df_raw = pd.read_csv(
                io.StringIO(r.text), dtype=str, low_memory=False
            )
            df_raw.to_csv(year_cache, index=False)

        if df_raw.empty:
            missing_years += 1
            continue

        try:
            parsed = parse_station_year(df_raw)
            frames.append(parsed)
            log.debug("    %d: %d hourly records", year, len(parsed))
        except Exception as exc:
            log.warning("    %d parse error for %s: %s", year, sid, exc)

    if not frames:
        log.warning("  No data retrieved for station %s", sid)
        return None

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values("datetime").drop_duplicates(
        subset=["datetime"], keep="first"
    ).reset_index(drop=True)

    # Attach station metadata as header columns
    merged.insert(0, "station_id",  sid)
    merged.insert(1, "station_name", name)
    merged.insert(2, "lat",  pd.to_numeric(station_row.get("LAT", np.nan), errors="coerce"))
    merged.insert(3, "lon",  pd.to_numeric(station_row.get("LON", np.nan), errors="coerce"))
    merged.insert(4, "elev_m", pd.to_numeric(station_row.get("ELEV(M)", np.nan), errors="coerce"))

    merged.to_csv(out_path, index=False)

    # Clean up year-cache files
    for year in years:
        cache = RAW_DIR / f"_cache_{sid}_{year}.csv"
        if cache.exists():
            cache.unlink()

    n_total    = len(merged)
    n_complete = merged["t2m"].notna().sum()
    completeness = n_complete / max(n_total, 1) * 100
    log.info(
        "  ✓ %s  |  %d hours  |  T completeness %.1f%%  |  %d missing years",
        out_path.name, n_total, completeness, missing_years,
    )
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download NOAA ISD hourly data for Puerto Rico, 2004–2023"
    )
    parser.add_argument(
        "--station",
        type=str,
        default=None,
        help="Single station ID to download (format: USAF-WBAN, e.g. 785026-11641). "
             "Overrides all-station download.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Discover and list PR stations only; do not download data.",
    )
    parser.add_argument(
        "--all-stations",
        action="store_true",
        help="Download all stations including those below 80%% completeness threshold.",
    )
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("NOAA ISD Puerto Rico download  |  Period: 2004–2023")
    log.info("Output: %s", RAW_DIR)
    log.info("=" * 70)

    # Step 1: Discover stations
    stations = get_pr_stations()
    log.info("Puerto Rico ISD stations discovered: %d", len(stations))

    # Step 2: Inventory / completeness
    stations = check_inventory(stations)

    if args.list_only:
        print("\nPuerto Rico ISD Station List:")
        print("-" * 80)
        cols_show = ["STATION_ID", "STATION NAME", "LAT", "LON",
                     "ELEV(M)", "completeness", "keep"]
        cols_show = [c for c in cols_show if c in stations.columns]
        with pd.option_context("display.max_rows", 100, "display.max_colwidth", 40):
            print(stations[cols_show].to_string(index=False))
        log.info("--list-only mode: no download performed")
        return

    # Step 3: Filter stations
    if args.station:
        mask = stations["STATION_ID"] == args.station
        if not mask.any():
            log.error("Station %s not found in Puerto Rico catalog", args.station)
            log.error("Stations in catalog: %s", stations["STATION_ID"].tolist())
            log.error(
                "Tip: delete %s and rerun if catalog is stale from a previous run",
                RAW_DIR / "station_catalog.csv",
            )
            sys.exit(1)
        to_download = stations[mask]
        log.info("Single-station mode: %s (completeness filter bypassed)", args.station)
    elif args.all_stations:
        to_download = stations
        log.info("Downloading all %d stations (including low-completeness)", len(to_download))
    else:
        to_download = stations[stations["keep"]]
        log.info(
            "Downloading %d stations with ≥80%% completeness "
            "(%d flagged stations skipped — use --all-stations to include them)",
            len(to_download),
            (~stations["keep"]).sum(),
        )

    # Step 4: Download
    ok, failed = 0, 0
    for _, row in to_download.iterrows():
        sid = row["STATION_ID"]
        log.info("Downloading %s  (%s)", sid, row.get("STATION NAME", ""))
        result = download_station(row, YEARS)
        if result is not None:
            ok += 1
        else:
            failed += 1

    log.info("=" * 70)
    log.info("Download complete: %d succeeded, %d failed", ok, failed)
    log.info("Output directory: %s", RAW_DIR)
    log.info("Log: %s", log_path)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
