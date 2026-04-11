"""
Tests for pr_ngvla.physics.atmosphere
"""
import numpy as np
import pytest
from pr_ngvla.physics.atmosphere import (
    relative_humidity, dew_point_depression, wind_speed,
)


class TestRelativeHumidity:

    def test_saturated(self):
        """T == Td -> RH = 100%"""
        rh = relative_humidity(np.array([20.0]), np.array([20.0]))
        assert abs(rh[0] - 100.0) < 0.1

    def test_very_dry(self):
        """Large T-Td -> very low RH"""
        rh = relative_humidity(np.array([30.0]), np.array([-10.0]))
        assert rh[0] < 15.0

    def test_clipped_below_100(self):
        """RH must never exceed 100% (ERA5 numerical noise)"""
        # Td slightly above T (ERA5 artifact)
        rh = relative_humidity(np.array([20.0]), np.array([20.01]))
        assert rh[0] <= 100.0

    def test_clipped_above_0(self):
        """RH must never be negative"""
        rh = relative_humidity(np.array([50.0]), np.array([-20.0]))
        assert rh[0] >= 0.0

    def test_typical_pr_conditions(self):
        """Typical Puerto Rico coastal day: T=28C, Td=22C -> RH ~70-75%"""
        rh = relative_humidity(np.array([28.0]), np.array([22.0]))
        assert 65.0 < rh[0] < 85.0


class TestDewPointDepression:

    def test_basic(self):
        tdep = dew_point_depression(np.array([25.0]), np.array([20.0]))
        assert abs(tdep[0] - 5.0) < 1e-6

    def test_saturated(self):
        """T == Td -> T-Td = 0"""
        tdep = dew_point_depression(np.array([20.0]), np.array([20.0]))
        assert abs(tdep[0]) < 1e-6

    def test_fog_below_zero(self):
        """T < Td -> T-Td < 0 (condensation / fog)"""
        tdep = dew_point_depression(np.array([19.9]), np.array([20.0]))
        assert tdep[0] < 0.0


class TestWindSpeed:

    def test_pythagoras(self):
        """Classic 3-4-5 triangle"""
        ws = wind_speed(np.array([3.0]), np.array([4.0]))
        assert abs(ws[0] - 5.0) < 1e-6

    def test_zero(self):
        ws = wind_speed(np.array([0.0]), np.array([0.0]))
        assert abs(ws[0]) < 1e-6

    def test_always_positive(self):
        """Wind speed is always >= 0 even with negative components"""
        ws = wind_speed(np.array([-5.0]), np.array([-5.0]))
        assert ws[0] > 0.0
