# pr_ngvla — Atmospheric Site Characterization for ngVLA in Puerto Rico

**Lead:** César Pollack (M.S. student, UPR Río Piedras)  
**Advisor:** Dr. Mayra Lebrón Santos  
**Collaborators:** Dr. H. Arce (Yale) · Dr. J. Morales (UPR) · Dr. C. Pantoja (UPR)  
**Institution:** Department of Physics, UPR Río Piedras / CARSE  
**Support:** NSF – RUM CARSE SPEED Program  
**Last updated:** April 2026

---

## What this project does

This project characterizes 20 years (2004–2023) of atmospheric conditions across
Puerto Rico to identify the most favorable regions for ngVLA antenna placement.

Puerto Rico is already included in the ngVLA design as a Long Baseline Array (LBA)
node. This study does **not** evaluate whether PR qualifies — it identifies which
regions within PR are **more or less favorable** for high-frequency radio astronomy.

The analysis uses ERA5-Land reanalysis data (~9 km resolution, hourly) for all
surface meteorological variables, and ERA5 Single-Levels for precipitable water
vapor (PWV). Results are validated against 5 NOAA ISD stations.

---

## Scientific context

High-frequency radio astronomy (>10 GHz) requires low water vapor, low
precipitation, and moderate winds. The ngVLA System Environmental Specification
(Selina et al. 2020) and Memo 117 (Linford & Cooper 2023) define four operational
tiers — Good, Questionable, Poor, Very Poor — for each variable.

**Seven variables analyzed:**

| Variable | Role | Good threshold |
|---|---|---|
| PWV (mm) | Primary | ≤ 6 mm |
| Relative Humidity (%) | Primary | ≤ 50% |
| Precipitation (mm/hr) | Primary | 0 mm/hr |
| Wind Speed (m/s) | Primary | ≤ 9 m/s |
| Dew Point Depression (°C) | Derived | ≥ 2°C |
| Air Temperature (°C) | Supportive | −15 to +35°C |
| Surface Pressure (hPa) | Supportive | input to PWV |

---

## Key results (Phases 1–3 complete)

- **Most favorable region:** SW corridor — San Germán, Yauco, Guayanilla, Las Marías
- **Best municipality:** San Germán (site selection index = 0.5153)
- **Best temporal window:** January–March (dry season)
- **Best single month:** February
- **Wind:** not a discriminating variable (~0% exceedance of 9 m/s threshold)
- **PWV:** entire PR exceeds the Good threshold year-round; SW corridor drops
  to ~50% exceedance during Jan–Mar (quantifies atmospheric correction need)

---

## Project phases

| Phase | Description | Status |
|---|---|---|
| 1 | 20-year monthly climatology (7 variables, 7 maps) | ✅ Complete |
| 2 | Hourly exceedance analysis + ERA5 vs ISD validation | ✅ Complete |
| 3A | Fuzzy-logic site selection index | ✅ Complete |
| 3B | ERA5-SL gap-fill for coastal pixels | ✅ Complete |
| 4 | Monte Carlo uncertainty + DEM lapse rate downscaling | Planned May 2026 |
| 5 | WRF dynamical downscaling at 1–3 km | Planned Jun–Aug 2026 |

---

## Quick start

```bash
# Clone the repository
git clone https://github.com/cesarpollack/pr_ngvla.git
cd pr_ngvla

# Create conda environment (installs all dependencies + library)
conda env create -f environment.yml
conda activate pr_ngvla

# Verify installation
python -c "import pr_ngvla; print(pr_ngvla.__version__)"
python -m pytest tests/ -v
```

> **Data not included.** Raw ERA5 and NOAA files are not in the repository
> (~300 GB). See `docs/DATA_SOURCES.md` for download instructions.

---

## Repository structure

```
pr_ngvla/
├── src/pr_ngvla/              ← Installable Python library (all logic here)
│   ├── config.py              ← ALL paths, constants, thresholds — single source of truth
│   ├── data/
│   │   ├── loaders.py         ← ERA5 and NOAA ISD file readers
│   │   ├── spatial.py         ← Vector data loader (returns 3 values — see ARCHITECTURE.md)
│   │   └── temporal.py        ← Monthly climatology, precipitation unit conversion
│   ├── physics/
│   │   └── thermodynamics.py  ← Magnus RH formula, dew point depression
│   ├── analysis/
│   │   ├── thresholds.py      ← ngVLA threshold dictionary
│   │   ├── exceedance.py      ← Hourly exceedance fraction computation
│   │   ├── validation.py      ← ERA5 vs NOAA ISD statistical validation
│   │   ├── fuzzy.py           ← Fuzzy-logic site selection index
│   │   └── gapfill.py         ← ERA5-SL coastal gap-fill
│   └── visualization/
│       └── maps.py            ← All map rendering functions
│
├── scripts/                   ← Orchestration only (no scientific logic)
│   ├── phase1_map_*.py        ← Phase 1 climatology maps (7 scripts)
│   ├── phase2_exceedance.py   ← Compute exceedance NetCDFs
│   ├── phase2_validation.py   ← ERA5 vs ISD validation metrics
│   ├── phase2_map_exceedance.py ← Phase 2 exceedance maps
│   ├── phase3_composite_index.py ← Compute site selection index
│   ├── phase3_map_composite.py   ← Phase 3 composite maps
│   ├── phase3_gapfill_singlelev.py ← ERA5-SL gap-fill computation
│   ├── phase3_map_gapfill.py  ← Gap-filled composite maps (poster figures)
│   └── download_*.py          ← ERA5 and NOAA data downloads
│
├── data_raw/                  ← Raw data — NOT in repository (~300 GB)
├── outputs/                   ← Generated figures and NetCDFs — NOT in repository
├── docs/                      ← Scientific and technical documentation
│   ├── ARCHITECTURE.md        ← Code design rules (READ BEFORE EDITING CODE)
│   ├── DECISIONS.md           ← Every scientific/methodological decision with rationale
│   ├── FUTURE_WORK.md         ← Roadmap beyond Phase 3
│   └── REPRODUCING.md         ← Step-by-step guide to reproduce all results
├── tests/                     ← Unit tests (run before any code change)
├── environment.yml            ← Conda environment (pinned dependencies)
├── pyproject.toml             ← Library installation config
└── pr_ngvla_INSTALL_QA_GUIDE.md ← Detailed server setup and QA checklist
```

---

## Critical design rules

These rules prevent silent bugs. Read `docs/ARCHITECTURE.md` for full details.

**1. Library vs script separation**  
All scientific logic lives in `src/pr_ngvla/`. Scripts in `scripts/` are
orchestration only — they load data, call library functions, and save outputs.
Never put physics or analysis logic in a script.

**2. `load_vector_data()` returns exactly 3 values**
```python
# ALWAYS unpack all three:
muni_clip, coast_union, muni_land_union = load_vector_data(COAST_SHP, MUNI_SHP)
```

**3. Ocean masking uses `muni_land_union`, never `coast_union`**
```python
mask_ocean(ax, muni_land_union)   # correct
mask_ocean(ax, coast_union)       # WRONG — causes white patches in SW lagoons
```

**4. ERA5-SL time dimension is `valid_time`, not `time`**  
ERA5-Land uses `time`; ERA5 Single-Levels uses `valid_time`. Check before indexing.

**5. No hardcoded values**  
All paths, thresholds, and constants go in `config.py`. Never type a number or
path directly in a script.

---

## Server information

| Item | Value |
|---|---|
| Host | astroiupi |
| User | cpollack |
| OS | OpenSUSE Leap 15.6 |
| RAM / Cores | 1 TB / 96 |
| Conda env | pr_ngvla |
| Project root | `/export/ngvla/cpollack/pr_ngvla/` |
| Sessions | tmux (NOT slurm) |

> **Rule:** Always work in `/export/ngvla/cpollack/pr_ngvla/`. Never in `~home/`.

---

## Key references

- Selina et al. (2020). ngVLA System Environmental Specification. NRAO ENV0313.
- Linford & Cooper (2023). ngVLA Memo 117. NRAO.
- Muñoz-Sabater et al. (2021). ERA5-Land. ESSD 13:4349–4383.
- Hersbach et al. (2020). ERA5 global reanalysis. QJRMS 146:1999–2049.
- Nikolic et al. (2013). ALMA WVR phase correction. A&A 552:A104.
- Bi et al. (2024). ERA5 for astronomical site characterization. MNRAS 527:4616.
- Zhang et al. (2019). ERA5 PWV validation. Radio Science 54:561.

---

## Scientific framing (important)

When presenting results, always use this language:

| ❌ Never use | ✅ Always use |
|---|---|
| "suitability index" | "site selection index" |
| "suitable/unsuitable" | "more/less favorable" |
| "Puerto Rico qualifies/fails" | "SW corridor is most favorable" |

See `docs/DECISIONS.md` entry D01 and D12 for full rationale.
