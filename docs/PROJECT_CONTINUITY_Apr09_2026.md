# ngVLA Puerto Rico — Project Continuity Document
# Generated: April 9, 2026
# Use this file as the FIRST message in a new chat to restore full context.

---

## PROJECT IDENTITY
- **Project:** Atmospheric site characterization for ngVLA antenna placement in Puerto Rico
- **Lead:** César Pollack (graduate student, UPR Río Piedras)
- **Advisor:** Dr. Mayra Lebrón Santos (UPR Río Piedras / CARSE)
- **Collaborators:** Dr. Héctor Arce (Yale), Dr. Jorge Morales (UPR), Dr. Carmen Pantoja (UPR)
- **Funding:** NSF – RUM CARSE SPEED Program
- **Deadlines:**
  - Zoom meeting with advisor: April 10, 2026 at 10:00 AM
  - Poster first draft: April 13, 2026 (Monday) — hard deadline
  - Poster submission: April 18, 2026
  - Full report: May 2026
- **Server:** astroiupi | user: cpollack | base path: `/export/ngvla/cpollack/`

---

## SCIENTIFIC FRAMING (CRITICAL — NEVER VIOLATE)
- Puerto Rico IS part of the ngVLA project — the study does NOT evaluate whether PR qualifies
- Goal: identify the BEST REGIONS within Puerto Rico for antenna placement
- The conclusion will NEVER be "Puerto Rico is not suitable"
- It will ALWAYS be "these regions are better than others"
- **Framing for limitations:** "this quantifies the challenge — antennas in PR will require
  atmospheric correction techniques. The SW region minimizes this impact."
- **Terminology:** Use "site selection index" — NEVER "suitability index"
- Source: Narrativocientifico.pdf (in project knowledge)

---

## PHASE STATUS (as of April 9, 2026)

### Phase 1 ✅ COMPLETE — 20-yr monthly climatology (ERA5-Land)
All 7 maps in `outputs/maps/phase1/`

### Phase 2 ✅ COMPLETE — Hourly exceedance + station validation
All exceedance NetCDFs in `outputs/phase2/`
All exceedance maps in `outputs/maps/phase2/`
Validation results in `outputs/validation/era5_vs_isd_metrics.csv`

### Phase 3A ✅ COMPLETE — Fuzzy-logic site selection index
- `outputs/phase3/composite_index_monthly.nc`
- `outputs/phase3/composite_index_annual.nc`
- `outputs/phase3/best_regions_annual.csv`
- `outputs/phase3/best_regions_monthly.csv`
- `outputs/phase3/best_municipalities.csv`
- `outputs/phase3/best_regions_summary.txt`
- Maps in `outputs/maps/phase3/`

### Phase 3B ✅ COMPLETE (with documented limitation) — ERA5-SL gap-fill
**OUTCOME:** Gap-fill attempted with ERA5 single-levels. Land fraction threshold
of 60% was applied (pixels must have ≥60% land area within PR municipality shapefile).
Result: 0 ERA5-SL pixels passed the threshold for gap regions — ERA5-Land result
stands at 59 land pixels.

**WHY:** Lajas/Guánica area (lat ~17.97°N) has max land fraction of 24% in
ERA5-SL 0.25° pixels. No ERA5-SL pixel near the SW coast is sufficiently
terrestrial to use without marine signal contamination.

**POSTER MAPS (USE THESE):**
- `outputs/maps/phase3/phase3_composite_annual_gf.png` ← annual poster figure
- `outputs/maps/phase3/phase3_composite_monthly_gf.png` ← monthly poster figure
- Best pixel: **San Germán** (−67.000, 18.100) index = 0.5153

**Provenance mask saved:** `outputs/phase3/gapfill/provenance_mask.nc`
(0=ocean, 1=ERA5-Land, 2=ERA5-SL — currently all 1 or 0)

### Phase 3 Scripts (complete)
```
scripts/phase3_composite_index.py     ✅
scripts/phase3_map_composite.py       ✅
scripts/phase3_best_regions_report.py ✅
scripts/phase3_gapfill_singlelev.py   ✅ (LAND_FRAC_THRESHOLD = 0.60)
scripts/phase3_map_gapfill.py         ✅
```

### Phase 4 ⏳ PENDING — Monte Carlo uncertainty + DEM downscaling (May 2026)
### Phase 5 ⏳ FUTURE — WRF downscaling at 1-3 km (Jun–Aug 2026)

---

## DOCUMENTATION (created April 9, 2026)
All docs in `/export/ngvla/cpollack/pr_ngvla/docs/`:
- `ARCHITECTURE.md` — project structure, design rules, data flow
- `DECISIONS.md` — 13 scientific/methodological decisions with justifications
- `FUTURE_WORK.md` — coastal coverage solutions plan (WRF, etc.)

---

## DATA STATUS — ALL COMPLETE ✅

| Dataset | Path | Status |
|---|---|---|
| ERA5-Land monthly | data_raw/era5/monthly/ | ✅ 2 files |
| ERA5-Land hourly | data_raw/era5/hourly/ | ✅ 480 files |
| ERA5 single-levels hourly | data_raw/era5/singlelev/ | ✅ 720 files (extracted from zip) |
| ERA5 PWV/TCWV | data_raw/era5/pwv/ | ✅ 20 files |
| NOAA ISD stations | data_raw/noaa/isd/ | ✅ 5 stations |
| DEM 30m | data_raw/dem/pr_dem_30m.tif | ✅ |
| GSHHS coastline | data_raw/shapefiles/ | ✅ |
| TIGER municipalities | data_raw/shapefiles/ | ✅ |
| PRISM normals | data_raw/prism/ | ✅ 39 .asc files |

### ERA5-SL File Structure (IMPORTANT — extracted from ZIP)
```
era5sl_hourly_t2m_d2m_PR_YYYY_MM.nc           ← t2m, d2m (valid)
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_instant.nc ← u10, v10, sp
era5sl_hourly_wind_tp_sp_PR_YYYY_MM_accum.nc   ← tp (accumulated)
```
- Time dimension: `valid_time` (NOT `time`)
- Grid: 4 lats × 13 lons at 0.25°

---

## CONFIRMED SCIENTIFIC RESULTS

### Phase 1 — Monthly Climatology
- Temperature: 21.2–27.8°C — within Normal Operations, no discriminating power
- RH: 67.7–87.2% — Questionable tier most of the year
- T−Td: 2.28–6.37°C — all above 2°C Good threshold (promising)
- Wind: 1.25–4.96 m/s — well below 9 m/s (excellent)
- Precipitation: Jan=43, Feb=39, Mar=63, Apr=97 mm/month (dry season)
- PWV: 26.1–46.7 mm — entire PR above 6 mm Good threshold year-round
- SW corridor (Lajas/Guánica/Ponce area) is driest region year-round
- Cordillera Central E–W orientation creates rain shadow on SW coast

### Phase 2 — Exceedance Climatology
| Variable | Threshold | Mean exceedance | Interpretation |
|---|---|---|---|
| RH | > 50% | 97.9% | Humid year-round; quantifies correction need |
| Wind | > 9 m/s | ~0% (max 4.4%) | Excellent — not a discriminating variable |
| Precip | > 1 mm/hr | 25.4% | SW corridor consistently lowest |
| Precip | > 7.6 mm/hr | 3.2% | Rare extreme events |
| PWV | > 26 mm | 90.2% | High year-round; Jan–Mar SW ~50% |

### Phase 2 — ERA5 vs NOAA ISD Validation
| Station | RH MBE (%) | RH r | Wind MBE (m/s) | Wind r |
|---|---|---|---|---|
| Hernández (NW) | −0.92 | 0.657 | −0.61 | 0.452 |
| Hostos (W) | +0.06 | 0.627 | −0.43 | 0.290 |
| SJU (NE) | +3.00 | 0.742 | −0.79 | 0.746 |
| Ribas (NE) | −1.58 | 0.578 | −1.20 | 0.615 |
| Roosevelt (E) | +1.36 | 0.665 | +0.60 | 0.669 |
Key: RH MBE < 3% (no systematic bias), Wind underestimation in 4/5 stations (known ERA5-Land behavior)

### Phase 3 — Site Selection Index (top municipalities, ERA5-Land)
| Rank | Municipality | Annual index | Best month |
|---|---|---|---|
| 1 | San Germán | 0.5153 | Feb |
| 2 | Yauco | 0.5136 | Feb |
| 3 | Lares | 0.5110 | Feb |
| 4 | Las Marías | 0.5088 | Feb |
| 5 | Guayanilla | 0.5071 | Feb |
| 6 | Adjuntas | 0.5060 | Feb |
| 7 | Peñuelas | 0.5007 | Feb |
| 8 | Utuado | 0.4997 | Feb |
| 9 | Jayuya | 0.4990 | Feb |
| 10 | Mayagüez | 0.4985 | Feb |

**Best temporal window:** January–March (dry season)
**Best month across all top municipalities:** February

---

## CRITICAL LIMITATION — Coastal Coverage

ERA5-Land (~9 km) assigns NaN to coastal pixels where land fraction <
internal ECMWF threshold. Affected municipalities: Lajas, Guánica, Cabo Rojo coastal.

ERA5-SL gap-fill was attempted (60% land fraction threshold). Result: no
ERA5-SL pixel near SW coast passes threshold (max 24% land fraction at 17.80°N).

**The main conclusion is NOT affected:** Adjacent ERA5-Land pixels in San Germán,
Yauco, and Guayanilla (10-15 km away) confirm the SW corridor is most favorable.

**Future work:** WRF dynamical downscaling at 1-3 km (Phase 5, Jun–Aug 2026).
See `docs/FUTURE_WORK.md` for full plan.

---

## DATASET DEFENSE — ERA5-Land is the best available

### Comparison table
| Dataset | Resolution | Temporal | ngVLA variables | Verdict |
|---|---|---|---|---|
| **ERA5-Land** ← used | 9 km, hourly | 1950–present | all 7 | ✅ Best option |
| ERA5 single-levels | 28 km, hourly | 1940–present | all 7 | ✅ Used for PWV |
| MERRA-2 (NASA) | 50 km, hourly | 1980–present | all 7 | ❌ Lower resolution |
| NCEP/NCAR | 200 km, 6-hr | 1948–present | limited | ❌ Obsolete |
| CFSR | 38 km, hourly | 1979–present | all 7 | ❌ Lower resolution |
| JRA-55 | 55 km, 6-hr | 1958–present | all 7 | ❌ Lower resolution |
| CHELSA | 1 km, monthly | 1981–present | T, P only | ❌ No RH, PWV, wind |
| Daymet | 1 km, daily | 1980–present | T, P only | ❌ No RH, PWV, wind |

### Why not MERRA-2?
> "ERA5-Land surpasses MERRA-2 in three critical aspects: spatial resolution
> (9 km vs 50 km), quality of surface data assimilation, and specific validation
> for land surface variables (Muñoz-Sabater et al. 2021). For PWV, Zhang et al.
> (2019, Radio Science) demonstrates ERA5 has higher accuracy than ERA-Interim —
> the predecessor that MERRA-2 rivals. ERA5 is currently the gold standard for
> astronomical site characterization studies (Bi et al. 2024, MNRAS)."

### Why not Daymet?
> "Daymet fails for two independent reasons: (1) it only provides temperature
> and precipitation — no RH, PWV, or wind speed, which are 5 of the 7 ngVLA
> study variables. (2) Daymet is a statistical interpolation of ground stations.
> In PR, all stations are coastal and at low elevation — Daymet extrapolates into
> the Cordillera without real data. ERA5-Land derives variables from the lowest
> IFS model level (~10m above surface) using physical laws, consistently across
> the entire domain regardless of station coverage."

### Why not WRF directly?
> "WRF requires ERA5 as boundary conditions — so ERA5 is used either way.
> WRF at high resolution for 20 years of hourly data requires weeks of
> computation. ERA5-Land provides the best balance of resolution and
> availability. WRF is planned as future work for coastal coverage."

---

## LIBRARY ARCHITECTURE (fully built and installed)
```
src/pr_ngvla/
├── config.py                    — ALL paths, bbox, CRS, periods, constants
├── physics/thermodynamics.py    — rh_from_t_td, dew_point_depression
├── data/loaders.py              — load_era5_monthly, load_era5_pwv, load_noaa_isd_stations
├── data/spatial.py              — load_vector_data (returns 3 values!), load_dem
├── data/temporal.py             — monthly_climatology, precip_to_mm_month
├── analysis/thresholds.py       — THRESHOLDS dict + classify()
├── analysis/exceedance.py       — monthly_exceedance_climatology
├── analysis/validation.py       — validate_station, compute_metrics
├── analysis/fuzzy.py            — composite_index, annual_composite, DEFAULT_WEIGHTS
├── analysis/gapfill.py          — regrid_singlelev_to_era5land, merge_era5land_singlelev
└── visualization/maps.py        — mask_ocean, plot_base_map, style_axes_grid,
                                   add_colorbar, add_station_overlay, add_north_arrow
```

### CRITICAL RULES
1. `spatial.py` returns 3 values: `muni_clip, coast_union, muni_land_union = load_vector_data(...)`
2. `mask_ocean()` uses `muni_land_union` NOT `coast_union`
3. No sys.path.insert — library is pip-installed editable
4. Scripts are orchestration only — all logic in src/pr_ngvla/
5. All constants in config.py — never hard-coded in scripts
6. Always run scripts from: `/export/ngvla/cpollack/pr_ngvla/`
7. ERA5-SL time dimension is `valid_time` NOT `time`

---

## PIPELINE (official order — do not deviate)

```bash
# Phase 1
python scripts/phase1_map_temperature.py
python scripts/phase1_map_rh.py
python scripts/phase1_map_tdep.py
python scripts/phase1_map_wind.py
python scripts/phase1_map_precip.py
python scripts/phase1_map_dem.py
python scripts/phase1_map_pwv.py

# Phase 2
python scripts/phase2_exceedance.py --var all
python scripts/phase2_validation.py
python scripts/phase2_map_exceedance.py --var all

# Phase 3A
python scripts/phase3_composite_index.py
python scripts/phase3_map_composite.py
python scripts/phase3_best_regions_report.py --top-pct 25

# Phase 3B (gap-fill)
python scripts/phase3_gapfill_singlelev.py   # LAND_FRAC_THRESHOLD=0.60
python scripts/phase3_map_gapfill.py         # uses gapfill NetCDFs
```

---

## KNOWN BUGS FIXED (do not reintroduce)
Bugs 1–8: See TECHNICAL_CONTINUITY_Mar17_2026.md
Bugs 9–13: See PROJECT_CONTINUITY_Mar23_2026.md

### Bug 14: ERA5-SL files downloaded as ZIP renamed as .nc
- **Symptom:** xarray ValueError — no matching IO backend
- **Cause:** CDS downloaded zip archives with .nc extension
- **Fix:** Extract with zipfile module; instant/accum files renamed separately
- **Files:** `era5sl_hourly_wind_tp_sp_PR_YYYY_MM_instant.nc` and `_accum.nc`

### Bug 15: ERA5-SL time dimension called `valid_time` not `time`
- **Symptom:** KeyError: 'time' in assign_coords
- **Fix:** Use `valid_time` in all ERA5-SL processing

### Bug 16: Marine signal contamination in ERA5-SL gap-fill
- **Symptom:** Arecibo appeared as best region (index=0.5209) — scientifically wrong
- **Cause:** ERA5-SL pixels at lat 18.55° have 35-51% land fraction — mix marine/terrestrial
- **Fix:** Land fraction threshold of 60% applied before gap-fill interpolation
- **Result:** No coastal pixels pass threshold → ERA5-Land pure result used

### Bug 17: Gap-fill composite pixel count collapsed to 2
- **Symptom:** `Original: 59 pixels, After: 2 pixels (-57)`
- **Cause:** PWV from ERA5-SL (4×13 grid) combined with ERA5-Land (9×31 grid)
  via composite_index() — xarray only kept coordinate intersections
- **Fix:** Interpolate PWV to ERA5-Land grid before composite

---

## NOAA ISD STATIONS (5 confirmed)
| Station ID | Name | Location | Coverage |
|---|---|---|---|
| 785140-11603 | Rafael Hernández Airport | Aguadilla NW | 2006–2023 |
| 785145-11653 | Eugenio M. de Hostos Airport | Mayagüez W | 2005–2017 |
| 785260-11641 | Luis Muñoz Marín Intl (SJU) | San Juan NE | 2005–2023 |
| 785265-00494 | Fernando Ribas Dominicci | Isla Grande SJ | 2011–2023 |
| 785350-11630 | Naval Station Roosevelt Roads | Ceiba E | 2004–2023 |

---

## KEY REFERENCES
- Hersbach et al. (2020) — ERA5. QJRMS 146:1999-2049. DOI:10.1002/qj.3803
- Muñoz-Sabater et al. (2021) — ERA5-Land. ESSD 13:4349-4383
- Bell et al. (2021) — ERA5 back-extension. QJRMS 147:4186-4227
- Selina et al. (2020) — ngVLA System Environmental Specification. NRAO
- Linford & Cooper (2023) — ngVLA Memo 117. NRAO
- Bi et al. (2024) — ERA5 for astronomical site characterization. MNRAS 527:4616
- Nikolic et al. (2013) — ALMA WVR and PWV. A&A 552:A104
- Zhang et al. (2019) — ERA5 PWV validation. Radio Science 54:561-571

---

## SERVER INFRASTRUCTURE
- **OS:** OpenSUSE Leap 15.6
- **Conda env:** `pr_ngvla`
- **Project path:** `/export/ngvla/cpollack/pr_ngvla/`
- **Presentations:** `/export/ngvla/cpollack/presentations/presentation_01/`
- **Rule:** NEVER work in home/ — always /export/ngvla/cpollack/
- **Sessions:** tmux (NOT slurm)

---

## NEXT STEPS (immediate)
1. ✅ Mapas finales generados — phase3_composite_annual_gf.png, phase3_composite_monthly_gf.png
2. → Talking points para reunión con asesora (April 10, 10:00 AM)
3. → Poster draft (April 13)
4. → Poster submission (April 18)
5. → Phase 4 Monte Carlo (May 2026)
6. → WRF downscaling para cobertura costera (Phase 5, Jun–Aug 2026)

---

## HOW TO START THE NEW CHAT
Paste this entire file as your first message, then say:
"Continuamos el proyecto ngVLA Puerto Rico."
