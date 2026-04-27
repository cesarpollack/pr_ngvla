# PR-ngVLA — Atmospheric site characterization for ngVLA in Puerto Rico

**Project:** Puerto Rico atmospheric characterization for ngVLA Long Baseline Array context
**Current branch:** `feat/ghcnh-hourly-download`
**Current workflow stage:** GHCNh hourly clean core
**Study period:** 2004-2023
**Last updated:** April 2026

---

## Current status

This repository is currently focused on building a reliable observational foundation for Puerto Rico using NOAA GHCNh hourly station data.

The current frozen workflow stage is:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

This stage prepares clean hourly station observations before comparison against reanalysis products such as ERA5.

The project is **not** currently claiming final site rankings from this branch. The immediate goal is to ensure that station data are physically meaningful, methodologically defensible, reproducible, and clearly documented.

---

## Scientific motivation

Puerto Rico is included in the ngVLA design context as a Long Baseline Array location. High-frequency radio astronomy is sensitive to atmospheric conditions such as water vapor, precipitation, humidity, wind, and related surface meteorological variables.

Before comparing gridded reanalysis products to observations, the in-situ station record must be understood carefully:

- Which stations have data?
- Which years are available?
- Which variables are actually present after strict quality control?
- Which values are physically plausible for Puerto Rico?
- Which precipitation records are truly hourly and which are multi-hour accumulations?

This branch addresses those questions for NOAA GHCNh hourly data.

---

## Main observational dataset

The current observational dataset is:

**NOAA Global Historical Climatology Network hourly (GHCNh)**

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

Raw and intermediate data products are local workflow outputs and are not tracked in Git.

---

## Variables in the clean core

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

## Cleaning principles

The clean-core workflow is conservative:

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

## Final clean ranges after strict QC

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

## No-threshold coverage summary

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

## Main scripts for the current stage

Build the strict clean core:

```bash
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Build no-threshold coverage tables:

```bash
python scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

These scripts are the current reproducible workflow for the GHCNh observational stage.

---

## Repository structure

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
│   └── archive/
├── data_raw/        # local raw data, not tracked
├── data_interim/    # local intermediate products, not tracked
├── outputs/         # local generated products, not tracked
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

Activate the project environment:

```bash
conda activate pr_ngvla
```

For long jobs, use `tmux`.

Example:

```bash
tmux new -s ghcnh_clean_core
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Detach without killing the process:

```text
Ctrl-b then d
```

Reconnect:

```bash
tmux attach -t ghcnh_clean_core
```

---

## Documentation map

| Document | Purpose |
|---|---|
| `docs/GHCNH_HOURLY_CLEAN_CORE.md` | Current technical reference for the GHCNh clean-core workflow |
| `docs/DATA_SOURCES.md` | Data source descriptions and local organization |
| `docs/REPRODUCING.md` | Step-by-step workflow reproduction |
| `docs/DECISIONS.md` | Methodological decisions and rationale |
| `docs/archive/` | Historical documentation from earlier workflow stages |

Some older documents may describe previous ERA5/ISD workflows. The current methodological reference for this branch is:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

---

## Next methodological stage

After documenting the GHCNh clean-core workflow, the next major stage is comparison against ERA5/reanalysis products.

The ERA5 stage should only proceed after the observational station data are clean, reproducible, and their coverage limitations are transparent.
