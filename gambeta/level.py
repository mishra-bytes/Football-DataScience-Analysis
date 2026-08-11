"""Era normalization: levelling the playing field across 25 seasons.

A goal in 2000-01 is not a goal in 2024-25. Every rate metric is z-scored
*within* its ``(league, season)``, so a player is measured against the
contemporaries they actually faced. Cross-era comparison then happens on the
z-scale, which is the only defensible way to do it with the data available.

A short season is not shrunk here. It is carried at full strength and then
weighted by its minutes when the career is pooled, in
:func:`gambeta.gate.career_profile`. The two are not the same correction and the
difference is worked through in the era chapter.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def zscore(
    df: pd.DataFrame,
    cols: Sequence[str],
    by: Sequence[str] = ("league", "season"),
) -> pd.DataFrame:
    """Add ``<col>_z`` columns holding within-group standard scores.

    Uses the population standard deviation (``ddof=0``): a season is the whole
    population of players who played it, not a sample drawn from something
    larger. A group with zero variance yields zeros rather than NaN or infinity.

    Parameters
    ----------
    df
        Frame to normalize.
    cols
        Columns to standardize.
    by
        Grouping keys defining an era. Defaults to league and season.
    """
    out = df.copy()
    for col in cols:
        grouped = out.groupby(list(by))[col]
        mean = grouped.transform("mean")
        std = grouped.transform("std", ddof=0)
        out[f"{col}_z"] = ((out[col] - mean) / std.where(std != 0)).fillna(0.0)
    return out
