"""
tests/test_noaa.py
==================

Unit tests for the NOAA metadata helpers used in the Puerto Rico
station-inventory workflow.

These tests use small synthetic DataFrames so that they:
- run quickly
- do not depend on large real files
- protect the most important metadata and filtering logic
"""

from __future__ import annotations

import pandas as pd

from pr_ngvla.data.noaa import (
    build_master_station_inventory,
    build_station_inventory_summary,
    coerce_date_column,
    derive_year_column,
    flag_stations_in_bbox,
    flag_stations_overlapping_period,
    normalize_column_names,
    standardize_ghcnd_stations,
    standardize_isd_history,
    summarize_ghcnd_inventory_period,
)


def test_normalize_column_names_basic() -> None:
    """
    Column-name normalization should be stable and predictable.
    """
    df = pd.DataFrame(columns=["STATION NAME", "ELEV(M)", "LON/LAT", "BEGIN-END"])
    out = normalize_column_names(df)

    assert list(out.columns) == [
        "station_name",
        "elev_m",
        "lon_lat",
        "begin_end",
    ]


def test_coerce_date_column_handles_mixed_formats() -> None:
    """
    Date coercion should parse both compact NOAA and ISO-style strings.
    """
    series = pd.Series(["20040131", "2023-12-31", "bad_value"])

    out = coerce_date_column(series)

    assert str(out.iloc[0].date()) == "2004-01-31"
    assert str(out.iloc[1].date()) == "2023-12-31"
    assert pd.isna(out.iloc[2])


def test_derive_year_column_returns_nullable_int() -> None:
    """
    Year extraction should yield nullable Int64 values.
    """
    series = pd.to_datetime(pd.Series(["2004-01-01", None, "2023-12-31"]))

    out = derive_year_column(series)

    assert list(out.astype("object")) == [2004, pd.NA, 2023]


def test_flag_stations_in_bbox_inclusive() -> None:
    """
    Bounding-box flagging should be inclusive on the edges.
    """
    df = pd.DataFrame(
        {
            "station_id": ["A", "B", "C"],
            "latitude": [17.8, 18.6, 19.0],
            "longitude": [-68.0, -65.0, -66.0],
        }
    )

    out = flag_stations_in_bbox(df, south=17.8, west=-68.0, north=18.6, east=-65.0)

    assert list(out["in_pr_bbox"]) == [True, True, False]


def test_flag_stations_overlapping_period() -> None:
    """
    Overlap flagging should identify stations intersecting the study window.
    """
    df = pd.DataFrame(
        {
            "station_id": ["A", "B", "C", "D"],
            "begin_date": pd.to_datetime(
                ["2000-01-01", "2024-01-01", "2010-05-01", None]
            ),
            "end_date": pd.to_datetime(
                ["2005-12-31", "2025-12-31", "2015-01-01", "2020-01-01"]
            ),
        }
    )

    out = flag_stations_overlapping_period(
        df,
        start_date="2004-01-01",
        end_date="2023-12-31",
    )

    assert list(out["overlaps_study_period"]) == [True, False, True, False]


def test_standardize_isd_history_builds_station_id() -> None:
    """
    ISD history standardization should preserve leading zeros in station IDs.
    """
    df = pd.DataFrame(
        {
            "USAF": ["007018"],
            "WBAN": ["99999"],
            "STATION NAME": ["TEST STATION"],
            "CTRY": ["US"],
            "STATE": ["PR"],
            "ICAO": ["TXXX"],
            "LAT": ["18.100"],
            "LON": ["-66.200"],
            "ELEV(M)": ["15.0"],
            "BEGIN": ["20040101"],
            "END": ["20231231"],
        }
    )

    out = standardize_isd_history(normalize_column_names(df))

    assert out.loc[0, "station_id"] == "007018-99999"
    assert out.loc[0, "begin_year"] == 2004
    assert out.loc[0, "end_year"] == 2023
    assert out.loc[0, "source"] == "isd"


def test_summarize_ghcnd_inventory_period() -> None:
    """
    GHCND inventory summarization should collapse element-specific rows
    into one station-wide period.
    """
    df = pd.DataFrame(
        {
            "station_id": ["STATION_A", "STATION_A", "STATION_B"],
            "latitude": [18.1, 18.1, 18.2],
            "longitude": [-66.1, -66.1, -66.2],
            "element": ["TMAX", "PRCP", "TMIN"],
            "first_year": [2004, 2006, 2010],
            "last_year": [2023, 2020, 2015],
        }
    )

    out = summarize_ghcnd_inventory_period(df)

    row_a = out.loc[out["station_id"] == "STATION_A"].iloc[0]
    row_b = out.loc[out["station_id"] == "STATION_B"].iloc[0]

    assert row_a["begin_year"] == 2004
    assert row_a["end_year"] == 2023
    assert row_b["begin_year"] == 2010
    assert row_b["end_year"] == 2015


def test_standardize_ghcnd_stations_uses_inventory_years() -> None:
    """
    GHCND station standardization should incorporate summarized inventory years.
    """
    stations = pd.DataFrame(
        {
            "station_id": ["RQ1TEST0001"],
            "latitude": [18.25],
            "longitude": [-66.10],
            "elevation_m": [100.0],
            "state_code": ["PR"],
            "station_name": ["TEST GHCN STATION"],
            "gsn_flag": [pd.NA],
            "hcn_crn_flag": [pd.NA],
            "wmo_id": [pd.NA],
        }
    )

    inventory = pd.DataFrame(
        {
            "station_id": ["RQ1TEST0001", "RQ1TEST0001"],
            "latitude": [18.25, 18.25],
            "longitude": [-66.10, -66.10],
            "element": ["TMAX", "PRCP"],
            "first_year": [2004, 2008],
            "last_year": [2023, 2020],
        }
    )

    out = standardize_ghcnd_stations(stations, inventory)

    assert out.loc[0, "source"] == "ghcnd"
    assert out.loc[0, "begin_year"] == 2004
    assert out.loc[0, "end_year"] == 2023
    assert str(out.loc[0, "begin_date"].date()) == "2004-01-01"
    assert str(out.loc[0, "end_date"].date()) == "2023-12-31"


def test_build_master_station_inventory_and_summary() -> None:
    """
    The master inventory builder should preserve one row per source/station_id
    and the summary should count rows by source.
    """
    isd = pd.DataFrame(
        {
            "source": ["isd"],
            "source_subtype": ["isd_history"],
            "station_id": ["123456-99999"],
            "station_name": ["ISD TEST"],
            "latitude": [18.1],
            "longitude": [-66.1],
            "elevation_m": [10.0],
            "country_code": ["US"],
            "state_code": ["PR"],
            "icao": ["TST1"],
            "usaf": ["123456"],
            "wban": ["99999"],
            "begin_date": pd.to_datetime(["2004-01-01"]),
            "end_date": pd.to_datetime(["2023-12-31"]),
            "begin_year": pd.Series([2004], dtype="Int64"),
            "end_year": pd.Series([2023], dtype="Int64"),
            "in_pr_bbox": [True],
            "overlaps_study_period": [True],
            "has_metadata_issue": [False],
            "notes": [pd.NA],
        }
    )

    ghcnd = pd.DataFrame(
        {
            "source": ["ghcnd"],
            "source_subtype": ["ghcnd_stations"],
            "station_id": ["RQ1TEST0001"],
            "station_name": ["GHCND TEST"],
            "latitude": [18.2],
            "longitude": [-66.2],
            "elevation_m": [20.0],
            "country_code": [pd.NA],
            "state_code": ["PR"],
            "icao": [pd.NA],
            "usaf": [pd.NA],
            "wban": [pd.NA],
            "begin_date": pd.to_datetime(["2005-01-01"]),
            "end_date": pd.to_datetime(["2022-12-31"]),
            "begin_year": pd.Series([2005], dtype="Int64"),
            "end_year": pd.Series([2022], dtype="Int64"),
            "in_pr_bbox": [True],
            "overlaps_study_period": [True],
            "has_metadata_issue": [False],
            "notes": [pd.NA],
        }
    )

    inventory = build_master_station_inventory([isd, ghcnd])
    summary = build_station_inventory_summary(inventory)

    assert len(inventory) == 2
    assert set(inventory["source"]) == {"isd", "ghcnd"}
    assert set(summary["source"]) == {"isd", "ghcnd"}
