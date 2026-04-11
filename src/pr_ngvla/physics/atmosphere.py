"""
pr_ngvla.physics.atmosphere
============================
Atmospheric physics calculations needed for ngVLA site characterisation.

All functions accept and return xarray DataArrays (or numpy arrays)
so they work transparently with dask lazy evaluation.

Functions
---------
relative_humidity      : RH from T and Td (Magnus equation)
dew_point_depression   : T - Td (fog/condensation indicator)
wind_speed             : scalar wind from u10, v10 components

References
----------
Magnus equation coefficients from Buck (1981):
  Buck, A.L. (1981). New equations for computing vapor pressure and
  enhancement factor. J. Appl. Meteorol., 20, 1527–1532.
  doi:10.1175/1520-0450(1981)020<1527:NEFCVP>2.0.CO;2
"""

from __future__ import annotations

import numpy as np
import xarray as xr


# ---------------------------------------------------------------------------
# Magnus / Buck equation constants (over liquid water, -40 to +60°C)
# ---------------------------------------------------------------------------
_A = 17.368   # dimensionless
_B = 238.83   # °C


def _saturation_vapor_pressure(T_celsius: xr.DataArray | np.ndarray) -> xr.DataArray | np.ndarray:
    """
    Saturation vapour pressure (hPa) using the Magnus equation.

    e_s(T) = 6.1078 * exp(A * T / (B + T))

    Parameters
    ----------
    T_celsius : array-like
        Temperature in °C.
    """
    return 6.1078 * np.exp(_A * T_celsius / (_B + T_celsius))


def relative_humidity(
    T: xr.DataArray | np.ndarray,
    Td: xr.DataArray | np.ndarray,
) -> xr.DataArray | np.ndarray:
    """
    Relative humidity (%) from 2m temperature and 2m dewpoint temperature.

    RH = 100 * e_s(Td) / e_s(T)

    Parameters
    ----------
    T : array-like
        2m air temperature in °C.
    Td : array-like
        2m dewpoint temperature in °C.

    Returns
    -------
    RH : array-like
        Relative humidity in %, clipped to [0, 100].

    Notes
    -----
    ERA5 can occasionally produce Td slightly above T due to numerical
    precision — the clip prevents RH > 100%.
    """
    es_T  = _saturation_vapor_pressure(T)
    es_Td = _saturation_vapor_pressure(Td)
    rh = 100.0 * es_Td / es_T

    if isinstance(rh, xr.DataArray):
        rh = rh.clip(0.0, 100.0)
        rh.attrs["units"] = "%"
        rh.attrs["long_name"] = "Relative humidity"
        rh.name = "rh"
    else:
        rh = np.clip(rh, 0.0, 100.0)

    return rh


def dew_point_depression(
    T: xr.DataArray | np.ndarray,
    Td: xr.DataArray | np.ndarray,
) -> xr.DataArray | np.ndarray:
    """
    Dew point depression: T - Td (°C).

    This is the single most important fog/condensation indicator for
    ngVLA site classification (Linford & Cooper 2023, Memo 117):
      T - Td < 2.0°C  → Questionable
      T - Td < 0.5°C  → Poor
      T - Td < 0.0°C  → Very Poor (T below dew point: fog/condensation)

    Parameters
    ----------
    T : array-like
        2m air temperature in °C.
    Td : array-like
        2m dewpoint temperature in °C.

    Returns
    -------
    T_minus_Td : array-like
        Dew point depression in °C. Negative values mean condensation.
    """
    tdep = T - Td

    if isinstance(tdep, xr.DataArray):
        tdep.attrs["units"] = "°C"
        tdep.attrs["long_name"] = "Dew point depression (T - Td)"
        tdep.name = "tdep"

    return tdep


def wind_speed(
    u10: xr.DataArray | np.ndarray,
    v10: xr.DataArray | np.ndarray,
) -> xr.DataArray | np.ndarray:
    """
    Scalar 10m wind speed (m/s) from U and V components.

    ws = sqrt(u10² + v10²)

    Parameters
    ----------
    u10 : array-like
        10m U (eastward) wind component in m/s.
    v10 : array-like
        10m V (northward) wind component in m/s.

    Returns
    -------
    ws : array-like
        Wind speed in m/s.
    """
    ws = np.sqrt(u10 ** 2 + v10 ** 2)

    if isinstance(ws, xr.DataArray):
        ws.attrs["units"] = "m/s"
        ws.attrs["long_name"] = "10m wind speed"
        ws.name = "wind_speed"

    return ws
