"""
src/pr_ngvla/analysis/thresholds.py
=====================================
ngVLA site environmental classification thresholds.

Source
------
- Selina et al. (2020) — ngVLA System Environmental Specification,
  NRAO Doc 020.10.15.10.00-0001-SPE (ENV0313)
- Linford & Cooper (2023) — ngVLA Memo 117 (wind speed)

Structure
---------
THRESHOLDS is a dict keyed by variable name.  Each entry is an ordered
list of (upper_bound, label, color) tuples from best to worst.
The final tier has upper_bound = +inf (no upper limit).

This structure is designed to drive both the MCDA scoring (Phase 2)
and the colorbar annotation (Phase 1 maps, optional).

Usage example
-------------
    from pr_ngvla.analysis.thresholds import THRESHOLDS, classify

    tier = classify(45.0, "pwv")   # → "Poor"
"""

from __future__ import annotations
import math


# ---------------------------------------------------------------------------
# Threshold table
# Each variable: list of (upper_bound, tier_label, hex_color)
# Read as: value <= upper_bound → this tier
# ---------------------------------------------------------------------------

THRESHOLDS: dict[str, list[tuple]] = {

    # Precipitable Water Vapor [mm]  — primary variable, weight 30 %
    "pwv": [
        (  6.0, "Good",        "#2166ac"),  # dark blue
        ( 18.0, "Questionable","#92c5de"),  # light blue
        ( 26.0, "Poor",        "#f4a582"),  # light orange
        (math.inf, "Very Poor","#d6604d"),  # red-orange
    ],

    # Relative Humidity [%]  — primary, weight 25 %
    "rh": [
        ( 50.0, "Good",        "#2166ac"),
        ( 80.0, "Questionable","#92c5de"),
        ( 99.9, "Poor",        "#f4a582"),
        (math.inf, "Very Poor","#d6604d"),  # = 100 % saturation
    ],

    # Total Precipitation [mm/hr]  — primary, weight 20 %
    # Note: Phase 1 maps use mm/month; thresholds apply to Phase 2 hourly data
    "precip_rate": [
        (  0.0, "Good",        "#2166ac"),  # no precipitation
        (  1.0, "Questionable","#92c5de"),
        (  7.6, "Poor",        "#f4a582"),
        (math.inf, "Very Poor","#d6604d"),
    ],

    # 10-metre Wind Speed [m/s]  — primary, weight 15 %  (Memo 117)
    "wind": [
        (  9.0, "Good",        "#2166ac"),
        ( 13.4, "Questionable","#92c5de"),
        ( 24.5, "Poor",        "#f4a582"),
        (math.inf, "Very Poor","#d6604d"),
    ],

    # Dew Point Depression T − Td [°C]  — derived, weight 10 %
    "tdep": [
        # NOTE: thresholds are LOWER bounds for Good (inverse of other vars)
        # Re-expressed as upper bounds for the worst tier:
        # Td ≥ 2 → Good; 0.5–2 → Q; 0–0.5 → Poor; <0 → VP
        (  0.0, "Very Poor",   "#d6604d"),  # < 0 °C (supersaturation)
        (  0.5, "Poor",        "#f4a582"),
        (  2.0, "Questionable","#92c5de"),
        (math.inf, "Good",     "#2166ac"),
    ],

    # Air Temperature [°C]  — supporting variable
    "temperature": [
        ( 25.0, "Precision ops","#2166ac"),  # −15 to +25 °C
        ( 35.0, "Normal ops",   "#92c5de"),  # −15 to +35 °C
        (math.inf, "Degraded",  "#f4a582"),
    ],
}


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------

def classify(value: float, variable: str) -> str:
    """
    Return the classification tier label for a given value and variable.

    Iterates through thresholds from best to worst and returns the first
    tier whose upper_bound >= value.

    Parameters
    ----------
    value    : the observed or modelled value (in the variable's native units)
    variable : key in THRESHOLDS (e.g. 'pwv', 'rh', 'wind')

    Returns
    -------
    label : str — e.g. 'Good', 'Questionable', 'Poor', 'Very Poor'

    Raises
    ------
    KeyError   : if variable is not in THRESHOLDS
    ValueError : if no tier matches (should never happen with +inf sentinel)
    """
    if variable not in THRESHOLDS:
        raise KeyError(
            f"Unknown variable '{variable}'. "
            f"Available: {sorted(THRESHOLDS.keys())}"
        )

    for upper_bound, label, _ in THRESHOLDS[variable]:
        if value <= upper_bound:
            return label

    raise ValueError(
        f"No tier found for {variable}={value}. "
        "Check that THRESHOLDS has a +inf sentinel as the last tier."
    )
