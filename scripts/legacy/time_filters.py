"""
src/pr_ngvla/data/time_filters.py
=================================

Centralized temporal filters for PR-ngVLA climatological analyses.

Purpose
-------
The GHCNh clean core is intentionally kept as the complete cleaned
observational record for 2004-2023. This module provides explicit,
documented time-window exclusions that can be applied by downstream analysis
scripts when a climatological product should omit a known observational
disruption window.

Current exclusion window
------------------------
- Hurricane Maria observational-disruption window:
  2017-09-01 00:00:00 <= time < 2017-11-01 00:00:00

Design rules
------------
- No file I/O.
- No hidden mutation of the input DataFrame unless the caller explicitly keeps
  the returned filtered DataFrame.
- Start time is inclusive and end time is exclusive. This convention avoids
  ambiguity at the final hour/day boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TimeExclusionWindow:
    """
    A named time window to exclude from downstream climatological analyses.

    Parameters
    ----------
    name : str
        Stable machine-readable name for the exclusion.
    start : pandas.Timestamp
        Inclusive start timestamp.
    end : pandas.Timestamp
        Exclusive end timestamp.
    reason : str
        Human-readable explanation for reports/logs.
    """

    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    reason: str


HURRICANE_MARIA_OBSERVATIONAL_DISRUPTION_WINDOW = TimeExclusionWindow(
    name="hurricane_maria_observational_disruption_window",
    start=pd.Timestamp("2017-09-01 00:00:00"),
    end=pd.Timestamp("2017-11-01 00:00:00"),
    reason=(
        "Hurricane Maria observational-disruption window used for "
        "climatological sensitivity checks."
    ),
)


DEFAULT_CLIMATOLOGICAL_EXCLUSION_WINDOWS: tuple[TimeExclusionWindow, ...] = (
    HURRICANE_MARIA_OBSERVATIONAL_DISRUPTION_WINDOW,
)


def build_time_exclusion_mask(
    df: pd.DataFrame,
    *,
    datetime_column: str,
    windows: Iterable[TimeExclusionWindow] = DEFAULT_CLIMATOLOGICAL_EXCLUSION_WINDOWS,
) -> pd.Series:
    """
    Return a boolean mask marking rows that fall inside any exclusion window.

    Parameters
    ----------
    df : pandas.DataFrame
        Input table containing a datetime column.
    datetime_column : str
        Name of the datetime column to evaluate.
    windows : iterable of TimeExclusionWindow
        Exclusion windows to apply.

    Returns
    -------
    pandas.Series
        Boolean Series aligned to ``df.index``. True means the row is inside an
        exclusion window.

    Notes
    -----
    The convention is:

        window.start <= datetime_column < window.end
    """
    if datetime_column not in df.columns:
        raise ValueError(
            f"Missing datetime column '{datetime_column}'. "
            f"Available columns: {df.columns.tolist()}"
        )

    timestamps = pd.to_datetime(df[datetime_column], errors="raise")
    mask = pd.Series(False, index=df.index)

    for window in windows:
        mask |= (timestamps >= window.start) & (timestamps < window.end)

    return mask


def apply_time_exclusions(
    df: pd.DataFrame,
    *,
    datetime_column: str,
    windows: Iterable[TimeExclusionWindow] = DEFAULT_CLIMATOLOGICAL_EXCLUSION_WINDOWS,
    copy: bool = True,
) -> pd.DataFrame:
    """
    Return ``df`` with rows inside the requested exclusion windows removed.

    This function does not write files and does not modify the project clean
    core. It only returns a filtered DataFrame for the calling analysis script.
    """
    exclusion_mask = build_time_exclusion_mask(
        df,
        datetime_column=datetime_column,
        windows=windows,
    )
    filtered = df.loc[~exclusion_mask]
    return filtered.copy() if copy else filtered


def apply_hurricane_maria_exclusion(
    df: pd.DataFrame,
    *,
    datetime_column: str = "datetime_hour",
    copy: bool = True,
) -> pd.DataFrame:
    """
    Return ``df`` excluding the Hurricane Maria observational-disruption window.

    Window applied:

        2017-09-01 00:00:00 <= datetime_column < 2017-11-01 00:00:00
    """
    return apply_time_exclusions(
        df,
        datetime_column=datetime_column,
        windows=(HURRICANE_MARIA_OBSERVATIONAL_DISRUPTION_WINDOW,),
        copy=copy,
    )


def describe_time_exclusion_windows(
    windows: Iterable[TimeExclusionWindow] = DEFAULT_CLIMATOLOGICAL_EXCLUSION_WINDOWS,
) -> pd.DataFrame:
    """
    Return a small table documenting the configured exclusion windows.

    The returned DataFrame is intended for logs or report-support tables if a
    script needs to expose which windows were applied.
    """
    records = [
        {
            "name": window.name,
            "start_inclusive": window.start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_exclusive": window.end.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": window.reason,
        }
        for window in windows
    ]
    return pd.DataFrame.from_records(records)
