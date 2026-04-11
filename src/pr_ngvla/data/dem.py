"""
pr_ngvla.data.dem
==================
Loader and utilities for the SRTM 30m Digital Elevation Model.
Used for topographic downscaling of ERA5-Land fields.

TODO: implement
  - load_srtm_dem()           → rasterio dataset
  - elevation_at_points(lons, lats)
  - lapse_rate_correction(T_era5, dem, lapse_rate_per_month)
"""
