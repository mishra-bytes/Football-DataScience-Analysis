"""Era normalization: levelling the playing field across 25 seasons.

A goal in 2000-01 is not a goal in 2024-25. Every rate metric is z-scored
*within* its ``(league, season)``, so a player is measured against the
contemporaries they actually faced. Cross-era comparison then happens on the
z-scale, which is the only defensible way to do it with the data available.

Low-minute seasons are shrunk toward the mean, because three good games is not
evidence of a good season.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from gambeta.kit import Config


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


def shrink(values: np.ndarray, minutes: np.ndarray, prior_minutes: float) -> np.ndarray:
    """Shrink standard scores toward zero in inverse proportion to minutes played.

    Empirical-Bayes shrinkage with a fixed prior strength. Each season is
    weighted ``m / (m + m0)``, so a player-season is trusted in proportion to how
    much football it actually contains. At ``m == m0`` the score is halved; a
    player with no minutes scores zero rather than infinity.

    Parameters
    ----------
    values
        Standard scores to shrink.
    minutes
        Minutes played, same shape as ``values``.
    prior_minutes
        Prior strength in minutes. Larger values shrink harder.

    Returns
    -------
    np.ndarray
        Shrunk scores.
    """
    weight = minutes / (minutes + prior_minutes)
    return np.asarray(values * weight, dtype=float)


def score(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Add a single era-normalized, minutes-shrunk ``score`` per player-season.

    Phase 1 scores on goals-plus-assists per 90. Later phases fold in the other
    metrics; the column contract stays the same so the lenses do not change.
    """
    out = zscore(df, ["ga_p90"])
    out["score"] = shrink(
        out["ga_p90_z"].to_numpy(dtype=float),
        out["minutes"].to_numpy(dtype=float),
        cfg.prior_minutes,
    )
    return out
