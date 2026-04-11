#!/usr/bin/env python3
"""
download_prism_pr.py

Download PRISM monthly climate normals for Puerto Rico via FTP.

PURPOSE
-------
PRISM (Parameter-elevation Regressions on Independent Slopes Model) is the
gold-standard observational climatology for Puerto Rico at 450m resolution.
It integrates station data with topographic, coastal proximity, and atmospheric
layer information — covering Puerto Rico, Vieques, AND Culebra.

This data serves two roles in the ngVLA site suitability project:
  1. Bias correction reference: ERA5-Land corrected to match PRISM monthly
     normals (Phase 2 Level 3 downscaling).
  2. Visual validation: confirms ERA5 spatial patterns are physically correct.

AVAILABLE VARIABLES FOR PUERTO RICO (1963-1995)
-----------------------------------------------
  ppt    — Monthly total precipitation (mm)
  tmax   — Monthly maximum 2m temperature (°C)
  tmin   — Monthly minimum 2m temperature (°C)

NOTE: tdmean (dew point) and RH are NOT in the PR PRISM project.
      Use NOAA ASOS station data for those variables instead.

DATASET
-------
PRISM Climate Group, Oregon State University
PR project: 1963-1995 monthly normals at 450m resolution
FTP server: prism.oregonstate.edu (anonymous login, no password)
Citation: Daly et al. (2003), Int. J. Climatol., 23, 1359-1381.

OUTPUT
------
  data_raw/prism/<variable>/PRISM_<var>_pr_1963-1995_normal_450mM1_<MM>.zip
  data_raw/prism/<variable>/<unzipped files>

USAGE
-----
  python download_prism_pr.py --test        # verify FTP paths first
  python download_prism_pr.py               # download all
  python download_prism_pr.py --variables tmax tmin
"""

from __future__ import annotations
import argparse
import ftplib
import logging
import time
import zipfile
from pathlib import Path

FTP_HOST      = "prism.oregonstate.edu"
FTP_BASE_PATH = "/projects/public/pr/grids"
VARIABLES     = {
    "ppt":  "Monthly total precipitation (mm)",
    "tmax": "Monthly maximum 2m temperature (deg C)",
    "tmin": "Monthly minimum 2m temperature (deg C)",
}
MONTHS       = [f"{m:02d}" for m in range(1, 13)]
FILE_PATTERN = "PRISM_{var}_pr_1963-1995_normal_450mM1_{period}.zip"
OUTDIR       = Path("data_raw/prism")
TIMEOUT      = 120

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def test_ftp_connection() -> None:
    """Test FTP connection and list directory structure."""
    log.info("Testing FTP connection to %s ...", FTP_HOST)
    try:
        with ftplib.FTP(FTP_HOST, timeout=30) as ftp:
            ftp.login()
            log.info("Connected: %s", ftp.getwelcome())
            try:
                ftp.cwd(FTP_BASE_PATH)
                log.info("Base path OK. Contents: %s", ftp.nlst())
            except ftplib.error_perm as e:
                log.error("Base path not found: %s", e)
                ftp.cwd("/")
                log.info("Root contents: %s", ftp.nlst())
                return
            for var in VARIABLES:
                try:
                    ftp.cwd(f"{FTP_BASE_PATH}/{var}")
                    sample = ftp.nlst()[:3]
                    log.info("  %s/ OK — sample: %s", var, sample)
                except ftplib.error_perm:
                    log.warning("  %s/ NOT FOUND", var)
    except Exception as e:
        log.error("FTP failed: %s", e)


def download_variable_month(variable: str, period: str, outdir: Path) -> bool:
    """Download and unzip one PRISM PR file. Returns True on success."""
    var_dir  = outdir / variable
    var_dir.mkdir(parents=True, exist_ok=True)
    filename = FILE_PATTERN.format(var=variable, period=period)
    ftp_path = f"{FTP_BASE_PATH}/{variable}/{filename}"
    zip_path = var_dir / filename

    # Skip if already unzipped
    if list(var_dir.glob(f"*{period}*.tif")) + list(var_dir.glob(f"*{period}*.asc")):
        log.info("SKIP (exists): %s/%s", variable, period)
        return True

    try:
        with ftplib.FTP(FTP_HOST, timeout=TIMEOUT) as ftp:
            ftp.login()
            log.info("GET %s", ftp_path)
            with open(zip_path, "wb") as f:
                ftp.retrbinary(f"RETR {ftp_path}", f.write)
        size_kb = zip_path.stat().st_size / 1000
        log.info("OK  %.1f KB", size_kb)
    except ftplib.error_perm as e:
        log.error("FTP error: %s — %s", ftp_path, e)
        if zip_path.exists(): zip_path.unlink()
        return False
    except Exception as e:
        log.error("Failed: %s — %s", ftp_path, e)
        if zip_path.exists() and zip_path.stat().st_size < 1000: zip_path.unlink()
        return False

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(var_dir)
        log.info("Unzipped → %s/", var_dir)
        return True
    except zipfile.BadZipFile:
        log.error("Bad zip: %s", zip_path)
        zip_path.unlink()
        return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download PRISM PR normals via FTP")
    p.add_argument("--variables", nargs="+", choices=list(VARIABLES.keys()),
                   default=list(VARIABLES.keys()))
    p.add_argument("--months", nargs="+", default=MONTHS)
    p.add_argument("--annual", action="store_true",
                   help="Also download annual normal files")
    p.add_argument("--outdir", type=Path, default=OUTDIR)
    p.add_argument("--test", action="store_true",
                   help="Test FTP paths only, no download")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.test:
        test_ftp_connection()
        return

    periods = list(args.months)
    if args.annual:
        periods.append("annual")

    total = len(args.variables) * len(periods)
    args.outdir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("PRISM Puerto Rico Normals — FTP Download")
    log.info("=" * 60)
    log.info("FTP        : %s%s", FTP_HOST, FTP_BASE_PATH)
    log.info("Resolution : 450m | Period: 1963-1995")
    log.info("Coverage   : Puerto Rico, Vieques, Culebra")
    log.info("Variables  : %s", args.variables)
    log.info("Periods    : %s", periods)
    log.info("Total      : %d files", total)
    log.info("Output     : %s", args.outdir.resolve())
    log.info("=" * 60)
    log.info("TIP: Run --test first to verify FTP paths before full download.")
    log.info("=" * 60)

    ok, failed, n = 0, 0, 0
    for variable in args.variables:
        log.info("--- %s: %s ---", variable, VARIABLES[variable])
        for period in periods:
            n += 1
            log.info("[%d/%d]", n, total)
            if download_variable_month(variable, period, args.outdir):
                ok += 1
            else:
                failed += 1
            time.sleep(1)

    log.info("=" * 60)
    log.info("SUMMARY: %d OK, %d failed / %d total", ok, failed, total)
    if failed:
        log.warning("Run --test to check FTP paths. Update FTP_BASE_PATH if needed.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()

