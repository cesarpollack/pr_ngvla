"""
Tests for pr_ngvla.analysis.classify — Memo 117 classification engine.
Each test case has a clear physical rationale.
"""
import numpy as np
import xarray as xr
import pytest
from pr_ngvla.analysis.classify import classify_hourly, fraction_good, class_fractions


def da(val):
    """Helper: scalar -> 1x1 DataArray"""
    return xr.DataArray(np.array([[float(val)]]))


def classify(rh, ws, tp, tdep, pwv=None):
    """Classify a single set of conditions, return integer 0-3."""
    pwv_da = da(pwv) if pwv is not None else None
    return int(classify_hourly(da(rh), da(ws), da(tp), da(tdep), pwv_da).values[0, 0])


class TestClassifyRH:

    def test_good(self):
        assert classify(rh=40, ws=3, tp=0, tdep=5) == 0  # Good

    def test_questionable(self):
        assert classify(rh=60, ws=3, tp=0, tdep=5) == 1  # RH > 50%

    def test_poor(self):
        assert classify(rh=90, ws=3, tp=0, tdep=5) == 2  # RH > 80%

    def test_very_poor(self):
        assert classify(rh=100, ws=3, tp=0, tdep=5) == 3  # RH = 100%

    def test_boundary_exactly_50(self):
        """RH = 50% is exactly the Good/Q boundary -> Good"""
        assert classify(rh=50, ws=3, tp=0, tdep=5) == 0

    def test_boundary_just_above_50(self):
        assert classify(rh=50.1, ws=3, tp=0, tdep=5) == 1


class TestClassifyWind:

    def test_good(self):
        assert classify(rh=30, ws=5, tp=0, tdep=5) == 0

    def test_questionable(self):
        assert classify(rh=30, ws=10, tp=0, tdep=5) == 1  # ws > 9

    def test_poor(self):
        assert classify(rh=30, ws=15, tp=0, tdep=5) == 2  # ws > 13.4

    def test_very_poor(self):
        assert classify(rh=30, ws=25, tp=0, tdep=5) == 3  # ws > 24.5


class TestClassifyPrecip:

    def test_no_rain_good(self):
        assert classify(rh=30, ws=3, tp=0.0, tdep=5) == 0

    def test_trace_rain_questionable(self):
        assert classify(rh=30, ws=3, tp=0.5, tdep=5) == 1  # 0.1-2.5 mm/hr

    def test_moderate_rain_poor(self):
        assert classify(rh=30, ws=3, tp=5.0, tdep=5) == 2  # 2.5-7.6 mm/hr

    def test_heavy_rain_very_poor(self):
        assert classify(rh=30, ws=3, tp=10.0, tdep=5) == 3  # > 7.6 mm/hr


class TestClassifyTdep:

    def test_good(self):
        assert classify(rh=30, ws=3, tp=0, tdep=5.0) == 0  # T-Td >= 2

    def test_questionable(self):
        assert classify(rh=30, ws=3, tp=0, tdep=1.0) == 1  # T-Td < 2

    def test_poor(self):
        assert classify(rh=30, ws=3, tp=0, tdep=0.3) == 2  # T-Td < 0.5

    def test_very_poor_fog(self):
        assert classify(rh=30, ws=3, tp=0, tdep=-0.5) == 3  # T < Td (fog)


class TestWorstCaseLogic:
    """Confirm worst-case (maximum tier) is applied across variables."""

    def test_wind_questionable_rh_poor_gives_poor(self):
        """ws=10 (Q) + rh=85 (P) -> Poor"""
        assert classify(rh=85, ws=10, tp=0, tdep=5) == 2

    def test_all_questionable_gives_questionable(self):
        assert classify(rh=60, ws=10, tp=0.5, tdep=1.5) == 1

    def test_one_very_poor_dominates(self):
        """Perfect wind+precip+tdep, but rh=100 -> Very Poor"""
        assert classify(rh=100, ws=3, tp=0, tdep=5) == 3


class TestPWVClassification:

    def test_pwv_good(self):
        assert classify(rh=30, ws=3, tp=0, tdep=5, pwv=4.0) == 0  # <= 6mm

    def test_pwv_questionable(self):
        assert classify(rh=30, ws=3, tp=0, tdep=5, pwv=15.0) == 1  # 6-26mm

    def test_pwv_very_poor(self):
        assert classify(rh=30, ws=3, tp=0, tdep=5, pwv=30.0) == 3  # > 26mm


class TestFractionGood:

    def test_all_good(self):
        c = xr.DataArray(np.zeros((10, 3, 3), dtype=int))  # all Good
        frac = fraction_good(c, dim='dim_0')
        assert float(frac.mean()) == 1.0

    def test_none_good(self):
        c = xr.DataArray(np.ones((10, 3, 3), dtype=int))  # all Questionable
        frac = fraction_good(c, dim='dim_0')
        assert float(frac.mean()) == 0.0

    def test_half_good(self):
        data = np.zeros((10, 1, 1), dtype=int)
        data[5:] = 1  # 5 Good, 5 Questionable
        c = xr.DataArray(data)
        frac = fraction_good(c, dim='dim_0')
        assert abs(float(frac.values[0, 0]) - 0.5) < 1e-6
