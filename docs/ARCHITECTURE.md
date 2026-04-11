# ARCHITECTURE.md
# ngVLA Puerto Rico — Project Architecture
# Last updated: April 9, 2026
# Author: César Pollack, UPR Río Piedras

---

## Overview

This project performs a systematic atmospheric site characterization
for ngVLA antenna placement in Puerto Rico. The codebase follows a
strict separation between reusable library logic (`src/pr_ngvla/`)
and phase-specific orchestration scripts (`scripts/`).

---

## Directory Structure

```
pr_ngvla/
├── src/pr_ngvla/              ← Installable Python library (all logic here)
│   ├── __init__.py
│   ├── config.py              ← ALL paths, constants, CRS, bounding box
│   ├── physics/
│   │   └── thermodynamics.py  ← Magnus RH formula, dew point depression
│   ├── data/
│   │   ├── loaders.py         ← load_era5_monthly, load_era5_pwv, load_noaa_isd_stations
│   │   ├── spatial.py         ← load_vector_data (returns 3 values!), load_dem
│   │   └── temporal.py        ← monthly_climatology, precip_to_mm_month
│   ├── analysis/
│   │   ├── thresholds.py      ← THRESHOLDS dict + classify()
│   │   ├── exceedance.py      ← monthly_exceedance_climatology, save_exceedance
│   │   ├── validation.py      ← validate_station, compute_metrics, build_land_mask
│   │   ├── fuzzy.py           ← linear_membership, composite_index, annual_composite
│   │   └── gapfill.py         ← regrid_singlelev_to_era5land, merge_era5land_singlelev
│   └── visualization/
│       └── maps.py            ← mask_ocean, plot_base_map, style_axes_grid,
│                                 add_colorbar, add_station_overlay, add_north_arrow
│
├── scripts/                   ← Orchestrators only (no logic, no hard-coding)
│   ├── phase1_map_temperature.py
│   ├── phase1_map_rh.py
│   ├── phase1_map_tdep.py
│   ├── phase1_map_wind.py
│   ├── phase1_map_precip.py
│   ├── phase1_map_dem.py
│   ├── phase1_map_pwv.py
│   ├── phase2_exceedance.py
│   ├── phase2_validation.py
│   ├── phase2_map_exceedance.py
│   ├── phase3_composite_index.py
│   ├── phase3_map_composite.py
│   ├── phase3_best_regions_report.py
│   ├── phase3_gapfill_singlelev.py
│   └── phase3_map_gapfill.py
│
├── data_raw/                  ← RAW DATA — NEVER MODIFIED
│   ├── era5/
│   │   ├── monthly/           ← 2 NetCDF files (complete)
│   │   ├── hourly/            ← 480 NetCDF files, ERA5-Land (complete)
│   │   ├── singlelev/         ← 720 NetCDF files, ERA5-SL (complete)
│   │   └── pwv/               ← 20 NetCDF files (complete)
│   ├── noaa/isd/              ← 5 stations + catalog (complete)
│   ├── dem/pr_dem_30m.tif     ← SRTM 30m DEM (complete)
│   ├── shapefiles/
│   │   ├── GSHHS_h_L1.shp    ← High-res coastline
│   │   └── tl_2024_us_county/ ← TIGER municipalities
│   └── prism/                 ← 39 .asc files, 1963-1995 normals
│
├── outputs/                   ← GENERATED — reproducible from scripts
│   ├── maps/
│   │   ├── phase1/            ← 7 monthly climatology PNGs
│   │   ├── phase2/            ← 4 exceedance PNGs
│   │   └── phase3/            ← site selection index PNGs
│   ├── phase2/                ← exceedance NetCDFs + validation CSV
│   ├── phase3/
│   │   ├── composite_index_monthly.nc
│   │   ├── composite_index_annual.nc
│   │   ├── best_regions_annual.csv
│   │   ├── best_regions_monthly.csv
│   │   ├── best_municipalities.csv
│   │   ├── best_regions_summary.txt
│   │   └── gapfill/           ← gap-filled composites + provenance mask
│   └── validation/
│       └── era5_vs_isd_metrics.csv
│
├── docs/                      ← Scientific and technical documentation
│   ├── ARCHITECTURE.md        ← This file
│   ├── DECISIONS.md           ← Scientific and methodological decisions
│   ├── BUGS_FIXED.md          ← Bug registry (prevents regressions)
│   └── REPRODUCING.md         ← How to reproduce all results from scratch
│
└── pyproject.toml             ← Library installation config

```

---

## Core Design Rules

### Rule 1 — Library vs Script separation
- **Library** (`src/pr_ngvla/`): all reusable logic, functions, classes
- **Scripts** (`scripts/`): orchestration only — load data, call library, save outputs
- Scripts NEVER contain scientific logic. If logic appears in a script, move it to the library.

### Rule 2 — No hard-coding
- ALL paths, constants, thresholds, CRS codes go in `config.py`
- Scripts import from config. Never type a path or number directly in a script.

### Rule 3 — Idempotent scripts
- Every script can be run twice without breaking anything
- Outputs are overwritten cleanly on re-run
- No script depends on the state of a previous interactive session

### Rule 4 — spatial.py returns 3 values (CRITICAL)
```python
# ALWAYS unpack all 3:
muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)

# coast_union      → GSHHS polygon, used for DRAWING coastline only
# muni_land_union  → dissolved municipalities, used for OCEAN MASKING only
# muni_clip        → clipped municipalities for map overlay
```

### Rule 5 — Ocean masking
```python
# ALWAYS use muni_land_union for masking (NOT coast_union)
# GSHHS has interior rings for coastal lagoons → white patches if used for masking
mask_ocean(ax, muni_land_union)
```

### Rule 6 — Library installation
```bash
# Library is installed in editable mode — NEVER use sys.path.insert
cd /export/ngvla/cpollack/pr_ngvla
pip install -e .
python -c "import pr_ngvla; print(pr_ngvla.__version__)"
```

---

## Data Flow

```
data_raw/era5/hourly/          ─┐
data_raw/era5/monthly/          │
data_raw/era5/pwv/              ├─→ Phase 1 scripts → outputs/maps/phase1/
data_raw/dem/                   │
data_raw/shapefiles/           ─┘

data_raw/era5/hourly/          ─┐
data_raw/noaa/isd/              ├─→ Phase 2 scripts → outputs/phase2/
                               ─┘                  → outputs/maps/phase2/

outputs/phase2/*.nc            ─┐
                                ├─→ Phase 3A scripts → outputs/phase3/
                               ─┘                   → outputs/maps/phase3/

data_raw/era5/singlelev/       ─┐
outputs/phase2/*.nc             ├─→ Phase 3B scripts → outputs/phase3/gapfill/
outputs/phase3/*.nc            ─┘                   → outputs/maps/phase3/*_gf.png
```

---

## ERA5-SL File Structure (post-extraction)

ERA5 single-levels files were downloaded as ZIP archives and extracted:

```
era5sl_hourly_t2m_d2m_PR_YYYY_MM.nc      ← t2m, d2m (instant)
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_instant.nc  ← u10, v10, sp
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_accum.nc    ← tp (accumulated)
```

Key difference from ERA5-Land files:
- Time dimension is called `valid_time` (not `time`)
- Grid: 4 lats × 13 lons (0.25° resolution)
- ERA5-Land grid: 9 lats × 31 lons (0.1° resolution)

---

## Gap-Fill Architecture (Phase 3B)

```
ERA5-Land exceedance (0.1°, 68 land px)
         +
ERA5-SL exceedance (0.25°, filtered by land fraction ≥60%)
         ↓
Land fraction mask (computed from PR municipality shapefile)
         ↓
Bilinear interpolation to ERA5-Land grid
         ↓
Merge: ERA5-Land primary, ERA5-SL for NaN gaps only
         ↓
Provenance mask saved (0=ocean, 1=ERA5-Land, 2=ERA5-SL)
         ↓
Composite site selection index (gap-filled)
```

---

## Compilation

```bash
# Presentation (server)
cd /export/ngvla/cpollack/presentations/presentation_01/
lualatex ngvla_pr_phase1.tex
lualatex ngvla_pr_phase1.tex  # twice for ToC

# Sync maps to laptop
rsync -avz --progress cpollack@astroiupi:/export/ngvla/cpollack/pr_ngvla/outputs/maps/ ./maps/
```

---

## Server Information

- **Host:** astroiupi | **User:** cpollack
- **OS:** OpenSUSE Leap 15.6
- **RAM:** 1 TB | **Cores:** 96 | **Disk:** 11 TB
- **Conda env:** pr_ngvla
- **Project root:** `/export/ngvla/cpollack/pr_ngvla/`
- **Rule:** NEVER work in home/ — always use /export/ngvla/cpollack/
- **Sessions:** tmux (NOT slurm/squeue)
