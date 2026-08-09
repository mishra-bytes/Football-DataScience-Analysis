"""Derived metrics: transfer collapsing, per-90 rates, and share of club output.

Everything here is vectorized. ``groupby.apply`` is deliberately avoided — its
semantics shifted in pandas 3.0 and it is slower than the merge-based
equivalents below.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_SUM = ["minutes", "mp", "goals", "assists", "npg", "yellow", "red"]
_KEEP = ["qid", "league", "player", "born", "nation", "pos"]
_MINUTES_PER_MATCH = 90.0


def collapse_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse mid-season transfers into one row per ``(player_id, season)``.

    A player who changes clubs mid-season appears once per club in FBref's
    output. Counting stats are summed and the clubs are joined into a ``teams``
    string, so a transfer season is not silently counted twice.
    """
    keys = ["player_id", "season"]
    grouped = df.groupby(keys, as_index=False, sort=False)

    totals = grouped.agg({**{c: "sum" for c in _SUM}, **{c: "first" for c in _KEEP}})
    teams = (
        df.sort_values("team")
        .groupby(keys, as_index=False, sort=False)["team"]
        .agg(lambda names: ", ".join(dict.fromkeys(names)))
        .rename(columns={"team": "teams"})
    )
    return totals.merge(teams, on=keys, how="left")


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-90 rate columns.

    Zero minutes yields a zero rate rather than a division error, so squad
    players who never took the pitch do not poison downstream aggregates.
    """
    out = df.copy()
    nineties = out["minutes"].to_numpy(dtype=float) / _MINUTES_PER_MATCH
    safe = np.where(nineties > 0, nineties, np.nan)

    for name, source in (("goals_p90", "goals"), ("assists_p90", "assists"), ("npg_p90", "npg")):
        out[name] = np.nan_to_num(out[source].to_numpy(dtype=float) / safe)
    out["ga_p90"] = out["goals_p90"] + out["assists_p90"]
    return out


def add_team_share(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Add each player's share of the goals scored by the clubs they played for.

    A player who scores 20 of their club's 40 goals carried more of the attack
    than one who scored 20 of 90, and this column is what lets a later lens say
    so.

    Parameters
    ----------
    df
        Collapsed player-season frame, one row per ``(player_id, season)``.
    raw
        Uncollapsed frame carrying ``player_id``, ``season``, ``team`` and
        ``goals``, used to total each club's output.
    """
    keys = ["player_id", "season"]

    club_goals = (
        raw.groupby(["season", "team"], as_index=False)["goals"]
        .sum()
        .rename(columns={"goals": "_club_goals"})
    )
    per_club = raw[["player_id", "season", "team", "goals"]].merge(
        club_goals, on=["season", "team"], how="left"
    )
    totals = per_club.groupby(keys, as_index=False).agg(
        _player_goals=("goals", "sum"), _club_total=("_club_goals", "sum")
    )
    totals["team_goal_share"] = np.where(
        totals["_club_total"] > 0,
        totals["_player_goals"] / totals["_club_total"].replace(0, np.nan),
        0.0,
    )
    return df.merge(totals[[*keys, "team_goal_share"]], on=keys, how="left")
