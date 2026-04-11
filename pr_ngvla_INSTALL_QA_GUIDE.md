# pr_ngvla — Installation & Reproducibility Guide

**Project:** ngVLA Puerto Rico Site Suitability Analysis  
**Server:** astroiupi (OpenSUSE Leap 15.6, 96 cores, 1 TB RAM)  
**Project path:** `/export/ngvla/cpollack/pr_ngvla`  
**Conda root:** `/export/ngvla/cpollack/miniconda3`  
**Python:** 3.11 (conda env: `pr_ngvla`)  
**Last updated:** March 2026

---

## PART 1 — Fresh Installation

Follow these steps in order. Do not skip steps or run them out of sequence.

### Step 1 — Erase the old project

If a previous version exists, remove it completely before unzipping a new one.

```bash
cd /export/ngvla/cpollack
rm -rf pr_ngvla
ls /export/ngvla/cpollack/    # pr_ngvla should NOT appear
```

### Step 2 — Transfer and unzip

From your local machine:
```bash
scp pr_ngvla_v2.zip cpollack@astroiupi:/export/ngvla/cpollack/
```

On the server:
```bash
cd /export/ngvla/cpollack
unzip pr_ngvla_v2.zip
ls pr_ngvla/
```

Expected contents:
```
environment.yml  pyproject.toml  README.md  scripts/  src/
tests/  data_raw/  logs/  outputs/  config/
```

### Step 3 — Create the conda environment

One command installs all dependencies and the library in editable mode:

```bash
cd /export/ngvla/cpollack/pr_ngvla
/export/ngvla/cpollack/miniconda3/bin/conda env create -f environment.yml
```

This takes 5–15 minutes. Expected final lines:
```
  Running command pip install --no-build-isolation -e .
  Successfully installed pr-ngvla-0.1.0
  done
```

> ⚠️ **Do NOT run `pip install -e .` manually afterward** — it is already done
> inside `conda env create`. Running it again is harmless but unnecessary.

### Step 4 — Activate and verify

```bash
conda activate pr_ngvla
```

**Verify 1 — library imports and key constants:**
```bash
python -c "
import pr_ngvla
from pr_ngvla.config import PWV_PRECISION_MAX, TEMP_PRECISION_MIN, TEMP_PRECISION_MAX
print('version          :', pr_ngvla.__version__)
print('PWV_PRECISION_MAX:', PWV_PRECISION_MAX,   '(expect 6.0)')
print('TEMP_PRECISION_MIN:', TEMP_PRECISION_MIN, '(expect -15.0)')
print('TEMP_PRECISION_MAX:', TEMP_PRECISION_MAX, '(expect 25.0)')
"
```

**Verify 2 — core scientific imports:**
```bash
python -c "import xarray, numpy, pandas, cdsapi, metpy, rasterio, geopandas; print('OK')"
```

**Verify 3 — run the test suite:**
```bash
python -m pytest tests/ -v
```

> ⚠️ **Always use `python -m pytest`**, not bare `pytest`. The server has a
> system Python 3.6 with its own pytest at `/usr/bin/pytest` which will be
> found first if the conda one is missing. Since `pytest` is now in
> `environment.yml` this should not happen, but `python -m pytest` is always
> unambiguous.

### Step 5 — Configure the CDS API key

The ERA5 downloads need your Copernicus CDS Personal Access Token.

```bash
nano ~/.cdsapirc
```

Paste exactly (replace with your token):
```
url: https://cds.climate.copernicus.eu/api
key: YOUR-PERSONAL-ACCESS-TOKEN-HERE
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`. Then verify:
```bash
python -c "import cdsapi; c = cdsapi.Client(); print('CDS API OK')"
```

> **Token format:** The token is the UUID string alone — no UID prefix.
> Old format (pre-2024) was `UID:token`. New format is the token only.
> The URL must be `https://cds.climate.copernicus.eu/api` with no `/v2` at the end.

### Step 6 — Start downloads

```bash
chmod +x scripts/run_all_downloads.sh
./scripts/run_all_downloads.sh
```

This launches 4 tmux sessions. Monitor them:
```bash
tmux ls
tmux attach -t era5_monthly      # Ctrl+B then D to detach without killing
tmux attach -t era5_pwv
tmux attach -t era5_hourly_A     # note: capital A and B
tmux attach -t era5_hourly_B
```

Check logs at any time:
```bash
tail -f logs/download_monthly.log
tail -f logs/download_hourly_A.log
tail -f logs/download_hourly_B.log
tail -f logs/download_pwv.log
```

Check CDS request status online:
```
https://cds.climate.copernicus.eu/requests
```

---

## PART 2 — CDS Download Limits and Known Issues

These are lessons learned from actual download failures during this project.

### CDS per-request size limit (403 cost limits exceeded)

CDS enforces a cost limit per request based on: variables × time steps × grid points.

| Request type              | Time steps | Approx size | Result   |
|---------------------------|------------|-------------|----------|
| Monthly means (20 yrs)    | 240        | ~130 KB     | ✅ OK    |
| Hourly, 1 year, 2 vars    | 17,568     | ~5 GB       | ❌ 403 FAIL |
| Hourly, 1 month, 2 vars   | 1,488      | ~450 MB     | ✅ OK    |

The fix applied in this project: request **one month at a time** instead of one
year. This produces 480 files (20 years × 12 months × 2 groups) instead of 40,
but each request succeeds.

> ⚠️ **Rule for future downloads:** If you add new variables or extend the time
> period, always request one month at a time for hourly ERA5-Land data.
> Monthly-mean data can be requested all at once.

### CDS processes one request at a time per user

Even though 4 tmux sessions run simultaneously on the server, CDS queues your
requests sequentially. Sessions will show "accepted" status while waiting.
This is normal — do not relaunch sessions that are waiting.

### Tmux session names are case-sensitive

Sessions are named `era5_hourly_A` and `era5_hourly_B` (capital A/B).
Using lowercase will give `can't find session` even if they exist.

### System Python 3.6 conflict

The server has a system Python 3.6 at `/usr/bin/`. Always verify which Python
is active before running anything:

```bash
which python      # must show: miniconda3/envs/pr_ngvla/bin/python
python --version  # must show: Python 3.11.x
```

If `which python` shows `/usr/bin/python`, the conda env is not active.
Fix with:
```bash
source /export/ngvla/cpollack/miniconda3/bin/activate pr_ngvla
```

### run_all_downloads.sh stops on any error

The script has `set -euo pipefail` which means it exits completely on any error.
If the hourly sessions are missing from `tmux ls`, the script stopped before
launching them. Launch them manually:

```bash
tmux new-session -d -s era5_hourly_A \
  "cd /export/ngvla/cpollack/pr_ngvla && \
   PYTHONUNBUFFERED=1 \
   /export/ngvla/cpollack/miniconda3/envs/pr_ngvla/bin/python \
   scripts/download_era5land_hourly_pr.py --group A \
   2>&1 | tee logs/download_hourly_A.log"

tmux new-session -d -s era5_hourly_B \
  "cd /export/ngvla/cpollack/pr_ngvla && \
   PYTHONUNBUFFERED=1 \
   /export/ngvla/cpollack/miniconda3/envs/pr_ngvla/bin/python \
   scripts/download_era5land_hourly_pr.py --group B \
   2>&1 | tee logs/download_hourly_B.log"
```

> Using `PYTHONUNBUFFERED=1` and the full Python path avoids both the buffering
> problem (empty logs) and the `conda run` issue that caused the original script
> to stop.

---

## PART 3 — Quality Assurance for Every Code Delivery

Every time new code is delivered, follow this checklist before continuing.

### Layer 1 — Run the test suite (30 seconds)

```bash
conda activate pr_ngvla
cd /export/ngvla/cpollack/pr_ngvla
python -m pytest tests/ -v
```

The tests cover:

| Test file                  | What it verifies                                                      |
|----------------------------|-----------------------------------------------------------------------|
| `tests/test_config.py`     | All 40 ngVLA threshold constants vs primary sources (Selina 2020, Memo 117) |
| `tests/test_atmosphere.py` | RH, dew point depression, wind speed physics — numerical correctness  |
| `tests/test_classify.py`   | 20 classification scenarios: Good/Questionable/Poor/Very Poor logic   |

> ⚠️ If pytest shows ANY `FAILED` or `ERROR` — stop. Do not run new code.
> Report the failure and wait for a fix.

### Layer 2 — Spot-check new constants (2 minutes)

Every time new thresholds or formulas are delivered, verify 3–5 key values
manually against the source documents in the project knowledge:

- `ngvla_variables_table.docx` — all 7 variables with thresholds and ENV codes
- `NGVLA_117.pdf` — Memo 117 Table 2 (Good/Q/Poor/VP classification tiers)
- `ngVLAs_site_requirements.md` — summary with ENV specification codes

Require an audit table with every delivery:

| Constant            | Value  | Source document              | ENV/Section |
|---------------------|--------|------------------------------|-------------|
| `PWV_PRECISION_MAX` | 6.0    | ngvla_variables_table.docx   | ENV0316     |
| `TEMP_PRECISION_MIN`| -15.0  | ngvla_variables_table.docx   | ENV0313     |
| `WIND_GOOD_MAX`     | 9.0    | NGVLA_117.pdf Table 2        | Memo 117    |

### Layer 3 — Physical plausibility check (when data is available)

Once ERA5 files are downloaded, verify output ranges are physically sensible
for Puerto Rico:

| Variable      | Expected (PR coastal) | Expected (El Yunque) | Flag if outside  |
|---------------|----------------------|----------------------|------------------|
| T2m (°C)      | 18 – 34              | 5 – 25               | < 0 or > 40      |
| RH (%)        | 50 – 100             | 70 – 100             | < 20 or > 100    |
| Wind (m/s)    | 1 – 15               | 1 – 20               | < 0 or > 50      |
| PWV (mm)      | 20 – 65              | 15 – 55              | < 5 or > 80      |
| Precip (mm/hr)| 0 – 50               | 0 – 80               | < 0 or > 200     |

### Layer 4 — Transparency requirement for each delivery

Every code delivery must state explicitly:

1. What files changed (exact filenames)
2. What was added or fixed (with scientific rationale)
3. What tests cover the new code
4. What was **not** tested and why

### Layer 5 — Git commit after each verified delivery

After pytest passes and spot-checks are done:

```bash
cd /export/ngvla/cpollack/pr_ngvla
git add .
git commit -m "Add ERA5 loader + smoke tests — all pytest pass"
```

To recover a previous working state if a new delivery breaks something:
```bash
git log --oneline                                                 # see history
git diff HEAD~1                                                   # see what changed
git checkout HEAD~1 -- src/pr_ngvla/analysis/classify.py         # restore one file
```

### Summary checklist

```
[ ] python -m pytest tests/ -v ............. all green?
[ ] Spot-check 3+ constants vs docx/PDF .... values match?
[ ] Physical plausibility of any new output . PR ranges sensible?
[ ] git commit .............................. recovery point saved?
```

---

## PART 4 — Reproducibility for Other Researchers

A researcher with no prior knowledge of this project should be able to reproduce
all results by following these steps with no additional guidance.

### What they need

| Item               | Where to get it                                                          |
|--------------------|--------------------------------------------------------------------------|
| Project code       | `pr_ngvla_v2.zip` or `git clone` from project repository                |
| CDS account        | Register free at cds.climate.copernicus.eu — token is personal           |
| ERA5 licence       | Accept once on CDS dataset pages — cannot be automated                   |
| Conda              | Miniconda or Anaconda — any version supporting Python 3.11               |
| ~300 GB disk space | For raw ERA5 hourly files (480 monthly NetCDF files)                     |

### What is fully pinned (reproducible without any decisions)

- **Python version:** 3.11 (locked in `environment.yml`)
- **All package versions:** resolved by conda from `conda-forge` channel
- **All scientific thresholds:** in `src/pr_ngvla/config.py` with source citations
- **ERA5 dataset IDs, bounding box, time period:** in download scripts and `config.py`
- **Classification logic:** in `src/pr_ngvla/analysis/classify.py` with tests

### What requires manual action (cannot be automated)

- **CDS personal access token:** each researcher must register their own free account
- **ERA5 terms of use:** must be accepted once per dataset on the CDS website before downloading
- **Download time:** 480 requests at ~5 min each on CDS queue = several days of wall time

### Minimal reproduction steps

```
1. Get the code      unzip pr_ngvla_v2.zip && cd pr_ngvla
2. Install env       conda env create -f environment.yml && conda activate pr_ngvla
3. Verify install    python -m pytest tests/ -v   (must be all green)
4. Set up CDS        configure ~/.cdsapirc with personal token
5. Download data     ./scripts/run_all_downloads.sh   (runs for several days)
6. Run analysis      python scripts/run_analysis.py   (Phase 2, to be delivered)
7. Collect results   outputs/maps/ and outputs/figures/
```

> **Tip for testing before full download:** The monthly ERA5 data (2 files,
> ~400 KB total) downloads in minutes and is sufficient to test the entire
> analysis pipeline end-to-end. A researcher can verify the code works correctly
> using monthly data before committing to the multi-day hourly download.

---

*Last updated: March 2026 — César Pollack, advisor: Dr. Mayra Lebrón Santos, UPR Río Piedras / CARSE*
