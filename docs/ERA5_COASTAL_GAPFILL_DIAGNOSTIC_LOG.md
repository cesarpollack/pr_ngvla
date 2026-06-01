# ERA5 Coastal Gap-Fill Diagnostic Log

Project: PR-ngVLA  
Purpose: Diagnose and redesign the coastal gap-fill methodology for Puerto Rico ERA5-Land / ERA5 Single Levels products.

This document records the diagnostic sequence so the workflow does not become circular, undocumented, or driven by preliminary code assumptions.

## Working Rules

1. Do not treat preliminary mapping/gap-fill code as methodological authority.
2. Use old code only as evidence of what was attempted.
3. Do not modify production scripts until the physical/methodological rule is clear.
4. Run one diagnostic step at a time.
5. Each diagnostic must answer a specific question.
6. Stop and document whenever results contradict previous assumptions.
7. Distinguish:
   - visualization masking,
   - analytical land-cell definition,
   - ERA5-Land missing values,
   - ERA5 Single Levels fallback,
   - final site-candidate cells.
8. Candidate cells must be Puerto Rico land cells, not ocean pixels made visible by interpolation.
9. All spatial land-fraction calculations must be done using an area-preserving projection, not raw degree area.

---

## Current Repository State

Initial verified state:

- Repository: `/export/ngvla/cpollack/pr_ngvla`
- Branch: `feat/ghcnh-hourly-download`
- Working tree: clean at the time of initial check
- HEAD: `d32b1e1 Update README for observational raw acquisition stage`
- `data_raw` contained:
  - `dem`
  - `era5`
  - `noaa`
  - `prism`
  - `shapefiles`
  - `usgs`

---

## Diagnostic Tests Completed

### T00 — Repository and raw-data presence check

Question: Are we in the correct repo/branch, and does local ERA5 raw data exist?

Result:

- Correct repo and branch.
- `data_raw/era5` exists.
- Working tree was clean.

Decision:

- Proceed with read-only ERA5 inventory.

---

### T01 — ERA5 local file inventory

Question: What ERA5 products/files exist locally?

Result:

- Total NetCDF files under `data_raw/era5`: 1222.
- First-level NetCDF counts:
  - `hourly`: 480
  - `monthly`: 2
  - `pwv`: 20
  - `singlelev`: 720

Pattern summary:

- ERA5-Land hourly:
  - 240 files `era5land_hourly_t2m_d2m_PR_YYYY_MM.nc`
  - 240 files `era5land_hourly_wind_tp_sp_PR_YYYY_MM.nc`
- ERA5 Single Levels:
  - 240 files `era5sl_hourly_t2m_d2m_PR_YYYY_MM.nc`
  - 240 monthly `instant` files for wind/surface pressure
  - 240 monthly `accum` files for precipitation
- PWV/TCWV:
  - 20 annual files `era5_hourly_tcwv_PR_YYYY.nc`
- Period covered: 2004–2023.

Decision:

- Products are present locally for the project period.
- Proceed to inspect representative NetCDF metadata and missing values.

---

### T02 — Representative NetCDF metadata and missing-value audit

Question: What are the real grid dimensions, coordinates, variables, and missing-value patterns?

Representative sample: January 2020.

Result:

ERA5-Land:

- Grid: 9 lat × 31 lon = 279 cells
- Resolution: approximately 0.1°
- Latitude range: 17.8 to 18.6
- Longitude range: -68.0 to -65.0
- Variables checked:
  - `t2m`
  - `d2m`
  - `u10`
  - `v10`
  - `tp`
  - `sp`
- First timestamp missing values:
  - 211 / 279 missing
  - 68 / 279 valid

ERA5 Single Levels:

- Grid: 4 lat × 13 lon = 52 cells
- Resolution: approximately 0.25°
- Variables checked:
  - `t2m`
  - `d2m`
  - `u10`
  - `v10`
  - `sp`
  - `tp`
- First timestamp missing values:
  - 0 / 52 missing

ERA5 TCWV/PWV:

- Grid: 3 lat × 13 lon = 39 cells
- Resolution: approximately 0.25°
- Variable checked:
  - `tcwv`
- First timestamp missing values:
  - 0 / 39 missing

Decision:

- ERA5-Land contains a large fixed land/ocean mask over the PR bounding box.
- ERA5 Single Levels has complete coverage over its coarser grid.
- Products cannot be merged without explicit target-grid and provenance rules.

---

### T03 — ERA5-Land mask consistency audit

Question: Is the ERA5-Land missing-value mask fixed across time and variables?

Sample: January 2020.

Result:

For `t2m`, `d2m`, `u10`, `v10`, `tp`, `sp`:

- Total cells: 279
- Always valid cells: 68
- Always missing cells: 211
- Mixed-over-time cells: 0

The spatial mask was identical for all variables tested.

Decision:

- The issue is not a temporal download problem.
- The issue is a fixed spatial mask / land-sea representation problem.

---

### T04 — Preliminary code audit

Question: What did the preliminary gap-fill code attempt?

Files inspected:

- `src/pr_ngvla/analysis/gapfill.py`
- `scripts/phase3_gapfill_singlelev.py`
- `scripts/phase3_map_gapfill.py`
- `scripts/phase3_map_composite.py`
- vector/map utilities

Observed preliminary strategy:

- ERA5-Land used where not NaN.
- ERA5 Single Levels interpolated to ERA5-Land grid.
- ERA5-SL used to fill ERA5-Land NaN pixels.
- A land-fraction filter was applied on the ERA5-SL grid before regridding.
- Code used `LAND_FRAC_THRESHOLD = 0.60`.
- Some comments/provenance text still mentioned 40%, creating documentation inconsistency.
- Provenance mask did not fully distinguish all important classes:
  - real ocean,
  - target-grid land but missing in ERA5-Land,
  - partial coastal cell,
  - ERA5-Land source,
  - ERA5-SL interpolated source,
  - filtered/invalid fallback.

Decision:

- Preliminary code is useful as audit evidence only.
- Do not patch it yet.
- First independently define target-grid land/candidate logic.

---

### T05 — ERA5-Land target-grid land-fraction audit

Question: On the ERA5-Land target grid itself, how many cells are actual Puerto Rico land cells?

Method:

- Used TIGER/Line municipalities filtered by `STATEFP == 72`.
- Used a local Albers Equal Area projection centered near Puerto Rico.
- Computed land fraction for each ERA5-Land 0.1° target cell.
- Compared land fraction against ERA5-Land finite/missing mask.

Result:

ERA5-Land target grid:

- Shape: 9 × 31 = 279 cells
- ERA5-Land valid: 68
- ERA5-Land missing: 211

Puerto Rico municipalities:

- Rows: 78
- Bounds:
  - lon min: -67.998751
  - lat min: 17.83151884
  - lon max: -65.16850796
  - lat max: 18.5680123

Target-grid land-fraction counts:

- `land_frac > 0.00`: 158 cells
- `land_frac >= 0.10`: 143 cells
- `land_frac >= 0.25`: 133 cells
- `land_frac >= 0.50`: 121 cells
- `land_frac >= 0.60`: 112 cells
- `land_frac >= 0.75`: 100 cells
- `land_frac >= 0.90`: 89 cells

Cross-check ERA5-Land validity:

| Land-fraction bin | Total | ERA5-Land valid | ERA5-Land missing |
|---:|---:|---:|---:|
| 0 | 121 | 0 | 121 |
| 0–0.10 | 15 | 0 | 15 |
| 0.10–0.25 | 10 | 0 | 10 |
| 0.25–0.50 | 12 | 0 | 12 |
| 0.50–0.60 | 9 | 0 | 9 |
| 0.60–0.75 | 12 | 0 | 12 |
| 0.75–0.90 | 11 | 1 | 10 |
| >=0.90 | 89 | 67 | 22 |

Key findings:

- ERA5-Land missing but target-grid `land_frac >= 0.60`: 44 cells
- ERA5-Land missing but `0 < land_frac < 0.60`: 46 cells
- ERA5-Land valid but `land_frac < 0.50`: 0 cells

Decision:

- The real target-grid issue is not all 211 ERA5-Land NaNs.
- At a 60% target-cell land threshold, only 44 NaN cells are strong land-cell recovery candidates.
- The analytical target grid would contain 112 land cells at `land_frac >= 0.60`.
- This differs from the preliminary Phase 3 statement of 96 land pixels; that discrepancy must be investigated before any code rewrite.

---

## Current Provisional Conclusions

1. ERA5-Land mask is fixed, not temporally inconsistent.
2. ERA5-Land valid cells are strongly terrestrial according to TIGER/Line land fraction.
3. Many ERA5-Land NaNs are ocean or partial coastal cells and should not automatically be filled.
4. A physically defensible gap-fill must operate on the ERA5-Land target grid, not only on the ERA5-SL source grid.
5. The target-grid land-fraction threshold is a methodological decision and must be explicit.
6. The preliminary code likely over-simplifies provenance and may have inconsistent documentation.
7. The discrepancy between 96 preliminary land pixels and 112 target-grid cells at land fraction >= 0.60 is now a priority diagnostic item.

---

## Open Questions

### O01 — Why did the preliminary Phase 3 output/report state 96 land pixels?

Need compare:

- raw ERA5-Land target-grid mask,
- Phase 2 exceedance products,
- Phase 3 gap-filled outputs,
- provenance mask,
- target-grid land-fraction classification.

### O02 — What target-grid land-fraction threshold should define analytical land cells?

Candidate thresholds to evaluate:

- >=0.50
- >=0.60
- >=0.75
- >=0.90

The threshold must be chosen for methodological defensibility, not to force a desired map.

### O03 — For each variable, should ERA5-SL be used as fallback?

Needs variable-specific decision:

- RH: derived from t2m/d2m
- wind: u10/v10
- precipitation: tp accumulation conventions
- PWV: only ERA5-SL/TCWV source, not ERA5-Land
- surface pressure: support variable only

### O04 — Should coastal gap-fill be analytical or visual only?

Must distinguish:

- visualization continuity,
- site-candidate ranking,
- final scientific interpretation.

---

## Next Planned Diagnostic

Compare existing Phase 2 and Phase 3 output masks against the independent target-grid land-fraction audit.

Purpose:

- determine where the preliminary 96-pixel result came from,
- verify whether current outputs are based on source-grid land fraction, target-grid land fraction, plotting mask, or another implicit rule,
- avoid patching old code before understanding the discrepancy.


---

### T06 — Inventory of existing Phase 2 / Phase 3 outputs

Question: Which existing output NetCDF files should be compared against the independent ERA5-Land target-grid land-fraction audit?

Result:

Relevant files found:

Phase 2 exceedance outputs:

- `outputs/phase2/precip_exceedance_climatology.nc`
- `outputs/phase2/pwv_exceedance_climatology.nc`
- `outputs/phase2/rh_exceedance_climatology.nc`
- `outputs/phase2/wind_exceedance_climatology.nc`

Phase 3 non-gap-filled composite outputs:

- `outputs/phase3/composite_index_annual.nc`
- `outputs/phase3/composite_index_monthly.nc`

Phase 3 gap-filled outputs:

- `outputs/phase3/gapfill/rh_exceedance_gapfilled.nc`
- `outputs/phase3/gapfill/wind_exceedance_gapfilled.nc`
- `outputs/phase3/gapfill/precip_exceedance_gapfilled.nc`
- `outputs/phase3/gapfill/pwv_exceedance_gapfilled.nc`
- `outputs/phase3/gapfill/composite_index_annual_gf.nc`
- `outputs/phase3/gapfill/composite_index_monthly_gf.nc`
- `outputs/phase3/gapfill/provenance_mask.nc`
- `outputs/phase3/gapfill/gapfill_report.txt`

Decision:

- Proceed to compare masks from:
  1. an original Phase 2 ERA5-Land exceedance product,
  2. the Phase 3 gap-filled product,
  3. the Phase 3 provenance mask,
  4. the independently computed target-grid land-fraction mask.

Next diagnostic:

T07 — Compare Phase 2 / Phase 3 / provenance masks against target-grid land-fraction classes.

Purpose:

- determine where the preliminary 96-pixel result came from,
- identify whether the gap-fill result was controlled by ERA5-SL source-grid land fraction, target-grid land fraction, or another implicit mask,
- decide whether old Phase 3 outputs should be discarded and regenerated under a cleaner rule.


---

### T07 — Compare Phase 2 / Phase 3 / provenance masks against target-grid land fraction

Question: Where does the preliminary 96-pixel result come from: Phase 2 mask, Phase 3 composite, gap-filled products, provenance mask, or another implicit rule?

Result:

Independent target-grid land fraction:

- `land_frac >= 0.50`: 121 cells
- `land_frac >= 0.60`: 112 cells
- `land_frac >= 0.75`: 100 cells
- `land_frac >= 0.90`: 89 cells
- `land_frac >= 0.60` but raw ERA5-Land missing: 44 cells

Current output mask counts:

- Raw ERA5-Land valid cells: 68
- Phase 2 RH valid cells: 68
- Phase 3 non-gap-filled annual composite valid cells: 59
- Gap-filled RH valid cells: 68
- Gap-filled wind valid cells: 68
- Gap-filled precipitation valid cells: 68
- Gap-filled PWV valid cells: 155
- Gap-filled annual composite valid cells: 59
- Provenance valid/nonzero cells: 68

Provenance flag counts:

- `0`: 211 cells
- `1`: 68 cells
- No `2` cells were present.

Comparison against `land_frac >= 0.60`:

- Raw ERA5-Land covers 68 / 112 target land cells.
- Phase 2 RH covers 68 / 112 target land cells.
- Gap-filled RH/wind/precip still cover only 68 / 112 target land cells.
- Provenance covers only 68 / 112 target land cells.
- Gap-filled composite covers only 59 / 112 target land cells.
- Gap-filled composite has 0 valid cells outside `land_frac >= 0.60`.

Key interpretation:

- The current Phase 3 gap-filled products did not actually recover RH, wind, or precipitation coastal cells.
- The provenance mask confirms this because it contains only ERA5-Land source cells and no ERA5-SL gap-fill source cells.
- The current annual gap-filled composite is not a 96-pixel product; it has only 59 valid cells.
- The previously documented 96-pixel result is not represented in the current NetCDF outputs inspected here.
- The 59-cell composite appears to be the intersection of the 68 ERA5-Land cells for RH/wind/precip with the PWV mask after interpolation/regridding.

Decision:

- Treat current Phase 3 gap-filled outputs as preliminary and not scientifically reliable for final site ranking.
- Do not patch map scripts first.
- Redesign the analytical mask/provenance/gap-fill rule before regenerating Phase 3 outputs.
- The next diagnostic should identify why RH/wind/precip ERA5-SL fallback produced no recovered cells, but only if this helps design the corrected method. It should not become a rabbit hole.

Next methodological direction:

- Define the target analytical grid first.
- Use ERA5-Land grid as the target grid.
- Define Puerto Rico land cells by target-cell land fraction.
- Keep ERA5-Land values where available.
- For target land cells where ERA5-Land is missing, evaluate whether ERA5-SL fallback is scientifically acceptable by variable.
- Produce a complete provenance mask with at least:
  - ocean/no Puerto Rico land,
  - partial land below analytical threshold,
  - ERA5-Land source,
  - ERA5-SL fallback source,
  - target land cell still unresolved.


---

### T08 — ERA5-SL fallback feasibility on target-grid strong-land missing cells

Question: Can ERA5 Single Levels produce interpolated values on the 44 strong-land cells where ERA5-Land is missing?

Definition:

- Target grid: ERA5-Land 0.1° grid.
- Strong land cell: target-grid cell with `land_frac >= 0.60`.
- Strong-land missing cell: `land_frac >= 0.60` and ERA5-Land value is NaN.

Result:

- ERA5-Land raw valid cells: 68
- Target land cells with `land_frac >= 0.60`: 112
- Strong-land missing cells: 44

ERA5-SL interpolation to the ERA5-Land target grid covered:

- `t2m`: 44 / 44 strong-land missing cells
- `d2m`: 44 / 44 strong-land missing cells
- `u10`: 44 / 44 strong-land missing cells
- `v10`: 44 / 44 strong-land missing cells
- `sp`: 44 / 44 strong-land missing cells
- `tp`: 44 / 44 strong-land missing cells

ERA5-SL interpolation also covered:

- 112 / 112 target cells with `land_frac >= 0.60`

Decision:

- ERA5-SL fallback is technically feasible for RH, wind, precipitation, and surface pressure on the 44 strong-land cells missing in ERA5-Land.
- The previous Phase 3 gap-fill failure was not caused by lack of ERA5-SL spatial coverage for these variables.
- The corrected method should apply fallback on the ERA5-Land target grid after defining the analytical land mask.
- Do not use the old Phase 3 outputs as scientific products.

Important remaining issue:

- PWV/TCWV was not tested in T08.
- T07 showed that the current PWV gap-filled product covered only 91 / 112 target land cells and had many valid cells outside the target land mask.
- PWV coverage must be diagnosed before defining the corrected composite index.

Next diagnostic:

T09 — Test TCWV/PWV coverage on the same target-grid land mask.

Purpose:

- determine whether the 21 missing target land cells in PWV are caused by the smaller TCWV latitude coverage, interpolation edge effects, file extent, or the old processing logic.


---

### T09 — PWV/TCWV coverage on the ERA5-Land target mask

Question: Why does PWV not cover all 112 target-grid cells with `land_frac >= 0.60`?

Result:

Target ERA5-Land grid:

- Shape: 9 × 31 = 279 cells
- Latitude range: 17.8 to 18.6
- Longitude range: -68.0 to -65.0
- Raw ERA5-Land valid cells: 68
- Target cells with `land_frac >= 0.60`: 112
- Strong-land missing cells: 44

Raw TCWV source file inspected:

- File: `data_raw/era5/pwv/era5_hourly_tcwv_PR_2020.nc`
- Shape: 3 latitude × 13 longitude
- Latitude values: `[18.5, 18.25, 18.0]`
- Longitude range: -68.0 to -65.0
- Finite cells in raw source: 39 / 39

Raw TCWV interpolation to ERA5-Land target grid:

- Linear interpolation finite on all target cells: 155 / 279
- Linear interpolation finite on `target60`: 91 / 112
- Linear interpolation finite on strong-land missing cells: 32 / 44
- Nearest interpolation produced the same coverage counts.

Target60 cells missing after linear TCWV interpolation:

- 21 cells were missing.
- Missing cells occur on the southern target rows, especially `lat=18.00` and `lat=17.90`.
- These cells are outside, or effectively at/outside, the usable southern latitude extent of the current TCWV source grid.

Additional observation:

- The diagnostic crashed when comparing `phase2_pwv` directly to the ERA5-Land target mask because `phase2_pwv` is still on the native PWV grid shape 3 × 13, while the target mask is 9 × 31.
- This confirms that PWV products require explicit regridding before mask comparison.

Decision:

- The current PWV/TCWV raw acquisition is spatially too narrow for a corrected 112-cell ERA5-Land target-grid composite.
- PWV is the current limiting variable for the corrected composite.
- Do not patch the composite map to hide this.
- Inspect the PWV download/configuration next to determine whether the raw TCWV product should be re-downloaded with a slightly wider bounding box.

Next diagnostic:

T10 — Inspect PWV download script and configuration.

Purpose:

- identify the latitude/longitude request box used for TCWV,
- determine whether the missing southern coverage is caused by the requested CDS area,
- design a minimal corrected PWV acquisition if needed.


---

### T10 — Inspection of ERA5 Single Levels TCWV/PWV download configuration

Question: Does the ERA5 Single Levels TCWV/PWV raw download configuration explain the missing PWV values over southern Puerto Rico after regridding to the ERA5-Land target grid?

Files inspected:

- `scripts/download_era5_pwv_pr.py`
- `src/pr_ngvla/config.py`
- `docs/ERA5_LOCAL_DATA_INVENTORY_2004_2023.md`

Findings:

1. `scripts/download_era5_pwv_pr.py` defines the TCWV/PWV download area internally:

        AREA_PR = [18.6, -68.0, 17.8, -65.0]

2. The CDS request uses this hard-coded area directly:

        "area": AREA_PR

3. The script does not import `ERA5_BBOX` from `src/pr_ngvla/config.py`.

4. The project configuration defines the same standard Puerto Rico bbox:

        PR_BBOX_S = 17.8
        PR_BBOX_W = -68.0
        PR_BBOX_N = 18.6
        PR_BBOX_E = -65.0
        ERA5_BBOX = [PR_BBOX_N, PR_BBOX_W, PR_BBOX_S, PR_BBOX_E]

5. The local ERA5 inventory documents TCWV/PWV as downloaded with bbox:

        [18.6, -68.0, 17.8, -65.0]

Interpretation:

The inspected TCWV/PWV download configuration is consistent with the missing southern PWV coverage observed in T09. ERA5 Single Levels TCWV is on a 0.25 degree grid. With a southern request boundary of 17.8 degrees, the retrieved latitude rows can include 18.50, 18.25, and 18.00, but not 17.75. Therefore, target ERA5-Land cells near the southern part of Puerto Rico can fall outside the TCWV interpolation domain.

Preliminary decision:

The PWV/TCWV gap should be treated as a raw-data spatial coverage problem, not as a composite-map plotting problem. Do not patch the composite output. The next methodological step should be to define a slightly expanded TCWV/PWV download bounding box and then redownload/verify TCWV before rerunning downstream PWV regridding.

No production code was edited in T10.


---

### T11 — Downstream references to PWV/TCWV raw files and variables

Question: Which scripts and documents currently depend on the existing ERA5 Single Levels TCWV/PWV raw-file path, filename pattern, or variable naming?

Command used:

        grep -RInE "era5_hourly_tcwv_PR|data_raw/era5/pwv|ERA5_PWV_DIR|total_column_water_vapour|tcwv|phase2_pwv|PWV|pwv" scripts src docs | sed -n '1,260p'

Key findings:

1. `scripts/download_era5_pwv_pr.py` writes annual TCWV files to:

        data_raw/era5/pwv/
        era5_hourly_tcwv_PR_YYYY.nc

2. `src/pr_ngvla/data/loaders.py` searches for the fixed filename pattern:

        era5_hourly_tcwv_PR_*.nc

3. `src/pr_ngvla/data/era5.py` opens yearly PWV files using the fixed filename:

        era5_hourly_tcwv_PR_{year}.nc

4. `src/pr_ngvla/analysis/exceedance.py` also constructs yearly PWV filenames using:

        era5_hourly_tcwv_PR_{year}.nc

5. Several Phase 1 / Phase 2 / Phase 3 scripts consume PWV/TCWV directly or indirectly, including:

        scripts/phase1_map_pwv.py
        scripts/phase2_exceedance.py
        scripts/phase2_map_exceedance.py
        scripts/phase3_composite_index.py
        scripts/phase3_gapfill_singlelev.py
        scripts/phase3_map_composite.py
        scripts/phase3_best_regions_report.py

6. `scripts/run_all_downloads.sh` contains an old `tmux`-based PWV download workflow. This should not be used for the current correction because the project has moved away from `tmux` for long jobs.

Interpretation:

The TCWV/PWV correction cannot be treated as an isolated raw-download change only. Multiple downstream scripts assume the existing PWV directory and filename pattern. Therefore, overwriting or renaming the current TCWV files without a controlled transition could introduce regressions.

Preliminary decision:

Preserve the existing TCWV/PWV raw files as diagnostic evidence of the too-narrow spatial request. The corrected acquisition should be designed so that it is traceable, reproducible, and does not silently overwrite the old files. Before editing production code, inspect the exact PWV loaders and exceedance code paths to decide whether the safest strategy is:

- a new corrected raw subdirectory,
- a new filename suffix,
- or a minimal update to the central PWV download and loader logic.

No production code was edited in T11.


---

### T12 — Exact PWV loader and exceedance code paths

Question: How rigidly are the current PWV/TCWV downstream scripts tied to the existing raw directory and filename pattern?

Files inspected:

- `src/pr_ngvla/config.py`
- `scripts/download_era5_pwv_pr.py`
- `src/pr_ngvla/data/era5.py`
- `src/pr_ngvla/data/loaders.py`
- `src/pr_ngvla/analysis/exceedance.py`

Findings:

1. The default PWV raw directory is configured as:

        ERA5_PWV_DIR = ERA5_DIR / "pwv"

2. The downloader supports a CLI output directory:

        --outdir

This means corrected TCWV/PWV files can be downloaded to a separate directory without overwriting the existing raw files.

3. The downloader does not currently expose the CDS area/bounding box as a CLI argument. The spatial request is still controlled by the hard-coded `AREA_PR` constant inspected in T10.

4. `src/pr_ngvla/data/era5.py` opens yearly PWV files using:

        filepath = data_dir / f"era5_hourly_tcwv_PR_{year}.nc"

The function accepts a `data_dir` parameter, but its default is `ERA5_PWV_DIR`.

5. `src/pr_ngvla/data/loaders.py` accepts a `pwv_dir` argument, but still searches for the fixed filename pattern:

        era5_hourly_tcwv_PR_*.nc

6. `src/pr_ngvla/analysis/exceedance.py` constructs PWV paths directly from:

        ERA5_PWV_DIR / f"era5_hourly_tcwv_PR_{year}.nc"

Therefore, the main exceedance workflow currently points to the default PWV directory unless the code or configuration is changed.

Interpretation:

The current code base allows a safe corrected acquisition directory through `--outdir`, but it does not yet allow a corrected TCWV spatial request without editing the downloader. Downstream code is partially flexible at the loader level, but the exceedance workflow is still tied to `ERA5_PWV_DIR` and the fixed yearly filename pattern.

Preliminary decision:

Do not overwrite the existing TCWV/PWV raw files. The safer correction path is:

1. preserve `data_raw/era5/pwv/` as the original too-narrow TCWV acquisition;
2. add a minimal, explicit way for `scripts/download_era5_pwv_pr.py` to request a corrected/buffered TCWV bbox;
3. download corrected TCWV files into a separate traceable directory;
4. verify the corrected latitude/longitude grid before any downstream recomputation;
5. only after verification decide how to switch the exceedance/composite workflow to the corrected PWV source.

No production code was edited in T12.


---

### T13 — Grid coverage needed for corrected TCWV/PWV acquisition

Question: What TCWV/PWV spatial coverage is needed to support interpolation onto the ERA5-Land target grid without losing southern Puerto Rico cells?

Files inspected:

- `data_raw/era5/pwv/era5_hourly_tcwv_PR_2020.nc`
- representative ERA5-Land hourly file: `data_raw/era5/hourly/era5land_hourly_t2m_d2m_PR_2020_01.nc`

Findings:

1. The existing TCWV/PWV raw file has latitude rows:

        18.50, 18.25, 18.00

and longitude columns from:

        -68.00 to -65.00

with shape:

        3 x 13

2. The representative ERA5-Land target grid has latitude rows:

        18.60, 18.50, 18.40, 18.30, 18.20, 18.10, 18.00, 17.90, 17.80

and longitude columns from:

        -68.00 to -65.00

with shape:

        9 x 31

3. The current TCWV request bbox:

        [18.6, -68.0, 17.8, -65.0]

is expected to produce only the rows:

        18.50, 18.25, 18.00

and does not include the 17.75 row.

4. A minimal south-only correction:

        [18.6, -68.0, 17.75, -65.0]

is expected to include:

        18.50, 18.25, 18.00, 17.75

This would address the immediate southern missing-row problem.

5. A stronger south-only buffer:

        [18.6, -68.0, 17.50, -65.0]

is expected to include:

        18.50, 18.25, 18.00, 17.75, 17.50

6. A buffered bbox on all sides:

        [18.75, -68.25, 17.50, -64.75]

is expected to include latitude rows:

        18.75, 18.50, 18.25, 18.00, 17.75, 17.50

and longitude columns:

        -68.25 to -64.75

with expected shape:

        6 x 15

Interpretation:

The missing PWV coverage over southern Puerto Rico is explained by insufficient TCWV latitude coverage in the original raw acquisition. The current TCWV file starts at 18.00 degrees southward, while the ERA5-Land target grid extends to 17.80 degrees. Linear interpolation cannot safely fill target cells below the southernmost source latitude.

The diagnostic also shows that the ERA5-Land target grid extends north to 18.60 degrees, while the current TCWV source grid reaches only 18.50 degrees. Even if the observed missing target60 cells were concentrated in the south, a robust corrected TCWV acquisition should avoid interpolation-edge limitations on all sides.

Preliminary decision:

For a corrected TCWV/PWV acquisition, prefer a small interpolation buffer around the Puerto Rico analysis domain rather than only changing the southern boundary. The buffered acquisition bbox:

        [18.75, -68.25, 17.50, -64.75]

is methodologically preferable because it provides native ERA5 0.25-degree support around the ERA5-Land target grid. This does not expand the final analysis region; it only supplies interpolation support. The final analysis mask should remain restricted to the Puerto Rico target domain.

No production code was edited in T13.


---

### T14 — Pre-edit anti-regression check for corrected TCWV/PWV acquisition

Question: Is the repository in a safe state before editing the ERA5 Single Levels TCWV/PWV downloader?

Files inspected:

- `scripts/download_era5_pwv_pr.py`

Commands inspected:

- `git status --short`
- `git branch --show-current`
- `git --no-pager log --oneline -5`
- full contents of `scripts/download_era5_pwv_pr.py`

Findings:

1. The active branch is:

        feat/ghcnh-hourly-download

2. The latest commit is:

        d32b1e1 Update README for observational raw acquisition stage

3. There are no modified production scripts or source files before editing.

4. The working tree contains untracked diagnostic documentation files:

        docs/ERA5_COASTAL_GAPFILL_DIAGNOSTIC_LOG.md
        docs/ERA5_COASTAL_GAPFILL_DIAGNOSTIC_LOG.md.bak_*

These should not be confused with production-code changes.

5. The current TCWV/PWV downloader is compact and has only two CLI options:

        --years
        --outdir

6. The TCWV/PWV spatial request is not configurable from the command line. It is still controlled by the hard-coded constant:

        AREA_PR = [18.6, -68.0, 17.8, -65.0]

7. The CDS request is built by `build_request(year)` and uses:

        "area": AREA_PR

8. The yearly filename pattern is:

        era5_hourly_tcwv_PR_YYYY.nc

Interpretation:

The repository is safe for a minimal targeted edit because no production code is currently modified. However, the diagnostic log and backup files are untracked and should be handled deliberately before the final commit. The downloader is the appropriate central place to make the TCWV/PWV spatial request configurable.

Preliminary decision:

Proceed with a minimal edit to `scripts/download_era5_pwv_pr.py` that preserves default behavior but allows an explicit corrected/buffered TCWV/PWV acquisition. The corrected acquisition should be written to a separate output directory first, not used to overwrite the original `data_raw/era5/pwv/` files.

Recommended corrected TCWV/PWV bbox from T13:

        [18.75, -68.25, 17.50, -64.75]

No production code was edited in T14.


---

### T15 — Validation of patched TCWV/PWV downloader without CDS download

Question: Did the patched `scripts/download_era5_pwv_pr.py` preserve default behavior while adding an explicit buffered Puerto Rico bbox option?

File inspected:

- `scripts/download_era5_pwv_pr.py`

Validation method:

The script was inspected using Python AST and string checks. No CDS request was made and no data were downloaded.

Findings:

1. The original/default Puerto Rico bbox remains:

        AREA_PR = [18.6, -68.0, 17.8, -65.0]

2. The corrected buffered bbox is present:

        AREA_PR_BUFFERED_FOR_INTERPOLATION = [18.75, -68.25, 17.5, -64.75]

3. The default output directory remains:

        data_raw/era5/pwv

4. The ERA5 dataset and variable remain:

        reanalysis-era5-single-levels
        total_column_water_vapour

5. The patched request path is present:

        def build_request(year: int, area: list[float]) -> dict:
        "area": area

6. The patched yearly download path is present:

        def download_year(..., area: list[float], ...)
        client.retrieve(DATASET, build_request(year, area), str(target))

7. The new CLI option is present:

        --buffered-pr

8. The main function chooses the bbox explicitly:

        area = AREA_PR_BUFFERED_FOR_INTERPOLATION if args.buffered_pr else AREA_PR

9. The download loop passes the selected area:

        result = download_year(client, year, args.outdir, area)

Interpretation:

The downloader patch is behavior-preserving by default. Existing calls without `--buffered-pr` still use the original project bbox. The corrected buffered acquisition is only activated explicitly with `--buffered-pr`.

Decision:

The patch is technically safe to keep. The next step should be to run a controlled corrected TCWV/PWV acquisition into a separate output directory, not into the original `data_raw/era5/pwv/` directory.

No CDS download was performed in T15.


---

### T16 — Controlled one-year corrected TCWV/PWV acquisition test

Question: Can the patched TCWV/PWV downloader retrieve one corrected buffered year without overwriting the original PWV raw files?

Command used:

        python scripts/download_era5_pwv_pr.py --years 2020 --outdir data_raw/era5/pwv_buffered_pr --buffered-pr

Output directory:

        data_raw/era5/pwv_buffered_pr

Log file:

        logs/download_pwv_buffered_pr_2020_test.log

Findings:

1. The downloader used the corrected buffered bbox:

        [18.75, -68.25, 17.5, -64.75]

2. The downloader wrote to the corrected separate directory:

        data_raw/era5/pwv_buffered_pr

3. The original PWV directory was not overwritten.

4. The CDS request was accepted, ran successfully, and downloaded:

        era5_hourly_tcwv_PR_2020.nc

5. The final downloader summary was:

        SUMMARY: 1 downloaded, 0 failed

Connection note:

The SSH client connection reset while the foreground job was running. Because the job had been launched directly in the terminal rather than via `systemd-run --user`, this was not the preferred workflow. However, inspection after reconnecting showed that the 2020 file was successfully downloaded and is readable.

Post-download verification:

The downloaded file exists:

        data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc

File size:

        2088606 bytes

`xarray.open_dataset()` succeeded.

Dataset dimensions:

        valid_time: 8784
        latitude: 6
        longitude: 15

Latitude rows:

        18.75, 18.50, 18.25, 18.00, 17.75, 17.50

Longitude columns:

        -68.25, -68.00, -67.75, -67.50, -67.25, -67.00, -66.75, -66.50,
        -66.25, -66.00, -65.75, -65.50, -65.25, -65.00, -64.75

Interpretation:

The corrected buffered acquisition worked for the 2020 test year. The file has the expected 6 x 15 ERA5 Single Levels native grid, including the southern support rows needed for interpolation over the ERA5-Land target grid.

Important workflow correction:

Future CDS/ECMWF jobs or other long/remote-dependent jobs should not be launched directly in the foreground over SSH. Use `systemd-run --user` with explicit logs under the project directory. Also, before the full 2004–2023 run, the downloader should be made more verification-aware so that an existing partial/corrupt file is not blindly skipped.

Decision:

Do not redownload 2020. It is complete and valid. The next diagnostic should test whether this corrected 2020 TCWV file eliminates the PWV interpolation coverage gap over the ERA5-Land target grid.


---

### T17 — Verification of corrected buffered TCWV/PWV interpolation coverage

Question: Does the corrected buffered TCWV/PWV 2020 file eliminate the PWV interpolation coverage gap on the ERA5-Land target grid?

Files inspected:

- Original TCWV/PWV file:
        data_raw/era5/pwv/era5_hourly_tcwv_PR_2020.nc

- Corrected buffered TCWV/PWV file:
        data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc

- Representative ERA5-Land target grid:
        data_raw/era5/hourly/era5land_hourly_t2m_d2m_PR_2020_01.nc

ERA5-Land target grid:

        latitude rows: 18.6 to 17.8
        longitude columns: -68.0 to -65.0
        shape: 9 x 31
        total target cells: 279

Original too-narrow TCWV/PWV 2020:

        source latitude rows: 18.50, 18.25, 18.00
        source longitude columns: -68.00 to -65.00
        source shape: 3 x 13

Linear interpolation onto the ERA5-Land target grid:

        finite target cells: 155 / 279
        missing target cells: 124

Corrected buffered TCWV/PWV 2020:

        source latitude rows: 18.75, 18.50, 18.25, 18.00, 17.75, 17.50
        source longitude columns: -68.25 to -64.75
        source shape: 6 x 15

Linear interpolation onto the ERA5-Land target grid:

        finite target cells: 279 / 279
        missing target cells: 0

Interpretation:

The corrected buffered TCWV/PWV acquisition fully covers the ERA5-Land target grid after linear interpolation. This confirms that the earlier PWV gap was caused by insufficient spatial coverage in the original raw TCWV/PWV acquisition, not by the composite map itself.

Decision:

The buffered TCWV/PWV acquisition strategy is validated for 2020. The corrected bbox:

        [18.75, -68.25, 17.50, -64.75]

should be used for the full corrected TCWV/PWV acquisition. The final analysis region must still remain restricted to the Puerto Rico target grid/mask; the buffered bbox is only interpolation support.

Before launching the full 2004–2023 acquisition, improve or verify the downloader's handling of existing files so that partial/corrupt NetCDF files are not blindly skipped.

No additional production code was edited in T17.


---

### T18 — Verification-aware TCWV/PWV downloader patch

Question: Can the TCWV/PWV downloader safely resume/reuse existing files without blindly skipping partial, corrupt, or wrong-grid NetCDF files?

File edited:

- `scripts/download_era5_pwv_pr.py`

Patch summary:

1. Added imports needed for file validation:

        datetime
        numpy
        xarray

2. Added expected ERA5 native-grid coordinate calculation for a CDS area request:

        expected_era5_native_coords(area)

3. Added longitude normalization for validation:

        normalize_longitudes(lons)

4. Added NetCDF validation before skipping or accepting files:

        validate_tcwv_file(filepath, area)

5. Added invalid-file quarantine behavior:

        quarantine_invalid_file(filepath, reason)

6. Changed existing-file behavior from blind skip to validation-aware skip:

        SKIP only if the existing file opens correctly,
        contains TCWV,
        has valid time,
        and has latitude/longitude coordinates matching the requested area.

7. Changed post-download behavior so that a downloaded file is validated immediately before being accepted.

8. If an existing or downloaded file fails validation, it is moved aside with an `.invalid_YYYYMMDDTHHMMSSZ` suffix instead of being silently reused.

First validation attempt:

The first implementation incorrectly expected the NetCDF data variable to be named:

        total_column_water_vapour

Observed issue:

Existing ERA5 Single Levels TCWV NetCDF files store the variable as:

        tcwv

Therefore, the first validation attempt failed for both the original and buffered valid files.

Correction applied:

The validation now accepts either:

        tcwv

or:

        total_column_water_vapour

This matches the fact that the CDS request uses the long variable name, while the resulting NetCDF commonly stores the GRIB short name.

Final validation results:

1. Original file with original/default bbox:

        data_raw/era5/pwv/era5_hourly_tcwv_PR_2020.nc
        expected result: valid
        observed result: valid
        time=8784, lat=3, lon=13

2. Buffered file with buffered bbox:

        data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc
        expected result: valid
        observed result: valid
        time=8784, lat=6, lon=15

3. Buffered file checked against original/default bbox:

        data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc
        expected result: invalid
        observed result: invalid
        reason: latitude mismatch

Interpretation:

The downloader is now safer for resumable corrected TCWV/PWV acquisition. It will not blindly skip an existing file simply because the filename exists. It verifies that the existing file matches the requested spatial grid before reuse.

Decision:

The validation-aware patch is technically successful. Before launching the full 2004–2023 corrected buffered acquisition, one remaining minor issue should be considered: the final summary counter may not distinguish newly downloaded files from valid skipped files. This does not affect data integrity, but it can affect logging clarity.

No CDS download was performed in T18.


---

### T19 — Summary-counter correction for verification-aware TCWV/PWV downloader

Question: Does the TCWV/PWV downloader clearly distinguish newly downloaded files from valid existing files that are safely skipped?

File edited:

- `scripts/download_era5_pwv_pr.py`

Patch summary:

1. Changed `download_year(...)` return type from:

        Path | None

to:

        tuple[str, Path | None]

2. The possible status values are now:

        downloaded
        skipped
        failed

3. Existing valid files now return:

        ("skipped", target)

4. Successfully downloaded and validated files now return:

        ("downloaded", target)

5. Failed downloads or failed validation now return:

        ("failed", None)

6. The final summary now reports:

        downloaded
        skipped_valid_existing
        failed

Validation performed:

A no-download status test was run using the already validated buffered 2020 file:

        data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc

The test called `download_year(...)` with `client=None`. This is safe because a valid existing file should return before any CDS client request is attempted.

Observed result:

        SKIP (valid existing): data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc
        status: skipped
        Summary-counter behavior test: OK

Interpretation:

The downloader can now safely support resumable corrected TCWV/PWV acquisition. Existing valid files are not redownloaded, invalid files are not blindly reused, and the final log summary will distinguish valid skips from new downloads.

Decision:

The downloader is ready for a controlled full corrected buffered TCWV/PWV acquisition using `systemd-run --user`, with logs written under the project directory. The original foreground SSH workflow should not be used for the full run.

No CDS download was performed in T19.


---

### T20 — Preflight for full corrected buffered TCWV/PWV acquisition

Question: Is the server environment ready to launch the full corrected buffered TCWV/PWV acquisition using `systemd-run --user`?

Preflight results:

1. Git state showed the expected modified downloader:

        M scripts/download_era5_pwv_pr.py

   The diagnostic log and backup files were untracked. This is expected during the diagnostic stage.

2. Downloader syntax check passed:

        py_compile: OK

3. `systemd-run` was available:

        /usr/bin/systemd-run

4. The user systemd state was suitable for long jobs:

        RuntimePath=/run/user/33125
        State=active
        Linger=yes
        systemctl --user is-system-running: running

5. A simple `systemd-run --user` smoke test completed successfully:

        Finished with result: success
        code=exited/status=0

6. Current corrected buffered PWV inventory contained one file:

        era5_hourly_tcwv_PR_2020.nc

7. The downloader validator confirmed the 2020 corrected buffered file is valid:

        valid TCWV file: time=8784, lat=6, lon=15

T20B result:

An initial dry-run attempt using `systemd-run --user` without explicit conda activation failed with:

        code=exited/status=127

Interpretation:

The user service did not inherit the interactive conda environment. This confirmed that long jobs should explicitly activate conda inside the `systemd-run` service command.

T20C result:

A corrected dry-run was launched with explicit conda activation:

        source /export/ngvla/cpollack/miniconda3/bin/activate
        conda activate pr_ngvla

The service used the correct Python:

        /export/ngvla/cpollack/miniconda3/envs/pr_ngvla/bin/python
        Python 3.11.15

Required imports succeeded:

        cdsapi
        numpy
        xarray

The CDS configuration file was visible:

        cdsapirc_exists: True

The downloader dry-run for 2020 succeeded without downloading:

        SKIP (valid existing): data_raw/era5/pwv_buffered_pr/era5_hourly_tcwv_PR_2020.nc
        valid TCWV file: time=8784, lat=6, lon=15

Final summary:

        SUMMARY: 0 downloaded, 1 skipped_valid_existing, 0 failed

Interpretation:

The corrected buffered TCWV/PWV downloader can run safely under `systemd-run --user` when conda is activated explicitly inside the service command. The full 2004–2023 acquisition should use the same pattern.

Decision:

Proceed to launch the full corrected buffered TCWV/PWV acquisition with `systemd-run --user`, explicit conda activation, logs under the project directory, and output under:

        data_raw/era5/pwv_buffered_pr


---

### T22 — Completion and independent structural validation of buffered ERA5 Single Levels TCWV/PWV acquisition

Purpose: confirm that the corrected buffered ERA5 Single Levels TCWV/PWV raw acquisition for Puerto Rico was completed successfully for the full project period.

Acquisition target:

- Product: ERA5 Single Levels
- Variable: total column water vapour (`tcwv`; TCWV approximately PWV in mm)
- Period: 2004–2023
- Output directory: `data_raw/era5/pwv_buffered_pr`
- Buffered request area: `[18.75, -68.25, 17.50, -64.75]`
- Expected native grid for this request: `latitude=6`, `longitude=15`

Job result:

~~~text
SUMMARY: 19 downloaded, 1 skipped_valid_existing, 0 failed
date_end: Sun May 31 08:29:40 PM AST 2026
~~~

Independent structural validation result:

~~~text
OK 2004: time=8784, lat=6, lon=15, vars=['tcwv']
OK 2005: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2006: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2007: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2008: time=8784, lat=6, lon=15, vars=['tcwv']
OK 2009: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2010: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2011: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2012: time=8784, lat=6, lon=15, vars=['tcwv']
OK 2013: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2014: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2015: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2016: time=8784, lat=6, lon=15, vars=['tcwv']
OK 2017: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2018: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2019: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2020: time=8784, lat=6, lon=15, vars=['tcwv']
OK 2021: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2022: time=8760, lat=6, lon=15, vars=['tcwv']
OK 2023: time=8760, lat=6, lon=15, vars=['tcwv']

SUMMARY: ok=20, bad=0, expected=20
~~~

Validation criteria satisfied for every year:

- TCWV variable present as `tcwv`
- `latitude = 6`
- `longitude = 15`
- hourly time dimension equals `8760` for non-leap years
- hourly time dimension equals `8784` for leap years

Leap years correctly identified in the validated files:

~~~text
2004, 2008, 2012, 2016, 2020
~~~

Interpretation:

The corrected buffered ERA5 Single Levels TCWV/PWV raw acquisition is complete and structurally valid for 2004–2023. This closes the raw acquisition and structural QA step for the buffered PWV dataset.

This does not yet constitute final scientific validation of PWV maps or site-selection results. Downstream use must still verify interpolation/regridding behavior onto the ERA5-Land target grid and document how the buffered domain is used only as interpolation support, while the final analytical domain remains Puerto Rico.

