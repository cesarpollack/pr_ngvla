# Reproducing the current PR-ngVLA workflow

**Project:** PR-ngVLA
**Current workflow stage:** GHCNh hourly clean core
**Study period:** 2004-2023
**Last updated:** April 2026

---

## 1. Purpose

This document explains how to reproduce the current active workflow in this branch.

The current frozen stage is:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

This workflow builds a reliable observational station dataset from NOAA GHCNh hourly data for Puerto Rico before comparison against ERA5 or other reanalysis products.

This document does **not** reproduce the older ERA5-first, NOAA ISD, or site-ranking prototype workflow. Those older scripts may still exist in the repository, but they are not the current methodological reference for this branch.

Current technical reference:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

Current data-source reference:

```text
docs/DATA_SOURCES.md
```

---

## 2. Important workflow rule

Do not advance to ERA5/reanalysis comparison until the GHCNh observational workflow is clean, reproducible, and documented.

The purpose of this stage is to answer:

1. Which Puerto Rico stations exist in GHCNh?
2. Which station-year files are available?
3. Which variables survive strict quality control?
4. What is the real clean coverage by station, year, and variable?
5. Are the retained values physically and methodologically defensible?

---

## 3. Environment setup

### 3.1 Activate the conda environment

On `astroiupi`:

```bash
cd /export/ngvla/cpollack/pr_ngvla
conda activate pr_ngvla
```

Verify Python:

```bash
which python
python --version
```

Expected: Python should come from the `pr_ngvla` conda environment, not from `/usr/bin/python`.

### 3.2 Basic code checks

```bash
python -m pytest tests/ -v
```

If tests fail, stop and fix the environment or code before continuing.

---

## 4. Data tracking policy

Large data products are not tracked in Git.

Not tracked:

```text
data_raw/
data_interim/
outputs/
logs/
```

Tracked:

```text
scripts/
docs/
src/
tests/
environment.yml
pyproject.toml
README.md
```

The workflow should be reproducible from scripts and documentation, not from committing raw or intermediate data.

---

## 5. Required local input data

The current GHCNh workflow depends on these local data categories:

### 5.1 GHCNh metadata

Expected location:

```text
data_raw/noaa/ghcnh/metadata/
```

Required files:

```text
ghcnh-station-list.csv
ghcnh-inventory.txt
```

If missing, download them with:

```bash
python scripts/download_ghcnh_metadata.py
```

### 5.2 Geospatial support files for the station inventory

The station-inventory workflow uses Puerto Rico spatial reference layers to filter stations to the territory.

Expected local sources include:

```text
data_raw/shapefiles/GSHHS_h_L1.shp
data_raw/shapefiles/tl_2024_us_county/tl_2024_us_county.shp
```

These are auxiliary mapping/spatial-filtering layers. They do not define meteorological values.

### 5.3 GHCNh hourly station-year files

Expected raw hourly files:

```text
data_raw/noaa/ghcnh/hourly/by_year/<YYYY>/parquet/GHCNh_<station>_<YYYY>.parquet
```

The current clean-core workflow expects Parquet station-year files.

---

## 6. Step 1 — Build the Puerto Rico GHCNh station inventory

Run:

```bash
python scripts/build_ghcnh_station_inventory_pr.py
```

Expected output directory:

```text
data_interim/noaa/ghcnh_station_inventory/
```

Important expected file:

```text
data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet
```

This master inventory is used by the download and coverage-table stages.

Expected current inventory basis:

```text
39 stations
```

If the script fails, check that the GHCNh metadata files and geospatial shapefiles exist locally.

---

## 7. Step 2 — Download GHCNh hourly station-year files

The downloader uses direct NOAA/NCEI HTTPS access. It does **not** require a CDO token.

Dry run:

```bash
python scripts/download_ghcnh_hourly_station_year_pr.py --dry-run
```

Recommended current download mode:

```bash
python scripts/download_ghcnh_hourly_station_year_pr.py --file-mode parquet
```

For long runs, use `tmux`:

```bash
tmux new -s ghcnh_hourly_download
```

Inside `tmux`:

```bash
cd /export/ngvla/cpollack/pr_ngvla
conda activate pr_ngvla

python scripts/download_ghcnh_hourly_station_year_pr.py --file-mode parquet 2>&1 | tee data_raw/noaa/ghcnh/hourly/logs/ghcnh_hourly_download_run.log
```

Detach without killing the process:

```text
Ctrl-b then d
```

Reconnect:

```bash
tmux attach -t ghcnh_hourly_download
```

The current completed workflow used station-year Parquet files in:

```text
data_raw/noaa/ghcnh/hourly/by_year/
```

Expected current number of raw Parquet files used by the clean-core stage:

```text
591 files
```

---

## 8. Step 3 — Raw coverage diagnostics before cleaning

Run the raw variable coverage diagnostic:

```bash
python scripts/build_ghcnh_hourly_variable_coverage_pr.py
```

Purpose:

1. Verify which raw Parquet files exist.
2. Count records, timestamps, and unique hours.
3. Identify available variables by station-year.
4. Inspect raw numeric ranges before cleaning.
5. Inspect quality-code availability before clean-core decisions.

This script is diagnostic. It does not define the final clean dataset.

---

## 9. Step 4 — Quality/unit diagnostics before clean core

Run:

```bash
python scripts/build_ghcnh_hourly_quality_units_diagnostics_pr.py
```

Purpose:

1. Inspect raw values and quality codes.
2. Identify physically unreasonable values.
3. Identify scale issues such as values encoded in tenths.
4. Inspect precipitation metadata such as `Source_Code`, `Quality_Code`, `Measurement_Code`, and `Report_Type`.
5. Support strict clean-core rules before they are applied.

This script is diagnostic. It should be used to understand the data before trusting the clean-core output.

---

## 10. Step 5 — Build the strict GHCNh hourly clean core

Run:

```bash
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

For a long run, use `tmux`:

```bash
tmux new -s ghcnh_clean_core
```

Inside `tmux`:

```bash
cd /export/ngvla/cpollack/pr_ngvla
conda activate pr_ngvla

python scripts/build_ghcnh_hourly_clean_core_pr.py 2>&1 | tee data_interim/noaa/ghcnh_hourly/clean_core/build_clean_core_run.log
```

Main output:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

Expected current clean-core summary:

```text
rows: 3,345,498
stations: 39
time range: 2004-01-01 00:00:00 to 2023-12-31 23:00:00
```

---

## 11. Clean-core rules to verify

The strict clean core must satisfy these rules:

1. No variable keeps suspect QC.
2. Strong QC errors are dropped.
3. Physically unreasonable values are dropped.
4. Dew point greater than air temperature is dropped.
5. Precipitation Source 382 / QC `A` is excluded from hourly precipitation.
6. Legacy non-hourly precipitation reports such as `4-DSI-3240` are excluded.
7. Sub-hourly precipitation reports are not summed blindly.
8. Hourly precipitation aggregation uses `last_valid_report_in_hour`.
9. Wind speed is limited to 50 m/s for the clean core.
10. PWV is not included because it is not available directly from GHCNh.

---

## 12. Step 6 — Final physical checks

After building the clean core, run:

```bash
python - <<'PY'
import pandas as pd

path = "data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet"
df = pd.read_parquet(path)

cols = [
    "temperature_c",
    "dew_point_temperature_c",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "station_level_pressure_hpa",
    "precipitation_mm",
]

print(df[cols].describe().T[["count", "min", "max", "mean"]])

print("\nFinal checks:")
print("T < 4 C:", (df["temperature_c"] < 4).sum())
print("T > 41 C:", (df["temperature_c"] > 41).sum())
print("Wind > 50 m/s:", (df["wind_speed_m_s"] > 50).sum())
print("Precip > 150 mm:", (df["precipitation_mm"] > 150).sum())
print("RH < 1:", (df["relative_humidity_pct"] < 1).sum())
print("RH > 100:", (df["relative_humidity_pct"] > 100).sum())

mask_td = (
    df["temperature_c"].notna()
    & df["dew_point_temperature_c"].notna()
    & (df["dew_point_temperature_c"] > df["temperature_c"] + 0.5)
)
print("Td > T + 0.5 C:", mask_td.sum())
PY
```

Expected current ranges:

| Variable | Final clean range |
|---|---:|
| `temperature_c` | 14.0-40.0 °C |
| `dew_point_temperature_c` | 2.0-31.0 °C |
| `relative_humidity_pct` | 11-100 % |
| `wind_speed_m_s` | 0.0-31.4 m/s |
| `station_level_pressure_hpa` | 902.0-1024.4 hPa |
| `precipitation_mm` | 0.0-101.9 mm |

Expected final checks:

```text
T < 4 C: 0
T > 41 C: 0
Wind > 50 m/s: 0
Precip > 150 mm: 0
RH < 1: 0
RH > 100: 0
Td > T + 0.5 C: 0
```

If any of these checks fail, stop and inspect the clean-core script and decision summaries before continuing.

---

## 13. Step 7 — Build no-threshold coverage tables

Run:

```bash
python scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

Output directory:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

Expected generated tables:

```text
ghcnh_hourly_clean_core_station_year_variable_coverage_no_thresholds.csv
ghcnh_hourly_clean_core_station_year_variable_coverage_no_thresholds.parquet

ghcnh_hourly_clean_core_station_year_coverage_wide_no_thresholds.csv
ghcnh_hourly_clean_core_station_year_coverage_wide_no_thresholds.parquet

ghcnh_hourly_clean_core_station_variable_summary_no_thresholds.csv
ghcnh_hourly_clean_core_station_variable_summary_no_thresholds.parquet

ghcnh_hourly_clean_core_variable_summary_no_thresholds.csv
ghcnh_hourly_clean_core_variable_summary_no_thresholds.parquet
```

Expected station-year grid:

```text
39 stations × 20 years = 780 station-years
```

Expected no-threshold variable summary:

| Variable | Station-years with any data | Stations with any data | Total valid hours | Fraction of all possible station-hours |
|---|---:|---:|---:|---:|
| `precipitation_mm` | 384 | 25 | 2,096,607 | 0.306634 |
| `temperature_c` | 238 | 17 | 1,495,071 | 0.218658 |
| `wind_speed_m_s` | 216 | 17 | 1,340,993 | 0.196124 |
| `dew_point_temperature_c` | 127 | 9 | 693,016 | 0.101355 |
| `relative_humidity_pct` | 127 | 9 | 692,829 | 0.101328 |
| `station_level_pressure_hpa` | 66 | 5 | 362,616 | 0.053034 |

These tables intentionally do **not** apply usability thresholds.

---

## 14. Step 8 — Check repository state

After running the workflow, data outputs should remain untracked.

Check Git:

```bash
git status --short
```

Expected tracked changes should only be in scripts or documentation when intentionally edited.

Do not commit:

```text
data_raw/
data_interim/
outputs/
logs/
```

---

## 15. Current reproducible endpoint

The current endpoint of the workflow is:

```text
GHCNh hourly clean core + no-threshold coverage tables
```

The main deliverables are:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet

data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

The main documentation references are:

```text
README.md
docs/DATA_SOURCES.md
docs/GHCNH_HOURLY_CLEAN_CORE.md
docs/REPRODUCING.md
docs/DECISIONS.md
```

---

## 16. What not to run as the current workflow

The repository still contains older ERA5, ERA5-Land, ISD, PRISM, mapping, and site-index scripts from previous prototype stages.

Examples include scripts with names such as:

```text
phase1_*
phase2_*
phase3_*
download_era5*
download_noaa_isd*
download_prism*
```

These scripts are retained for historical continuity and future reuse, but they are **not** the current GHCNh clean-core workflow.

Do not treat older ERA5/ISD results as the current validated result of this branch.

---

## 17. Next methodological stage

After the GHCNh clean-core workflow is fully documented, the next major stage is ERA5/reanalysis comparison.

The ERA5 stage should use the clean GHCNh station data as the observational reference and should explicitly handle:

1. Variable alignment.
2. Time alignment.
3. Spatial station-to-grid matching.
4. Different station coverage by variable.
5. Missing PWV in GHCNh.
6. Puerto Rico coastal/grid-cell limitations.

Do not start ERA5 comparison until the observational station data are clean, reproducible, and their coverage limitations are transparent.
