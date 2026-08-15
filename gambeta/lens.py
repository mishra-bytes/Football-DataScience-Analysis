"""Rating lenses. Each is a pure function from player-seasons to a ranking.

Phase 1 implements one lens, ``peak5``. Later phases add ``career``, ``per90``,
``biggame`` and ``teamfit`` with the same signature, and ``blend`` combines them
under a reader-controlled weight vector.

A lens answers one clearly-stated question. It does not pretend to answer
"who was best". That is a choice about which lens matters, and the project
makes the reader make it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from gambeta.doubt import bca
from gambeta.kit import SEASONS, Config

_SEASON_ORDER = {season: i for i, season in enumerate(SEASONS)}
_BOOTSTRAP_RESAMPLES = 2000
_FULL_SEASON = 3420.0
"""A full season's minutes: 38 matches at 90 minutes."""
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


def _rate_careers(
    df: pd.DataFrame,
    cfg: Config,
    score_column: str,
    reduce: Callable[[np.ndarray, np.ndarray], float],
    require_nonzero: bool = False,
) -> pd.DataFrame:
    """Rank whole careers under one reduction from seasons to a single number.

    Shared by every lens except ``peak5``, which needs a window search the others
    do not. The reduction receives ``(scores, minutes)`` so a lens can weight by
    playing time or ignore it, and the interval is bootstrapped over the same
    seasons the reduction consumed, which is what makes the interval mean
    anything.
    """
    rows = []
    for player_id, group in df.groupby("player_id", sort=False):
        careerframe = group.sort_values("season")
        scores = careerframe[score_column].to_numpy(dtype=float)
        minutes = careerframe.get("minutes", pd.Series(1.0, index=careerframe.index)).to_numpy(
            dtype=float
        )
        if len(scores) < cfg.min_seasons:
            continue
        if require_nonzero and not np.any(scores > 0):
            continue

        _, lo, hi = bca(scores, n=_BOOTSTRAP_RESAMPLES, seed=cfg.seed)
        rows.append(
            {
                "player_id": player_id,
                "player": str(careerframe["player"].iloc[0]),
                "score": reduce(scores, minutes),
                "lo": lo,
                "hi": hi,
                "start_season": str(careerframe["season"].iloc[0]),
                "end_season": str(careerframe["season"].iloc[-1]),
                "seasons_used": int(len(scores)),
            }
        )
    out = pd.DataFrame(rows, columns=_COLUMNS)
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def career(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Rank by cumulative value: how good, multiplied by how much of it there was.

    ``peak5`` deliberately cannot see the difference between ten great seasons
    and five, because it measures a peak. This lens is the other half of that
    argument, and it is the one under which a long, level career beats a short,
    brilliant one.

    Seasons are summed rather than averaged, each weighted by its share of a full
    campaign, so half a season contributes half. Summing raw season scores
    instead would let a player accumulate value from cameos.
    """
    return _rate_careers(
        df, cfg, "score", lambda s, m: float(np.sum(s * np.clip(m / _FULL_SEASON, 0.0, 1.0)))
    )


def per90(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Rank by level alone, weighted by minutes, with length deliberately ignored.

    The complement of :func:`career`. It answers "how good was he when he
    played", which is the question a fan actually argues about and the one every
    volume metric refuses to answer.

    Minutes weighting is what stops this being a cameo lens: without it, one
    outstanding 200-minute season would outrank a decade.
    """
    return _rate_careers(
        df, cfg, "score", lambda s, m: float(np.average(s, weights=np.where(m > 0, m, 1e-9)))
    )


def biggame(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Rank by European and international output only.

    Players with no continental minutes across their whole career are
    **excluded**, not scored zero. That is the opposite of what the
    ``continental`` requirement does in the gate, and deliberately so: the gate
    asks "did he meet this requirement", where never turning up is an answer,
    while this lens asks "how good was he on the big nights", where never turning
    up is not a low score but no data at all. Ranking an empty career at zero
    would put every domestic-only player in a tie at the bottom and imply they
    had been measured.
    """
    return _rate_careers(
        df, cfg, "continental", lambda s, m: float(np.mean(s)), require_nonzero=True
    )


LENSES: dict[str, Callable[[pd.DataFrame, Config], pd.DataFrame]] = {
    "peak5": peak5,
    "career": career,
    "per90": per90,
    "biggame": biggame,
}
"""Every lens, by name. The dashboard builds its selector from this."""
