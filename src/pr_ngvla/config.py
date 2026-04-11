"""
src/pr_ngvla/config.py
======================
Project-wide constants: file paths, geographic parameters, CRS strings,
time period, and unit conversion factors.

This module is imported by every other module in the package.
It contains NO logic — only constants derived from the project structure
and the study design (Pollack & Lebrón Santos, 2024–2026).

Design rule
-----------
If a value is used in more than one place, it lives here.
Scripts and library modules import from this file; they never
hard-code paths or magic numbers.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root  (resolves to /export/ngvla/cpollack/pr_ngvla/)
# ---------------------------------------------------------------------------
# __file__ is  src/pr_ngvla/config.py  →  parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Raw data directories
# ---------------------------------------------------------------------------
DATA_RAW      = PROJECT_ROOT / "data_raw"
ERA5_DIR      = DATA_RAW / "era5"
ERA5_MONTHLY_DIR  = ERA5_DIR / "monthly"
ERA5_HOURLY_DIR   = ERA5_DIR / "hourly"
ERA5_PWV_DIR      = ERA5_DIR / "pwv"
ERA5_SINGLELEV_DIR= ERA5_DIR / "singlelev"
NOAA_ISD_DIR  = DATA_RAW / "noaa" / "isd"
PRISM_DIR     = DATA_RAW / "prism"
DEM_PATH      = DATA_RAW / "dem" / "pr_dem_30m.tif"
SHAPES_DIR    = DATA_RAW / "shapefiles"

# Shapefile paths (used by data.spatial)
# COAST_SHP = SHAPES_DIR / "pr_coastline.shp"
COAST_SHP = SHAPES_DIR / "GSHHS_h_L1.shp"   # high-resolution L1 (main land polygons) coastline
MUNI_SHP  = SHAPES_DIR / "tl_2024_us_county" / "tl_2024_us_county.shp"

# ---------------------------------------------------------------------------
# Processed / output directories
# ---------------------------------------------------------------------------
DATA_INTERIM  = PROJECT_ROOT / "data_interim"
DATA_PRODUCTS = PROJECT_ROOT / "data_products"
OUTPUTS       = PROJECT_ROOT / "outputs"
OUT_MAPS      = OUTPUTS / "maps"
OUT_FIGURES   = OUTPUTS / "figures"
OUT_TABLES    = OUTPUTS / "tables"

# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
WGS84      = "EPSG:4326"   # geographic CRS — plotting and storage
METRIC_CRS = "EPSG:32620"  # UTM zone 20N  — geometric operations (metres)

# ---------------------------------------------------------------------------
# Geographic bounding box  (NSWE, decimal degrees WGS84)
# Covers PR main island + Mona + Vieques + Culebra
# ---------------------------------------------------------------------------
PR_BBOX_N =  18.6
PR_BBOX_S =  17.8
PR_BBOX_W = -68.0
PR_BBOX_E = -65.0

# Map display limits — slightly wider than the data bbox for visual breathing room
MAP_XLIM = (PR_BBOX_W - 0.2, PR_BBOX_E + 0.05)
MAP_YLIM = (PR_BBOX_S - 0.05, PR_BBOX_N + 0.05)

# ERA5 CDS API bounding box order: [N, W, S, E]
ERA5_BBOX = [PR_BBOX_N, PR_BBOX_W, PR_BBOX_S, PR_BBOX_E]

# ---------------------------------------------------------------------------
# Study period
# ---------------------------------------------------------------------------
STUDY_YEAR_START = 2004
STUDY_YEAR_END   = 2023
STUDY_YEARS      = list(range(STUDY_YEAR_START, STUDY_YEAR_END + 1))  # 20 years

# Hurricane Maria data exclusion window (inclusive, YYYY-MM strings)
MARIA_START = "2017-09"
MARIA_END   = "2018-06"

# ---------------------------------------------------------------------------
# Unit conversion constants
# ---------------------------------------------------------------------------
KELVIN_TO_CELSIUS = -273.15   # add to K to get °C
PA_TO_HPA         =    0.01   # multiply Pa by this to get hPa
M_TO_MM           = 1000.0    # multiply m by this to get mm
MM_TO_M           =    0.001

# Days per calendar month (non-leap year)
# Used when converting ERA5 monthly mean daily rate → monthly total
DAYS_PER_MONTH = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31,  6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}
