# tests/test_noaa_variable_coverage.py

import pandas as pd

from pr_ngvla.data.noaa_variable_coverage import (
    build_ghcnd_daily_validation_long,
    build_ghcnd_variable_coverage,
    build_ghcnh_hourly_validation_long,
    build_mixed_resolution_validation_long,
    build_mixed_resolution_validation_wide,
    build_isd_variable_coverage,
    build_noaa_variable_coverage_long,
    build_noaa_variable_coverage_wide,
    standardize_ghcnh_master_inventory,
    standardize_master_inventory,
    summarize_mixed_resolution_validation,
    summarize_variable_coverage,
)


def test_standardize_master_inventory_keeps_station_id_and_source():
    master = pd.DataFrame(
        {
            "id": ["STA001", "STA002", "STA001"],
            "source": ["ghcnd", "isd", "ghcnd"],
            "name": ["A", "B", "A"],
        }
    )

    out = standardize_master_inventory(master)

    assert list(out.columns) == ["station_id", "source"]
    assert len(out) == 2
    assert set(out["station_id"]) == {"STA001", "STA002"}
    assert set(out["source"]) == {"ghcnd", "isd"}


def test_build_ghcnd_variable_coverage_maps_elements_to_canonical_variables():
    master = pd.DataFrame(
        {
            "station_id": ["GHCN1"],
            "source": ["ghcnd"],
        }
    )

    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["GHCN1", "GHCN1", "GHCN1"],
            "element": ["TMIN", "AWND", "PRCP"],
            "first_year": [2005, 2010, 2004],
            "last_year": [2020, 2015, 2023],
        }
    )

    out = build_ghcnd_variable_coverage(master, ghcnd_inventory)

    assert set(out["variable"]) == {"temperature", "wind", "precipitation"}
    assert set(out["native_timescale"]) == {"daily"}
    assert out["prelim_usable"].all()


def test_build_ghcnd_variable_coverage_rejects_non_overlapping_station_variable():
    master = pd.DataFrame(
        {
            "station_id": ["GHCN1"],
            "source": ["ghcnd"],
        }
    )

    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["GHCN1"],
            "element": ["PRCP"],
            "first_year": [1990],
            "last_year": [2003],
        }
    )

    out = build_ghcnd_variable_coverage(master, ghcnd_inventory)

    assert len(out) == 1
    assert out.iloc[0]["variable"] == "precipitation"
    assert bool(out.iloc[0]["study_overlap"]) is False
    assert bool(out.iloc[0]["prelim_usable"]) is False
    assert int(out.iloc[0]["years_with_data"]) == 0


def test_build_isd_variable_coverage_uses_station_year_proxy():
    master = pd.DataFrame(
        {
            "station_id": ["123456-78901"],
            "source": ["isd"],
        }
    )

    isd_inventory = pd.DataFrame(
        {
            "usaf": [123456, 123456, 123456],
            "wban": [78901, 78901, 78901],
            "year": [2004, 2005, 2006],
            "jan": [10, 8, 0],
            "feb": [10, 8, 0],
            "mar": [10, 8, 0],
            "apr": [10, 8, 0],
            "may": [10, 8, 0],
            "jun": [10, 8, 0],
            "jul": [10, 8, 0],
            "aug": [10, 8, 0],
            "sep": [10, 8, 0],
            "oct": [10, 8, 0],
            "nov": [10, 8, 0],
            "dec": [10, 8, 0],
        }
    )

    out = build_isd_variable_coverage(master, isd_inventory)

    assert set(out["variable"]) == {
        "temperature",
        "dewpoint_rh",
        "wind",
    }
    assert set(out["native_timescale"]) == {"hourly"}
    assert set(out["native_datatype"]) == {"station_year_obs_count"}

    temp_row = out[out["variable"] == "temperature"].iloc[0]
    assert int(temp_row["start_year"]) == 2004
    assert int(temp_row["end_year"]) == 2005
    assert bool(temp_row["prelim_usable"]) is True


def test_build_noaa_variable_coverage_long_combines_sources():
    master = pd.DataFrame(
        {
            "station_id": ["G1", "123456-78901"],
            "source": ["ghcnd", "isd"],
        }
    )

    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["G1"],
            "element": ["PRCP"],
            "first_year": [2004],
            "last_year": [2023],
        }
    )

    isd_inventory = pd.DataFrame(
        {
            "usaf": [123456, 123456],
            "wban": [78901, 78901],
            "year": [2010, 2011],
            "jan": [3, 2],
            "feb": [3, 2],
            "mar": [3, 2],
            "apr": [3, 2],
            "may": [3, 2],
            "jun": [3, 2],
            "jul": [3, 2],
            "aug": [3, 2],
            "sep": [3, 2],
            "oct": [3, 2],
            "nov": [3, 2],
            "dec": [3, 2],
        }
    )

    out = build_noaa_variable_coverage_long(
        master_inventory=master,
        ghcnd_inventory=ghcnd_inventory,
        isd_inventory=isd_inventory,
    )

    assert set(out["source"]) == {"ghcnd", "isd"}
    assert set(out["variable"]) == {
        "precipitation",
        "temperature",
        "dewpoint_rh",
        "wind",
    }


def test_build_noaa_variable_coverage_wide_pivots_expected_columns():
    long_df = pd.DataFrame(
        {
            "station_id": ["S1", "S1", "S2"],
            "source": ["ghcnd", "ghcnd", "isd"],
            "variable": ["temperature", "wind", "dewpoint_rh"],
            "native_datatype": ["TMIN|TMAX", "AWND", "station_year_obs_count"],
            "native_timescale": ["daily", "daily", "hourly"],
            "start_year": [2004, 2010, 2008],
            "end_year": [2023, 2012, 2023],
            "years_with_data": [20, 3, 16],
            "study_overlap": [True, True, True],
            "prelim_usable": [True, True, True],
            "notes": [pd.NA, pd.NA, pd.NA],
        }
    )

    out = build_noaa_variable_coverage_wide(long_df)

    assert "temperature_available" in out.columns
    assert "wind_available" in out.columns
    assert "dewpoint_rh_available" in out.columns
    assert "precipitation_available" in out.columns
    assert "n_variables_available" in out.columns

    s1 = out[(out["source"] == "ghcnd") & (out["station_id"] == "S1")].iloc[0]
    assert bool(s1["temperature_available"]) is True
    assert bool(s1["wind_available"]) is True
    assert int(s1["n_variables_available"]) == 2

    s2 = out[(out["source"] == "isd") & (out["station_id"] == "S2")].iloc[0]
    assert bool(s2["dewpoint_rh_available"]) is True
    assert int(s2["n_variables_available"]) == 1


def test_summarize_variable_coverage_counts_rows_and_usable():
    long_df = pd.DataFrame(
        {
            "station_id": ["A", "B", "C"],
            "source": ["ghcnd", "ghcnd", "isd"],
            "variable": ["temperature", "temperature", "wind"],
            "prelim_usable": [True, False, True],
        }
    )

    out = summarize_variable_coverage(long_df)

    row_ghcnd_temp = out[
        (out["source"] == "ghcnd") & (out["variable"] == "temperature")
    ].iloc[0]
    assert int(row_ghcnd_temp["n_station_variable_rows"]) == 2
    assert int(row_ghcnd_temp["n_prelim_usable"]) == 1

    row_isd_wind = out[
        (out["source"] == "isd") & (out["variable"] == "wind")
    ].iloc[0]
    assert int(row_isd_wind["n_station_variable_rows"]) == 1
    assert int(row_isd_wind["n_prelim_usable"]) == 1



def test_standardize_ghcnh_master_inventory_derives_missing_selector_flags():
    master = pd.DataFrame(
        {
            "station_id": ["H1"],
            "source": ["ghcnh"],
            "start_year": [2004],
            "end_year": [2023],
        }
    )

    out = standardize_ghcnh_master_inventory(master)

    assert list(out.columns) == [
        "station_id",
        "source",
        "start_year",
        "end_year",
        "years_with_data",
        "study_overlap",
        "prelim_usable",
    ]
    assert out.iloc[0]["station_id"] == "H1"
    assert int(out.iloc[0]["years_with_data"]) == 20
    assert bool(out.iloc[0]["study_overlap"]) is True
    assert bool(out.iloc[0]["prelim_usable"]) is True



def test_build_ghcnh_hourly_validation_long_selects_core_hourly_variables():
    ghcnh_master = pd.DataFrame(
        {
            "station_id": ["H1"],
            "source": ["ghcnh"],
            "start_year": [2004],
            "end_year": [2023],
            "years_with_data": [20],
            "study_overlap": [True],
            "prelim_usable": [True],
        }
    )

    out = build_ghcnh_hourly_validation_long(ghcnh_master)

    assert set(out["variable"]) == {"temperature", "dewpoint_rh", "wind"}
    assert set(out["validation_tier"]) == {"hourly_core"}
    assert set(out["native_timescale"]) == {"hourly"}
    assert set(out["selector_status"]) == {"accepted"}
    assert out["selector_selected"].all()



def test_build_ghcnd_daily_validation_long_keeps_daily_wind_conditional_by_default():
    master = pd.DataFrame(
        {
            "station_id": ["G1"],
            "source": ["ghcnd"],
        }
    )

    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["G1", "G1", "G1"],
            "element": ["TMIN", "PRCP", "AWND"],
            "first_year": [2004, 2004, 2004],
            "last_year": [2023, 2023, 2023],
        }
    )

    out = build_ghcnd_daily_validation_long(master, ghcnd_inventory)

    accepted = out[out["selector_status"] == "accepted"]
    assert set(accepted["variable"]) == {"temperature", "precipitation"}
    assert accepted["selector_selected"].all()

    wind = out[out["variable"] == "wind"].iloc[0]
    assert wind["selector_status"] == "conditional"
    assert bool(wind["prelim_usable"]) is True
    assert bool(wind["selector_selected"]) is False



def test_build_ghcnd_daily_validation_long_can_enable_daily_wind_explicitly():
    master = pd.DataFrame(
        {
            "station_id": ["G1"],
            "source": ["ghcnd"],
        }
    )

    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["G1"],
            "element": ["AWND"],
            "first_year": [2004],
            "last_year": [2023],
        }
    )

    out = build_ghcnd_daily_validation_long(
        master,
        ghcnd_inventory,
        include_daily_wind=True,
    )

    assert len(out) == 1
    assert out.iloc[0]["selector_status"] == "accepted"
    assert bool(out.iloc[0]["selector_selected"]) is True



def test_build_mixed_resolution_validation_wide_creates_tier_specific_selector_columns():
    ghcnh_master = pd.DataFrame(
        {
            "station_id": ["H1"],
            "source": ["ghcnh"],
            "start_year": [2004],
            "end_year": [2023],
            "years_with_data": [20],
            "study_overlap": [True],
            "prelim_usable": [True],
        }
    )
    ghcnd_master = pd.DataFrame(
        {
            "station_id": ["G1"],
            "source": ["ghcnd"],
        }
    )
    ghcnd_inventory = pd.DataFrame(
        {
            "station_id": ["G1", "G1"],
            "element": ["TMIN", "PRCP"],
            "first_year": [2004, 2004],
            "last_year": [2023, 2023],
        }
    )

    long_df = build_mixed_resolution_validation_long(
        ghcnh_master_inventory=ghcnh_master,
        ghcnd_master_inventory=ghcnd_master,
        ghcnd_inventory=ghcnd_inventory,
    )
    wide_df = build_mixed_resolution_validation_wide(long_df)

    assert "hourly_core_temperature_selected" in wide_df.columns
    assert "hourly_core_dewpoint_rh_selected" in wide_df.columns
    assert "hourly_core_wind_selected" in wide_df.columns
    assert "daily_broad_temperature_selected" in wide_df.columns
    assert "daily_broad_precipitation_selected" in wide_df.columns

    hourly_row = wide_df[wide_df["validation_tier"] == "hourly_core"].iloc[0]
    assert bool(hourly_row["hourly_core_temperature_selected"]) is True
    assert int(hourly_row["n_selected_variables"]) == 3

    daily_row = wide_df[wide_df["validation_tier"] == "daily_broad"].iloc[0]
    assert bool(daily_row["daily_broad_temperature_selected"]) is True
    assert bool(daily_row["daily_broad_precipitation_selected"]) is True
    assert int(daily_row["n_selected_variables"]) == 2



def test_summarize_mixed_resolution_validation_counts_selected_rows():
    long_df = pd.DataFrame(
        {
            "station_id": ["H1", "G1", "G2"],
            "source": ["ghcnh", "ghcnd", "ghcnd"],
            "validation_tier": ["hourly_core", "daily_broad", "daily_broad"],
            "variable": ["temperature", "wind", "wind"],
            "native_datatype": ["a", "b", "b"],
            "native_timescale": ["hourly", "daily", "daily"],
            "start_year": [2004, 2004, 2004],
            "end_year": [2023, 2023, 2023],
            "years_with_data": [20, 20, 20],
            "study_overlap": [True, True, True],
            "prelim_usable": [True, True, False],
            "selector_status": ["accepted", "conditional", "conditional"],
            "selector_selected": [True, False, False],
            "notes": [pd.NA, pd.NA, pd.NA],
        }
    )

    out = summarize_mixed_resolution_validation(long_df)

    hourly = out[
        (out["source"] == "ghcnh")
        & (out["validation_tier"] == "hourly_core")
        & (out["variable"] == "temperature")
    ].iloc[0]
    assert int(hourly["n_station_variable_rows"]) == 1
    assert int(hourly["n_prelim_usable"]) == 1
    assert int(hourly["n_selected"]) == 1

    daily_wind = out[
        (out["source"] == "ghcnd")
        & (out["validation_tier"] == "daily_broad")
        & (out["variable"] == "wind")
    ].iloc[0]
    assert int(daily_wind["n_station_variable_rows"]) == 2
    assert int(daily_wind["n_prelim_usable"]) == 1
    assert int(daily_wind["n_selected"]) == 0
