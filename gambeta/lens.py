"""Rating lenses. Each is a pure function from player-seasons to a ranking.

Phase 1 implements one lens, ``peak5``. Later phases add ``career``, ``per90``,
``biggame`` and ``teamfit`` with the same signature, and ``blend`` combines them
under a reader-controlled weight vector.

A lens answers one clearly-stated question. It does not pretend to answer
"who was best". That is a choice about which lens matters, and the project
makes the reader make it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gambeta.doubt import bca
from gambeta.kit import SEASONS, Config

_SEASON_ORDER = {season: i for i, season in enumerate(SEASONS)}
_BOOTSTRAP_RESAMPLES = 2000
_COLUMNS = [
    "player_id",
    "player",
    "score",
    "lo",
    "hi",
    "start_season",
    "end_season",
    "seasons_used",
]


def _best_window(scores: np.ndarray, positions: np.ndarray, window: int) -> tuple[float, int, int]:
    """Return ``(mean, start_index, end_index)`` of the best consecutive run.

    Selection is lexicographic: **longest window first, then highest mean.**

    Maximising the mean alone would be wrong. A single 6.0 season would beat two
    seasons averaging 5.0, so every player's "peak" would collapse to their one
    best year and the lens would stop measuring sustained excellence, which is
    the entire thing it exists to measure. Length dominates; the mean only
    separates windows of equal length.

    Seasons must be adjacent on the calendar: a gap in ``positions`` breaks the
    run, so a career interrupted by a season elsewhere cannot be bridged into a
    false peak.
    """
    best = (0, -np.inf, 0, 0)  # (length, mean, start, end)
    for i in range(len(scores)):
        for j in range(i, min(i + window, len(scores))):
            if positions[j] - positions[i] != j - i:
                break  # non-consecutive; no longer window can start here
            candidate = (j - i + 1, float(scores[i : j + 1].mean()), i, j)
            if candidate[:2] > best[:2]:
                best = candidate
    return best[1], best[2], best[3]


def peak5(df: pd.DataFrame, cfg: Config, window: int = 5) -> pd.DataFrame:
    """Rank players by their best ``window`` consecutive seasons.

    Players whose longest consecutive run is shorter than ``cfg.min_seasons``
    are **excluded**, not merely down-weighted. Two reasons, both load-bearing:

    * A one-season "best five consecutive seasons" is a category error. On real
      data this let a single outstanding campaign outrank five-season windows
      from Rooney and Ronaldo, which is not what the lens claims to measure.
    * Bootstrapping a single observation returns a zero-width interval. That is
      arithmetically correct, since one point has no resampling spread, but it
      renders as *perfect confidence* on the shakiest estimate in the table.

    Parameters
    ----------
    df
        Player-seasons with ``player_id``, ``player``, ``season``, ``score``.
    cfg
        Project config; supplies the random seed and the season floor.
    window
        Maximum window length in seasons. Shorter careers use what they have,
        subject to the ``cfg.min_seasons`` floor.

    Returns
    -------
    pd.DataFrame
        Conforms to :data:`gambeta.laws.RATING`: one row per qualifying player,
        sorted best first, each with a 95% bootstrap interval.
    """
    rows = []
    for player_id, group in df.groupby("player_id", sort=False):
        career = group.sort_values("season")
        scores = career["score"].to_numpy(dtype=float)
        positions = np.array([_SEASON_ORDER.get(s, -1) for s in career["season"]])

        mean, start, end = _best_window(scores, positions, window)
        if end - start + 1 < cfg.min_seasons:
            continue

        _, lo, hi = bca(scores[start : end + 1], n=_BOOTSTRAP_RESAMPLES, seed=cfg.seed)

        rows.append(
            {
                "player_id": player_id,
                "player": str(career["player"].iloc[0]),
                "score": mean,
                "lo": lo,
                "hi": hi,
                "start_season": str(career["season"].iloc[start]),
                "end_season": str(career["season"].iloc[end]),
                "seasons_used": int(end - start + 1),
            }
        )

    # Explicit columns so an all-excluded result is still a valid, typed frame
    # rather than a shapeless empty one that breaks the first sort downstream.
    out = pd.DataFrame(rows, columns=_COLUMNS)
    return out.sort_values("score", ascending=False).reset_index(drop=True)
