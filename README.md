# PR-ngVLA — Atmospheric site characterization for ngVLA in Puerto Rico

**Project:** Puerto Rico atmospheric characterization for ngVLA Long Baseline Array context  
**Current branch:** `feat/ghcnh-hourly-download`  
**Current workflow stage:** observational raw-data acquisition and documentation  
**Study period:** 2004-2023  
**Last updated:** May 2026

---

## Current status

This repository is building a reproducible observational and reanalysis foundation for atmospheric site characterization in Puerto Rico.

The current branch contains two complementary workflow levels:

```text
1. NOAA GHCNh hourly clean core
   - strict quality-control workflow completed
   - no-threshold coverage tables generated
   - clean/interim observational core available locally

2. Additional observational raw-data acquisition
   - raw data sources are being acquired and documented before scientific processing
   - USGS NWIS precipitation UV raw acquisition is completed, recovered, verified, documented, and pushed
```

The project is **not** currently claiming final site rankings from this branch. The immediate goal is to ensure that observational data sources are physically meaningful, methodologically defensible, reproducible, and clearly documented before interpolation, gridded-product comparison, or site ranking.

---

## Scientific motivation

Puerto Rico is included in the ngVLA design context as a Long Baseline Array location. High-frequency radio astronomy is sensitive to atmospheric conditions such as water vapor, precipitation, humidity, wind, and related surface meteorological variables.

Before comparing gridded reanalysis products to observations, the in-situ and observational record must be understood carefully:

- Which stations and instruments have data?
- Which years are available?
- Which variables are actually present after strict quality control?
- Which values are physically plausible for Puerto Rico?
- Which precipitation records are truly hourly and which are multi-hour accumulations?
- Which raw sources require source-specific unit, timestamp, flag, or accumulation-interval review before scientific use?

This branch first addressed those questions for NOAA GHCNh hourly data and is now documenting additional raw observational sources.

---

## Main observational workflows

### NOAA GHCNh hourly clean core

NOAA Global Historical Climatology Network hourly (GHCNh) is the first strict-QC observational core in this branch.

Raw station-year Parquet files are stored locally as:

```text
data_raw/noaa/ghcnh/hourly/by_year/<YYYY>/parquet/GHCNh_<station>_<YYYY>.parquet
```

Puerto Rico station inventory:

```text
data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet
```

Clean hourly core:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

No-threshold coverage tables:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

Detailed technical reference:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

### USGS NWIS precipitation UV raw acquisition

USGS NWIS instantaneous/unit-value precipitation data are included as raw point-based hydrometeorological observations.

Current status:

```text
USGS NWIS precipitation UV raw acquisition: completed
USGS NWIS canonical manifest: completed
USGS NWIS error recovery manifest: completed
USGS NWIS technical acquisition errors remaining: 0
USGS NWIS clean/interim dataset: not started
```

Main local paths:

```text
data_raw/usgs/nwis/raw/precipitation_uv/
data_raw/usgs/nwis/metadata/usgs_nwis_pr_precipitation_uv_download_manifest_20040101_20231231.csv
data_raw/usgs/nwis/metadata/usgs_nwis_pr_precipitation_uv_retry_errors_manifest_20040101_20231231.csv
```

Final acquisition verification:

```text
canonical_rows = 5420
canonical_status_counts = {'skipped_existing': 2912, 'error': 402, 'ok': 2106}
canonical_error_rows = 402
recovery_rows = 402
recovery_status_counts = {'json_fallback_ok': 402}
unrecovered_canonical_errors = 0
missing_or_empty_recovery_files = 0
```

USGS NWIS data are currently raw only. They have not yet been converted, cleaned, quality-controlled, aggregated, interpolated, or compared scientifically.

Detailed acquisition record:

```text
docs/OBSERVATIONAL_DATA_DOWNLOADS.md
```

Raw and intermediate data products are local workflow outputs and are not tracked in Git unless project policy explicitly allows selected lightweight metadata summaries.

---

## Variables in the GHCNh clean core

| Clean column | Unit |
|---|---:|
| `temperature_c` | °C |
| `dew_point_temperature_c` | °C |
| `relative_humidity_pct` | % |
| `wind_speed_m_s` | m/s |
| `station_level_pressure_hpa` | hPa |
| `precipitation_mm` | mm |

PWV is **not** directly available from GHCNh. PWV must come from another source, such as ERA5, GNSS/GPS PWV, radiosondes, or another validated atmospheric product.

---

## Cleaning principles for the GHCNh clean core

The GHCNh clean-core workflow is conservative:

1. Values marked with suspect QC are not retained.
2. Values marked with strong error QC are not retained.
3. Physically unreasonable values are removed.
4. Dew point cannot exceed air temperature by more than 0.5 °C.
5. Precipitation is handled with source-specific rules.
6. Source 382 / QC `A` precipitation is excluded because it represents accumulation over more than one hour.
7. General coverage tables are generated without usability thresholds.

The purpose is not to maximize data count. The purpose is to build a defensible observational core.

Detailed documentation:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

---

## Final GHCNh clean ranges after strict QC

| Variable | Final clean range |
|---|---:|
| `temperature_c` | 14.0-40.0 °C |
| `dew_point_temperature_c` | 2.0-31.0 °C |
| `relative_humidity_pct` | 11-100 % |
| `wind_speed_m_s` | 0.0-31.4 m/s |
| `station_level_pressure_hpa` | 902.0-1024.4 hPa |
| `precipitation_mm` | 0.0-101.9 mm |

Final consistency checks:

```text
T < 4 C: 0
T > 41 C: 0
Wind > 50 m/s: 0
Precip > 150 mm: 0
RH < 1: 0
RH > 100: 0
Td > T + 0.5 C: 0
```

---

## No-threshold GHCNh coverage summary

Coverage is currently reported without usability thresholds.

Full station-year grid:

```text
39 stations × 20 years = 780 station-years
```

Current clean coverage summary:

| Variable | Station-years with any data | Stations with any data | Total valid hours | Fraction of all possible station-hours |
|---|---:|---:|---:|---:|
| `precipitation_mm` | 384 | 25 | 2,096,607 | 0.306634 |
| `temperature_c` | 238 | 17 | 1,495,071 | 0.218658 |
| `wind_speed_m_s` | 216 | 17 | 1,340,993 | 0.196124 |
| `dew_point_temperature_c` | 127 | 9 | 693,016 | 0.101355 |
| `relative_humidity_pct` | 127 | 9 | 692,829 | 0.101328 |
| `station_level_pressure_hpa` | 66 | 5 | 362,616 | 0.053034 |

Thresholds such as 25%, 50%, or 80% coverage may be evaluated later, but they are not used to define the base coverage tables.

---

## Main scripts for the current workflows

Build the GHCNh strict clean core:

```bash
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Build GHCNh no-threshold coverage tables:

```bash
python scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

Acquire and audit USGS NWIS station/parameter inventory and precipitation UV raw data:

```bash
python scripts/download_usgs_nwis_pr.py
```

The USGS NWIS script includes discovery, precipitation UV probing, raw download, JSON fallback, and `retry-errors` recovery for failed raw chunks.

---

## Repository structure

```text
pr_ngvla/
├── scripts/
│   ├── build_ghcnh_hourly_clean_core_pr.py
│   ├── build_ghcnh_hourly_clean_core_coverage_tables_pr.py
│   └── download_usgs_nwis_pr.py
├── docs/
│   ├── GHCNH_HOURLY_CLEAN_CORE.md
│   ├── OBSERVATIONAL_DATA_DOWNLOADS.md
│   ├── DATA_SOURCES.md
│   ├── REPRODUCING.md
│   ├── DECISIONS.md
│   └── archive/
├── data_raw/        # local raw data, not tracked
├── data_interim/    # local intermediate products, not tracked
├── outputs/         # local generated products, not tracked
├── logs/            # local run logs, not tracked unless explicitly selected
├── src/
├── tests/
├── environment.yml
├── pyproject.toml
└── README.md
```

---

## Server workflow

Recommended project root on `astroiupi`:

```text
/export/ngvla/cpollack/pr_ngvla
```

Activate the project environment for interactive work:

```bash
conda activate pr_ngvla
```

For long jobs on the current server, prefer `systemd-run --user` with explicit logs under the repository. Do **not** rely on `tmux` for long-running jobs in this environment.

Use the project conda environment explicitly when launching detached jobs:

```text
/export/ngvla/cpollack/miniconda3/envs/pr_ngvla/bin/python
```

Example pattern:

```bash
cd /export/ngvla/cpollack/pr_ngvla && \
mkdir -p logs/<source>/<workflow> && \
systemd-run --user \
  --unit=<unit-name> \
  --collect \
  --same-dir \
  bash -lc '<absolute-python-path> <script> <arguments> >> <log-file> 2>&1'
```

For each long-running acquisition or processing job, document:

- exact command used;
- log path;
- input manifest or source inventory;
- output manifest or data path;
- completion status and exit code;
- verification counts.

---

## Documentation map

| Document | Purpose |
|---|---|
| `docs/GHCNH_HOURLY_CLEAN_CORE.md` | Technical reference for the GHCNh clean-core workflow |
| `docs/OBSERVATIONAL_DATA_DOWNLOADS.md` | Raw observational data acquisition workflows, commands, paths, logs, and verification summaries |
| `docs/DATA_SOURCES.md` | Data source descriptions and local organization |
| `docs/REPRODUCING.md` | Step-by-step workflow reproduction |
| `docs/DECISIONS.md` | Methodological decisions and rationale |
| `docs/archive/` | Historical documentation from earlier workflow stages |

Some older documents may describe previous ERA5/ISD workflows. The current methodological references for this branch are:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
docs/OBSERVATIONAL_DATA_DOWNLOADS.md
```

---

## Next methodological stage

The next stage should not jump directly from raw acquisition to scientific comparison.

Recommended order:

1. Finish raw acquisition and documentation for selected observational sources.
2. Review source-specific units, timestamps, flags, accumulation intervals, and station metadata.
3. Build clean/interim observational tables only after source-specific QA.
4. Document each clean/interim workflow before using it for scientific outputs.
5. Compare observations with ERA5, ERA5-Land, ERA5 Single Levels, GPM IMERG, or other gridded products only after the observational sources are traceable and interpretable.

The ERA5/reanalysis stage should only proceed after the observational station and raw-source limitations are transparent.
