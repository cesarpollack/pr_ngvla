# FUTURE_WORK.md
# ngVLA Puerto Rico — Future Work and Coastal Coverage Plan
# Created: April 9, 2026
# Author: César Pollack, UPR Río Piedras
#
# PURPOSE: Document the plan for resolving coastal coverage limitations
# and all future work items. This is the scientific roadmap beyond the
# PRISM poster (April 18, 2026).

---

## CURRENT LIMITATION — Coastal Coverage (Lajas/Guánica)

### What the problem is
ERA5-Land (~9 km resolution) assigns NaN to coastal pixels where the
land fraction within the 9×9 km cell is below an internal ECMWF threshold.
The municipalities most affected are:

| Municipality | Approx. coordinates | Status |
|---|---|---|
| Lajas | −67.05°W, 18.00°N | NaN in ERA5-Land |
| Guánica | −66.93°W, 17.97°N | NaN in ERA5-Land |
| Cabo Rojo (coastal) | −67.15°W, 17.98°N | NaN in ERA5-Land |

These municipalities are scientifically significant because they lie in
the rain shadow of the Cordillera Central — the driest zone in PR —
and are therefore likely candidates for the best ngVLA antenna locations.

### Why ERA5-SL gap-fill did not solve it
ERA5 single-levels (0.25°) was attempted as a gap-fill source. The
nearest ERA5-SL pixel to Lajas/Guánica is at latitude 17.80°N, which
has a maximum land fraction of 24% (76% ocean). Using this pixel
introduces a marine signal bias — artificially low precipitation
exceedance — that distorts the site selection index. With a 60% land
fraction threshold (scientifically defensible), no ERA5-SL pixel
recovers Lajas/Guánica.

### Scientific impact
The SW corridor result is confirmed by adjacent ERA5-Land pixels:
- San Germán (18.1°N): index = 0.5153 ← best annual pixel
- Yauco (18.1°N): index = 0.5136
- Guayanilla (18.1°N): index = 0.5071

These are 10-15 km from Lajas/Guánica and capture the same rain shadow.
The conclusion — SW corridor is most favorable — is robust. The
limitation is that we cannot quantify conditions AT Lajas/Guánica
specifically.

---

## PLANNED SOLUTIONS — Ordered by Priority

### Solution 1 — WRF Dynamical Downscaling ⭐ RECOMMENDED
**Priority:** High | **Timeline:** Phase 5 (post-May 2026)

**What:** Run the WRF (Weather Research and Forecasting) model at
1-3 km resolution over Puerto Rico, using ERA5 as boundary conditions.
WRF resolves individual municipalities, coastlines, and topographic
features at the scale needed to evaluate Lajas, Guánica, Mona Island,
Culebra, and Vieques.

**Why this is the right answer:**
- WRF is the standard approach for high-resolution climate studies
  in the Caribbean
- Multiple WRF studies over PR already exist — methodology is established
- Resolves all coastal municipalities simultaneously
- Can be validated against NOAA ISD stations
- Directly comparable to ERA5 results from this study

**References to search:**
- WRF climate studies in Puerto Rico / Caribbean
- Tropical cyclone downscaling with WRF in the Caribbean
- Search terms: "WRF Puerto Rico climate", "WRF Caribbean downscaling"

**Computational requirements:**
- Requires WRF installation on astroiupi or similar HPC
- ERA5 boundary conditions already downloaded (data_raw/era5/)
- Estimated run time: days to weeks for 20-year simulation

**Poster language:**
> "Future work includes dynamical downscaling using the WRF model at
> 1–3 km resolution to resolve coastal municipalities not captured by
> ERA5-Land. ERA5 boundary conditions for this simulation are already
> available from the current study."

---

### Solution 2 — Custom Land-Sea Mask for ERA5-SL
**Priority:** Medium | **Timeline:** Phase 4 / report (May 2026)

**What:** Instead of using ECMWF's internal land-sea mask, construct a
custom binary mask from the PR municipality shapefile. For each ERA5-SL
pixel, assign the value from the nearest VALID land point (not the
pixel-averaged value that mixes land and ocean).

**Why this could work:**
- Avoids the marine signal contamination problem
- Uses the same ERA5-SL data already downloaded
- Methodologically similar to nearest-neighbor land extraction used
  in other island studies

**Implementation sketch:**
```python
# For each ERA5-SL pixel that intersects PR land:
# Instead of using the pixel value (which mixes land+ocean),
# find the nearest ERA5-Land pixel that IS valid
# and use that as the fill value

# This is essentially a spatial extrapolation from known land points
# rather than a direct ERA5-SL value
```

**Limitation:** This is extrapolation, not independent data.
Must be clearly labeled as such in methodology.

---

### Solution 3 — CHELSA Climate Data (Precipitation + Temperature)
**Priority:** Low for this study | **Timeline:** Future publication

**What:** CHELSA (Climatologies at High Resolution for the Earth's
Land Surface Areas) provides 1 km resolution climate data for
precipitation and temperature derived from ERA5 with statistical
downscaling.

**Available variables:** Precipitation, Tmax, Tmin (monthly means)
**Not available:** RH, PWV, Wind — limiting for ngVLA site selection

**Use case:** Spatial validation of ERA5-Land precipitation patterns
at 1 km resolution. Could replace PRISM as validation dataset since
PRISM PR normals will not be updated.

**Download:** https://chelsa-climate.org/

---

### Solution 4 — In-Situ Weather Station Deployment
**Priority:** High for final site selection | **Timeline:** Phase 6+

**What:** Deploy a portable weather station (similar to ngVLA Memo 117
methodology) at candidate sites in Lajas/Guánica for 6-12 months.
Collect in-situ measurements of all 7 study variables.

**Why this is the definitive answer:**
- Eliminates all reanalysis resolution limitations
- Directly comparable to Memo 117 methodology
- Provides site-specific validation that ERA5 cannot
- Standard practice in radio telescope site characterization

**Precedent:** ngVLA Memo 117 (Linford & Cooper 2023) deployed a
portable weather station at Pohakuloa Training Area, Hawaii.
Same methodology would apply to SW Puerto Rico.

**Requirements:**
- Funding for equipment and deployment
- Site access agreements with landowners in Lajas/Guánica
- Minimum 1 year of continuous data for climatological significance

---

### Solution 5 — ERA5 Pressure Levels + Vertical Interpolation
**Priority:** Low | **Timeline:** Future publication

**What:** Use ERA5 pressure-level data to extract near-surface
conditions using vertical interpolation to the actual surface
elevation from the DEM.

**Why considered:** Could recover coastal pixels by using a level
above the surface and interpolating down.

**Why low priority:** Complex methodology, adds uncertainty,
and WRF downscaling (Solution 1) is more scientifically robust
and already standard in the field.

---

## PHASE 4 AND BEYOND — Full Roadmap

| Phase | Timeline | Goal | Status |
|---|---|---|---|
| 3A | Mar 2026 ✅ | Fuzzy-logic site selection index | Complete |
| 3B | Apr 2026 🔄 | ERA5-SL gap-fill (partial success) | In progress |
| Poster | Apr 18, 2026 | PRISM conference presentation | ← DEADLINE |
| 4 | May 2026 | Monte Carlo uncertainty + sensitivity analysis | Pending |
| 4 | May 2026 | DEM lapse rate downscaling (T, P) | Pending |
| 4 | May 2026 | Hurricane Maria exclusion sensitivity | Pending |
| 5 | Jun–Aug 2026 | WRF downscaling at 1-3 km | Future |
| 6 | TBD | In-situ station deployment | Future |
| 7 | TBD | Final journal publication | Future |

---

## WHAT TO SAY IN THE POSTER — Future Work Section

**Short version (poster):**
> "Coastal municipalities (Lajas, Guánica) were not resolved by ERA5-Land
> at 9 km resolution. Future work includes: (1) dynamical downscaling
> using the WRF model at 1–3 km resolution, and (2) Phase 4 Monte Carlo
> sensitivity analysis of the site selection index weights."

**Extended version (for questions):**
> "ERA5-Land assigns NaN to coastal pixels where land fraction is below
> an internal threshold. An ERA5 single-levels gap-fill was attempted,
> but pixels near Lajas/Guánica have <25% land fraction and introduce
> marine signal contamination. The SW corridor result is confirmed by
> adjacent ERA5-Land pixels in San Germán, Yauco, and Guayanilla —
> municipalities 10-15 km from the unresolved coastal zone that capture
> the same rain shadow pattern. WRF downscaling at 1-3 km is planned
> to resolve individual coastal municipalities in future work."

---

## KEY POINT FOR COMMITTEE AND ADVISOR

The poster presents scientifically valid progress. The limitation
(coastal coverage) is:
1. Fully documented in DECISIONS.md (D08)
2. Does NOT affect the main conclusion (SW corridor is most favorable)
3. Has a clear methodological path forward (WRF)
4. Is consistent with published limitations of ERA5-Land in coastal zones
   (Muñoz-Sabater et al. 2021)

A poster that honestly documents limitations and identifies future work
is stronger than one that glosses over them.
