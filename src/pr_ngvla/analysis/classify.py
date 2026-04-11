"""
pr_ngvla.analysis.classify
===========================
Hourly weather quality classification following Linford & Cooper (2023),
ngVLA Memo No. 117, Table 2.

Four-tier classification applied at each grid cell and time step:
  Good         → all variables within normal operating thresholds
  Questionable → at least one variable borderline
  Poor         → at least one variable significantly out of spec
  Very Poor    → at least one variable critically out of spec

The final classification for each hour is the WORST tier across all variables
(i.e., if wind is Good but RH is Poor → hour is classified as Poor).

This module is the analytical core of the project. Every suitability
map and exceedance statistic depends on this classification.

References
----------
Linford, J. & Cooper, J. (2023). The Portable Weather Station: 2022
  Site Testing. ngVLA Memo No. 117. NRAO.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from pr_ngvla.config import (
    CLASS_GOOD, CLASS_QUESTIONABLE, CLASS_POOR, CLASS_VERY_POOR, CLASS_ORDER,
    RH_GOOD_MAX, RH_QUESTIONABLE_MIN, RH_POOR_MIN, RH_VERY_POOR,
    WIND_GOOD_MAX, WIND_QUESTIONABLE_MIN, WIND_POOR_MIN, WIND_VERY_POOR_MIN,
    PRECIP_QUESTIONABLE_MIN_MM_HR, PRECIP_POOR_MIN_MM_HR, PRECIP_VERY_POOR_MIN_MM_HR,
    TDEP_GOOD_MIN, TDEP_QUESTIONABLE_MAX, TDEP_POOR_MAX, TDEP_VERY_POOR,
    PWV_PRECISION_MAX, PWV_NORMAL_MAX,
)

# Numeric encoding for CLASS_ORDER (used for vectorised worst-case selection)
_CLASS_NUM = {CLASS_GOOD: 0, CLASS_QUESTIONABLE: 1, CLASS_POOR: 2, CLASS_VERY_POOR: 3}
_NUM_CLASS = {v: k for k, v in _CLASS_NUM.items()}


# ---------------------------------------------------------------------------
# Per-variable classifiers (return integer 0-3)
# ---------------------------------------------------------------------------

def _classify_rh(rh: xr.DataArray) -> xr.DataArray:
    """Classify relative humidity (%) into 0–3 tier."""
    c = xr.zeros_like(rh, dtype=int)
    c = c.where(rh <= RH_GOOD_MAX,         other=1)  # > 50% → Questionable
    c = c.where(rh <= RH_POOR_MIN,         other=2)  # > 80% → Poor
    c = c.where(rh <  RH_VERY_POOR,        other=3)  # =100% → Very Poor
    return c


def _classify_wind(ws: xr.DataArray) -> xr.DataArray:
    """Classify 10m wind speed (m/s) into 0–3 tier."""
    c = xr.zeros_like(ws, dtype=int)
    c = c.where(ws <= WIND_GOOD_MAX,        other=1)
    c = c.where(ws <= WIND_POOR_MIN,        other=2)
    c = c.where(ws <= WIND_VERY_POOR_MIN,   other=3)
    return c


def _classify_precip(tp: xr.DataArray) -> xr.DataArray:
    """Classify precipitation rate (mm/hr) into 0–3 tier."""
    c = xr.zeros_like(tp, dtype=int)
    c = c.where(tp < PRECIP_QUESTIONABLE_MIN_MM_HR, other=1)
    c = c.where(tp < PRECIP_POOR_MIN_MM_HR,         other=2)
    c = c.where(tp < PRECIP_VERY_POOR_MIN_MM_HR,    other=3)
    return c


def _classify_tdep(tdep: xr.DataArray) -> xr.DataArray:
    """Classify dew point depression T - Td (°C) into 0–3 tier."""
    c = xr.zeros_like(tdep, dtype=int)
    c = c.where(tdep >= TDEP_GOOD_MIN,        other=1)   # < 2°C   → Questionable
    c = c.where(tdep >= TDEP_POOR_MAX,        other=2)   # < 0.5°C → Poor
    c = c.where(tdep >= TDEP_VERY_POOR,       other=3)   # < 0°C   → Very Poor
    return c


def _classify_pwv(pwv: xr.DataArray) -> xr.DataArray:
    """
    Classify PWV (mm) into 0–3 tier.
    Precision ops require PWV ≤ 6 mm; normal ops ≤ 26 mm.
    PWV > 26 mm → Very Poor (exceeds normal operating limit).
    6 < PWV ≤ 26 mm → Questionable (precision ops degraded).
    """
    c = xr.zeros_like(pwv, dtype=int)
    c = c.where(pwv <= PWV_PRECISION_MAX,  other=1)   # > 6 mm  → Questionable
    c = c.where(pwv <= PWV_NORMAL_MAX,     other=3)   # > 26 mm → Very Poor
    return c


# ---------------------------------------------------------------------------
# Main classification function
# ---------------------------------------------------------------------------

def classify_hourly(
    rh:   xr.DataArray,
    ws:   xr.DataArray,
    tp:   xr.DataArray,
    tdep: xr.DataArray,
    pwv:  xr.DataArray | None = None,
) -> xr.DataArray:
    """
    Classify each grid cell × hour as Good / Questionable / Poor / Very Poor.

    The final class is the WORST (highest tier number) across all variables.

    Parameters
    ----------
    rh   : Relative humidity (%)
    ws   : 10m wind speed (m/s)
    tp   : Precipitation rate (mm/hr)
    tdep : Dew point depression T - Td (°C)
    pwv  : Precipitable water vapour (mm), optional.
           If None, PWV classification is skipped.

    Returns
    -------
    xr.DataArray
        Integer array (0=Good, 1=Questionable, 2=Poor, 3=Very Poor)
        with same shape as inputs. Attribute 'class_labels' maps
        integers to string labels.
    """
    tiers = [
        _classify_rh(rh),
        _classify_wind(ws),
        _classify_precip(tp),
        _classify_tdep(tdep),
    ]

    if pwv is not None:
        tiers.append(_classify_pwv(pwv))

    # Worst-case: take the maximum tier across all variables
    worst = tiers[0]
    for tier in tiers[1:]:
        worst = xr.where(tier > worst, tier, worst)

    worst.name = "ngvla_class"
    worst.attrs["long_name"] = "ngVLA weather quality class (Memo 117)"
    worst.attrs["class_labels"] = str(_NUM_CLASS)
    worst.attrs["0"] = CLASS_GOOD
    worst.attrs["1"] = CLASS_QUESTIONABLE
    worst.attrs["2"] = CLASS_POOR
    worst.attrs["3"] = CLASS_VERY_POOR
    return worst


def fraction_good(classification: xr.DataArray, dim: str = "time") -> xr.DataArray:
    """
    Fraction of hours classified as 'Good' along a dimension.

    This is the primary metric NRAO uses for site selection:
    "% of observing time in Good conditions per month."

    Parameters
    ----------
    classification : xr.DataArray
        Integer class array from classify_hourly().
    dim : str
        Dimension to reduce over (default: 'time').

    Returns
    -------
    xr.DataArray
        Fraction in [0, 1]. Multiply by 100 for percentage.
    """
    is_good = (classification == _CLASS_NUM[CLASS_GOOD]).astype(float)
    frac = is_good.mean(dim=dim)
    frac.name = "fraction_good"
    frac.attrs["long_name"] = "Fraction of hours classified as Good (Memo 117)"
    frac.attrs["units"] = "dimensionless [0–1]"
    return frac


def class_fractions(
    classification: xr.DataArray,
    dim: str = "time",
) -> xr.Dataset:
    """
    Fraction of hours in each class (Good/Questionable/Poor/Very Poor).

    Returns
    -------
    xr.Dataset with variables: frac_good, frac_questionable, frac_poor,
    frac_very_poor. All values sum to 1.0 at each grid point.
    """
    fracs = {}
    for label, num in _CLASS_NUM.items():
        key = f"frac_{label.lower().replace(' ', '_')}"
        da = (classification == num).astype(float).mean(dim=dim)
        da.name = key
        da.attrs["long_name"] = f"Fraction of hours: {label}"
        fracs[key] = da

    return xr.Dataset(fracs)
