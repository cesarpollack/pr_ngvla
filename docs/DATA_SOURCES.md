# DATA_SOURCES.md
# ngVLA Puerto Rico — Data Sources and Download Instructions
# Last updated: April 2026
# Author: César Pollack, UPR Río Piedras

---

## Overview

This project uses four primary data sources. None of the raw data is included
in the repository (~300 GB total). This document explains what each dataset is,
why we use it, where to get it, and how it is organized on the server.

---

## What is ERA5? What is reanalysis?

A **reanalysis** is a reconstruction of past atmospheric conditions produced
by running a numerical weather prediction (NWP) model over historical periods,
assimilating all available observations (satellites, radiosondes, surface
stations, aircraft). The result is a physically consistent, spatially complete
gridded dataset of all atmospheric variables at regular time intervals.

The advantage over station data: global coverage, no gaps, all variables
available at every grid point. The limitation: values represent a grid-cell
average (~9 km for ERA5-Land), not a point measurement.

**ERA5** is the fifth generation reanalysis produced by ECMWF (European Centre
for Medium-Range Weather Forecasts). It is currently the gold standard for
atmospheric reanalysis and is used in astronomical site characterization
studies worldwide (Bi et al. 2024, MNRAS).

---

## Dataset 1 — ERA5-Land (primary dataset)

**What it is:** A land-surface enhanced version of ERA5. ECMWF runs the HTESSEL
land surface model forced by ERA5 atmospheric fields at higher spatial resolution,
specifically optimized for land surface variables.

**Why we use it:**
- Highest resolution publicly available reanalysis for land (~9 km)
- Provides all 7 ngVLA study variables with hourly temporal resolution
- Globally validated (Muñoz-Sabater et al. 2021)
- Used as the gold standard in astronomical site characterization

**Important limitation:** ERA5-Land assigns NaN to coastal pixels where the
land fraction within the ~9 km cell falls below an internal ECMWF threshold.
This affects Lajas, Guánica, and parts of the SW coast — addressed in Phase 3B.

**Variables downloaded:**
- `t2m` — 2m air temperature [K]
- `d2m` — 2m dew point temperature [K] (used to compute RH and T−Td)
- `u10`, `v10` — 10m wind components [m/s]
- `tp` — total precipitation [m/hour accumulated]
- `sp` — surface pressure [Pa] (input to PWV retrieval)

**Resolution:** 0.1° × 0.1° (~9 km), hourly, 2004–2023

**Bounding box:** lat 17.5–18.6°N, lon −68.0 to −65.0°W

**Files on server:**
```
data_raw/era5/hourly/
    era5land_hourly_t2m_d2m_PR_YYYY_MM.nc          ← temperature + dew point
    era5land_hourly_wind_tp_sp_PR_YYYY_MM.nc        ← wind + precip + pressure
data_raw/era5/monthly/
    era5land_monthly_t2m_d2m_PR_2004_2023.nc
    era5land_monthly_wind_tp_sp_PR_2004_2023.nc
```
Total: 480 hourly files + 2 monthly files

**Download script:** `scripts/download_era5land_hourly_pr.py`

**Source:** https://cds.climate.copernicus.eu  
Dataset: `reanalysis-era5-land`  
Access: free account required, terms of use must be accepted

---

## Dataset 2 — ERA5 Single-Levels (PWV and gap-fill)

**What it is:** ERA5 at standard (~28 km) resolution, extracted at the single
level closest to the surface. Unlike ERA5-Land, it covers both land and ocean
and provides total column water vapor (TCWV = PWV).

**Why we use it:**
- ERA5-Land does not provide total column water vapor
- TCWV is validated against GNSS and radiosondes with correlation >0.99
  (Zhang et al. 2019)
- Used as secondary source for coastal pixel gap-fill (Phase 3B)

**Variables downloaded:**
- `tcwv` — total column water vapor [kg/m² = mm PWV]
- `t2m`, `d2m`, `u10`, `v10`, `tp`, `sp` — for gap-fill only

**Resolution:** 0.25° × 0.25° (~28 km), hourly, 2004–2023

**Files on server:**
```
data_raw/era5/pwv/
    era5_hourly_tcwv_PR_YYYY.nc                    ← one file per year
data_raw/era5/singlelev/
    era5sl_hourly_t2m_d2m_PR_YYYY_MM.nc
    era5sl_hourly_wind_tp_sp_PR_YYYY_MM_instant.nc
    era5sl_hourly_wind_tp_sp_PR_YYYY_MM_accum.nc
```
Total: 20 PWV files + ~720 singlelev files

**Download scripts:**
- `scripts/download_era5_pwv_pr.py`
- `scripts/download_era5_singlelev_pr.py`

**Source:** https://cds.climate.copernicus.eu  
Dataset: `reanalysis-era5-single-levels`

**Key difference from ERA5-Land files:**
ERA5-SL uses `valid_time` as the time dimension name, not `time`.
This is handled in `src/pr_ngvla/data/loaders.py`.

---

## Dataset 3 — NOAA ISD (validation stations)

**What it is:** The NOAA Integrated Surface Database — hourly surface
meteorological observations from airport and military weather stations.

**Why we use it:** To validate ERA5-Land against in-situ observations in PR.
These are the only stations with continuous hourly records for our study period.

**Limitation:** All 5 stations are coastal and at airports or military bases.
No mountain stations exist in the Cordillera Central — the validation does not
cover the interior highlands.

**The 5 stations:**

| Station ID | Name | Location | ICAO |
|---|---|---|---|
| 785140-11603 | Rafael Hernández Airport | Aguadilla (NW) | TJBQ |
| 785145-11653 | Eugenio María de Hostos Airport | Mayagüez (W) | TJMZ |
| 785260-11641 | Luis Muñoz Marín International | San Juan (NE) | TJSJ |
| 785265-00494 | Fernando Luis Ribas Dominicci | Isla Grande, SJ (NE) | TJIG |
| 785350-11630 | Naval Station Roosevelt Roads | Ceiba (E) | TJNR |

**Files on server:**
```
data_raw/noaa/isd/
    station_catalog.csv                            ← station metadata
    station_inventory.csv                          ← availability summary
    785140-11603_RAFAEL_HERNANDEZ_AIRPORT.csv
    785145-11653_EUGENIO_MARIA_DE_HOSTOS_AIRPOR.csv
    785260-11641_LUIS_MUNOZ_MARIN_INTERNATIONAL.csv
    785265-00494_FERNANDO_LUIS_RIBAS_DOMINICCI_.csv
    785350-11630_NAVAL_STATION_ROOSEVELT_ROADS_.csv
```

**Download script:** `scripts/download_noaa_isd_pr.py`

**Source:** https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database  
Access: free, no account required

---

## Dataset 4 — Digital Elevation Model (DEM)

**What it is:** A 30-meter resolution elevation grid of Puerto Rico derived
from the SRTM (Shuttle Radar Topography Mission) / Copernicus DEM.

**Why we use it:**
- Context map (Cordillera Central topography)
- Future work: lapse rate temperature correction (Phase 4)

**File on server:**
```
data_raw/dem/pr_dem_30m.tif     ← single GeoTIFF, EPSG:4326
```

**Source:** https://opentopography.org or Copernicus DEM at ESA  
Access: free, registration may be required

---

## Dataset 5 — Shapefiles (vector boundaries)

These are used for map rendering — not ERA5 data.

| File | Description | Source |
|---|---|---|
| `GSHHS_h_L1.shp` | High-resolution coastline | GSHHG (NOAA) |
| `tl_2024_us_county/` | PR municipality boundaries | US Census TIGER/Line 2024 |

**Files on server:**
```
data_raw/shapefiles/
    GSHHS_h_L1.shp (.dbf .prj .shx)
    tl_2024_us_county/
        tl_2024_us_county.shp (.dbf .prj .shx .cpg)
```

**Sources:**
- GSHHG coastline: https://www.soest.hawaii.edu/pwessel/gshhg/
- TIGER/Line: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

---

## Dataset 6 — PRISM (independent precipitation validation)

**What it is:** Parameter-elevation Regressions on Independent Slopes Model.
A 450-meter resolution precipitation climatology derived from station observations,
covering Puerto Rico 1963–1995.

**Why we use it:** Independent spatial validation of ERA5 precipitation patterns.
Not used in the main analysis — used only to confirm that ERA5 captures the
correct spatial gradient (wet NE, dry SW).

**Important limitation:** PRISM confirmed they will not update PR normals
(indefinitely on hold). The period mismatch (PRISM 1963–1995 vs ERA5 2004–2023)
means quantitative comparison is not valid — spatial pattern validation only.

**Files on server:**
```
data_raw/prism/
    PRISM_ppt_pr_1963-1995_normal_450mM1_MM_asc.asc   ← monthly (12 files)
    PRISM_ppt_pr_1963-1995_normal_450mM1_annual_asc.asc
```

**Source:** https://prism.oregonstate.edu  
Access: free

---

## Storage summary

| Dataset | Location | Size | Files |
|---|---|---|---|
| ERA5-Land hourly | `data_raw/era5/hourly/` | ~200 GB | 480 |
| ERA5-Land monthly | `data_raw/era5/monthly/` | ~2 MB | 2 |
| ERA5 Single-Levels | `data_raw/era5/singlelev/` | ~80 GB | ~720 |
| ERA5 PWV | `data_raw/era5/pwv/` | ~500 MB | 20 |
| NOAA ISD | `data_raw/noaa/isd/` | ~50 MB | 7 |
| DEM | `data_raw/dem/` | ~150 MB | 1 |
| Shapefiles | `data_raw/shapefiles/` | ~50 MB | ~10 |
| PRISM | `data_raw/prism/` | ~5 MB | 27 |
| **Total** | | **~300 GB** | |

---

## Download order (important)

Download in this order — later steps depend on earlier ones:

```
1. Shapefiles     → needed by all map scripts
2. DEM            → needed by phase1_map_dem.py
3. NOAA ISD       → needed by phase2_validation.py and all map scripts
4. ERA5 monthly   → needed by Phase 1 (fast, minutes)
5. ERA5 PWV       → needed by Phase 1 PWV map and Phase 2 PWV exceedance
6. ERA5 hourly    → needed by Phase 2 exceedance (slow, several days)
7. ERA5 singlelev → needed by Phase 3B gap-fill (slow, several days)
8. PRISM          → optional, validation only
```

The monthly ERA5 data (~2 MB) is sufficient to test the entire Phase 1
pipeline while the hourly data downloads in the background.

---

*Last updated: April 2026 — César Pollack, UPR Río Piedras / CARSE*
