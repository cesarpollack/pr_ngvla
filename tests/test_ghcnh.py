import pandas as pd

from pr_ngvla.data.ghcnh import (
    build_ghcnh_master_inventory,
    filter_to_bbox,
    standardize_ghcnh_inventory,
    standardize_ghcnh_station_list,
    summarize_ghcnh_inventory_period,
)


def test_standardize_ghcnh_station_list_basic():
    df = pd.DataFrame(
        {
            "ID": ["USW00094846"],
            "LATITUDE": [18.43],
            "LONGITUDE": [-66.00],
            "ELEVATION": [3.0],
            "NAME": ["SAN JUAN AP"],
            "STATE": ["PR"],
            "WMO_ID": ["78526"],
            "ICAO": ["TJSJ"],
        }
    )

    out = standardize_ghcnh_station_list(df)

    assert list(out.columns) == [
        "station_id",
        "station_name",
        "lat",
        "lon",
        "elevation_m",
        "state",
        "wmo_id",
        "icao",
        "source",
    ]
    assert out.iloc[0]["station_id"] == "USW00094846"
    assert out.iloc[0]["source"] == "ghcnh"


def test_standardize_ghcnh_inventory_basic():
    df = pd.DataFrame(
        {
            "ID": ["USW00094846", "USW00094846"],
            "YEAR": [2004, 2005],
            "JAN": [10, 20],
            "FEB": [10, 20],
            "MAR": [10, 20],
            "APR": [10, 20],
            "MAY": [10, 20],
            "JUN": [10, 20],
            "JUL": [10, 20],
            "AUG": [10, 20],
            "SEP": [10, 20],
            "OCT": [10, 20],
            "NOV": [10, 20],
            "DEC": [10, 20],
        }
    )

    out = standardize_ghcnh_inventory(df)

    assert "annual_obs_count" in out.columns
    assert int(out.iloc[0]["annual_obs_count"]) == 120
    assert out.iloc[0]["station_id"] == "USW00094846"


def test_summarize_ghcnh_inventory_period_positive_years_only():
    df = pd.DataFrame(
        {
            "ID": ["USW00094846", "USW00094846", "USW00094846"],
            "YEAR": [2003, 2004, 2005],
            "JAN": [0, 1, 1],
            "FEB": [0, 1, 1],
            "MAR": [0, 1, 1],
            "APR": [0, 1, 1],
            "MAY": [0, 1, 1],
            "JUN": [0, 1, 1],
            "JUL": [0, 1, 1],
            "AUG": [0, 1, 1],
            "SEP": [0, 1, 1],
            "OCT": [0, 1, 1],
            "NOV": [0, 1, 1],
            "DEC": [0, 1, 1],
        }
    )

    out = summarize_ghcnh_inventory_period(df)

    assert len(out) == 1
    assert int(out.iloc[0]["start_year"]) == 2004
    assert int(out.iloc[0]["end_year"]) == 2005
    assert int(out.iloc[0]["n_years_positive"]) == 2


def test_filter_to_bbox_keeps_pr_station():
    df = pd.DataFrame(
        {
            "station_id": ["A", "B"],
            "lat": [18.30, 30.0],
            "lon": [-66.20, -90.0],
        }
    )

    out = filter_to_bbox(df, south=17.8, west=-68.0, north=18.6, east=-65.0)

    assert len(out) == 1
    assert out.iloc[0]["station_id"] == "A"


def test_build_ghcnh_master_inventory_overlap():
    stations = pd.DataFrame(
        {
            "ID": ["USW00094846"],
            "LATITUDE": [18.43],
            "LONGITUDE": [-66.00],
            "ELEVATION": [3.0],
            "NAME": ["SAN JUAN AP"],
        }
    )

    inv = pd.DataFrame(
        {
            "source": ["ghcnh"],
            "station_id": ["USW00094846"],
            "start_year": [2004],
            "end_year": [2023],
            "n_years_positive": [20],
        }
    )

    out = build_ghcnh_master_inventory(
        stations,
        inv,
        study_start_year=2004,
        study_end_year=2023,
    )

    assert len(out) == 1
    assert bool(out.iloc[0]["study_overlap"]) is True
    assert int(out.iloc[0]["years_with_data"]) == 20
