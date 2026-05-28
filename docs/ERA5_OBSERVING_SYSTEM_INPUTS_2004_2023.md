# ERA5 Observing-System Inputs for PR-ngVLA, 2004–2023

**Project:** Characterization of the Weather Conditions for the Next Generation Very Large Array in Puerto Rico  
**Repository path:** `docs/ERA5_OBSERVING_SYSTEM_INPUTS_2004_2023.md`  
**Status:** Initial methodological documentation. This document defines the verification strategy. It does not yet present a completed regional observing-system inventory.

---

## 1. Purpose

This document defines how the PR-ngVLA project will investigate the observations and observing-system inputs associated with ERA5 over the Puerto Rico analysis domain during 2004–2023.

The central question is:

```text
Which observations or observation classes were available to, monitored by, screened by,
or actively used/passively used/rejected by the ERA5 assimilation system over the
Puerto Rico regional domain during 2004–2023?
```

This document is intentionally separate from the local ERA5-family NetCDF inventory:

```text
docs/ERA5_LOCAL_DATA_INVENTORY_2004_2023.md
```

The local NetCDF inventory documents gridded products downloaded from the Copernicus Climate Data Store (CDS). This document concerns observation inputs, observation monitoring, and observation-feedback information associated with the ERA5 data assimilation system.

---

## 2. Project scope for this stage

### 2.1 Period

The official period for this stage is:

```text
2004–2023
```

This matches the current PR-ngVLA local ERA5-family data inventory and the working analysis period used in the project.

### 2.2 Spatial domain

The official domain for this stage is the same bounding box used in the local ERA5-family download scripts:

```python
AREA_PR = [18.6, -68.0, 17.8, -65.0]  # [North, West, South, East]
```

This stage will not expand the analysis to the wider Caribbean unless a later project decision explicitly defines a new bounding box.

---

## 3. What this document can and cannot claim

### 3.1 What can be stated now

ERA5 is a global reanalysis produced using a data assimilation system that combines model background information with observations. Official ECMWF documentation states that ERA5 was produced using 4D-Var data assimilation with 12-hour assimilation windows.

ECMWF also provides observing-system monitoring resources, including data coverage charts and global data monitoring reports. These resources can help identify which observation classes were available to ECMWF or monitored by ECMWF.

Observation Feedback / ODB / MARS records are the most relevant sources for determining whether individual observations were active, passive, rejected, or blocklisted/blacklisted in the data assimilation workflow.

### 3.2 What cannot be stated yet

At this stage, the project must not claim that:

```text
ERA5 actively used station X at time Y.
ERA5 rejected buoy Z.
A specific satellite pass directly corrected the Puerto Rico grid cell.
An ERA5-Land grid value is an average of local observations.
The local ERA5 or ERA5-Land NetCDF files contain the individual observations.
```

Those claims require observation-feedback evidence, status flags, or another official traceable source.

---

## 4. Key methodological distinction

The project must distinguish between three levels of evidence:

| Level | Meaning | Evidence needed | What can be claimed |
|---|---|---|---|
| Available | Observations existed or were available to the ECMWF system for a given time or region | ECMWF observation coverage charts, data monitoring reports, or official monitoring documentation | The observation class was available or received |
| Monitored | ECMWF produced availability, quality, or usage statistics for that observation class | ECMWF observation monitoring dashboard or global data monitoring reports | The observation class was monitored by ECMWF |
| Used / passive / rejected / blocklisted | A report or datum passed through observation processing and has a usage/QC status | Observation Feedback, ODB, BUFR-feedback, or MARS records | The report/datum was active, passive, rejected, or blocklisted/blacklisted |

Important:

```text
Available does not automatically mean actively assimilated.
Monitored does not automatically mean actively assimilated.
Only observation-feedback/status information can support a claim of active/passive/rejected/blocklisted use.
```

---

## 5. Official technical basis

### 5.1 ERA5 assimilation

ERA5 was produced with the ECMWF Integrated Forecasting System using 4D-Var data assimilation. The assimilation windows are 12 hours long. The background forecast and observations within each window are used to produce the analyses.

Implication for this project:

```text
ERA5 grid values should not be interpreted as direct station measurements or simple pixel averages.
They are gridded reanalysis estimates produced by combining a prior model state with observations,
observation operators, uncertainty information, and quality-control decisions.
```

### 5.2 ECMWF observing-system monitoring

ECMWF observing-system monitoring provides information on observation availability, quality, and usage. Data coverage charts can show observations available for use by the ECMWF 4D-Var system at 6-hourly intervals.

Implication for this project:

```text
Monitoring products may help identify observation classes available over or near the Puerto Rico
domain, but they may not by themselves prove that each observation was actively assimilated.
```

### 5.3 Observation Feedback / ODB / MARS

Observation-feedback records are the strongest evidence for determining how observations were treated by the data assimilation system.

Relevant feedback information can include:

- blacklists or blocklists,
- quality checks,
- duplicate-report flags,
- first-guess departure,
- analysis departure,
- report or datum status.

Implication for this project:

```text
A rigorous claim that ERA5 actively used, passively used, rejected, or blocklisted a specific
observation requires observation-feedback/status evidence.
```

---

## 6. Candidate observation classes to verify

The following observation classes are candidate sources to investigate. They are not yet confirmed as active inputs over the Puerto Rico domain for every year/month in 2004–2023.

| Observation class | Examples | Possible relevance to Puerto Rico domain | Directly comparable to local surface variables? | Verification route |
|---|---|---|---|---|
| Surface land stations | SYNOP, METAR, airport reports | Near-surface temperature, humidity, wind, pressure | Partly, depending on variable and representativeness | Monitoring charts, ODB/MARS feedback, station metadata |
| Upper-air soundings | TEMP/radiosondes | Vertical profiles of temperature, humidity, wind | Not directly comparable to 2 m fields; useful for profiles/columns | ODB/MARS feedback, monitoring reports |
| Aircraft observations | AMDAR, aircraft reports | Upper-air temperature and wind along flight paths | Not directly comparable to local surface fields | ECMWF monitoring, ODB/MARS feedback |
| Marine surface observations | Ships, buoys, drifting buoys | Sea-level pressure, wind, marine surface conditions near PR | Partly, mostly over ocean; not equivalent to land grid cells | ECMWF monitoring, ODB/MARS feedback |
| Satellite radiances | Microwave and infrared sounders | Temperature/humidity information over broad footprints | Not directly comparable without an observation operator | Satellite monitoring, ODB/MARS feedback |
| Atmospheric motion vectors | Satellite-derived winds | Wind information from cloud/water-vapour tracking | Not directly comparable to 10 m wind | Satellite monitoring, ODB/MARS feedback |
| Scatterometer winds | Ocean surface vector winds | Marine winds near Puerto Rico | Comparable only over ocean, not land | Satellite monitoring, ODB/MARS feedback |
| GNSS radio occultation | Bending angle/refractivity profiles | Temperature/moisture profile constraints | Not directly comparable to 2 m fields | Satellite monitoring, ODB/MARS feedback |
| Altimeter observations | Sea-surface related observations | Marine/ocean context near the domain | Not directly comparable to land variables | Satellite monitoring, ODB/MARS feedback |
| Dropsondes | Tropical cyclone or campaign observations | Possible relevance during storms/hurricanes | Profiles, not simple surface comparison | ODB/MARS feedback, campaign metadata |

---

## 7. Minimum information to extract if observation feedback becomes accessible

If ODB, MARS observation feedback, or another official feedback source becomes accessible, the target inventory should extract fields like:

| Field | Purpose |
|---|---|
| observation time | Match observation to ERA5 assimilation window |
| latitude, longitude | Filter to `AREA_PR` |
| observation type/class | Identify source class |
| platform/station/satellite identifier | Track source identity |
| observed variable or channel | Identify what was measured |
| observed value | Compare with background/analysis if appropriate |
| first-guess departure | Difference between observation and model background |
| analysis departure | Difference between observation and analysis |
| report/datum status | Active, passive, rejected, blocklisted/blacklisted |
| QC flags/events | Reason for rejection or special handling where available |

Important caution:

```text
A small analysis departure alone is not sufficient to prove active assimilation.
Usage/status flags must be checked.
```

---

## 8. Initial verification workflow

This workflow is documentation-first and non-destructive.

### Step 1 — Official documentation review

Document the official ECMWF/ERA5 sources that describe:

- ERA5 4D-Var assimilation,
- observation monitoring,
- observation feedback,
- ODB/MARS status flags,
- observation classes monitored by ECMWF.

Output:

```text
A source table with official references and a short note on what each source can support.
```

### Step 2 — Monitoring-level inventory

Use ECMWF observing-system monitoring and data coverage products to determine which observation classes are visible or monitored for the period and domain, where possible.

Output:

```text
Observation class | monitoring source | temporal coverage | spatial relevance | limitations
```

### Step 3 — Feedback-level feasibility check

Determine whether ERA5 observation feedback / ODB / MARS records can be accessed for:

```text
period = 2004–2023
area   = [18.6, -68.0, 17.8, -65.0]
```

Output:

```text
Access route | required account/tool | query parameters | export fields | limitations
```

### Step 4 — Pilot extraction only after access is confirmed

Only after the access route is verified, run a small pilot query. Do not attempt the full 20-year extraction first.

Recommended pilot options:

```text
One month in dry season: February 2020
One month in wet season: September 2020
One hurricane-related period: September 2017, only if justified and handled separately
```

The pilot should test:

- whether the area filter works,
- which observation classes appear,
- whether status flags are available,
- whether first-guess and analysis departures are available,
- whether the data volume is manageable.

---

## 9. Documentation table to maintain

The following table should be filled gradually as evidence is collected.

| Observation class | Evidence level | Evidence source | Period checked | Domain checked | What is supported | What is not supported yet |
|---|---|---|---|---|---|---|
| Surface land stations | pending | pending | pending | pending | pending | pending |
| Radiosondes / upper-air | pending | pending | pending | pending | pending | pending |
| Aircraft | pending | pending | pending | pending | pending | pending |
| Ships / buoys | pending | pending | pending | pending | pending | pending |
| Satellite radiances | pending | pending | pending | pending | pending | pending |
| Atmospheric motion vectors | pending | pending | pending | pending | pending | pending |
| Scatterometer winds | pending | pending | pending | pending | pending | pending |
| GNSS radio occultation | pending | pending | pending | pending | pending | pending |
| Altimeters | pending | pending | pending | pending | pending | pending |
| Dropsondes | pending | pending | pending | pending | pending | pending |

---

## 10. Current status

Current status:

```text
Scope fixed:
  period = 2004–2023
  area   = [18.6, -68.0, 17.8, -65.0]

Documentation started:
  local ERA5-family inventory completed separately.
  observing-system input methodology started here.

Not yet completed:
  no regional observation-feedback extraction has been performed.
  no observation class has yet been confirmed as actively used within AREA_PR for 2004–2023.
  no station/platform-specific active assimilation claim has been made.
```

---

## 11. References

- ECMWF. ERA5 data documentation. ERA5 produced using 4D-Var data assimilation and 12-hour assimilation windows.  
  https://confluence.ecmwf.int/plugins/viewsource/viewpagesrc.action?pageId=540945091

- ECMWF. Monitoring of the observing system.  
  https://www.ecmwf.int/en/forecasts/quality-our-forecasts/monitoring-observing-system

- ECMWF. ECMWF Global Data Monitoring Report Archive.  
  https://www.ecmwf.int/en/forecasts/quality-our-forecasts/monitoring-observing-system/ecmwf-global-data-monitoring-report-archive

- ECMWF. Observation feedback archiving in MARS.  
  https://www.ecmwf.int/sites/default/files/elibrary/2009/10562-observation-feedback-archiving-mars.pdf

- ECMWF. IFS Documentation, Part I: Observations, ODB report/datum status and events.  
  https://www.ecmwf.int/sites/default/files/elibrary/112024/81623-ifs-documentation-cy49r1-part-i-observations.pdf

- ECMWF. IFS Documentation, Part I: Observations, ERA5-era documentation / CY41R2 observation processing reference.  
  https://www.ecmwf.int/sites/default/files/elibrary/2016/79695-ifs-documentation-cy41r2-part-i-observations_1.pdf
