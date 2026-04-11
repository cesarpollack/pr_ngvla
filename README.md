# pr_ngvla

GIS-based atmospheric site suitability analysis for the ngVLA Puerto Rico node.

## Overview

Python library characterising 20 years (2004–2023) of meteorological conditions
across Puerto Rico for ngVLA antenna placement, using ERA5-Land reanalysis data
validated against NOAA ASOS in-situ stations.

**Seven variables:** PWV, Relative Humidity, Precipitation, Wind Speed,
Air Temperature, Dew Point Depression, Barometric Pressure.

**Classification framework:** Linford & Cooper (2023), ngVLA Memo No. 117
(Good / Questionable / Poor / Very Poor).

## Installation (server)

```bash
# 1. Create conda environment (includes all dependencies + editable install)
conda env create -f environment.yml

# 2. Activate
conda activate pr_ngvla

# 3. Verify
python -c "import pr_ngvla; from pr_ngvla.config import PWV_PRECISION_MAX; print('OK —', PWV_PRECISION_MAX)"
```

## Project structure

```
pr_ngvla/
├── src/pr_ngvla/
│   ├── config.py          # All ngVLA thresholds — single source of truth
│   ├── data/
│   │   ├── era5.py        # ERA5-Land and ERA5 single-levels loaders
│   │   ├── noaa.py        # NOAA ASOS / GHCN loaders (TODO)
│   │   └── dem.py         # SRTM DEM loader (TODO)
│   ├── physics/
│   │   └── atmosphere.py  # RH, dew point depression, wind speed
│   ├── analysis/
│   │   ├── classify.py    # Memo 117 Good/Q/Poor/VP classification engine
│   │   ├── bias.py        # ERA5 bias correction vs ASOS (TODO)
│   │   ├── downscale.py   # Topographic downscaling (TODO)
│   │   └── suitability.py # Composite suitability maps (TODO)
│   └── visualization/
│       ├── maps.py        # Cartographic maps for Puerto Rico (TODO)
│       └── plots.py       # Statistical / validation plots (TODO)
├── scripts/               # ERA5 download scripts
├── data_raw/              # Raw ERA5, NOAA, DEM data (never commit)
├── data_interim/          # Intermediate processed data (never commit)
├── data_products/         # Final analysis products (never commit)
└── outputs/               # Figures, maps, tables

```

## Key references

- Selina et al. (2020). ngVLA System Environmental Specification. NRAO Doc. 020.10.15.10.00-0001-SPE.
- Linford & Cooper (2023). The Portable Weather Station: 2022 Site Testing. ngVLA Memo No. 117.
- Muñoz-Sabater et al. (2021). ERA5-Land. Earth Syst. Sci. Data, 13, 4349–4383.
- Lebrón Santos et al. (2025). Characterization of Weather Conditions for ngVLA in Puerto Rico. UPR Río Piedras.
