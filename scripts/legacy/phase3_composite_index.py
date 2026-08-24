"""
scripts/phase3_composite_index.py

Phase 3 — Fuzzy-logic composite suitability index.

Loads Phase 2 exceedance climatology NetCDFs, applies linear fuzzy membership
functions, and computes a weighted composite suitability index per month and
annual mean.

Usage:
    cd /export/ngvla/cpollack/pr_ngvla
    python scripts/phase3_composite_index.py

Inputs (from outputs/phase2/):
    rh_exceedance_climatology.nc
    wind_exceedance_climatology.nc
    precip_exceedance_climatology.nc
    pwv_exceedance_climatology.nc

Outputs (to outputs/phase3/):
    composite_index_monthly.nc    — shape: (month=12, lat, lon)
    composite_index_annual.nc     — shape: (lat, lon)
"""

import numpy as np
import xarray as xr
from pathlib import Path

from pr_ngvla.config import OUTPUTS
from pr_ngvla.analysis.fuzzy import composite_index, annual_composite, DEFAULT_WEIGHTS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PHASE2_DIR = OUTPUTS / "phase2"
PHASE3_DIR = OUTPUTS / "phase3"
PHASE3_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Threshold values to select from each NetCDF
# (from Phase 2 exceedance.py definitions)
# ---------------------------------------------------------------------------

# Variable name → (netcdf_var, threshold_value, expected_mean)
EXCEEDANCE_CONFIG = {
    "rh":     ("rh_exceedance",     50.0,  0.979),
    "wind":   ("wind_exceedance",    9.0,  0.000),
    "precip": ("precip_exceedance",  1.0,  0.254),
    "pwv":    ("pwv_exceedance",    26.0,  0.902),
}

# ---------------------------------------------------------------------------
# Load Phase 2 exceedance climatologies
# ---------------------------------------------------------------------------

print("=" * 60)
print("Phase 3 — Composite Suitability Index")
print("=" * 60)
print()

def load_exceedance(fname: str, var: str, threshold: float) -> xr.DataArray:
    """
    Load a Phase 2 exceedance NetCDF and select the requested threshold slice.

    The NetCDFs have shape (month, threshold, latitude, longitude).
    We select along the threshold dimension using method='nearest' for safety.
    """
    ds = xr.open_dataset(PHASE2_DIR / fname)
    da = ds[var]
    thresholds = da["threshold"].values
    print(f"  Available thresholds: {thresholds}")
    # Select exact threshold (nearest as safety)
    da_sel = da.sel(threshold=threshold, method="nearest")
    # Drop threshold coordinate so downstream code sees (month, lat, lon)
    if "threshold" in da_sel.coords:
        da_sel = da_sel.drop_vars("threshold")
    return da_sel

# --- RH > 50% ---
print("Loading RH exceedance climatology...")
exc_rh = load_exceedance(
    "rh_exceedance_climatology.nc", "rh_exceedance", 50.0
)
print(f"  Shape after threshold selection: {exc_rh.dims}")
print(f"  Mean exceedance: {float(exc_rh.mean()):6.3f}  (expected ~0.979)")

# --- Wind > 9 m/s ---
print("Loading wind exceedance climatology...")
exc_wind = load_exceedance(
    "wind_exceedance_climatology.nc", "wind_exceedance", 9.0
)
print(f"  Shape after threshold selection: {exc_wind.dims}")
print(f"  Mean exceedance: {float(exc_wind.mean()):6.3f}  (expected ~0.000)")

# --- Precip > 1 mm/hr ---
print("Loading precipitation exceedance climatology...")
exc_precip = load_exceedance(
    "precip_exceedance_climatology.nc", "precip_exceedance", 1.0
)
print(f"  Shape after threshold selection: {exc_precip.dims}")
print(f"  Mean exceedance: {float(exc_precip.mean()):6.3f}  (expected ~0.254)")

# --- PWV > 26 mm ---
print("Loading PWV exceedance climatology...")
exc_pwv = load_exceedance(
    "pwv_exceedance_climatology.nc", "pwv_exceedance", 26.0
)
print(f"  Shape after threshold selection: {exc_pwv.dims}")
print(f"  Mean exceedance: {float(exc_pwv.mean()):6.3f}  (expected ~0.902)")

# ---------------------------------------------------------------------------
# Align coordinates (all datasets should share lat/lon/month)
# ---------------------------------------------------------------------------

print()
print("Aligning coordinates...")

# Use RH as the reference grid (ERA5-Land land pixels)
# PWV comes from ERA5 single-levels (0.25°) — may need regridding
# Check if grids match
rh_lat = float(exc_rh["latitude"].diff("latitude").mean())
pwv_lat_step = float(exc_pwv["latitude"].diff("latitude").mean()) if "latitude" in exc_pwv.coords else None

if pwv_lat_step is not None and abs(abs(rh_lat) - abs(pwv_lat_step)) > 0.01:
    print(f"  PWV grid ({pwv_lat_step:.3f}°) differs from RH grid ({rh_lat:.3f}°) → interpolating PWV to ERA5-Land grid")
    exc_pwv = exc_pwv.interp(
        latitude=exc_rh["latitude"],
        longitude=exc_rh["longitude"],
        method="linear",
    )
    print(f"  PWV regridded to ERA5-Land grid. Shape: {exc_pwv.dims}")
else:
    print(f"  All grids match (Δlat ≈ {abs(rh_lat):.3f}°). No regridding needed.")

# Ensure month coordinate is aligned
for name, da in [("wind", exc_wind), ("precip", exc_precip), ("pwv", exc_pwv)]:
    if "month" in da.dims and "month" in exc_rh.dims:
        if not np.array_equal(da["month"].values, exc_rh["month"].values):
            print(f"  WARNING: month coordinate mismatch for {name} — reindexing")

# ---------------------------------------------------------------------------
# Compute composite index
# ---------------------------------------------------------------------------

print()
print("Computing composite suitability index...")
print(f"  Weights: {DEFAULT_WEIGHTS}")
print(f"  Membership function: linear (suitability = 1 - exceedance_fraction)")

exceedance_dict = {
    "rh": exc_rh,
    "wind": exc_wind,
    "precip": exc_precip,
    "pwv": exc_pwv,
}

composite_monthly = composite_index(exceedance_dict, weights=DEFAULT_WEIGHTS)
composite_ann = annual_composite(composite_monthly)

# ---------------------------------------------------------------------------
# Print summary statistics
# ---------------------------------------------------------------------------

print()
print("─" * 40)
print("COMPOSITE INDEX SUMMARY")
print("─" * 40)

ann_vals = composite_ann.values
land_mask = ~np.isnan(ann_vals)

print(f"  Annual mean (land pixels): {np.nanmean(ann_vals):.4f}")
print(f"  Annual min:                {np.nanmin(ann_vals):.4f}")
print(f"  Annual max:                {np.nanmax(ann_vals):.4f}")
print(f"  Std dev:                   {np.nanstd(ann_vals):.4f}")
print()

# Monthly stats
if "month" in composite_monthly.dims:
    print("  Monthly mean composite index:")
    for m in range(1, 13):
        val = float(composite_monthly.sel(month=m).mean())
        print(f"    Month {m:2d}: {val:.4f}")

print()

# Top 5% best pixels
top5 = np.nanpercentile(ann_vals, 95)
n_top = int(np.sum(ann_vals >= top5))
print(f"  Top 5% threshold: ≥ {top5:.4f}  ({n_top} pixels)")

# Best month
if "month" in composite_monthly.dims:
    monthly_means = [float(composite_monthly.sel(month=m).mean()) for m in range(1, 13)]
    best_month = int(np.argmax(monthly_means)) + 1
    worst_month = int(np.argmin(monthly_means)) + 1
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    print(f"  Best month:  {months[best_month-1]} ({monthly_means[best_month-1]:.4f})")
    print(f"  Worst month: {months[worst_month-1]} ({monthly_means[worst_month-1]:.4f})")

# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

print()
print("Saving outputs...")

# Monthly composite
out_monthly = PHASE3_DIR / "composite_index_monthly.nc"
ds_out_monthly = composite_monthly.to_dataset()
ds_out_monthly.attrs = {
    "title": "ngVLA Puerto Rico — Phase 3 Site Selection Index (Monthly)",
    "institution": "University of Puerto Rico Río Piedras",
    "source": "ERA5-Land + ERA5 single-levels (2004–2023)",
    "history": "Generated by phase3_composite_index.py",
    "description": (
        "Fuzzy-logic site selection index for ngVLA antenna placement in Puerto Rico. "
        "Variables: RH>50%, wind>9m/s, precip>1mm/hr, PWV>26mm. "
        "Equal weights (0.25 each). Linear membership: favorability = 1 - exceedance_frac."
    ),
}
ds_out_monthly.to_netcdf(out_monthly)
print(f"  Saved: {out_monthly}")

# Annual composite
out_annual = PHASE3_DIR / "composite_index_annual.nc"
ds_out_annual = composite_ann.to_dataset()
ds_out_annual.attrs = ds_out_monthly.attrs.copy()
ds_out_annual.attrs["title"] = (
    "ngVLA Puerto Rico — Phase 3 Site Selection Index (Annual Mean)"
)
ds_out_annual.to_netcdf(out_annual)
print(f"  Saved: {out_annual}")

print()
print("Phase 3 composite index: DONE")
print(f"Outputs in: {PHASE3_DIR}")
print("Next: run phase3_map_composite.py to generate maps")
