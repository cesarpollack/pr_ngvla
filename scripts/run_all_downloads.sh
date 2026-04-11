#!/usr/bin/env bash
# =============================================================================
# run_all_downloads.sh
#
# Launch all ERA5 download jobs as background processes on the research server.
# Uses tmux sessions so downloads survive SSH disconnection.
#
# SERVER: astroiupi (OpenSUSE Leap 15.6)
# WORKDIR: /export/ngvla/cpollack/pr_ngvla
# CONDA ENV: pr_ngvla
#
# Usage (from project root):
#   chmod +x scripts/run_all_downloads.sh
#   ./scripts/run_all_downloads.sh
#
# Monitor progress:
#   tmux ls                          # list sessions
#   tmux attach -t era5_monthly      # attach to a session
#   Ctrl+B then D                    # detach without killing
#
# Check logs:
#   tail -f logs/download_monthly.log
#   tail -f logs/download_hourly_A.log
#   tail -f logs/download_hourly_B.log
#   tail -f logs/download_pwv.log
# =============================================================================

set -euo pipefail

# --- Project paths ---
PROJECT_ROOT="/export/ngvla/cpollack/pr_ngvla"
CONDA_BASE="/export/ngvla/cpollack/miniconda3"
CONDA_ENV="pr_ngvla"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
LOG_DIR="${PROJECT_ROOT}/logs"

# --- Activate conda ---
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV}"

mkdir -p "${LOG_DIR}"
cd "${PROJECT_ROOT}"

echo "============================================"
echo "  ngVLA Puerto Rico — ERA5 Download Launcher"
echo "  $(date)"
echo "  Project: ${PROJECT_ROOT}"
echo "  Env:     ${CONDA_ENV}"
echo "============================================"
echo ""

# ---------------------------------------------------------------------------
# JOB 1: Monthly means (small, fast — done in hours, not days)
# Start this FIRST because it gives you data to test your analysis code
# ---------------------------------------------------------------------------
echo "[1/4] Launching ERA5-Land monthly means download..."
tmux new-session -d -s era5_monthly \
    "cd ${PROJECT_ROOT} && \
     conda run -n ${CONDA_ENV} python ${SCRIPTS_DIR}/download_era5land_monthly_pr.py \
     2>&1 | tee ${LOG_DIR}/download_monthly.log; \
     echo 'MONTHLY DOWNLOAD COMPLETE' >> ${LOG_DIR}/download_monthly.log"
echo "      → tmux session: era5_monthly"
echo "      → log: logs/download_monthly.log"
echo ""

# Brief pause so CDS doesn't see simultaneous logins as suspicious
sleep 5

# ---------------------------------------------------------------------------
# JOB 2: ERA5 PWV (single-levels TCWV) — medium size, ~5-10 GB total
# ---------------------------------------------------------------------------
echo "[2/4] Launching ERA5 single-levels PWV (TCWV) download..."
tmux new-session -d -s era5_pwv \
    "cd ${PROJECT_ROOT} && \
     conda run -n ${CONDA_ENV} python ${SCRIPTS_DIR}/download_era5_pwv_pr.py \
     2>&1 | tee ${LOG_DIR}/download_pwv.log; \
     echo 'PWV DOWNLOAD COMPLETE' >> ${LOG_DIR}/download_pwv.log"
echo "      → tmux session: era5_pwv"
echo "      → log: logs/download_pwv.log"
echo ""

sleep 5

# ---------------------------------------------------------------------------
# JOB 3: ERA5-Land hourly Group A (t2m + d2m) — largest download
# CDS queues one request at a time per user, so this will queue
# ---------------------------------------------------------------------------
echo "[3/4] Launching ERA5-Land hourly Group A (t2m + d2m)..."
tmux new-session -d -s era5_hourly_A \
    "cd ${PROJECT_ROOT} && \
     conda run -n ${CONDA_ENV} python ${SCRIPTS_DIR}/download_era5land_hourly_pr.py \
       --group A \
     2>&1 | tee ${LOG_DIR}/download_hourly_A.log; \
     echo 'HOURLY-A DOWNLOAD COMPLETE' >> ${LOG_DIR}/download_hourly_A.log"
echo "      → tmux session: era5_hourly_A"
echo "      → log: logs/download_hourly_A.log"
echo ""

sleep 5

# ---------------------------------------------------------------------------
# JOB 4: ERA5-Land hourly Group B (wind + precip + pressure)
# CDS will queue this after Job 3 finishes each year's request
# ---------------------------------------------------------------------------
echo "[4/4] Launching ERA5-Land hourly Group B (wind + precip + pressure)..."
tmux new-session -d -s era5_hourly_B \
    "cd ${PROJECT_ROOT} && \
     conda run -n ${CONDA_ENV} python ${SCRIPTS_DIR}/download_era5land_hourly_pr.py \
       --group B \
     2>&1 | tee ${LOG_DIR}/download_hourly_B.log; \
     echo 'HOURLY-B DOWNLOAD COMPLETE' >> ${LOG_DIR}/download_hourly_B.log"
echo "      → tmux session: era5_hourly_B"
echo "      → log: logs/download_hourly_B.log"
echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "============================================"
echo "  All download jobs launched."
echo ""
echo "  Active tmux sessions:"
tmux ls 2>/dev/null || echo "  (tmux not available — check manually)"
echo ""
echo "  Monitor all logs at once:"
echo "  tail -f logs/download_*.log"
echo ""
echo "  Expected download sizes (rough estimates):"
echo "    Monthly means:   ~50-100 MB  (fast)"
echo "    PWV (TCWV):      ~5-10 GB    (hours)"
echo "    Hourly Group A:  ~80-120 GB  (1-3 days)"
echo "    Hourly Group B:  ~160-240 GB (2-4 days)"
echo ""
echo "  NOTE: CDS processes one request per user at a time."
echo "  Jobs will queue internally. Check CDS status at:"
echo "  https://cds.climate.copernicus.eu/requests"
echo "============================================"
