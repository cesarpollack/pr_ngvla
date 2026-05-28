
# ERA5 / ERA5-Land Local Data Inventory for PR-ngVLA

**Project:** Characterization of the Weather Conditions for the Next Generation Very Large Array in Puerto Rico  
**Working analysis period:** **2004–2023**  
**Status:** Documentation update after review of the local ERA5-family download scripts and the April 2026 PRISM/JTM poster.  
**Repository path:** `docs/ERA5_LOCAL_DATA_INVENTORY_2004_2023.md`

---

## 1. Purpose of this document

This document records the ERA5-family gridded datasets that have been downloaded and used in the PR-ngVLA workflow.

It is intended to answer the local-data questions:

- What ERA5-family products are stored locally?
- Which scripts downloaded them?
- Which variables were requested?
- What period and geographic bounding box were used?
- Where are the files stored?
- What role did each product play in the analysis?

This document does **not** identify the individual observations assimilated into ERA5. That is a separate methodological task requiring ERA5 Observation Feedback, ODB/MARS records, ECMWF observation monitoring, or equivalent official documentation.

---

## 2. Correct analysis period

The correct project analysis period is:

```text
2004–2023
```

This is the period used by the local ERA5-family download scripts and the PR-ngVLA poster workflow. Earlier references to a 2003–2024 investigation period should be corrected for the current project documentation unless a future extension is explicitly defined.

The local workflow should therefore be described as a **20-year analysis covering 2004–2023**.

---

## 3. Study domain used in the download scripts

All reviewed ERA5-family download scripts use the same Puerto Rico regional bounding box:

```python
AREA_PR = [18.6, -68.0, 17.8, -65.0]  # [North, West, South, East]
```

This region covers Puerto Rico and nearby islands included in the workflow.

---

## 4. Methodological separation

The following distinction must be preserved in all documentation:

```text
ERA5-family local NetCDF files
    = gridded reanalysis products downloaded from CDS.

ERA5 assimilated observations
    = individual observations that entered, were screened by, or were rejected/passively used by
      the ERA5 data assimilation system.
```

The local NetCDF files used for maps, climatologies, exceedance statistics, and site-selection indices do **not** contain the individual observations assimilated into ERA5.

Therefore, the local inventory documented here is necessary for reproducibility, but it is not sufficient to answer which specific observations were assimilated in the Puerto Rico / Caribbean region.

---

## 5. Local ERA5-family dataset inventory

| Local product | Download script | CDS dataset | Product type | Variables requested | Period | Frequency | Area | Output path | File pattern | Role in workflow |
|---|---|---|---|---|---|---|---|---|---|---|
| ERA5-Land hourly, Group A | `scripts/download_era5land_hourly_pr.py` | `reanalysis-era5-land` | ERA5-Land hourly | `2m_temperature`, `2m_dewpoint_temperature` | 2004–2023 | hourly | `[18.6, -68.0, 17.8, -65.0]` | `data_raw/era5/hourly/` | `era5land_hourly_t2m_d2m_PR_YYYY_MM.nc` | Main higher-resolution land product for near-surface temperature and dew point |
| ERA5-Land hourly, Group B | `scripts/download_era5land_hourly_pr.py` | `reanalysis-era5-land` | ERA5-Land hourly | `10m_u_component_of_wind`, `10m_v_component_of_wind`, `total_precipitation`, `surface_pressure` | 2004–2023 | hourly | `[18.6, -68.0, 17.8, -65.0]` | `data_raw/era5/hourly/` | `era5land_hourly_wind_tp_sp_PR_YYYY_MM.nc` | Main higher-resolution land product for wind, precipitation, and pressure |
| ERA5-Land monthly means, Group A | `scripts/download_era5land_monthly_pr.py` | `reanalysis-era5-land-monthly-means` | `monthly_averaged_reanalysis` | `2m_temperature`, `2m_dewpoint_temperature` | 2004–2023 | monthly | `[18.6, -68.0, 17.8, -65.0]` | `data_raw/era5/monthly/` | `era5land_monthly_t2m_d2m_PR_2004_2023.nc` | Monthly climatology workflow |
| ERA5-Land monthly means, Group B | `scripts/download_era5land_monthly_pr.py` | `reanalysis-era5-land-monthly-means` | `monthly_averaged_reanalysis` | `10m_u_component_of_wind`, `10m_v_component_of_wind`, `total_precipitation`, `surface_pressure` | 2004–2023 | monthly | `[18.6, -68.0, 17.8, -65.0]` | `data_raw/era5/monthly/` | `era5land_monthly_wind_tp_sp_PR_2004_2023.nc` | Monthly climatology workflow |
| ERA5 single levels TCWV/PWV | `scripts/download_era5_pwv_pr.py` | `reanalysis-era5-single-levels` | `reanalysis` | `total_column_water_vapour` | 2004–2023 | hourly | `[18.6, -68.0, 17.8, -65.0]` | `data_raw/era5/pwv/` | `era5_hourly_tcwv_PR_YYYY.nc` | PWV / total-column water-vapour analysis |
| ERA5 single levels auxiliary, Group A | `scripts/download_era5_singlelev_pr.py` | `reanalysis-era5-single-levels` | `reanalysis` | `2m_temperature`, `2m_dewpoint_temperature` | 2004–2023 | hourly | `[18.6, -68.0, 17.8, -65.0]`; grid `[0.25, 0.25]` | `data_raw/era5/singlelev/` | `era5sl_hourly_t2m_d2m_PR_YYYY_MM.nc` | Auxiliary coarser-grid atmospheric product for coastal/small-island support |
| ERA5 single levels auxiliary, Group B | `scripts/download_era5_singlelev_pr.py` | `reanalysis-era5-single-levels` | `reanalysis` | `10m_u_component_of_wind`, `10m_v_component_of_wind`, `total_precipitation`, `surface_pressure` | 2004–2023 | hourly | `[18.6, -68.0, 17.8, -65.0]`; grid `[0.25, 0.25]` | `data_raw/era5/singlelev/` | `era5sl_hourly_wind_tp_sp_PR_YYYY_MM.nc` | Auxiliary coarser-grid atmospheric product for coastal/small-island support |

---

## 6. Expected local file counts from the download scripts

### ERA5-Land hourly

The hourly ERA5-Land script downloads one file per month and variable group:

```text
20 years × 12 months × 2 groups = 480 files
```

Expected patterns:

```text
data_raw/era5/hourly/era5land_hourly_t2m_d2m_PR_YYYY_MM.nc
data_raw/era5/hourly/era5land_hourly_wind_tp_sp_PR_YYYY_MM.nc
```

### ERA5-Land monthly means

The monthly ERA5-Land script downloads one file per variable group:

```text
data_raw/era5/monthly/era5land_monthly_t2m_d2m_PR_2004_2023.nc
data_raw/era5/monthly/era5land_monthly_wind_tp_sp_PR_2004_2023.nc
```

### ERA5 single levels TCWV/PWV

The TCWV/PWV script downloads one file per year:

```text
20 years × 1 variable group = 20 files
```

Expected pattern:

```text
data_raw/era5/pwv/era5_hourly_tcwv_PR_YYYY.nc
```

### ERA5 single levels auxiliary

The auxiliary ERA5 single-levels script is documented as one file per month and variable group:

```text
20 years × 12 months × 2 groups = 480 files
```

However, later workflow outputs show that the wind/precipitation/pressure group may be split into instantaneous and accumulated files in the processed/local file tree:

```text
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_instant.nc
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_accum.nc
```

This difference should be checked before making final claims about the exact number of local ERA5-SL files.

---

## 7. Variable mapping and derived quantities

| Analysis variable | Source variable(s) | Product | Local handling |
|---|---|---|---|
| Air temperature | `2m_temperature` / `t2m` | ERA5-Land hourly/monthly; ERA5-SL auxiliary | Convert from K to °C where needed |
| Dew point temperature | `2m_dewpoint_temperature` / `d2m` | ERA5-Land hourly/monthly; ERA5-SL auxiliary | Convert from K to °C where needed |
| Relative humidity | derived from `t2m` and `d2m` | ERA5-Land, ERA5-SL auxiliary | Computed using a Magnus-type formula |
| Wind speed | `10m_u_component_of_wind`, `10m_v_component_of_wind` / `u10`, `v10` | ERA5-Land, ERA5-SL auxiliary | `sqrt(u10^2 + v10^2)` |
| Precipitation | `total_precipitation` / `tp` | ERA5-Land, ERA5-SL auxiliary | Requires careful treatment of accumulation conventions and unit conversion |
| Surface pressure | `surface_pressure` / `sp` | ERA5-Land, ERA5-SL auxiliary | Stored in Pa; convert to hPa where needed |
| PWV / TCWV | `total_column_water_vapour` / `tcwv` | ERA5 single levels | `kg m^-2` is numerically equivalent to mm of precipitable water depth |

---

## 8. Relationship to the April 2026 poster

The April 2026 PRISM/JTM poster used the same core 20-year period:

```text
2004–2023
```

The poster presented the following high-level workflow:

- ERA5-Land hourly data as the primary atmospheric dataset.
- ERA5 single levels for PWV and coastal gap-fill support.
- NOAA ISD hourly observations for validation of relative humidity and wind speed.
- Hurricane María months excluded from exceedance counts, not imputed.
- Monthly climatology, hourly exceedance analysis, station validation, and a fuzzy-logic site-selection index.

This document updates the poster-stage methodology by making the local-data inventory explicit and by qualifying statements that should remain provisional.

---

## 9. Documentation status and remaining methodological notes

### 9.1 Period correction

Use:

```text
2004–2023
```

Do not use:

```text
2003–2024
```

unless a new extension of the analysis period is explicitly defined and corresponding data are downloaded and verified.

---

### 9.2 ERA5-Land vs ERA5 single levels

Status: the download-script comments were updated to avoid overstating the role of ERA5 single levels. Current recommended wording:

```text
ERA5-Land is the primary higher-resolution land-surface product used for near-surface
temperature, dew point, derived relative humidity, 10 m wind, precipitation, and surface pressure
over resolved land pixels.

ERA5 single levels are used for total-column water vapour / PWV and as an auxiliary coarser-grid
product for coastal and small-island support where ERA5-Land masking or land-sea representation
limits interpretation.
```

Avoid overly strong wording such as:

```text
ERA5 single levels is the only ERA5 product that provides atmospheric data for these islands.
```

A safer formulation is:

```text
ERA5 single levels was downloaded as a coarser-resolution auxiliary product because it provides
values over ocean and mixed land–sea grid cells, including coastal and small-island areas that
may be unresolved or masked in ERA5-Land.
```

---

### 9.3 PWV/TCWV wording

Status: the unverified numerical PWV validation-error claim was removed from the download-script comments. Current recommended wording:

```text
ERA5-Land does not provide PWV/TCWV. Therefore, total column water vapour was downloaded
from ERA5 single levels using the CDS variable `total_column_water_vapour`. TCWV has units
of kg m^-2, which is numerically equivalent to millimetres of precipitable water depth.
```

Do not state a specific numerical PWV validation-error value unless the exact supporting reference and context are checked and cited.

---

### 9.4 Coastal gap-fill wording

The current documentation should not claim that the coastal gap-fill solved the coastal-coverage problem.

Recommended wording:

```text
An ERA5 single-levels coastal-support workflow was implemented as a diagnostic step to explore
whether coarser ERA5 single-level fields could reduce unresolved coastal/small-island gaps in the
ERA5-Land-based products. The poster-stage maps should be interpreted as diagnostic products.
The coastal treatment remains provisional and requires re-evaluation before final regional ranking
or site recommendation.
```

Avoid:

```text
Phase 3 successfully gap-filled the coastal pixels.
```

unless this is re-verified quantitatively after the gap-fill workflow is reviewed.

---

### 9.5 Monthly means and validation / bias correction wording

Status: the monthly ERA5-Land download-script comments were updated so that station comparison and seasonal diagnostics are described as possible or future uses, not as completed project results.

Current recommended wording:

```text
ERA5-Land monthly means were downloaded to support monthly climatology products and possible
future monthly-scale comparison or seasonal diagnostics. Only analyses that have been completed
and verified should be described as project results.
```

---

## 10. Current methodological limitation

The project currently uses gridded ERA5-family products to provide spatially and temporally continuous atmospheric fields over Puerto Rico.

This is scientifically useful because station data alone do not provide complete spatial coverage across the island, especially in interior, mountainous, and south-coastal regions.

However:

```text
ERA5/ERA5-Land values are not direct station observations.
They are gridded reanalysis fields produced from a data assimilation and model system.
They must be interpreted as physically consistent gridded estimates, not as direct measurements.
```

Therefore, station and observational datasets should be used for validation, plausibility checks, and uncertainty assessment, but the gridded fields provide the spatial continuity needed for site-selection mapping.

---

## 11. Separate next-stage task: ERA5 observing-system inputs

The next methodological stage should address a different question:

```text
Which observations or observation classes were available to, screened by, or actively used by
the ERA5 assimilation system over the Puerto Rico / Caribbean region during 2004–2023?
```

This should not be confused with the local ERA5 NetCDF inventory.

A future observing-system inventory should attempt to document, where accessible:

- observation class or platform,
- observation variable or satellite channel,
- time,
- latitude and longitude,
- station/platform/satellite identifier,
- first-guess departure (`fg_depar`) where available,
- analysis departure (`an_depar`) where available,
- usage/status flag where available,
- quality-control or rejection information where available.

Possible official sources include:

- ECMWF Observation Feedback Archive,
- ODB/MARS observation feedback records,
- ECMWF observation monitoring,
- ERA5 technical documentation,
- CDS/ECMWF product documentation.

---

## 12. Recommended short paragraph for the methodology section

```text
The PR-ngVLA analysis uses a 20-year period from 2004 to 2023. ERA5-Land was used as the
primary higher-resolution land-surface reanalysis product for near-surface temperature, dew point,
derived relative humidity, 10 m wind, precipitation, and surface pressure over Puerto Rico. ERA5
single levels were used for total column water vapour, interpreted as precipitable water vapour, and
as a coarser-resolution auxiliary product for coastal and small-island support. The local NetCDF
files are gridded reanalysis products downloaded from the Copernicus Climate Data Store; they do
not contain the individual observations assimilated into ERA5. The identification of ERA5
observing-system inputs for Puerto Rico and the surrounding Caribbean region is treated as a
separate methodological task requiring official observation-feedback or ODB/MARS records.
```

---

## 13. References for documentation

- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146, 1999–2049.
- Muñoz-Sabater, J. et al. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. *Earth System Science Data*, 13, 4349–4383.
- ECMWF / Copernicus Climate Data Store documentation for `reanalysis-era5-land`.
- ECMWF / Copernicus Climate Data Store documentation for `reanalysis-era5-land-monthly-means`.
- ECMWF / Copernicus Climate Data Store documentation for `reanalysis-era5-single-levels`.
- PR-ngVLA April 2026 PRISM/JTM poster: *Characterization of the Weather Conditions for the Next Generation Very Large Array in Puerto Rico*.
