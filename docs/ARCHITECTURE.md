# PR-ngVLA project architecture

**Project:** PR-ngVLA
**Current workflow stage:** GHCNh hourly clean core
**Study period:** 2004-2023
**Last updated:** April 2026

---

## 1. Purpose

This document describes the current project architecture for the PR-ngVLA workflow.

The current active stage is:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

The current architecture is centered on building a reliable observational station dataset from NOAA GHCNh hourly data before comparison against ERA5 or other reanalysis products.

Older phase-based ERA5, NOAA ISD, PRISM, fuzzy-index, and gap-fill scripts may still exist in the repository for historical continuity, but they are not the current active workflow for this branch.

---

## 2. Current architectural principle

The project architecture follows this principle:

```text
raw data -> intermediate clean products -> documented reproducible outputs
```

The current workflow does not attempt to hide missing data or prematurely classify stations as usable/unusable. Instead, it builds:

1. A strict hourly clean core.
2. No-threshold station/year/variable coverage tables.
3. Documentation describing assumptions, limitations, and decisions.

---

## 3. Current repository structure

```text
pr_ngvla/
├── scripts/
│   ├── build_ghcnh_hourly_clean_core_pr.py
│   └── build_ghcnh_hourly_clean_core_coverage_tables_pr.py
├── docs/
│   ├── GHCNH_HOURLY_CLEAN_CORE.md
│   ├── DATA_SOURCES.md
│   ├── REPRODUCING.md
│   ├── DECISIONS.md
│   ├── ARCHITECTURE.md
│   ├── FUTURE_WORK.md
│   └── archive/
├── data_raw/        # local raw data, not tracked
├── data_interim/    # local intermediate products, not tracked
├── outputs/         # local generated products, not tracked
├── logs/            # local logs, not tracked
├── src/
├── tests/
├── environment.yml
├── pyproject.toml
└── README.md
```

---

## 4. Data directories

### 4.1 `data_raw/`

`data_raw/` contains raw external datasets.

For the current GHCNh workflow, the main raw files are:

```text
data_raw/noaa/ghcnh/hourly/by_year/<YYYY>/parquet/GHCNh_<station>_<YYYY>.parquet
```

Raw data are not modified by scripts.

Raw data are not tracked in Git.

### 4.2 `data_interim/`

`data_interim/` contains reproducible intermediate workflow products.

Current important products:

```text
data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet

data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet

data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

These products are generated from scripts and are not tracked in Git.

### 4.3 `outputs/`

`outputs/` is reserved for generated maps, figures, reports, and later analysis products.

The current GHCNh clean-core stage does not depend on committing files from `outputs/`.

---

## 5. Script architecture

Scripts are used as reproducible workflow stages.

The current active scripts are:

```text
scripts/build_ghcnh_hourly_clean_core_pr.py
scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

### 5.1 Clean-core builder

```bash
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Purpose:

1. Read raw GHCNh station-year Parquet files.
2. Apply strict quality-control rules.
3. Apply physical consistency checks.
4. Handle precipitation source-specific metadata.
5. Aggregate observations to hourly clean records.
6. Write the clean core and decision summaries.

Main output:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

### 5.2 Coverage-table builder

```bash
python scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

Purpose:

1. Read the clean core.
2. Build the full station-year grid.
3. Generate station/year/variable coverage tables.
4. Avoid applying usability thresholds.
5. Write long, wide, station summary, and variable summary tables.

Main output directory:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

---

## 6. Documentation architecture

The current documentation is organized as follows:

| Document | Role |
|---|---|
| `README.md` | High-level project status and current workflow summary |
| `docs/GHCNH_HOURLY_CLEAN_CORE.md` | Main technical reference for the current clean-core stage |
| `docs/DATA_SOURCES.md` | Data-source descriptions and local organization |
| `docs/REPRODUCING.md` | Step-by-step reproduction guide |
| `docs/DECISIONS.md` | Frozen methodological decisions |
| `docs/ARCHITECTURE.md` | Project architecture |
| `docs/FUTURE_WORK.md` | Current roadmap and next stages |
| `docs/archive/` | Historical documentation from previous workflow stages |

The current methodological reference for this branch is:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

---

## 7. Current data flow

The current active data flow is:

```text
GHCNh metadata + station inventory
        |
        v
Puerto Rico station inventory
        |
        v
GHCNh station-year Parquet files, 2004-2023
        |
        v
strict QC clean core
        |
        v
no-threshold station/year/variable coverage tables
        |
        v
documented observational reference for ERA5 comparison
```

More explicitly:

```text
data_raw/noaa/ghcnh/metadata/
        |
        v
data_interim/noaa/ghcnh_station_inventory/
        |
        v
data_raw/noaa/ghcnh/hourly/by_year/
        |
        v
data_interim/noaa/ghcnh_hourly/clean_core/
        |
        v
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

---

## 8. Clean-core rules encoded in the architecture

The clean-core stage is conservative.

Current architectural rules:

1. Do not retain suspect QC for any variable.
2. Do not retain strong QC errors.
3. Do not use numeric values without metadata interpretation.
4. Do not treat all precipitation values as equivalent.
5. Do not sum sub-hourly precipitation blindly.
6. Do not retain Source 382 / QC `A` precipitation as hourly rainfall.
7. Do not apply usability thresholds in the general coverage tables.
8. Do not include PWV in GHCNh because GHCNh does not provide PWV directly.
9. Do not advance to ERA5 comparison until station coverage is documented.

---

## 9. Current clean-core variables

The current clean core retains:

| Clean column | Unit |
|---|---:|
| `temperature_c` | °C |
| `dew_point_temperature_c` | °C |
| `relative_humidity_pct` | % |
| `wind_speed_m_s` | m/s |
| `station_level_pressure_hpa` | hPa |
| `precipitation_mm` | mm |

PWV is not part of the GHCNh clean core.

---

## 10. Current clean-core endpoint

The current reproducible endpoint is:

```text
GHCNh hourly clean core + no-threshold coverage tables
```

Current clean-core table:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

Current no-threshold coverage directory:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

Current clean value ranges:

| Variable | Final clean range |
|---|---:|
| `temperature_c` | 14.0-40.0 °C |
| `dew_point_temperature_c` | 2.0-31.0 °C |
| `relative_humidity_pct` | 11-100 % |
| `wind_speed_m_s` | 0.0-31.4 m/s |
| `station_level_pressure_hpa` | 902.0-1024.4 hPa |
| `precipitation_mm` | 0.0-101.9 mm |

---

## 11. No-threshold coverage endpoint

The full station-year grid is:

```text
39 stations × 20 years = 780 station-years
```

Current no-threshold variable summary:

| Variable | Station-years with any data | Stations with any data | Total valid hours | Fraction of all possible station-hours |
|---|---:|---:|---:|---:|
| `precipitation_mm` | 384 | 25 | 2,096,607 | 0.306634 |
| `temperature_c` | 238 | 17 | 1,495,071 | 0.218658 |
| `wind_speed_m_s` | 216 | 17 | 1,340,993 | 0.196124 |
| `dew_point_temperature_c` | 127 | 9 | 693,016 | 0.101355 |
| `relative_humidity_pct` | 127 | 9 | 692,829 | 0.101328 |
| `station_level_pressure_hpa` | 66 | 5 | 362,616 | 0.053034 |

These summaries do not apply station usability thresholds.

---

## 12. Relationship to ERA5

ERA5 and/or ERA5-Land are not the current primary data source in this branch.

The next major stage is ERA5/reanalysis comparison using the clean GHCNh station data as the observational reference.

The ERA5 architecture should be designed after the observational coverage limitations are understood.

The future ERA5 stage must handle:

1. Variable alignment.
2. Time alignment.
3. Spatial station-to-grid matching.
4. Different station coverage by variable.
5. Missing PWV in GHCNh.
6. Puerto Rico coastal and grid-cell limitations.

---

## 13. Older prototype scripts

Older scripts may remain in the repository, including scripts related to:

```text
phase1_*
phase2_*
phase3_*
download_era5*
download_noaa_isd*
download_prism*
```

These scripts are retained for historical continuity and future reference, but they are not the current active workflow for the GHCNh clean-core stage.

Do not treat older ERA5/ISD outputs as current validated results.

---

## 14. Server and execution architecture

Recommended project root:

```text
/export/ngvla/cpollack/pr_ngvla
```

Recommended environment:

```bash
conda activate pr_ngvla
```

Long jobs should be run in `tmux`.

Example:

```bash
tmux new -s ghcnh_clean_core
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Detach:

```text
Ctrl-b then d
```

Reconnect:

```bash
tmux attach -t ghcnh_clean_core
```

---

## 15. Git and reproducibility rules

Git should track:

```text
scripts/
docs/
src/
tests/
environment.yml
pyproject.toml
README.md
```

Git should not track:

```text
data_raw/
data_interim/
outputs/
logs/
```

The project should be reproducible through scripts and documentation, not by committing large data products.

---

## 16. Next architecture step

After this documentation stage, the next architecture task is to design the ERA5/reanalysis comparison stage.

That stage should be added incrementally and should not overwrite the frozen GHCNh clean-core architecture.
