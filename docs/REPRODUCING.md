# REPRODUCING.md
# ngVLA Puerto Rico — How to Reproduce All Results from Scratch
# Last updated: April 2026
# Author: César Pollack, UPR Río Piedras
#
# PURPOSE: A new graduate student with no prior knowledge of this project
# should be able to reproduce all results by following this document alone.
# Assumes: Linux, Python, basic physics knowledge. No ERA5 or reanalysis
# experience required.

---

## Before you start — read these two documents first

1. `docs/ARCHITECTURE.md` — understand the code structure and design rules
2. `docs/DECISIONS.md` — understand why every scientific choice was made

Do not skip this. The design rules in ARCHITECTURE.md prevent silent bugs
that are very hard to debug later.

---

## Overview of what you are reproducing

The analysis has three phases, each depending on the previous:

```
Phase 1 → Monthly climatology maps (7 variables, 20-year means)
    ↓
Phase 2 → Hourly exceedance analysis + ERA5 validation vs NOAA stations
    ↓
Phase 3A → Site selection index (fuzzy-logic composite of Phase 2 results)
    ↓
Phase 3B → ERA5-SL gap-fill for coastal pixels
    ↓
    Final maps (poster figures)
```

Total computation time after data download: approximately 2–4 hours on astroiupi.
Data download time: several days (ERA5 queue is slow — plan ahead).

---

## STEP 0 — Set up the environment

### 0.1 — Clone the repository

```bash
cd /export/ngvla/cpollack
git clone https://github.com/cesarpollack/pr_ngvla.git
cd pr_ngvla
```

### 0.2 — Create the conda environment

```bash
/export/ngvla/cpollack/miniconda3/bin/conda env create -f environment.yml
conda activate pr_ngvla
```

This installs all dependencies and the `pr_ngvla` library in editable mode.
It takes 5–15 minutes. When finished you should see:
```
Successfully installed pr-ngvla-0.1.0
```

### 0.3 — Verify the installation

```bash
python -c "import pr_ngvla; print(pr_ngvla.__version__)"
python -m pytest tests/ -v
```

All tests must pass (green). If any test fails, stop — do not proceed.

### 0.4 — Check which Python is active

```bash
which python    # must show: .../miniconda3/envs/pr_ngvla/bin/python
python --version  # must show: Python 3.11.x
```

If it shows `/usr/bin/python`, the conda env is not active. Run:
```bash
source /export/ngvla/cpollack/miniconda3/bin/activate pr_ngvla
```

---

## STEP 1 — Download the data

See `docs/DATA_SOURCES.md` for a full description of each dataset.
Here are the commands.

### 1.1 — Configure CDS API (Copernicus — for ERA5)

You need a free account at https://cds.climate.copernicus.eu

After registering and accepting the ERA5 terms of use:

```bash
nano ~/.cdsapirc
```

Paste (replace with your token):
```
url: https://cds.climate.copernicus.eu/api
key: YOUR-PERSONAL-ACCESS-TOKEN-HERE
```

Verify:
```bash
python -c "import cdsapi; c = cdsapi.Client(); print('CDS API OK')"
```

### 1.2 — Run all downloads

```bash
chmod +x scripts/run_all_downloads.sh
./scripts/run_all_downloads.sh
```

This launches 4 tmux sessions running in parallel. Monitor them:
```bash
tmux ls
tmux attach -t era5_monthly   # Ctrl+B then D to detach
tmux attach -t era5_pwv
tmux attach -t era5_hourly_A
tmux attach -t era5_hourly_B
```

Check progress in logs:
```bash
tail -f logs/download_monthly.log
tail -f logs/download_hourly_A.log
```

### 1.3 — Download NOAA ISD stations

```bash
python scripts/download_noaa_isd_pr.py
```

This downloads the 5 validation stations to `data_raw/noaa/isd/`.

### 1.4 — Verify data completeness

```bash
# ERA5-Land hourly: expect 480 files (20 years × 12 months × 2 variable groups)
ls data_raw/era5/hourly/*.nc | wc -l    # expect 480

# ERA5-Land monthly: expect 2 files
ls data_raw/era5/monthly/*.nc           # expect 2 files

# ERA5 Single-Levels hourly: expect 720 files
ls data_raw/era5/singlelev/*.nc | wc -l # expect ~720

# ERA5 PWV: expect 20 files (one per year)
ls data_raw/era5/pwv/*.nc | wc -l       # expect 20

# NOAA ISD: expect 5 station CSV files + catalog
ls data_raw/noaa/isd/*.csv
```

> ⚠️ Do not proceed to Phase 1 until all ERA5-Land hourly files are present.
> The monthly files download in minutes; the hourly files take several days.

---

## STEP 2 — Phase 1: Monthly climatology maps

These scripts compute 20-year monthly mean climatologies and save maps.
Each script is independent — they can run in any order.

```bash
conda activate pr_ngvla
cd /export/ngvla/cpollack/pr_ngvla

python scripts/phase1_map_temperature.py
python scripts/phase1_map_rh.py
python scripts/phase1_map_tdep.py
python scripts/phase1_map_wind.py
python scripts/phase1_map_precip.py
python scripts/phase1_map_pwv.py
python scripts/phase1_map_dem.py
```

**Expected outputs** in `outputs/maps/`:
```
phase1_temperature_monthly_climatology.png
phase1_rh_monthly_climatology.png
phase1_tdep_monthly_climatology.png
phase1_wind_monthly_climatology.png
phase1_precip_monthly_climatology.png
phase1_pwv_monthly_climatology.png
phase1_dem_stations.png
```

**Sanity check** — compare printed ranges against known PR climatology:
- Temperature: 21–28°C ✓ (tropical island)
- RH: 67–87% ✓ (humid tropical)
- Wind: 1–5 m/s ✓ (trade winds, well below 9 m/s threshold)
- PWV: 26–47 mm ✓ (entire PR exceeds 6 mm Good threshold)

---

## STEP 3 — Phase 2: Exceedance analysis and validation

### 3.1 — Compute exceedance climatologies

This is the most computationally intensive step (~1–2 hours on astroiupi).
It reads all 480 hourly ERA5-Land files and computes, for each pixel and
month, the fraction of hours exceeding each ngVLA threshold.

```bash
python scripts/phase2_exceedance.py
```

**Expected outputs** in `outputs/phase2/`:
```
rh_exceedance_climatology.nc
wind_exceedance_climatology.nc
precip_exceedance_climatology.nc
pwv_exceedance_climatology.nc
```

**Hurricane Maria exclusion:** months 2017-09 through 2018-06 are
automatically excluded (see `config.py: MARIA_START, MARIA_END`).
This removes 9 months from the 20-year record to avoid ERA5 quality
degradation during and after Maria.

### 3.2 — Validate ERA5 against NOAA ISD stations

```bash
python scripts/phase2_validation.py
```

**Expected output:** `outputs/validation/era5_vs_isd_metrics.csv`

**Expected results** (from completed analysis):
- RH: MBE < 3% at all 5 stations — no systematic bias
- Wind: ERA5-Land underestimates at 4/5 stations (MBE: −0.4 to −1.2 m/s)
  This is expected behavior in complex terrain at 9 km resolution.

### 3.3 — Generate exceedance maps

```bash
python scripts/phase2_map_exceedance.py --var rh
python scripts/phase2_map_exceedance.py --var wind
python scripts/phase2_map_exceedance.py --var precip
python scripts/phase2_map_exceedance.py --var pwv
```

Or all at once:
```bash
python scripts/phase2_map_exceedance.py --var all
```

**Expected outputs** in `outputs/maps/phase2/`:
```
phase2_rh_exceedance_climatology.png
phase2_wind_exceedance_climatology.png
phase2_precip_exceedance_climatology.png
phase2_pwv_exceedance_climatology.png
```

**Sanity check** — print the island-wide annual mean exceedance:
- RH > 50%: ~97.9% ← entire island is humid almost all the time
- Wind > 9 m/s: ~0% ← wind is never a problem in PR
- Precip > 1 mm/hr: ~25.4% ← SW much lower than NE
- PWV > 26 mm: ~90.2% ← very high island-wide, SW drops to ~50% in Jan–Mar

---

## STEP 4 — Phase 3A: Site selection index

### 4.1 — Compute the composite index

```bash
python scripts/phase3_composite_index.py
```

**Expected outputs** in `outputs/phase3/`:
```
composite_index_monthly.nc   ← (12, lat, lon) site selection index per month
composite_index_annual.nc    ← (lat, lon) annual mean index
best_regions_annual.csv      ← top pixels ranked by annual index
best_regions_monthly.csv     ← top pixels ranked per month
best_municipalities.csv      ← municipality-level aggregation
best_regions_summary.txt     ← human-readable summary
```

**Expected top result:** San Germán, index ≈ 0.5153

The site selection index formula (equal weights):
```
F_i = 1 - exceedance_fraction_i    (per variable)
Index = (F_RH + F_wind + F_precip + F_PWV) / 4
```
0 = least favorable, 1 = most favorable.

### 4.2 — Generate composite maps (without gap-fill)

```bash
python scripts/phase3_map_composite.py
```

**Expected outputs** in `outputs/maps/phase3/`:
```
phase3_composite_annual.png
phase3_composite_monthly.png
```

---

## STEP 5 — Phase 3B: ERA5-SL gap-fill for coastal pixels

ERA5-Land assigns NaN to coastal pixels where land fraction is too low.
This step uses ERA5 Single-Levels (coarser, ~28 km) to partially fill those gaps.

**Important limitation:** Lajas and Guánica (southernmost coast) remain NaN
even after gap-fill because the nearest ERA5-SL pixel has only ~24% land
fraction (below the 60% threshold). This is documented in `docs/DECISIONS.md`
entry D08 and `docs/FUTURE_WORK.md`.

### 5.1 — Run the gap-fill

```bash
python scripts/phase3_gapfill_singlelev.py
```

**Expected outputs** in `outputs/phase3/gapfill/`:
```
rh_exceedance_gapfilled.nc
wind_exceedance_gapfilled.nc
precip_exceedance_gapfilled.nc
pwv_exceedance_gapfilled.nc
composite_index_monthly_gf.nc
composite_index_annual_gf.nc
provenance_mask.nc           ← 0=ocean, 1=ERA5-Land, 2=ERA5-SL gap-fill
gapfill_report.txt           ← summary of pixels recovered
```

### 5.2 — Generate gap-filled maps (poster figures)

```bash
python scripts/phase3_map_gapfill.py
```

**Expected outputs** in `outputs/maps/phase3/`:
```
phase3_composite_annual_gf.png    ← PRIMARY POSTER FIGURE
phase3_composite_monthly_gf.png   ← SECONDARY POSTER FIGURE
```

---

## STEP 6 — Generate best regions report

```bash
python scripts/phase3_best_regions_report.py
```

This prints and saves the ranking of municipalities by site selection index.
The expected top 10 (annual mean):

| Rank | Municipality | Index |
|---|---|---|
| 1 | San Germán | 0.5153 |
| 2 | Yauco | 0.5136 |
| 3 | Lares | 0.5110 |
| 4 | Las Marías | 0.5088 |
| 5 | Guayanilla | 0.5071 |
| 6 | Adjuntas | 0.5060 |
| 7 | Peñuelas | 0.5007 |
| 8 | Utuado | 0.4997 |
| 9 | Jayuya | 0.4990 |
| 10 | Mayagüez | 0.4985 |

If your results differ significantly, check that Hurricane Maria months
are excluded and that the ERA5-SL land fraction threshold is 60%.

---

## STEP 7 — Sync results to your laptop

```bash
rsync -avz --progress \
    cpollack@astroiupi:/export/ngvla/cpollack/pr_ngvla/outputs/maps/ \
    ./maps/
```

---

## Troubleshooting common problems

**`ModuleNotFoundError: No module named 'pr_ngvla'`**  
The conda environment is not active or the library is not installed.
```bash
conda activate pr_ngvla
pip install -e .
```

**`KeyError: 'valid_time'` or `KeyError: 'time'`**  
ERA5-Land uses `time`; ERA5 Single-Levels uses `valid_time`. Check which
file you are loading and use the correct dimension name.

**`load_vector_data()` returns wrong number of values**  
Always unpack all three return values:
```python
muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
```

**White patches in SW coast of maps**  
You are using `coast_union` for ocean masking instead of `muni_land_union`.
See ARCHITECTURE.md Rule 5.

**CDS API 403 error during download**  
You have not accepted the ERA5 terms of use on the CDS website, or your
request is too large. Accept terms at cds.climate.copernicus.eu and
request one month at a time for hourly data.

**Exceedance values seem too high (e.g., 93% for precipitation)**  
You are using the >0 mm/hr threshold. ERA5 generates numerical drizzle.
Use >1 mm/hr as the threshold. See `docs/DECISIONS.md` entry D05.

---

## What results should look like

If everything works correctly:

- All Phase 1 maps show a clear west-to-east gradient — SW is drier,
  NE (El Yunque area) is much wetter
- Phase 2 exceedance maps show SW corridor consistently lowest for
  precipitation and PWV
- Phase 3 annual composite map shows a green cluster in the SW
  (San Germán, Yauco, Guayanilla area)
- The monthly composite clearly shows Jan–Mar as the most favorable window

If the spatial patterns are reversed or uniform, there is likely a
coordinate issue (latitude array reversed or wrong variable loaded).

---

*For questions about the science: contact Dr. Mayra Lebrón Santos (advisor)*  
*For questions about the code: read docs/DECISIONS.md and docs/ARCHITECTURE.md first*  
*Last updated: April 2026 — César Pollack, UPR Río Piedras / CARSE*
