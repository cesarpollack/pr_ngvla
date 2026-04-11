"""
pr_ngvla.analysis.downscale
============================
Topographic downscaling of ERA5-Land (0.1°) to SRTM DEM (30m).

Method: lapse rate correction for temperature and pressure.
  T_corrected = T_era5 + lapse_rate * (elev_dem - elev_era5)
  Standard environmental lapse rate: -6.5 K/km (varies seasonally)

TODO: implement
  - downscale_temperature(T_era5, dem, era5_dem, lapse_rate)
  - downscale_pressure(P_era5, dem, era5_dem)
  - monthly_lapse_rates_pr()  → dict of 12 monthly lapse rates for PR
"""
