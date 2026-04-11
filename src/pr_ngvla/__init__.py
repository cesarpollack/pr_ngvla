"""
src/pr_ngvla/__init__.py
pr_ngvla
========
GIS-based atmospheric site suitability analysis for the ngVLA Puerto Rico node.

Analysis window : 2004–2023 (20 years)
Primary dataset : ERA5-Land hourly, 0.1° resolution
Validation      : NOAA ASOS in-situ stations
Cross-validation: NASA MERRA-2 (PWV only)
DEM             : SRTM 30 m

References
----------
Selina et al. (2020) — ngVLA System Environmental Specification
Linford & Cooper (2023) — ngVLA Memo No. 117
Muñoz-Sabater et al. (2021) — ERA5-Land, Earth Syst. Sci. Data
Lebrón Santos et al. (2025) — Project proposal, UPR Río Piedras
"""

__version__ = "0.1.0"
__author__  = "César Pollack"
