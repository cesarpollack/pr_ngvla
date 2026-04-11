"""
src/pr_ngvla/physics/thermodynamics.py
=======================================
Atmospheric thermodynamics functions for the ngVLA PR site study.

All functions operate on plain NumPy arrays (or scalars) and are
unit-agnostic within the documented constraints.  They contain NO
file I/O and NO plotting — pure physics only.

They are designed to be called via xr.apply_ufunc so they work
transparently on xarray DataArrays without loading all data into
memory at once (Dask-compatible).

References
----------
- August–Roche–Magnus approximation:
    Alduchov & Eskridge (1996), J. Appl. Meteorol. 35:601–609
- Same coefficients used by WMO and ECMWF IFS documentation.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Magnus formula coefficients (Alduchov & Eskridge 1996)
# Valid range: −40 °C to +60 °C
# ---------------------------------------------------------------------------
_A = 17.625   # dimensionless
_B = 243.04   # °C


def _gamma(temp_c: np.ndarray) -> np.ndarray:
    """
    Compute the Magnus γ parameter.

    γ(T) = A·T / (B + T)

    Used internally by rh_from_t_td and saturation_vapour_pressure.
    """
    return _A * temp_c / (_B + temp_c)


def rh_from_t_td(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """
    Compute relative humidity (%) from temperature and dew-point.

    Formula (Magnus approximation):
        RH = 100 × exp( γ(Td) − γ(T) )

    Physical constraint: Td ≤ T, so RH ≤ 100 %.
    The result is clipped to [0, 100] % to suppress any floating-point
    overshoot.

    Parameters
    ----------
    t_c  : array-like — dry-bulb temperature [°C]
    td_c : array-like — dew-point temperature [°C]  (must be ≤ t_c)

    Returns
    -------
    rh : ndarray — relative humidity [%]  values in [0, 100]
    """
    return np.clip(100.0 * np.exp(_gamma(td_c) - _gamma(t_c)), 0.0, 100.0)


def dew_point_depression(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """
    Compute dew-point depression: T − Td  [°C].

    Physical meaning: how far the air is from saturation.
    A large value means dry air (good for radio astronomy).
    A value near zero means the air is close to saturation (fog/cloud risk).

    ngVLA ENV0313 (Selina 2020) classification:
        Good        : T − Td ≥ 2 °C
        Questionable: T − Td < 2 °C
        Poor        : T − Td < 0.5 °C
        Very Poor   : T − Td < 0 °C  (supersaturation — numerical artefact)

    Parameters
    ----------
    t_c  : array-like — dry-bulb temperature [°C]
    td_c : array-like — dew-point temperature [°C]

    Returns
    -------
    tdep : ndarray — dew-point depression [°C]  (≥ 0 physically)
    """
    return np.asarray(t_c, dtype=float) - np.asarray(td_c, dtype=float)
