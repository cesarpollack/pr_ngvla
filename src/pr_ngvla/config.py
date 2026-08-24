"""
src/pr_ngvla/config.py
======================

Project-wide constants: file paths, geographic parameters, CRS strings,
time period, and unit conversion factors.

This module is imported by every other module in the package.
It contains no data-processing logic — only constants derived from the
project structure and the study design.

Design rule
-----------
If a value is used in more than one place, it lives here.
Scripts and library modules import from this file; they never
hard-code paths or magic numbers.
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
# __file__ is: src/pr_ngvla/config.py
# parents[2] resolves to the project root directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Raw data directories
# ---------------------------------------------------------------------------
DATA_RAW = PROJECT_ROOT / "data_raw"

# ERA5 / reanalysis raw data
ERA5_DIR = DATA_RAW / "era5"
ERA5_MONTHLY_DIR = ERA5_DIR / "monthly"
ERA5_HOURLY_DIR = ERA5_DIR / "hourly"
# ERA5 single-levels TCWV/PWV.
# ERA5_PWV_DIR preserves the original narrow request for diagnostic traceability.
# ERA5_PWV_BUFFERED_PR_DIR is the corrected interpolation-support acquisition.
ERA5_PWV_DIR = ERA5_DIR / "pwv"
ERA5_PWV_BUFFERED_PR_DIR = ERA5_DIR / "pwv_buffered_pr"
ERA5_SINGLELEV_DIR = ERA5_DIR / "singlelev"

# NOAA raw data
NOAA_DIR = DATA_RAW / "noaa"
NOAA_ISD_DIR = NOAA_DIR / "isd"
NOAA_GHCN_DIR = NOAA_DIR / "ghcn"
NOAA_IGRA_DIR = NOAA_DIR / "igra"
NOAA_GNSS_PWV_DIR = NOAA_DIR / "gnss_pwv"

# NOAA authoritative metadata files
NOAA_ISD_METADATA_DIR = NOAA_ISD_DIR / "metadata"
NOAA_GHCN_METADATA_DIR = NOAA_GHCN_DIR / "metadata"

NOAA_ISD_HISTORY_CSV = NOAA_ISD_METADATA_DIR / "isd-history.csv"
NOAA_ISD_INVENTORY_CSV = NOAA_ISD_METADATA_DIR / "isd-inventory.csv"

NOAA_GHCN_STATIONS_TXT = NOAA_GHCN_METADATA_DIR / "ghcnd-stations.txt"
NOAA_GHCN_INVENTORY_TXT = NOAA_GHCN_METADATA_DIR / "ghcnd-inventory.txt"

# Other raw supporting datasets
PRISM_DIR = DATA_RAW / "prism"
DEM_PATH = DATA_RAW / "dem" / "pr_dem_30m.tif"
SHAPES_DIR = DATA_RAW / "shapefiles"

# Shapefile paths
COAST_SHP = SHAPES_DIR / "GSHHS_h_L1.shp"
MUNI_SHP = SHAPES_DIR / "tl_2024_us_county" / "tl_2024_us_county.shp"


# ---------------------------------------------------------------------------
# Processed / interim / output directories
# ---------------------------------------------------------------------------
DATA_INTERIM = PROJECT_ROOT / "data_interim"
DATA_PRODUCTS = PROJECT_ROOT / "data_products"
OUTPUTS = PROJECT_ROOT / "outputs"

# Existing output subdirectories
OUT_MAPS = OUTPUTS / "maps"
OUT_FIGURES = OUTPUTS / "figures"
OUT_TABLES = OUTPUTS / "tables"

# New NOAA / station-inventory interim directories
NOAA_INTERIM_DIR = DATA_INTERIM / "noaa"
NOAA_STATION_INVENTORY_DIR = NOAA_INTERIM_DIR / "station_inventory"
PWV_INTERIM_DIR = DATA_INTERIM / "pwv"
PWV_INVENTORY_DIR = PWV_INTERIM_DIR / "inventory"

# New output directories for station inventory / PWV inventory
OUT_STATION_INVENTORY_MAPS = OUT_MAPS / "station_inventory"
OUT_STATION_INVENTORY_TABLES = OUT_TABLES / "station_inventory"
OUT_PWV_MAPS = OUT_MAPS / "pwv"
OUT_PWV_TABLES = OUT_TABLES / "pwv"


# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
WGS84 = "EPSG:4326"      # Geographic CRS for storage and plotting
METRIC_CRS = "EPSG:32620"  # UTM Zone 20N for metric operations


# ---------------------------------------------------------------------------
# Geographic bounding box (decimal degrees, WGS84)
# ---------------------------------------------------------------------------
# Project standard bounding box:
# covers Puerto Rico main island + Mona + Vieques + Culebra
PR_BBOX_S = 17.8
PR_BBOX_W = -68.0
PR_BBOX_N = 18.6
PR_BBOX_E = -65.0

# Convenience tuple in south-west-north-east order
PR_BBOX = (PR_BBOX_S, PR_BBOX_W, PR_BBOX_N, PR_BBOX_E)

# Display limits for maps: slightly wider than the data bbox
MAP_XLIM = (PR_BBOX_W - 0.2, PR_BBOX_E + 0.05)
MAP_YLIM = (PR_BBOX_S - 0.05, PR_BBOX_N + 0.05)

# ERA5 CDS API order is [N, W, S, E]
ERA5_BBOX = [PR_BBOX_N, PR_BBOX_W, PR_BBOX_S, PR_BBOX_E]


# ---------------------------------------------------------------------------
# Study period
# ---------------------------------------------------------------------------
STUDY_YEAR_START = 2004
STUDY_YEAR_END = 2023
STUDY_YEARS = list(range(STUDY_YEAR_START, STUDY_YEAR_END + 1))

# String versions used by inventory and filtering code
STUDY_START_DATE = "2004-01-01"
STUDY_END_DATE = "2023-12-31"


# ---------------------------------------------------------------------------
# Hurricane María exclusion window
# ---------------------------------------------------------------------------
# Project-level exclusion window for climatological analyses affected by
# Hurricane María's post-landfall hydrological disruption.
#
# Window definition:
#   start inclusive: 2017-09-20 00:00:00
#   end inclusive:   2018-01-31 23:59:59...
#   end exclusive:   2018-02-01 00:00:00
#
# Rationale:
#   The window starts on Hurricane María's Puerto Rico landfall date and ends
#   before February 2018, following the project interpretation of Miller et al.
#   (2019), "Persistent Hydrological Consequences of Hurricane Maria in
#   Puerto Rico", Geophysical Research Letters, 46(3), 1413-1422,
#   doi:10.1029/2018GL081591.
#
# Important implementation detail:
#   MARIA_EXCLUSION_*_DATE provides the exact day-level window for hourly
#   station products. MARIA_START / MARIA_END are retained as month-level
#   compatibility constants for existing monthly ERA5 scripts that currently
#   filter by YYYY-MM rather than exact dates.
MARIA_EXCLUSION_START_DATE = "2017-09-20"
MARIA_EXCLUSION_END_DATE = "2018-01-31"
MARIA_EXCLUSION_END_EXCLUSIVE_DATE = "2018-02-01"
MARIA_EXCLUSION_SOURCE = (
    "Miller et al. (2019), Persistent Hydrological Consequences of "
    "Hurricane Maria in Puerto Rico, Geophysical Research Letters, "
    "doi:10.1029/2018GL081591"
)

# Month-level compatibility constants used by legacy monthly ERA5 code.
# This excludes full calendar months overlapping the date-level window.
MARIA_MONTH_START = "2017-09"
MARIA_MONTH_END = "2018-01"

# Backward-compatible names used by existing Phase 2 ERA5 code.
MARIA_START = MARIA_MONTH_START
MARIA_END = MARIA_MONTH_END


# ---------------------------------------------------------------------------
# Unit conversion constants
# ---------------------------------------------------------------------------
KELVIN_TO_CELSIUS = -273.15
PA_TO_HPA = 0.01
M_TO_MM = 1000.0
MM_TO_M = 0.001


# ---------------------------------------------------------------------------
# Calendar constants
# ---------------------------------------------------------------------------
DAYS_PER_MONTH = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}
