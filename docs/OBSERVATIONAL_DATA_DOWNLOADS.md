# PR-ngVLA Observational Data Downloads

**Project:** PR-ngVLA — Characterization of Weather Conditions for ngVLA Site Selection in Puerto Rico
**Active branch:** `feat/ghcnh-hourly-download`
**Last confirmed commit:** `a13719d Document CUON as partial upper-air feedback route`
**Document purpose:** preserve traceability of observational-data downloads, especially when data are acquired manually with command-line tools such as `wget`.

---

## 1. Purpose

This document records how observational datasets are acquired for the PR-ngVLA project.

The current project stage focuses on acquiring and organizing **public observational datasets for Puerto Rico** that may be used to evaluate, compare, or contextualize ERA5-Land / ERA5.

The reference guide for selecting sources is the **initial observational-data matrix**. This document records the practical download steps, verification commands, local paths, limitations, and next actions.

---

## 2. General rules

- Do not commit raw data files to Git.
- Use `tmux` for downloads whenever possible, even for moderate-size files, because SSH sessions can disconnect.
- Record all official source URLs used for downloads.
- Record exact commands when downloads are done manually.
- Record local output paths.
- Verify station identifiers before processing.
- Verify counts or metadata before interpreting the data.
- Do not claim active ERA5 assimilation unless confirmed through ECMWF/OFA/MARS/ODB feedback or equivalent official evidence.
- Classify each dataset as:
  - `direct_validation`,
  - `partial_comparison`,
  - or `physical_context`.
- If values look physically suspicious, stop and review before continuing.

---

## 3. Recommended tmux pattern

Create a dedicated `tmux` session for each data source:

```bash
tmux new -s igra_sanjuan
```

Run the download commands inside the session.

Detach without killing the session:

```text
Ctrl+b
d
```

Reattach later:

```bash
tmux attach -t igra_sanjuan
```

For future sources, use descriptive session names, for example:

```bash
tmux new -s coops_pr
tmux new -s usgs_nwis_pr
```

If a session name contains an accidental space, avoid it. Prefer simple names such as:

```bash
tmux new -s ndbc_pr
tmux new -s coops_pr
tmux new -s usgs_nwis_pr
```

---

## 4. IGRA / San Juan radiosonde

### 4.1 Status

Downloaded and minimally verified.

### 4.2 Source

NOAA/NCEI Integrated Global Radiosonde Archive (IGRA).

Official source locations used:

```text
https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt
https://www.ncei.noaa.gov/pub/data/igra/igra2-readme.txt
https://www.ncei.noaa.gov/pub/data/igra/data/igra2-data-format.txt
https://www.ncei.noaa.gov/pub/data/igra/data/data-por/RQM00078526-data.txt.zip
```

### 4.3 Station

```text
RQM00078526
PR SAN JUAN/INT.; PUERTO RICO
Latitude: 18.4317
Longitude: -65.9919
Elevation: 4.0 m
Official record: 1946–2026
Number of soundings listed: 57291
```

### 4.4 Local paths

```text
data_raw/noaa/igra/raw/igra2-station-list.txt
data_raw/noaa/igra/raw/igra2-readme.txt
data_raw/noaa/igra/raw/igra2-data-format.txt
data_raw/noaa/igra/raw/RQM00078526-data.txt.zip
data_raw/noaa/igra/raw/RQM00078526-data.txt
```

### 4.5 Pre-download Git check

Commands:

```bash
git status --short
git branch --show-current
git log --oneline -n 5
```

Expected active branch:

```text
feat/ghcnh-hourly-download
```

Expected latest confirmed commit:

```text
a13719d Document CUON as partial upper-air feedback route
```

### 4.6 Download commands used

Recommended: run inside `tmux`.

```bash
tmux new -s igra_sanjuan
```

Inside the `tmux` session:

```bash
mkdir -p data_raw/noaa/igra/raw data_raw/noaa/igra/doc logs

cd data_raw/noaa/igra/raw

wget -c https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt
wget -c https://www.ncei.noaa.gov/pub/data/igra/igra2-readme.txt
wget -c https://www.ncei.noaa.gov/pub/data/igra/data/igra2-data-format.txt
wget -c https://www.ncei.noaa.gov/pub/data/igra/data/data-por/RQM00078526-data.txt.zip

cd -
```

### 4.7 Extraction command

```bash
unzip -n data_raw/noaa/igra/raw/RQM00078526-data.txt.zip -d data_raw/noaa/igra/raw
```

### 4.8 Verification commands

```bash
ls -lh data_raw/noaa/igra/raw

unzip -l data_raw/noaa/igra/raw/RQM00078526-data.txt.zip | head

grep "RQM00078526" data_raw/noaa/igra/raw/igra2-station-list.txt

ls -lh data_raw/noaa/igra/raw/RQM00078526-data.txt

head -n 20 data_raw/noaa/igra/raw/RQM00078526-data.txt

grep -c "^#RQM00078526" data_raw/noaa/igra/raw/RQM00078526-data.txt

git status --short
```

### 4.9 Verification results

Observed local files:

```text
total 100M
-rw-r--r-- 1 cpollack epscor  99M May 27 18:02 RQM00078526-data.txt.zip
-rw-r--r-- 1 cpollack epscor  14K Jun 10  2025 igra2-data-format.txt
-rw-r--r-- 1 cpollack epscor  14K Sep  4  2025 igra2-readme.txt
-rw-r--r-- 1 cpollack epscor 255K May 27 18:03 igra2-station-list.txt
```

Zip contents:

```text
Archive:  data_raw/noaa/igra/raw/RQM00078526-data.txt.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
315688950  2026-05-27 17:55   RQM00078526-data.txt
---------                     -------
315688950                     1 file
```

Station-list verification:

```text
RQM00078526  18.4317  -65.9919    4.0 PR SAN JUAN/INT.; PUERTO RICO     1946 2026  57291
```

Extracted file:

```text
-rw-r--r-- 1 cpollack epscor 302M May 27 17:55 data_raw/noaa/igra/raw/RQM00078526-data.txt
```

Sounding count:

```text
grep -c "^#RQM00078526" data_raw/noaa/igra/raw/RQM00078526-data.txt
57291
```

Git status after download:

```text
(no output)
```

Interpretation: raw IGRA files are not being tracked by Git, which is correct.

### 4.10 Methodological use

IGRA San Juan provides upper-air observations from radiosonde launches at San Juan.

Each sounding follows the actual balloon trajectory. It should **not** be described as:

- a fixed vertical column over all Puerto Rico,
- a spatial network across Puerto Rico,
- or a direct validation source for all ERA5-Land surface variables across the island.

Better description:

```text
IGRA San Juan contains upper-air profiles from radiosondes launched at San Juan.
Each profile follows the balloon trajectory during ascent, which depends on winds during that launch.
The data are useful for describing atmospheric variation with height along the sounding trajectory,
not for constructing spatial maps within Puerto Rico.
```

Recommended classification:

```text
partial_comparison / physical_context
```

Potential uses:

- vertical temperature profiles;
- humidity structure;
- wind profiles;
- comparison with ERA5 atmospheric variables;
- possible derivation or contextualization of column water vapor;
- physical context for PWV/TCWV interpretation.

Limitations:

- not a spatial network across Puerto Rico;
- not a direct validation of ERA5-Land 2 m variables across the island;
- trajectory depends on winds during each launch;
- values must be parsed using the official IGRA format documentation;
- missing values such as `-9999` must not be interpreted as physical values;
- possible ERA5 assimilation cannot be claimed until confirmed through ECMWF/OFA/MARS/ODB feedback or official equivalent evidence.

### 4.11 ERA5 assimilation note

Radiosondes are a type of observation that may be used or monitored in global data assimilation systems.

However, for this project:

```text
Do not state that RQM00078526 was actively assimilated by ERA5 for any specific date,
variable, or level unless ECMWF/OFA/MARS/ODB feedback/status evidence confirms it.
```

Current status:

```text
ECMWF ticket submitted.
Waiting for response regarding MARS/OFA/ODB access or guidance.
```

### 4.12 Next processing step

Do not process yet until the IGRA format file is reviewed.

Next expected steps:

1. Read `igra2-data-format.txt`.
2. Design a small parser or identify a safe existing parser.
3. Filter to project period `2004–2023`.
4. Extract core variables.
5. Produce a compact intermediate table.
6. Verify units, missing-value codes, and physically plausible ranges.
7. Document processing before producing derived comparisons.

---

## 5. GHCNh review status

### Status

Do not download again at this stage.

### Reason

GHCNh is already part of the current branch workflow and should be reviewed before any new download is attempted.

### Immediate task

Review existing local GHCNh data products for:

- station coverage;
- variable coverage;
- year coverage;
- cleaned-core outputs;
- physically plausible ranges;
- existing documentation;
- whether any gap remains that requires additional download.

Recommended classification:

```text
direct_validation / partial_comparison
```

depending on variable, station, and temporal coverage.

---

## 6. NOAA GHCND

### Status

Not prioritized for download in the current stage.

### Reason

The project is prioritizing hourly or sub-hourly observational data. GHCND is daily. It may remain useful later for daily context or climatology, but it is not part of the immediate download plan.

---

## 7. NOAA ISD / Global Hourly

### Status

Not prioritized for download in the current stage.

### Reason

GHCNh is the current preferred hourly/synoptic surface dataset. ISD may remain as a legacy or secondary reference, but it should not be downloaded before reviewing GHCNh.

---

## 8. NDBC

### 8.1 Status

Downloaded and minimally verified.

### 8.2 Source

NOAA/NDBC historical standard meteorological data (`stdmet`).

Official source structure used:

```text
https://www.ndbc.noaa.gov/data/historical/stdmet/
https://www.ndbc.noaa.gov/station_page.php?station=<station_id>
https://www.ndbc.noaa.gov/station_history.php?station=<station_id>
```

### 8.3 Methodological use

NDBC provides buoy and coastal-station meteorological observations.

For this project, NDBC should be treated as:

```text
physical_context / partial_comparison
```

Expected uses:

- coastal and marine meteorological context;
- wind speed and wind direction near Puerto Rico waters;
- pressure, air temperature, sea-surface temperature, and dew point where available;
- possible comparison with ERA5 Single Levels over marine/coastal regions;
- physical context for the coastal gap-fill problem.

NDBC should not be described as direct validation of inland ERA5-Land pixels.

### 8.4 Candidate stations checked

The availability check was run for the period:

```text
2004–2023
```

Candidate stations checked:

```text
41043
41053
41056
41115
41121
42085
AROP4
FRDP4
JOXP4
LPRP4
MGIP4
SJNP4
VQSP4
```

### 8.5 Availability summary

Availability summary produced by:

```bash
python scripts/download_ndbc_pr.py summary
```

Result:

```text
station,available_years,missing_years
41043,17,3
41053,14,6
41056,11,9
41115,13,7
41121,3,17
42085,15,5
AROP4,13,7
FRDP4,8,12
JOXP4,0,20
LPRP4,6,14
MGIP4,19,1
SJNP4,19,1
VQSP4,8,12
```

Overall result:

```text
OK files:      146
Missing files: 114
```

The station `JOXP4` had no available `stdmet` files for 2004–2023 in the checked NDBC historical path.

### 8.6 Local paths

```text
scripts/download_ndbc_pr.py
data_raw/noaa/ndbc/metadata/ndbc_pr_candidate_stations.txt
data_raw/noaa/ndbc/metadata/ndbc_stdmet_availability_2004_2023.log
data_raw/noaa/ndbc/metadata/ndbc_stdmet_availability_summary_2004_2023.csv
data_raw/noaa/ndbc/metadata/ndbc_stdmet_download_manifest_2004_2023.csv
data_raw/noaa/ndbc/raw/stdmet/
data_raw/noaa/ndbc/raw/station_pages/
logs/
```

### 8.7 Commands used

The NDBC workflow was run with the project script:

```bash
python scripts/download_ndbc_pr.py init
python scripts/download_ndbc_pr.py metadata
python scripts/download_ndbc_pr.py availability
python scripts/download_ndbc_pr.py summary
python scripts/download_ndbc_pr.py download
```

The script was run inside a `tmux` session:

```bash
tmux new -s ndbc_pr
```

### 8.8 Download verification

Downloaded files:

```bash
find data_raw/noaa/ndbc/raw/stdmet -type f -name "*.txt.gz" | wc -l
```

Result:

```text
146
```

Disk usage:

```bash
du -sh data_raw/noaa/ndbc/raw/stdmet
```

Result:

```text
77M     data_raw/noaa/ndbc/raw/stdmet
```

Compression integrity check:

```bash
find data_raw/noaa/ndbc/raw/stdmet -type f -name "*.txt.gz" -exec gzip -t {} \;
```

Result:

```text
(no output)
```

Interpretation: no gzip integrity errors were detected.

Manifest generated with:

```bash
{
    echo "filename,size_bytes"
    find data_raw/noaa/ndbc/raw/stdmet -type f -name "*.txt.gz" -printf "%f,%s\n" | sort
} > data_raw/noaa/ndbc/metadata/ndbc_stdmet_download_manifest_2004_2023.csv
```

Manifest verification:

```bash
wc -l data_raw/noaa/ndbc/metadata/ndbc_stdmet_download_manifest_2004_2023.csv
```

Result:

```text
147 data_raw/noaa/ndbc/metadata/ndbc_stdmet_download_manifest_2004_2023.csv
```

Interpretation: 146 downloaded files plus one header line.

### 8.9 Header check

A sample header from the downloaded files shows the standard meteorological columns:

```text
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi    ft
```

Important processing notes:

- files are whitespace-delimited;
- each file includes two header lines;
- timestamps are in year/month/day/hour/minute columns;
- some annual files may include records from the previous UTC year near the year boundary;
- missing-value codes such as `999`, `999.0`, `99.0`, and `99.00` must be handled carefully by variable;
- visibility units may differ in the historical files (`mi` or `nmi`), so `VIS` should not be used before reviewing metadata and units;
- processing must filter by actual timestamp, not only by filename year.

### 8.10 Git status after raw download

After downloading raw NDBC files:

```bash
git status --short
```

Result:

```text
(no output)
```

Interpretation: raw NDBC files and generated metadata under `data_raw/` are not being tracked by Git, which is correct.

### 8.11 Next processing step

Do not process scientifically yet.

Next expected steps:

1. Review NDBC `stdmet` format and missing-value conventions.
2. Decide which variables are useful for the project.
3. Build a small parser for one station/year.
4. Verify timestamps, units, missing values, and plausible ranges.
5. Only after verification, scale to all downloaded NDBC files.
6. Produce compact intermediate tables under `data_interim/noaa/ndbc/`.
7. Document processing before producing comparisons with ERA5 or ERA5 Single Levels.

---

## 9. NOAA CO-OPS

### 9.1 Status

Downloaded and audited at the raw-data level.

This stage is considered complete for **raw acquisition**, but not for scientific processing.

Current status:

```text
CO-OPS raw acquisition: completed
CO-OPS availability audit: completed
CO-OPS raw structural audit: completed
CO-OPS physical range audit: completed with flagged water-temperature issues
CO-OPS clean/interim dataset: not started
```

### 9.2 Source

NOAA Center for Operational Oceanographic Products and Services (CO-OPS), National Ocean Service (NOS).

Official source locations used:

```text
https://tidesandcurrents.noaa.gov/web_services_info.html
https://api.tidesandcurrents.noaa.gov/api/prod/
https://api.tidesandcurrents.noaa.gov/mdapi/prod/
https://tidesandcurrents.noaa.gov/products.html
https://tidesandcurrents.noaa.gov/map/
```

APIs used:

```text
CO-OPS Metadata API
CO-OPS Data API
```

Important API notes for this workflow:

- hourly Data API requests were made by year because hourly products are limited to one year per request;
- meteorological products were requested with `interval=h`;
- units were requested as `metric`;
- timestamps were requested as `gmt`;
- water-level products were not downloaded in this stage because they require an explicit datum decision.

### 9.3 Methodological use

CO-OPS provides coastal and port station observations. For this project, the selected CO-OPS products should be treated as:

```text
physical_context / partial_comparison
```

Expected uses:

- coastal meteorological context around Puerto Rico;
- local coastal wind, air temperature, pressure, humidity, and water-temperature observations where available;
- future comparison with coastal or marine ERA5 / ERA5 Single Levels fields, if methodologically justified later;
- documentation of additional public observational datasets available for Puerto Rico and nearby coastal environments.

CO-OPS should not be described as direct validation of inland ERA5-Land pixels or mountainous interior candidate sites.

Better description:

```text
NOAA CO-OPS/NOS provides coastal point observations at specific station locations.
These data are useful as coastal meteorological and marine-context observations,
but they do not represent island-wide or inland Puerto Rico meteorology.
```

### 9.4 Products and physical scope

Products selected for this raw acquisition stage:

```text
air_temperature
water_temperature
air_pressure
wind
humidity
```

Physical interpretation by product:

```text
air_temperature
  Air temperature measured at the coastal station sensor.
  Useful as coastal meteorological context; not an island-wide or inland land-temperature field.

water_temperature
  Water temperature measured at the local marine/coastal sensor.
  Useful for marine/coastal thermal context; not air temperature and not directly inland meteorology.

air_pressure
  Barometric pressure measured at the coastal station sensor.
  Useful for synoptic/local coastal pressure context; compare carefully across elevations.

wind
  Local coastal wind speed/direction/gust measured at the station exposure.
  Useful for coastal wind regime; not automatically representative of mountainous or inland sites.

humidity
  Relative humidity measured at the coastal station sensor.
  Useful for observed coastal humidity context; not a direct proxy for inland humidity gradients.
```

### 9.5 Station/product targets

The final strict Puerto Rico target set contained:

```text
7 stations
27 station-product combinations
```

Geographic interpretation:

```text
pr_strict = Puerto Rico main island + Vieques + Culebra + Mona Island
```

Stations in the target set:

```text
9752235  Culebra
9752695  Esperanza, Vieques Island
9753216  Fajardo
9755371  San Juan, La Puntilla, San Juan Bay
9759110  Magueyes Island
9759394  Mayaguez
9759938  Mona Island
```

Target products by count:

```text
air_pressure         7 station-product targets
air_temperature      7 station-product targets
water_temperature    7 station-product targets
wind                 5 station-product targets
humidity             1 station-product target
```

The target list was built from CO-OPS sensor metadata, using inactive sensors as well as active sensors because the project period is historical (`2004–2023`). A sensor that is inactive now may still have valid historical data.

### 9.6 Local paths

Script:

```text
scripts/download_coops_pr.py
```

Metadata and audit outputs:

```text
data_raw/noaa/coops/metadata/
data_raw/noaa/coops/metadata/station_details/
```

Raw downloaded files:

```text
data_raw/noaa/coops/raw/
```

Logs:

```text
logs/noaa/coops/
```

Important metadata and audit files:

```text
data_raw/noaa/coops/metadata/coops_pr_candidate_stations.csv
data_raw/noaa/coops/metadata/coops_pr_station_sensor_inventory.csv
data_raw/noaa/coops/metadata/coops_pr_station_product_inventory.csv
data_raw/noaa/coops/metadata/coops_pr_station_datum_inventory.csv
data_raw/noaa/coops/metadata/coops_pr_variable_scope_notes.csv
data_raw/noaa/coops/metadata/coops_pr_station_product_targets_from_sensors.csv
data_raw/noaa/coops/metadata/coops_pr_data_api_availability_2004_2023.csv
data_raw/noaa/coops/metadata/coops_pr_data_api_availability_summary_2004_2023.csv
data_raw/noaa/coops/metadata/coops_download_manifest.csv
data_raw/noaa/coops/metadata/coops_raw_file_audit.csv
data_raw/noaa/coops/metadata/coops_raw_numeric_range_audit.csv
```

### 9.7 Commands used

The CO-OPS workflow was run with the project script:

```bash
python scripts/download_coops_pr.py init
python scripts/download_coops_pr.py metadata
python scripts/download_coops_pr.py station-details
python scripts/download_coops_pr.py targets --area pr_strict --include-inactive
python scripts/download_coops_pr.py availability \
  --area pr_strict \
  --products air_temperature,water_temperature,air_pressure,wind,humidity \
  --start 2004-01-01 \
  --end 2023-12-31 \
  --units metric \
  --time-zone gmt \
  --met-interval h \
  --sleep 0.8 \
  --include-inactive \
  2>&1 | tee logs/noaa/coops/coops_availability_2004_2023_pr_strict_v6_$(date -u +%Y%m%dT%H%M%SZ).log
python scripts/download_coops_pr.py download \
  --area pr_strict \
  --products air_temperature,water_temperature,air_pressure,wind,humidity \
  --start 2004-01-01 \
  --end 2023-12-31 \
  --units metric \
  --time-zone gmt \
  --met-interval h \
  --sleep 0.8 \
  --include-inactive \
  --overwrite \
  --fresh-manifest \
  2>&1 | tee logs/noaa/coops/coops_download_met_hourly_2004_2023_pr_strict_v6_$(date -u +%Y%m%dT%H%M%SZ).log
python scripts/download_coops_pr.py audit-raw
```

The long availability and download steps were run inside a `tmux` session:

```bash
tmux new -s coops_pr
```

### 9.8 Metadata verification

Station-detail outputs generated:

```text
coops_pr_station_sensor_inventory.csv
coops_pr_station_product_inventory.csv
coops_pr_station_datum_inventory.csv
coops_pr_variable_scope_notes.csv
```

Observed line counts:

```text
61  data_raw/noaa/coops/metadata/coops_pr_station_sensor_inventory.csv
300 data_raw/noaa/coops/metadata/coops_pr_station_product_inventory.csv
652 data_raw/noaa/coops/metadata/coops_pr_station_datum_inventory.csv
```

Interpretation:

```text
The station metadata stage produced sensor, product, datum, and variable-scope inventories.
These inventories were used to build a station/product target set before downloading data.
```

### 9.9 Availability verification

Availability was checked for:

```text
Period: 2004–2023
Products: air_temperature, water_temperature, air_pressure, wind, humidity
Units: metric
Time zone: GMT
Meteorological interval: hourly
```

Final availability result:

```text
ok       394
no_data  146
total    540
```

Availability by product:

```text
air_pressure         ok 106 / no_data 34
air_temperature      ok 107 / no_data 33
humidity             ok  10 / no_data 10
water_temperature    ok 101 / no_data 39
wind                 ok  70 / no_data 30
```

Important correction:

The CO-OPS Data API can return a CSV-like response with a valid header but with an API message such as:

```text
Error: No data was found. This product may not be offered at this station at the requested time.
```

These cases must be classified as:

```text
no_data
```

not as valid data.

### 9.10 Download verification

Final download manifest status:

```text
ok         394
no_data    146
```

Raw file audit status:

```text
ok             394
api_no_data    146
```

Chunks by product/status:

```text
air_pressure         no_data 34 / ok 106
air_temperature      no_data 33 / ok 107
humidity             no_data 10 / ok 10
water_temperature    no_data 39 / ok 101
wind                 no_data 30 / ok 70
```

Interpretation:

```text
The raw CO-OPS acquisition completed successfully.
The workflow now distinguishes valid API responses with data from API no-data responses.
The raw dataset is available for future work, but it is not yet a cleaned scientific dataset.
```

### 9.11 Raw audit and flagged values

The structural raw audit was completed with:

```bash
python scripts/download_coops_pr.py audit-raw
```

Audit outputs:

```text
data_raw/noaa/coops/metadata/coops_raw_file_audit.csv
data_raw/noaa/coops/metadata/coops_raw_numeric_range_audit.csv
```

The numeric range audit flagged two `water_temperature` chunks for physically suspicious values:

```text
station_id  product            year  issue
9755371     water_temperature  2004  31 values below 0 °C; minimum -19.2 °C
9759938     water_temperature  2009  21 values above 40 °C; maximum 43.4 °C
```

Interpretation:

```text
These flagged values do not invalidate the raw download.
They indicate that water_temperature requires explicit QC in a later clean/interim stage.
Raw files should remain unchanged.
```

### 9.12 Processing notes

Important notes for future processing:

- raw files must remain unchanged;
- API `no_data` responses must not be treated as physical observations;
- column names may contain leading or trailing spaces and must be normalized before processing;
- timestamps are GMT/UTC for this workflow;
- numeric columns must be converted safely;
- NOAA flags, where available, should be reviewed before filtering;
- broad physical ranges must be applied by variable;
- flagged observations must be documented rather than silently removed;
- water-level products were not downloaded and should not be added without a datum decision.

Recommended later QC handling:

1. Preserve raw files unchanged.
2. Create an interim/clean version under `data_interim/noaa/coops/`.
3. Normalize column names.
4. Parse timestamps as UTC/GMT.
5. Convert product columns to numeric values safely.
6. Remove or flag API no-data responses.
7. Apply physically realistic broad ranges by variable.
8. Respect NOAA flags where available.
9. Document all excluded or flagged observations.

### 9.13 Git status after raw download

Raw files and generated metadata are under `data_raw/` and should not be committed unless project policy explicitly allows selected lightweight metadata summaries.

Before committing documentation/script changes, run:

```bash
git status --short
git diff -- scripts/download_coops_pr.py docs/OBSERVATIONAL_DATA_DOWNLOADS.md
```

Recommended files to commit:

```text
scripts/download_coops_pr.py
docs/OBSERVATIONAL_DATA_DOWNLOADS.md
```

Do not commit raw downloaded files:

```text
data_raw/noaa/coops/raw/
```

### 9.14 Report-ready summary

A safe report statement is:

```text
NOAA CO-OPS/NOS coastal meteorological data for Puerto Rico were identified,
downloaded, and audited at the raw-data level for selected hourly products over
2004–2023. These observations provide coastal point measurements of air
temperature, water temperature, barometric pressure, wind, and relative humidity
where available. They are retained as an observational coastal dataset for future
analysis, but they were not converted into a cleaned scientific dataset in this
stage.
```

Shorter version:

```text
NOAA CO-OPS/NOS data were incorporated into the observational data inventory as
coastal point observations. Although not used directly in the present site-selection
analysis, the data were downloaded and audited at the raw level and may support
future analyses of coastal meteorological and marine conditions around Puerto Rico.
Further cleaning and quality control are required before formal scientific use.
```

### 9.15 Next processing step

Do not process scientifically yet.

Next expected steps, if CO-OPS is used later:

1. Review raw CSV format by product.
2. Build a small parser for one station/product/year.
3. Verify timestamps, column names, units, flags, and plausible ranges.
4. Define product-specific QC rules.
5. Produce compact intermediate tables under `data_interim/noaa/coops/`.
6. Document processing before producing comparisons with ERA5, ERA5-Land, or ERA5 Single Levels.

Do not use the CO-OPS raw files directly in scientific figures or statistical summaries until the clean/interim stage exists.

---

## 10. USGS NWIS

### Status

Candidate source.

### Expected use

Hydrometeorological context, especially precipitation if suitable historical data and temporal resolution are available for Puerto Rico stations.

Recommended classification:

```text
physical_context / partial_comparison
```

### Caution

Before large downloads, verify:

- parameter codes;
- station availability in Puerto Rico;
- period coverage;
- temporal resolution;
- whether historical precipitation access is limited.

---

## 11. NASA GPM IMERG

### Status

Candidate source for later context.

### Expected use

Spatial precipitation context.

Recommended classification:

```text
physical_context
```

### Caution

IMERG is satellite-based precipitation, not an in-situ station network. It should not be treated as direct station validation.

---

## 12. MADIS

### Status

Candidate source, not first priority.

### Expected use

Potential integrated surface observations and QC metadata.

Recommended classification:

```text
to_be_determined
```

### Caution

Before investing time:

- verify access;
- verify Puerto Rico station coverage;
- check overlap/duplication with GHCNh, METAR, and other NOAA sources;
- confirm whether it adds value beyond current datasets.

---

## 13. Open methodological notes

- The project should prioritize starting downloads while documentation continues in parallel.
- The observational-data matrix remains the reference for deciding priorities.
- Manual downloads are acceptable if fully documented.
- Later, if repeated downloads become necessary, these commands may be converted into small scripts.
- Avoid large scripts before source structure and verification are understood.
