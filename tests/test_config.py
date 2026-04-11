"""
Tests for pr_ngvla.config — verifies all ngVLA threshold constants
against their primary sources (Selina 2020, Linford & Cooper 2023).
Run with: pytest tests/
"""
import pytest
from pr_ngvla.config import (
    # System Spec — Temperature ENV0313/0323/0332/0342
    TEMP_PRECISION_MIN, TEMP_PRECISION_MAX,
    TEMP_NORMAL_MIN, TEMP_NORMAL_MAX,
    TEMP_LIMITS_MIN, TEMP_LIMITS_MAX,
    TEMP_SURVIVAL_MIN, TEMP_SURVIVAL_MAX,
    # System Spec — PWV ENV0316/0326
    PWV_PRECISION_MIN, PWV_PRECISION_MAX, PWV_PRECISION_MEDIAN,
    PWV_NORMAL_MIN, PWV_NORMAL_MAX, PWV_NORMAL_MEDIAN,
    # System Spec — Wind ENV0312/0322/0331/0341/0361
    WIND_PRECISION_AVG, WIND_PRECISION_GUST,
    WIND_NORMAL_AVG, WIND_NORMAL_GUST,
    WIND_LIMITS_AVG, WIND_LIMITS_GUST,
    WIND_STANDBY_AVG, WIND_SURVIVAL_AVG,
    # Memo 117 Table 2 — RH classification
    RH_GOOD_MAX, RH_QUESTIONABLE_MIN, RH_POOR_MIN, RH_VERY_POOR,
    # Memo 117 Table 2 — Wind classification
    WIND_GOOD_MAX, WIND_QUESTIONABLE_MIN, WIND_POOR_MIN, WIND_VERY_POOR_MIN,
    # Memo 117 Table 2 — Dew point depression
    TDEP_GOOD_MIN, TDEP_QUESTIONABLE_MAX, TDEP_POOR_MAX, TDEP_VERY_POOR,
    # Memo 117 — Precipitation (AMS-derived mm/hr)
    PRECIP_QUESTIONABLE_MIN_MM_HR, PRECIP_POOR_MIN_MM_HR, PRECIP_VERY_POOR_MIN_MM_HR,
    # Unit conversions
    KELVIN_TO_CELSIUS, PA_TO_HPA, M_TO_MM,
)


class TestTemperatureSystemSpec:
    """ENV0313, ENV0323, ENV0332, ENV0342 — verified against ngvla_variables_table.docx"""

    def test_precision_range(self):
        assert TEMP_PRECISION_MIN == -15.0, "ENV0313: -15°C <= T <= 25°C"
        assert TEMP_PRECISION_MAX ==  25.0, "ENV0313: -15°C <= T <= 25°C"

    def test_normal_range(self):
        assert TEMP_NORMAL_MIN == -15.0, "ENV0323: -15°C <= T <= 35°C"
        assert TEMP_NORMAL_MAX ==  35.0

    def test_limits_range(self):
        assert TEMP_LIMITS_MIN == -20.0, "ENV0332: -20°C <= T <= 45°C"
        assert TEMP_LIMITS_MAX ==  45.0

    def test_survival_range(self):
        assert TEMP_SURVIVAL_MIN == -30.0, "ENV0342: -30°C <= T <= 50°C"
        assert TEMP_SURVIVAL_MAX ==  50.0

    def test_tiers_are_progressively_wider(self):
        """Each tier must be wider than or equal to the previous."""
        assert TEMP_NORMAL_MIN   <= TEMP_PRECISION_MIN
        assert TEMP_NORMAL_MAX   >= TEMP_PRECISION_MAX
        assert TEMP_LIMITS_MIN   <= TEMP_NORMAL_MIN
        assert TEMP_LIMITS_MAX   >= TEMP_NORMAL_MAX
        assert TEMP_SURVIVAL_MIN <= TEMP_LIMITS_MIN
        assert TEMP_SURVIVAL_MAX >= TEMP_LIMITS_MAX


class TestPWVSystemSpec:
    """ENV0316, ENV0326"""

    def test_precision(self):
        assert PWV_PRECISION_MIN    ==  1.0
        assert PWV_PRECISION_MAX    ==  6.0
        assert PWV_PRECISION_MEDIAN ==  4.0

    def test_normal(self):
        assert PWV_NORMAL_MIN    ==  1.0
        assert PWV_NORMAL_MAX    == 26.0
        assert PWV_NORMAL_MEDIAN == 18.0

    def test_precision_is_stricter_than_normal(self):
        assert PWV_PRECISION_MAX < PWV_NORMAL_MAX


class TestWindSystemSpec:
    """ENV0312, ENV0322, ENV0331, ENV0341, ENV0361"""

    def test_precision(self):
        assert WIND_PRECISION_AVG  ==  5.0
        assert WIND_PRECISION_GUST ==  7.0

    def test_normal(self):
        assert WIND_NORMAL_AVG  ==  7.0
        assert WIND_NORMAL_GUST == 10.0

    def test_limits(self):
        assert WIND_LIMITS_AVG  == 15.0
        assert WIND_LIMITS_GUST == 20.0

    def test_standby_survival(self):
        assert WIND_STANDBY_AVG  == 30.0
        assert WIND_SURVIVAL_AVG == 50.0

    def test_tiers_are_progressively_looser(self):
        assert WIND_NORMAL_AVG   > WIND_PRECISION_AVG
        assert WIND_LIMITS_AVG   > WIND_NORMAL_AVG
        assert WIND_STANDBY_AVG  > WIND_LIMITS_AVG
        assert WIND_SURVIVAL_AVG > WIND_STANDBY_AVG


class TestMemo117RH:
    """Linford & Cooper 2023, Table 2"""

    def test_thresholds(self):
        assert RH_GOOD_MAX         ==  50.0
        assert RH_QUESTIONABLE_MIN ==  50.0
        assert RH_POOR_MIN         ==  80.0
        assert RH_VERY_POOR        == 100.0

    def test_good_questionable_boundary_is_same(self):
        assert RH_GOOD_MAX == RH_QUESTIONABLE_MIN


class TestMemo117Wind:
    """Linford & Cooper 2023, Table 2 — Max wind speed"""

    def test_thresholds(self):
        assert WIND_GOOD_MAX         ==  9.0
        assert WIND_QUESTIONABLE_MIN ==  9.0
        assert WIND_POOR_MIN         == 13.4
        assert WIND_VERY_POOR_MIN    == 24.5


class TestMemo117DewPointDepression:
    """Linford & Cooper 2023, Table 2"""

    def test_thresholds(self):
        assert TDEP_GOOD_MIN         == 2.0
        assert TDEP_QUESTIONABLE_MAX == 2.0
        assert TDEP_POOR_MAX         == 0.5
        assert TDEP_VERY_POOR        == 0.0

    def test_ordering(self):
        """TDEP thresholds must decrease from Good to Very Poor."""
        assert TDEP_GOOD_MIN > TDEP_POOR_MAX > TDEP_VERY_POOR


class TestMemo117Precipitation:
    """AMS rain categories as used in Memo 117 narrative."""

    def test_thresholds(self):
        assert PRECIP_QUESTIONABLE_MIN_MM_HR ==  0.1
        assert PRECIP_POOR_MIN_MM_HR         ==  2.5
        assert PRECIP_VERY_POOR_MIN_MM_HR    ==  7.6

    def test_ordering(self):
        assert PRECIP_QUESTIONABLE_MIN_MM_HR < PRECIP_POOR_MIN_MM_HR < PRECIP_VERY_POOR_MIN_MM_HR


class TestUnitConversions:

    def test_kelvin_to_celsius_direction(self):
        """0 degC = 273.15 K"""
        T_K = 273.15
        T_C = T_K + KELVIN_TO_CELSIUS
        assert abs(T_C - 0.0) < 1e-6

    def test_kelvin_to_celsius_boiling(self):
        """100 degC = 373.15 K"""
        T_K = 373.15
        T_C = T_K + KELVIN_TO_CELSIUS
        assert abs(T_C - 100.0) < 1e-6

    def test_pa_to_hpa(self):
        """Standard sea-level pressure: 101325 Pa = 1013.25 hPa"""
        P_Pa = 101325.0
        P_hPa = P_Pa * PA_TO_HPA
        assert abs(P_hPa - 1013.25) < 0.01

    def test_m_to_mm(self):
        """1 m = 1000 mm"""
        assert M_TO_MM == 1000.0
