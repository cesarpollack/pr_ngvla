# DECISIONS.md
# ngVLA Puerto Rico — Scientific and Methodological Decisions
# Last updated: April 9, 2026
# Author: César Pollack, UPR Río Piedras
#
# PURPOSE: Document every non-trivial decision made in this project.
# Each entry answers: What did we decide? Why? What are the alternatives?
# How do we defend this in front of the committee?
#
# This document is the scientific backbone of the final report.

---

## D01 — Scientific Framing (CRITICAL — never violate)

**Decision:** Puerto Rico IS part of the ngVLA project. The study does NOT
evaluate whether PR qualifies. The goal is to identify the BEST REGIONS
within Puerto Rico for antenna placement.

**Rationale:** PR is already included in the ngVLA design. The conclusion
will ALWAYS be "these regions are better than others" — never "PR is not
suitable."

**Terminology:** Use "site selection index" — never "suitability index."
The word "suitability" implies a pass/fail judgment that is scientifically
and politically inappropriate for this study.

**When RH/PWV exceedance is high:** Frame as "this quantifies the
atmospheric correction requirements — antennas in PR will require water
vapor radiometry and phase correction techniques. The SW region minimizes
this impact."

**Reference:** Narrativocientifico.pdf (project knowledge)

---

## D02 — Study Period: 2004–2023 (20 years)

**Decision:** Use ERA5-Land data from 2004 to 2023 inclusive.

**Rationale:** 20 years is the standard climatological period for site
characterization studies. ERA5-Land is available from 1950, but we chose
2004 to ensure data quality consistency post-satellite era and to have
clean data on both sides of Hurricane Maria (2017).

**Hurricane Maria exclusion:** Months 2017-09 through 2018-06 are
excluded from exceedance calculations. Maria destroyed ground stations
that were assimilated into ERA5, potentially degrading data quality
for that period.

**Alternative considered:** 2000–2023 (longer period). Rejected because
ERA5-Land quality before 2004 is slightly lower due to fewer assimilated
observations.

---

## D03 — Primary Dataset: ERA5-Land at 0.1° (~9 km)

**Decision:** Use ERA5-Land as the primary dataset for all surface
meteorological variables (t2m, d2m, u10, v10, tp, sp).

**Rationale:**
- Highest resolution publicly available reanalysis for land surfaces
- Globally validated by Muñoz-Sabater et al. (2021)
- Hourly temporal resolution matches ngVLA operational requirements
- Consistent with methodology used in other astronomical site
  characterization studies (Bi et al. 2024, MNRAS)

**Reference:** Muñoz-Sabater et al. (2021), ESSD 13:4349-4383

---

## D04 — PWV Source: ERA5 Single-Levels

**Decision:** Use ERA5 single-levels (0.25°) for PWV/TCWV instead of
ERA5-Land.

**Rationale:** ERA5-Land does not include total column water vapor (TCWV).
ERA5 single-levels provides this variable and has been validated for PWV
against GNSS and radiosondes with correlation >0.99 (Zhang et al. 2019).

**Reference:** Zhang et al. (2019), Radio Science 54:561-571

---

## D05 — Thresholds: Selina et al. (2020) + Linford & Cooper (2023)

**Decision:** Use thresholds from ngVLA System Environmental Specification
(Selina et al. 2020) and ngVLA Memo 117 (Linford & Cooper 2023).

| Variable | Good threshold | Source |
|---|---|---|
| PWV | ≤ 6 mm | ENV0316 (Precision) |
| RH | ≤ 50% | Memo 117 Table 2 |
| Precip | 0 mm/hr (use >1 mm/hr for ERA5) | Memo 117 |
| Wind | ≤ 9 m/s | Memo 117 Table 2 |
| T−Td | ≥ 2°C | Memo 117 Table 2 |

**ERA5 precipitation note:** ERA5 generates numerical drizzle — threshold
> 0 mm/hr gives unphysical 93% exceedance. Use > 1 mm/hr and > 7.6 mm/hr
only. Bias affects all pixels uniformly — does NOT distort spatial ranking.

---

## D06 — Validation: ERA5 vs NOAA ISD (5 stations)

**Decision:** Validate ERA5-Land against 5 NOAA ISD stations for RH
and wind. No hourly station data available for precip or PWV in PR.

**Known limitation:** All 5 stations are coastal and at airports. No
mountain stations exist in the Cordillera Central.

**Defense:** ERA5-Land global validation (Muñoz-Sabater et al. 2021)
compensates. Our regional validation adds specificity for PR's complex
topographic and climatic setting. RH MBE < 3%, wind MBE < 1.2 m/s.

**Standard answer for committee:** "Regional validation adds specificity
that global validation cannot provide. For precip and PWV, we rely on
global validation and spatial comparison with PRISM (independent 450m
climatology)."

---

## D07 — Site Selection Index: Equal Weights (Fuzzy-Logic)

**Decision:** Use equal weights (0.25 each) for RH, wind, precip, and
PWV in the composite site selection index.

**Membership function:** Linear — suitability = 1 - exceedance_fraction.

**Rationale:** No MCDA weights have been formally assigned for ngVLA.
Equal weights are the scientifically conservative choice for the poster.
Sensitivity analysis across weight sets is planned for Phase 4 (Monte Carlo).

**Defense:** "Equal weights represent the maximum entropy prior — no
variable is assumed more important than others without empirical evidence.
This is the appropriate baseline before Phase 4 sensitivity analysis."

**Alternative:** Data-driven weights from NOAA ISD stations. Rejected
for poster because 5 stations are insufficient for robust weight estimation.

---

## D08 — ERA5-SL Gap-Fill for Coastal Pixels

**Decision:** Use ERA5 single-levels (0.25°) to fill coastal NaN pixels
in ERA5-Land exceedance climatologies.

**Scientific justification:** ERA5-Land assigns NaN to coastal pixels
where land fraction is below an internal threshold (~9 km pixels). ERA5-SL
uses a different land-sea mask and recovers partial coverage. Both products
derive from the same ECMWF IFS system and are physically consistent.

**Key finding during implementation:** ERA5-SL pixels with low land
fraction produce artifically low precipitation exceedance values because
they mix terrestrial and marine signals. This can distort the site
selection index.

**Solution — Land fraction threshold of 60%:**
Only ERA5-SL pixels where ≥60% of the 0.25° pixel area falls within
PR municipality boundaries are used for gap-fill. This eliminates the
problematic northern coastal fringe (lat 18.55°) and all southern
coastal pixels (lat 17.80°).

**Threshold justification:** 60% is more conservative than the 40%
commonly used in regional downscaling literature (Nacar et al. 2022).
Chosen to ensure gap-fill pixels are clearly terrestrial.

**Remaining limitation:** Lajas and Guánica (lat ~17.97°N) remain NaN
because no ERA5-SL pixel at 17.80° has sufficient land fraction (max
24%). This is documented as a limitation and identified as future work.

**Provenance mask:** A NetCDF file (`provenance_mask.nc`) records for
each pixel: 0=ocean/no data, 1=ERA5-Land, 2=ERA5-SL gap-fill.

**Interpolation method:** Bilinear (xr.DataArray.interp, method="linear").
Same method used in ERA5-Land production (Muñoz-Sabater et al. 2021).

**Reference:** Muñoz-Sabater et al. (2021); Hersbach et al. (2020)

---

## D09 — PRISM as Independent Validation

**Decision:** Use PRISM precipitation normals (1963-1995, 450m) as
independent spatial validation of ERA5 precipitation patterns.

**Rationale:** PRISM is an independent dataset derived from station
observations with high spatial resolution. Agreement between ERA5 and
PRISM strengthens confidence in ERA5 spatial patterns.

**Limitation:** PRISM confirmed they will NOT update PR normals
(indefinitely on hold). Period mismatch: PRISM 1963-1995 vs ERA5 2004-2023.
Used for spatial pattern validation only — not quantitative comparison.

---

## D10 — DEM Downscaling: Deferred to Phase 4

**Decision:** Lapse rate correction for temperature and pressure fields
(0.65°C per 100m elevation) is deferred to Phase 4 (May 2026).

**Rationale:** Not needed for poster results. Monthly mean temperature
passes Normal Operations range at all elevations without correction.
DEM downscaling adds value for Phase 4 site ranking but is not critical
for Phase 3 site selection index.

---

## D11 — Hurricane Maria Exclusion

**Decision:** Exclude months 2017-09 through 2018-06 from all hourly
exceedance calculations.

**Rationale:** Maria destroyed ground stations that feed ERA5 assimilation.
Data quality for PR during this period is reduced. Exclusion removes
9 months from a 20-year record — negligible impact on climatology.

**Implementation:** `MARIA_START = "2017-09"`, `MARIA_END = "2018-06"`
in config.py. Applied in all Phase 2 exceedance scripts.

---

## D12 — Terminology Decisions

| Avoid | Use instead | Reason |
|---|---|---|
| "suitability index" | "site selection index" | No pass/fail implied |
| "suitable/unsuitable" | "more/less favorable" | Scientific framing |
| "Puerto Rico qualifies/fails" | "SW corridor is most favorable" | Correct framing |
| "limitation" alone | "limitation → future work" | Shows path forward |

---

## D13 — Key Results for Poster and Committee

**Phase 1 — Monthly Climatology:**
- Temperature: 21.2–27.8°C — all within Normal Operations (no discriminating power)
- RH: 67.7–87.2% — Questionable tier most of the year
- T−Td: 2.28–6.37°C — all above 2°C Good threshold (promising)
- Wind: 1.25–4.96 m/s — excellent, well below 9 m/s threshold
- Precipitation: SW corridor consistently driest year-round
- PWV: 26.1–46.7 mm — entire PR above 6 mm Good threshold year-round

**Phase 2 — Exceedance:**
- RH > 50%: 97.9% of hours — quantifies atmospheric correction need
- Wind > 9 m/s: ~0% — wind not a discriminating variable
- Precip > 1 mm/hr: 25.4% — SW corridor lowest
- PWV > 26 mm: 90.2% — Jan–Mar SW drops to ~50%

**Phase 3 — Site Selection Index:**
- Best municipalities (ERA5-Land): San Germán, Yauco, Lares, Las Marías,
  Guayanilla, Adjuntas, Peñuelas, Utuado, Jayuya, Mayagüez
- Best temporal window: January–March (dry season)
- Best pixel: San Germán (index=0.5153, annual mean)
- February is the best month across all top municipalities

---

## Standard Answers for Common Questions

**"Why validate if ERA5 is already globally validated?"**
Regional validation adds specificity for PR's complex topographic and
climatic setting. Our validation confirms ERA5 behavior in PR with known
biases documented. MBE < 3% for RH, < 1.2 m/s for wind.

**"PWV/RH is very high — does that disqualify PR?"**
No. The study identifies BEST REGIONS within PR. High PWV quantifies
atmospheric correction requirements for millimeter-wave observations —
standard practice for tropical radio telescope sites. The SW region and
dry season minimize this impact. Water vapor radiometers and phase
correction are established solutions (Nikolic et al. 2013).

**"Why only 5 validation stations?"**
These are the only NOAA ISD stations with continuous hourly records in
PR during our study period. All are coastal — a recognized limitation.
ERA5-Land global validation and agreement with PRISM partially compensates.

**"What about Lajas and Guánica?"**
ERA5-Land (0.1°) does not resolve these coastal municipalities with
sufficient land fraction. ERA5-SL gap-fill with 60% land fraction
threshold cannot recover them either (max land fraction 24% at 17.80°N).
Identified as future work: higher resolution reanalysis or WRF downscaling.

**"Why equal weights?"**
Equal weights represent the maximum entropy prior — no variable is assumed
more important without empirical evidence. This is the appropriate
baseline. Phase 4 Monte Carlo sensitivity analysis will explore the
impact of different weight sets on site ranking.
