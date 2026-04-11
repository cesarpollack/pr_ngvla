"""
pr_ngvla.analysis.bias
=======================
Bias correction of ERA5-Land fields against NOAA ASOS in-situ observations.

Strategy:
  - Separate correction factors for dry season (Dec–May) and
    wet season (Jun–Nov) — ERA5 moist bias is worse during summer convection.
  - Per-variable, per-month correction (12 monthly factors each).

TODO: implement
  - compute_monthly_bias(era5_at_stations, asos_obs)
  - apply_bias_correction(era5_grid, bias_factors)
"""
