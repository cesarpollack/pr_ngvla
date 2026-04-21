# tests/test_noaa_variable_coverage.py

import pandas as pd

from pr_ngvla.data.noaa_variable_coverage import (
    build_ghcnd_variable_coverage,
    build_isd_variable_coverage,
    build_noaa_variable_coverage_long,
    build_noaa_variable_coverage_wide,
    standardize_master_inventory,
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
