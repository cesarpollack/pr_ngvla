"""
src/pr_ngvla/analysis/fuzzy.py

Fuzzy-logic site selection index for ngVLA antenna placement in Puerto Rico.

Design
------
Each variable's exceedance fraction (0–1) is converted to a favorability score
(0=least favorable, 1=most favorable) via a linear membership function:

    favorability_i = 1 - exceedance_fraction_i

The composite index is a weighted mean of individual favorability scores.
Equal weights are used for the poster (Phase 3); sensitivity analysis across
weight sets is deferred to Phase 4.

Variables and primary thresholds (Phase 2 results)
---------------------------------------------------
  rh    : fraction of hours with RH > 50%   (mean ~97.9%)
  wind  : fraction of hours with wind > 9 m/s (mean ~0%)
  precip: fraction of hours with precip > 1 mm/hr (mean ~25.4%)
  pwv   : fraction of hours with PWV > 26 mm  (mean ~90.2%)

Usage
-----
    from pr_ngvla.analysis.fuzzy import linear_membership, composite_index, annual_composite
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import xarray as xr

# ---------------------------------------------------------------------------
# Default weights — equal (poster version; update for sensitivity analysis)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "rh": 0.25,
    "wind": 0.25,
    "precip": 0.25,
    "pwv": 0.25,
}


# ---------------------------------------------------------------------------
# Membership function
# ---------------------------------------------------------------------------

def linear_membership(exceedance: xr.DataArray) -> xr.DataArray:
    """
    Convert exceedance fraction [0, 1] → favorability score [0, 1].

    Linear inversion: favorability = 1 - exceedance_fraction.
    Values are clipped to [0, 1] for numerical safety.

    Parameters
    ----------
    exceedance : xr.DataArray
        Fraction of hours above threshold. Shape: (month, lat, lon) or (lat, lon).
        Must be in [0, 1].

    Returns
    -------
    xr.DataArray
        Favorability score in [0, 1]. 0 = least favorable, 1 = most favorable.
    """
    suit = (1.0 - exceedance).clip(0.0, 1.0)
    suit.attrs = {
        "long_name": "Favorability score (linear fuzzy membership)",
        "units": "dimensionless [0=least favorable, 1=most favorable]",
        "membership_function": "favorability = 1 - exceedance_fraction",
    }
    return suit


# ---------------------------------------------------------------------------
# Composite index
# ---------------------------------------------------------------------------

def composite_index(
    exceedance_dict: Dict[str, xr.DataArray],
    weights: Optional[Dict[str, float]] = None,
) -> xr.DataArray:
    """
    Compute weighted composite site selection index.

    Parameters
    ----------
    exceedance_dict : dict
        Keys: variable names that match keys in `weights`.
        Values: xr.DataArray of exceedance fractions, shape (month, lat, lon)
                or (lat, lon) for annual.
    weights : dict, optional
        Weights per variable. Missing variables are assigned weight=0.
        Weights are normalized to sum to 1. Defaults to DEFAULT_WEIGHTS (equal).

    Returns
    -------
    xr.DataArray
        Site selection index in [0, 1]. Same shape as inputs.
        NaN where any input is NaN (ocean pixels).
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Use only variables present in exceedance_dict
    active_vars = [v for v in exceedance_dict if v in weights]
    if not active_vars:
        raise ValueError(
            f"No matching variables between exceedance_dict {list(exceedance_dict)} "
            f"and weights {list(weights)}."
        )

    total_w = sum(weights[v] for v in active_vars)
    if total_w == 0:
        raise ValueError("All weights are zero.")

    composite: Optional[xr.DataArray] = None
    for var in active_vars:
        w = weights[var] / total_w
        suit = linear_membership(exceedance_dict[var])
        if composite is None:
            composite = w * suit
        else:
            composite = composite + w * suit

    # Propagate NaN: any pixel that is NaN in ANY variable → NaN in composite
    for var in active_vars:
        nan_mask = np.isnan(exceedance_dict[var])
        composite = composite.where(~nan_mask)

    composite.name = "site_selection_index"
    composite.attrs = {
        "long_name": "Composite site selection index (fuzzy-logic, equal weights)",
        "units": "dimensionless [0=least favorable, 1=most favorable]",
        "variables_used": ", ".join(active_vars),
        "weights_normalized": str({v: round(weights[v] / total_w, 4) for v in active_vars}),
        "membership_function": "linear: favorability = 1 - exceedance_fraction",
        "thresholds": "RH>50%, wind>9m/s, precip>1mm/hr, PWV>26mm",
        "period": "2004-2023 (20 years)",
    }
    return composite


# ---------------------------------------------------------------------------
# Annual summary
# ---------------------------------------------------------------------------

def annual_composite(monthly_composite: xr.DataArray) -> xr.DataArray:
    """
    Annual mean of monthly composite index.

    Parameters
    ----------
    monthly_composite : xr.DataArray
        Shape: (month, lat, lon), coordinate 'month' in [1, 12].

    Returns
    -------
    xr.DataArray
        Shape: (lat, lon). Annual mean suitability index.
    """
    ann = monthly_composite.mean(dim="month")
    ann.name = "site_selection_index_annual"
    ann.attrs = monthly_composite.attrs.copy()
    ann.attrs["long_name"] = (
        "Annual mean site selection index (fuzzy-logic, equal weights)"
    )
    return ann


# ---------------------------------------------------------------------------
# Sensitivity analysis (Phase 4 — placeholder)
# ---------------------------------------------------------------------------

def sensitivity_weights(n_samples: int = 1000, seed: int = 42) -> list[Dict[str, float]]:
    """
    Generate random weight sets for Monte Carlo sensitivity analysis (Phase 4).

    Draws uniformly from the 4-simplex (weights sum to 1, all ≥ 0).

    Parameters
    ----------
    n_samples : int
        Number of random weight sets to generate.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    list of dict
        Each dict maps variable name → weight, normalized to sum to 1.
    """
    rng = np.random.default_rng(seed)
    vars_ = ["rh", "wind", "precip", "pwv"]
    # Dirichlet distribution gives uniform samples on the simplex
    alphas = rng.dirichlet(np.ones(len(vars_)), size=n_samples)
    return [dict(zip(vars_, row)) for row in alphas]
