# Methodological decisions for PR-ngVLA

**Project:** PR-ngVLA
**Current workflow stage:** GHCNh hourly clean core
**Study period:** 2004-2023
**Last updated:** April 2026

---

## 1. Purpose

This document records methodological decisions that are currently frozen or should be treated as active guidance for the PR-ngVLA workflow.

The current active workflow stage is:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

The current technical reference is:

```text
docs/GHCNH_HOURLY_CLEAN_CORE.md
```

The current reproducing guide is:

```text
docs/REPRODUCING.md
```

---

## 2. Current primary observational dataset

### Decision

NOAA GHCNh hourly is the current primary observational station dataset for Puerto Rico.

### Rationale

GHCNh replaces the legacy Global Hourly / Integrated Surface Dataset product and provides hourly station-year files with variable-specific metadata fields.

The project needs a clean, physically meaningful observational station record before comparing with ERA5 or any other reanalysis product.

### Consequence

Older NOAA ISD-specific workflows are historical context only unless explicitly reintroduced.

---

## 3. Study period

### Decision

The current clean-core workflow uses:

```text
2004-2023
```

### Rationale

This provides a 20-year hourly observational period while keeping the workflow computationally manageable and consistent with the current project stage.

### Consequence

All coverage summaries and clean-core outputs should clearly state that they refer to 2004-2023.

---

## 4. Do not advance with physically inconsistent data

### Decision

If the data do not make physical or methodological sense, the workflow stops and the data problem is investigated before proceeding.

### Rationale

Carrying an error into downstream analysis is worse than moving slowly. The project should not advance merely to “get results.”

### Consequence

Suspicious values must be checked against physical plausibility, GHCNh metadata, and source-specific documentation before they are used.

---

## 5. Avoid unnecessary workflow fragmentation

### Decision

Do not create a new script for every small review or correction.

### Rationale

Too many narrowly scoped scripts make the workflow difficult to trace, reproduce, and explain.

### Consequence

If the needed change is a correction to an existing central stage, update the central script rather than creating a parallel script.

Creating a new script is appropriate only when it represents a reproducible workflow stage, such as:

```text
build_ghcnh_hourly_clean_core_pr.py
build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

---

## 6. GHCNh clean core is conservative

### Decision

The clean core prioritizes defensibility over maximizing retained data volume.

### Rationale

The cleaned observational dataset will be used as a reference for later comparison with reanalysis products. It must be physically meaningful and explainable.

### Consequence

Values are excluded when they are physically unreasonable, marked with suspect/error quality information, or methodologically ambiguous.

---

## 7. No suspect QC retained

### Decision

No variable keeps values marked as suspect QC.

This applies to:

```text
temperature
dew_point_temperature
relative_humidity
wind_speed
station_level_pressure
precipitation
```

### Rationale

Previous diagnostics showed that some suspect-QC values were physically implausible or inconsistent with Puerto Rico climatology.

### Consequence

Suspect-QC values are recorded in the decision summary as dropped, not retained in the final clean variable columns.

---

## 8. Strong QC errors are dropped

### Decision

Values marked with strong quality-code errors are excluded from the clean core.

### Rationale

The GHCNh metadata fields are essential for interpreting whether an observation is usable.

### Consequence

Numeric plausibility alone is not enough. A value can be physically plausible but still excluded if its QC metadata indicates a strong error.

---

## 9. Metadata fields are mandatory for interpretation

### Decision

GHCNh numeric values must be interpreted together with their metadata fields:

```text
variable_Measurement_Code
variable_Quality_Code
variable_Report_Type
variable_Source_Code
variable_Source_Station_ID
```

### Rationale

The same numeric value can mean different things depending on source, measurement code, report type, and quality code.

### Consequence

The clean-core workflow should not use numeric ranges alone to decide whether a value is valid.

---

## 10. Temperature range for Puerto Rico

### Decision

The clean-core physical cleaning range for air temperature is:

```text
4.0 <= temperature <= 41.0 °C
```

### Rationale

Values near 0 °C are not reasonable for Puerto Rico in this context and should not be treated as acceptable clean observations.

### Consequence

Values below 4 °C are excluded from the clean core. After strict QC, the retained clean temperature range is:

```text
14.0-40.0 °C
```

---

## 11. Temperature and dew point scaling

### Decision

For temperature-like variables, division by 10 is allowed only when the raw value appears clearly encoded in tenths:

```text
abs(raw) >= 100
```

### Rationale

Some raw values such as 227 or 340 plausibly represent 22.7 °C or 34.0 °C. However, values like 42.2 °C should not be divided by 10 into 4.22 °C.

### Consequence

The workflow avoids incorrectly converting suspicious but nearby values into apparently valid low temperatures.

---

## 12. Dew point cannot exceed air temperature

### Decision

If dew point temperature exceeds air temperature by more than 0.5 °C, temperature, dew point, and relative humidity are removed for that record/hour.

### Rationale

Dew point greater than air temperature is physically inconsistent except for very small measurement or rounding differences.

NOAA hourly normals methodology also treats dew point greater than temperature as invalid before computing normals.

### Consequence

The final clean core must satisfy:

```text
Td > T + 0.5 C: 0
```

---

## 13. Relative humidity limits

### Decision

Relative humidity must remain within:

```text
1 <= relative_humidity <= 100 %
```

### Rationale

Relative humidity outside this interval is physically invalid for this workflow.

### Consequence

Values such as extremely large RH artifacts are excluded from the clean core.

The final clean core must satisfy:

```text
RH < 1: 0
RH > 100: 0
```

---

## 14. Wind speed range

### Decision

The clean-core physical cleaning range for wind speed is:

```text
0.0 <= wind_speed <= 50.0 m/s
```

### Rationale

A retained value of 60.7 m/s was found in `wind_speed` rather than `wind_gust`. Although it passed source QC, it was not appropriate to keep as a clean hourly representative wind-speed value for this project.

### Consequence

The 60.7 m/s value is excluded as out of range. The final clean wind-speed maximum is:

```text
31.4 m/s
```

The final clean core must satisfy:

```text
Wind > 50 m/s: 0
```

---

## 15. Station-level pressure handling

### Decision

Station-level pressure is retained within a broad physical range:

```text
850.0 <= station_level_pressure <= 1050.0 hPa
```

### Rationale

Station pressure depends on station elevation and should not be treated the same as sea-level pressure.

### Consequence

A limited multiply-by-10 correction is allowed only when the raw value is implausible but the corrected value is physically plausible.

Example:

```text
101.4 hPa -> 1014.0 hPa
```

---

## 16. Precipitation is source-specific

### Decision

Precipitation cannot be cleaned using numeric range alone.

### Rationale

GHCNh precipitation is nominally hourly but can include sub-hourly reports, running totals, high-resolution HPD data, and legacy multi-hour accumulations.

### Consequence

Precipitation cleaning must use:

```text
precipitation_Measurement_Code
precipitation_Quality_Code
precipitation_Report_Type
precipitation_Source_Code
```

---

## 17. Do not sum sub-hourly precipitation blindly

### Decision

Hourly precipitation aggregation uses:

```text
last_valid_report_in_hour
```

not a sum of all reports within the hour.

### Rationale

For METAR/AWOS/ASOS-style reports, multiple observations within one hour can represent running totals. Summing them can double-count precipitation.

### Consequence

The clean hourly precipitation value uses the last valid report in the hour after QC filtering.

---

## 18. Source 382 / QC A precipitation is excluded

### Decision

For `precipitation_Source_Code == 382`, values with:

```text
precipitation_Quality_Code == A
```

are excluded from `precipitation_mm`.

### Rationale

For Source 382, QC `A` means the value is not an hourly precipitation total. It is an accumulation over a period greater than one hour ending at that hour.

### Consequence

Large multi-hour accumulations from legacy records are not interpreted as hourly precipitation.

---

## 19. Legacy non-hourly precipitation reports are excluded

### Decision

Legacy non-hourly precipitation reports such as:

```text
4-DSI-3240
```

are excluded from the hourly clean precipitation variable.

### Rationale

Diagnostics showed that many extreme values with this report type were multi-hour or monthly-style accumulations, not hourly precipitation totals.

### Consequence

These records are dropped as:

```text
dropped_non_hourly_precipitation_report
```

---

## 20. HPD high-resolution precipitation can be retained

### Decision

Source 382 reports of type:

```text
H-derived-HPD-C-high-res
```

with blank or missing QC may be retained if no other rule fails.

### Rationale

After filtering Source 382 QC `A` and legacy non-hourly reports, remaining high-resolution HPD values with blank QC are interpreted as retained hourly precipitation values.

### Consequence

The final retained clean precipitation range is:

```text
0.0-101.9 mm
```

Values around 100 mm are treated as extreme retained hourly values after QC, not typical conditions.

---

## 21. No usability thresholds in general coverage tables

### Decision

General coverage tables are generated without station usability thresholds.

### Rationale

Thresholds such as 25%, 50%, or 80% coverage are analytical choices and may be considered arbitrary. The first deliverable should show factual coverage.

### Consequence

The base coverage products report actual valid-hour counts and fractions without classifying stations as usable or unusable.

Threshold diagnostics may be computed later if requested, but they do not define the base tables.

---

## 22. Full station-year grid

### Decision

Coverage tables use the full station-year grid:

```text
39 stations × 20 years = 780 station-years
```

### Rationale

Using the full grid makes missing data explicit instead of hiding station-years with zero valid data.

### Consequence

Every variable summary should be interpreted against 780 possible station-years.

---

## 23. Current no-threshold coverage summary

### Decision

The following no-threshold coverage summary is the current reference for the clean GHCNh stage:

| Variable | Station-years with any data | Stations with any data | Total valid hours | Fraction of all possible station-hours |
|---|---:|---:|---:|---:|
| `precipitation_mm` | 384 | 25 | 2,096,607 | 0.306634 |
| `temperature_c` | 238 | 17 | 1,495,071 | 0.218658 |
| `wind_speed_m_s` | 216 | 17 | 1,340,993 | 0.196124 |
| `dew_point_temperature_c` | 127 | 9 | 693,016 | 0.101355 |
| `relative_humidity_pct` | 127 | 9 | 692,829 | 0.101328 |
| `station_level_pressure_hpa` | 66 | 5 | 362,616 | 0.053034 |

### Consequence

The station network is not uniform across variables. ERA5 comparison must account for variable-specific station coverage.

---

## 24. PWV is not in GHCNh

### Decision

PWV is not included in the GHCNh clean core.

### Rationale

GHCNh does not directly provide precipitable water vapor.

### Consequence

PWV must come from another source, such as ERA5, GNSS/GPS PWV, radiosonde data, or another validated atmospheric product.

---

## 25. ERA5 is the next stage, not the current primary dataset

### Decision

ERA5 and/or ERA5-Land are planned for the next major methodological stage.

### Rationale

ERA5 can provide gridded spatial continuity and variables not available directly from GHCNh, especially PWV.

### Consequence

ERA5 comparison should begin only after the GHCNh clean-core workflow is documented, reproducible, and its coverage limitations are transparent.

---

## 26. Geospatial auxiliary datasets

### Decision

Geospatial datasets such as SRTM DEM, GSHHG coastlines, and TIGER/Line municipality boundaries are auxiliary mapping layers.

### Rationale

These datasets support cartography and spatial interpretation but do not define meteorological observations.

### Consequence

They should be documented as auxiliary data sources, not as part of the GHCNh clean core.

---

## 27. Older prototype scripts are not the active workflow

### Decision

Older ERA5, ERA5-Land, ISD, PRISM, phase-based, and site-index scripts are not the active workflow for this branch unless explicitly reintroduced.

### Rationale

The project methodology changed to first understand and clean the hourly station data before advancing to reanalysis comparison.

### Consequence

Do not treat older outputs as current validated results.

---

## 28. Current frozen endpoint

### Decision

The current frozen endpoint is:

```text
GHCNh hourly clean core + no-threshold coverage tables
```

### Main scripts

```text
scripts/build_ghcnh_hourly_clean_core_pr.py
scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

### Main documentation

```text
README.md
docs/GHCNH_HOURLY_CLEAN_CORE.md
docs/DATA_SOURCES.md
docs/REPRODUCING.md
docs/DECISIONS.md
```

### Next step

After documentation is complete, proceed to ERA5/reanalysis comparison using the clean GHCNh data as the observational reference.
