# GHCNh hourly clean core workflow for Puerto Rico

**Project:** PR-ngVLA  
**Workflow stage:** NOAA GHCNh hourly observational network  
**Branch:** `feat/ghcnh-hourly-download`  
**Study period:** 2004-2023  
**Last updated:** April 2026  

---

## 1. Purpose

This document describes the current clean-core workflow for NOAA GHCNh hourly station data in Puerto Rico.

The purpose of this stage is to build a clean, physically meaningful, and well-documented hourly observational dataset before comparing station observations with gridded reanalysis products such as ERA5.

This stage does **not** rank candidate sites and does **not** apply station usability thresholds. It organizes the clean station record so that coverage and limitations are visible before downstream analysis.

---

## 2. Main input data

The current observational dataset is:

**NOAA Global Historical Climatology Network hourly (GHCNh)**

GHCNh replaces the legacy Global Hourly / Integrated Surface Dataset (ISD) product. In this project, the downloaded raw station-year Parquet files are stored as:

```text
data_raw/noaa/ghcnh/hourly/by_year/<YYYY>/parquet/GHCNh_<station>_<YYYY>.parquet
```

The station inventory used for Puerto Rico is:

```text
data_interim/noaa/ghcnh_station_inventory/pr_ghcnh_station_inventory_master.parquet
```

---

## 3. Variables retained in the clean core

The clean core currently retains these variables:

| Clean column | GHCNh source variable | Unit |
|---|---|---|
| `temperature_c` | `temperature` | degrees Celsius |
| `dew_point_temperature_c` | `dew_point_temperature` | degrees Celsius |
| `relative_humidity_pct` | `relative_humidity` | percent |
| `wind_speed_m_s` | `wind_speed` | meters per second |
| `station_level_pressure_hpa` | `station_level_pressure` | hPa |
| `precipitation_mm` | `precipitation` | millimeters |

Precipitable water vapor (PWV) is **not** directly available from GHCNh. PWV must come from another source, such as ERA5, GNSS/GPS PWV, radiosondes, or another validated atmospheric product.

---

## 4. Metadata fields used for cleaning

Each GHCNh variable is accompanied by metadata fields:

```text
variable_Measurement_Code
variable_Quality_Code
variable_Report_Type
variable_Source_Code
variable_Source_Station_ID
```

These fields are essential. The clean core should not be interpreted using only the numeric value column.

---

## 5. Cleaning philosophy

The current rule is conservative:

> If a value is physically unreasonable, marked with suspect/error quality information, or methodologically ambiguous, it is excluded from the clean core.

The purpose is not to maximize data count. The purpose is to create a defensible observational core for later comparison against reanalysis products.

---

## 6. Main QC decisions

### 6.1 No suspect QC retained

No variable keeps values marked as suspect QC.

Values marked as suspect or strong error quality codes are dropped and recorded in the decision summary.

### 6.2 Physical consistency check

If dew point temperature exceeds air temperature by more than 0.5 °C, then temperature, dew point, and relative humidity are removed for that record/hour.

### 6.3 Precipitation handling

Precipitation is the most delicate variable.

GHCNh `precipitation` is nominally an hourly total, but it can include intermediate reports and legacy accumulation behavior. Therefore, precipitation cannot be cleaned using value range alone.

For hourly aggregation, the clean core uses:

```text
last_valid_report_in_hour
```

This avoids summing sub-hourly running totals.

For `precipitation_Source_Code == 382`, the code `Quality_Code == A` means the value is **not** an hourly precipitation total. It is an accumulation over a period longer than one hour ending at that hour. These values are excluded from `precipitation_mm`.

Legacy non-hourly reports such as `4-DSI-3240` are also excluded from the hourly clean precipitation variable.

---

## 7. Physical cleaning ranges

Current physical cleaning ranges are:

| Variable | Minimum | Maximum | Unit |
|---|---:|---:|---|
| `temperature` | 4.0 | 41.0 | °C |
| `dew_point_temperature` | -20.0 | 35.0 | °C |
| `relative_humidity` | 1.0 | 100.0 | % |
| `wind_speed` | 0.0 | 50.0 | m/s |
| `station_level_pressure` | 850.0 | 1050.0 | hPa |
| `precipitation` | 0.0 | 500.0 | mm |

These are cleaning ranges, not ngVLA operational thresholds.

---

## 8. Final clean ranges after strict QC

After the strict clean-core run, the retained values had these ranges:

| Clean variable | Final clean range |
|---|---:|
| `temperature_c` | 14.0-40.0 °C |
| `dew_point_temperature_c` | 2.0-31.0 °C |
| `relative_humidity_pct` | 11-100 % |
| `wind_speed_m_s` | 0.0-31.4 m/s |
| `station_level_pressure_hpa` | 902.0-1024.4 hPa |
| `precipitation_mm` | 0.0-101.9 mm |

The final consistency checks returned:

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

## 9. Main scripts

### 9.1 Clean core builder

```bash
python scripts/build_ghcnh_hourly_clean_core_pr.py
```

Main output:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

### 9.2 No-threshold coverage table builder

```bash
python scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

Main output directory:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

---

## 10. No-threshold coverage tables

Coverage tables are intentionally generated without usability thresholds.

The purpose is to show factual coverage before deciding which stations or years are analytically usable.

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

---

## 11. Current status

This workflow stage is frozen as:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

The next major methodological stage is comparison against ERA5/reanalysis products, after the clean-core workflow is fully documented and reproducible.
