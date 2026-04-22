# Mixed-Resolution Validation Framework — pr_ngvla

Date: 2026-04-21  
Branch: `feat/noaa-station-inventory`

## Purpose

Define the next workflow stage after:
- NOAA variable-coverage metadata audit
- GHCNh metadata ingestion and Puerto Rico station inventory
- station-inventory map standardization

This framework preserves the frozen map standard and project architecture while shifting the validation design from the earlier ISD-centered hourly idea to the agreed mixed-resolution strategy.

## Frozen upstream stages

These are already working and are not reopened in this stage:
- NOAA station inventory metadata stage
- NOAA variable-coverage audit outputs
- GHCNh metadata + Puerto Rico station inventory stage
- station-inventory map styling

Legacy/audit outputs remain preserved for traceability.

## Scientific decision frozen for this stage

### Tier 1 — hourly validation core
Use **GHCNh** as the default hourly-capable validation branch for:
- temperature
- dew point / RH
- wind

**Hourly precipitation is not selected in v1 of this framework.**  
It remains deferred until later observation-level population checks confirm that the hourly precipitation branch is truly usable.

### Tier 2 — daily broad validation layer
Use **GHCND** as the default daily-capable validation branch for:
- daily temperature metrics
- daily precipitation totals

**Daily wind is not selected by default in v1.**  
It is preserved only as a **conditional candidate** because the project has not yet frozen the scientific/product-level decision that the GHCND wind product is appropriate for the default daily validation branch.

## Relationship to legacy ISD

ISD remains available only as a **legacy/audit artifact**.

That means:
- existing NOAA variable-coverage outputs that include the ISD proxy logic are preserved
- ISD still documents what the older hourly proxy stage looked like
- ISD is **not** the default selector source in the mixed-resolution validation framework

## Relationship to ERA5 / ERA5-Land

This framework preserves the earlier agreement that:
- hourly validation is needed for hourly behavior (RH/dew point, wind, event timing)
- daily validation is complementary, not a replacement
- ERA5 / ERA5-Land hourly fields may be aggregated to daily metrics and compared against daily station products where definitions are appropriate

## Design rule for this stage

Do **not** replace the working NOAA audit outputs.

Instead:
1. keep the existing NOAA variable-coverage products exactly as metadata/audit products
2. add a new selector framework layer that expresses the mixed-resolution validation decision explicitly

## New selector concepts

### Metadata eligibility vs selection
The new framework distinguishes two different ideas:

- **`prelim_usable`**: metadata-driven eligibility from the inventory logic
- **`selector_selected`**: whether the current workflow stage actually selects that station-variable combination into the active validation framework

This avoids conflating:
- “metadata says the station may support this variable”
- “the project has decided to use it in the default validation framework”

### Selector status
A new field `selector_status` is used:
- `accepted` = selected by the current framework
- `conditional` = metadata candidate retained, but not selected by default

## New code products added in this stage

### Existing audit products retained
These are preserved unchanged:
- `data_interim/noaa/variable_coverage/pr_noaa_variable_coverage_long.parquet`
- `data_interim/noaa/variable_coverage/pr_noaa_variable_coverage_long.csv`
- `data_interim/noaa/variable_coverage/pr_noaa_variable_coverage_wide.parquet`
- `data_interim/noaa/variable_coverage/pr_noaa_variable_coverage_wide.csv`
- `outputs/tables/pr_noaa_variable_coverage_summary.csv`

### New mixed-resolution selector products
The build script now also writes:

- `data_interim/noaa/variable_coverage/pr_mixed_resolution_validation_long.parquet`
- `data_interim/noaa/variable_coverage/pr_mixed_resolution_validation_long.csv`
- `data_interim/noaa/variable_coverage/pr_mixed_resolution_validation_wide.parquet`
- `data_interim/noaa/variable_coverage/pr_mixed_resolution_validation_wide.csv`
- `data_interim/noaa/variable_coverage/pr_hourly_validation_selectors_ghcnh.parquet`
- `data_interim/noaa/variable_coverage/pr_hourly_validation_selectors_ghcnh.csv`
- `data_interim/noaa/variable_coverage/pr_daily_validation_selectors_ghcnd.parquet`
- `data_interim/noaa/variable_coverage/pr_daily_validation_selectors_ghcnd.csv`
- `outputs/tables/pr_mixed_resolution_validation_summary.csv`

## Long-form mixed selector schema

The new long-form selector table uses:
- `station_id`
- `source`
- `validation_tier`
- `variable`
- `native_datatype`
- `native_timescale`
- `start_year`
- `end_year`
- `years_with_data`
- `study_overlap`
- `prelim_usable`
- `selector_status`
- `selector_selected`
- `notes`

## Tier logic implemented in v1

### GHCNh hourly-core
For every GHCNh master station overlapping 2004–2023:
- `temperature` → accepted
- `dewpoint_rh` → accepted
- `wind` → accepted

Selection rule:
- `selector_selected = prelim_usable`

### GHCND daily-broad
For GHCND metadata rows built from the existing inventory logic:
- `temperature` → accepted
- `precipitation` → accepted
- `wind` → conditional by default

Selection rule:
- accepted variables: `selector_selected = prelim_usable`
- conditional daily wind: `selector_selected = False` by default

The build script allows a future explicit override through:
- `VALIDATION_INCLUDE_DAILY_WIND`

If that config value is set to `True`, daily wind becomes selected.

## Why this design is safer

This design avoids regressions because it:
- does not delete the existing NOAA audit work
- does not re-open the frozen map stage
- does not reintroduce ISD as the default hourly selector logic
- records unresolved product questions explicitly as `conditional`
- keeps hourly and daily validation branches distinguishable in both long and wide outputs

## Expected first-pass interpretation of the outputs

### Hourly selector file
`pr_hourly_validation_selectors_ghcnh.*`
- authoritative hourly-capable default branch
- expected to be smaller spatially
- used for hourly validation planning

### Daily selector file
`pr_daily_validation_selectors_ghcnd.*`
- broader daily-capable branch
- expected to provide stronger island-wide coverage
- used for daily aggregated validation planning

### Mixed summary file
`pr_mixed_resolution_validation_summary.csv`
- quick QC table showing accepted vs conditional branches
- useful for continuity prompts, README updates, and later docs

## Files updated in this implementation

- `src/pr_ngvla/data/noaa_variable_coverage.py`
- `scripts/build_noaa_variable_coverage_pr.py`
- `tests/test_noaa_variable_coverage.py`

## Validation status for this patch bundle

Local test run in the patch workspace:

```bash
PYTHONPATH=/mnt/data/repo/src pytest -q tests/test_noaa_variable_coverage.py tests/test_ghcnh.py
```

Result:
- `18 passed`

## Not changed in this stage

Intentionally not changed:
- `src/pr_ngvla/data/ghcnh.py`
- `scripts/build_ghcnh_station_inventory_pr.py`
- map scripts / visualization helpers
- legacy NOAA station-inventory logic

## Next likely downstream step

After this selector framework is accepted and generated on the real branch, the next logical stage is:
- use the selector outputs to drive actual validation-ready station subsets and later observation-level extraction / comparison workflows
