# Future work for PR-ngVLA

**Project:** PR-ngVLA
**Current workflow stage:** GHCNh hourly clean core
**Study period:** 2004-2023
**Last updated:** April 2026

---

## 1. Purpose

This document records the current roadmap for the PR-ngVLA workflow.

The current frozen endpoint is:

```text
GHCNh hourly clean core + no-threshold coverage tables
```

The next major methodological stage is ERA5/reanalysis comparison using the clean GHCNh station data as the observational reference.

Older future-work notes related to ERA5-first processing, NOAA ISD-only validation, PRISM prototypes, gap filling, or site-index maps should be treated as historical context unless explicitly reintroduced.

---

## 2. Current completed stage

The following stage is considered frozen:

```text
GHCNh hourly clean core: strict QC + no-threshold coverage tables
```

Main scripts:

```text
scripts/build_ghcnh_hourly_clean_core_pr.py
scripts/build_ghcnh_hourly_clean_core_coverage_tables_pr.py
```

Main documentation:

```text
README.md
docs/GHCNH_HOURLY_CLEAN_CORE.md
docs/DATA_SOURCES.md
docs/REPRODUCING.md
docs/DECISIONS.md
docs/ARCHITECTURE.md
docs/FUTURE_WORK.md
```

Main clean product:

```text
data_interim/noaa/ghcnh_hourly/clean_core/ghcnh_hourly_clean_core_2004_2023.parquet
```

Main coverage products:

```text
data_interim/noaa/ghcnh_hourly/clean_core/coverage_no_thresholds/
```

---

## 3. Immediate next step

The immediate next methodological step is:

```text
Design the ERA5/reanalysis comparison stage.
```

This should be done carefully and incrementally. The ERA5 stage should not overwrite or bypass the frozen GHCNh clean-core workflow.

The ERA5 stage should use the clean GHCNh station data as the observational reference.

---

## 4. ERA5/reanalysis comparison goals

The next stage should answer:

1. How well do ERA5 or ERA5-Land variables match the cleaned GHCNh station observations?
2. Which variables can be compared directly?
3. Which variables require derived quantities or additional assumptions?
4. How does station coverage vary by variable?
5. Which stations have enough clean data to support comparison?
6. How should coastal and mountainous Puerto Rico grid-cell issues be handled?
7. How should PWV be incorporated, given that PWV is not available directly from GHCNh?

---

## 5. ERA5 variables to evaluate

Potential ERA5 or ERA5-Land variables for comparison include:

| Target concept | Possible reanalysis variable | GHCNh comparison availability |
|---|---|---|
| Air temperature | 2 m temperature | Available as `temperature_c` |
| Dew point | 2 m dew point temperature | Available as `dew_point_temperature_c` |
| Relative humidity | Derived from temperature and dew point if needed | Available as `relative_humidity_pct` |
| Wind speed | 10 m wind components or wind speed | Available as `wind_speed_m_s` |
| Surface/station pressure | Surface pressure or pressure adjusted by elevation | Available as `station_level_pressure_hpa`, but limited |
| Precipitation | Total precipitation | Available as `precipitation_mm`, with source-specific cleaning |
| PWV | Total column water vapor / precipitable water vapor | Not available in GHCNh |

PWV requires special treatment because it cannot be validated directly against GHCNh unless another observational PWV source is added.

---

## 6. Important methodological constraints for ERA5

The ERA5 comparison stage must handle:

1. Time alignment between GHCNh hourly records and ERA5 timestamps.
2. Unit conversion.
3. Station-to-grid matching.
4. Coastal grid-cell representation.
5. Elevation differences between station elevation and model grid elevation.
6. Variable-specific station coverage.
7. Missing observational PWV in GHCNh.
8. Puerto Rico’s strong precipitation and terrain gradients.

ERA5 comparison should not assume that all GHCNh stations have all variables.

---

## 7. Station coverage should remain visible

The no-threshold coverage tables should remain the base reference.

Thresholds such as 25%, 50%, or 80% may be discussed later, but they should not replace the general no-threshold coverage tables unless the advisor explicitly requests a threshold-based classification.

Current full grid:

```text
39 stations × 20 years = 780 station-years
```

Current no-threshold clean coverage summary:

| Variable | Station-years with any data | Stations with any data | Total valid hours | Fraction of all possible station-hours |
|---|---:|---:|---:|---:|
| `precipitation_mm` | 384 | 25 | 2,096,607 | 0.306634 |
| `temperature_c` | 238 | 17 | 1,495,071 | 0.218658 |
| `wind_speed_m_s` | 216 | 17 | 1,340,993 | 0.196124 |
| `dew_point_temperature_c` | 127 | 9 | 693,016 | 0.101355 |
| `relative_humidity_pct` | 127 | 9 | 692,829 | 0.101328 |
| `station_level_pressure_hpa` | 66 | 5 | 362,616 | 0.053034 |

---

## 8. Possible ERA5 workflow design

A future ERA5 workflow should probably be organized as a new reproducible stage.

Possible stages:

```text
1. Build station-target table from GHCNh clean coverage.
2. Download or locate ERA5/ERA5-Land hourly data.
3. Extract nearest-grid or interpolated ERA5 values at station locations.
4. Align ERA5 and GHCNh by timestamp.
5. Compare variable-by-variable.
6. Generate summary statistics and diagnostic plots.
7. Document limitations before using ERA5 spatial fields for site characterization.
```

This should be implemented with as few scripts as practical, avoiding fragmentation.

---

## 9. Comparison metrics to consider

Possible comparison metrics:

1. Mean bias error.
2. Mean absolute error.
3. Root mean square error.
4. Correlation coefficient.
5. Seasonal or monthly summaries.
6. Hour-of-day summaries.
7. Event-based checks for precipitation and wind.
8. Station-by-station diagnostic plots.

These metrics should be chosen after confirming variable availability and time alignment.

---

## 10. Precipitation-specific future work

Precipitation requires special caution.

Future ERA5 precipitation comparison should account for:

1. GHCNh precipitation source codes.
2. Hourly versus accumulated precipitation definitions.
3. ERA5 accumulation conventions.
4. Local convective extremes in Puerto Rico.
5. Terrain and coastal effects.
6. The fact that high hourly values can be real but should be interpreted as extremes.

The current retained GHCNh hourly precipitation maximum is:

```text
101.9 mm
```

This should be described as an extreme retained hourly value after QC, not as a typical condition.

---

## 11. PWV future work

PWV is scientifically important for ngVLA high-frequency observing, but it is not directly available from GHCNh.

Future PWV options:

1. ERA5 total column water vapor.
2. GNSS/GPS PWV products if available.
3. Radiosonde-derived PWV.
4. Other validated atmospheric products.

PWV should not be inserted into the GHCNh clean core unless it comes from a clearly documented external source.

---

## 12. Mapping future work

Geospatial mapping should use documented auxiliary layers:

```text
SRTM 1-Arcsecond Global DEM
NOAA NCEI GSHHG coastline
U.S. Census Bureau TIGER/Line municipality boundaries
```

Future maps should clearly distinguish between:

1. Observational station data.
2. Reanalysis gridded data.
3. Auxiliary geospatial layers.
4. Derived suitability or ranking products.

Maps should not imply unsupported precision where station coverage is limited.

---

## 13. Site suitability future work

Site suitability or ranking should wait until after:

1. GHCNh clean-core coverage is documented.
2. ERA5/reanalysis comparison is complete.
3. PWV source and methodology are defined.
4. Variable thresholds are justified.
5. Weighting or MCDA assumptions are clearly documented.

The project should not return to final suitability maps until the observational and reanalysis foundations are stable.

---

## 14. Possible threshold work

Coverage thresholds may be considered later.

Examples:

```text
25% annual coverage
50% annual coverage
80% annual coverage
```

However, these thresholds are analytical choices. They should not replace the no-threshold coverage tables unless explicitly adopted.

If thresholds are used later, they should be documented as decisions in:

```text
docs/DECISIONS.md
```

---

## 15. Documentation future work

Future documentation updates should remain incremental.

When a new workflow stage is frozen, update:

```text
README.md
docs/DATA_SOURCES.md
docs/REPRODUCING.md
docs/DECISIONS.md
docs/ARCHITECTURE.md
docs/FUTURE_WORK.md
```

Historical documents should be moved to:

```text
docs/archive/
```

only when they are clearly no longer part of the active workflow.

---

## 16. Current next action

The next action after completing this documentation update is:

```text
Start designing the ERA5/reanalysis comparison workflow.
```

Before writing ERA5 code, define:

1. Which ERA5 product to use first.
2. Which variables to compare first.
3. Which stations/years to use for the first test.
4. Whether to begin with one year as a pilot.
5. How to store extracted station-grid comparison tables.
6. Which diagnostic statistics and plots are required.

---

## 17. Guiding principle

The guiding principle remains:

```text
Do not advance with data that do not make physical or methodological sense.
```

If the values do not make sense, stop and understand the data before continuing.
