"""Derived metrics: transfer collapsing, per-90 rates, and share of club output.

Everything here is vectorized. ``groupby.apply`` is deliberately avoided, because its
semantics shifted in pandas 3.0 and it is slower than the merge-based
equivalents below.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_SUM = [
    "minutes",
    "mp",
    "goals",
    "assists",
    "npg",
    "yellow",
    "red",
    # Side-table counts. A transferred player's totals add up across clubs the
    # same way their goals do; rates are recomputed afterwards, never summed.
    "starts",
    "sot",
    "complete",
    "subs",
    "second_yellow",
    "fouls",
]
"""Counting stats. ``min_pct`` is deliberately absent: it is a share of one
club's minutes, and shares do not add. Summing it gave a transferred player up
to 296% of his team's minutes."""
_KEEP = ["qid", "league", "player", "born", "nation", "pos"]
_MINUTES_PER_MATCH = 90.0


def _sum_or_missing(values: pd.Series) -> float:
    """Sum a group, but a group that is entirely missing stays missing.

    pandas sums NaN to 0. That turns "FBref never recorded fouls in 2002" into
    "he committed none", a cleaner disciplinary record than any player alive,
    handed to the requirement that eliminates the most players.
    """
    # ponytail: a lambda-style agg gives up pandas' fast path. Fine at 68k rows
    # once per run; revisit if the population grows an order of magnitude.
    return float(values.sum(min_count=1))


def collapse_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse mid-season transfers into one row per ``(player_id, season)``.

    A player who changes clubs mid-season appears once per club in FBref's
    output. Counting stats are summed and the clubs are joined into a ``teams``
    string, so a transfer season is not silently counted twice.

    ``min_pct`` is recomputed rather than summed. It is a share of one club's
    minutes, so adding two of them is meaningless. It produced availability
    figures up to 296%. Each club's implied total is recovered from the share it
    came with, and the real share is taken against the sum of those.
    """
    keys = ["player_id", "season"]
    if "min_pct" in df.columns:
        share = df["min_pct"].where(df["min_pct"] > 0)
        df = df.assign(_team_min=df["minutes"] / share * 100.0)

    grouped = df.groupby(keys, as_index=False, sort=False)

    present = [c for c in _SUM if c in df.columns]
    aggs: dict[str, Any] = {c: _sum_or_missing for c in present}
    if "_team_min" in df.columns:
        aggs["_team_min"] = _sum_or_missing
    totals = grouped.agg({**aggs, **{c: "first" for c in _KEEP}})

    if "_team_min" in totals.columns:
        team_min = totals.pop("_team_min")
        totals["min_pct"] = 100.0 * totals["minutes"] / team_min.where(team_min > 0)
    # Named aggregation on the frame (not a selected column) keeps this a
    # DataFrame and needs no rename.
    teams = (
        df.sort_values("team")
        .groupby(keys, as_index=False, sort=False)
        .agg(teams=("team", lambda names: ", ".join(dict.fromkeys(names))))
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


def add_age(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Attach each player-season's age, joined on the keys rather than by position.

    This was ``df["age"] = raw.groupby(keys)["age"].first().to_numpy()``, which
    silently scrambled the column. ``collapse_transfers`` groups with
    ``sort=False`` and keeps insertion order, while ``groupby`` sorts by default,
    so the two sequences disagreed at **every** position: 61,131 of 65,069
    player-seasons carried somebody else's age, off by 5.4 years on average and
    by as much as 23.

    Nothing raised, because both sides were the same length. Age is a control in
    the league-strength regression, so the damage surfaced as offsets that
    quietly moved whenever row order did, which is exactly the kind of bug that
    hides until something unrelated perturbs the ordering.

    Parameters
    ----------
    df
        Collapsed player-season frame, one row per ``(player_id, season)``.
    raw
        Uncollapsed frame carrying ``player_id``, ``season`` and ``age``.
    """
    keys = ["player_id", "season"]
    ages = raw.groupby(keys, as_index=False)["age"].first()
    return df.merge(ages, on=keys, how="left")


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

    club_goals = raw.groupby(["season", "team"], as_index=False).agg(_club_goals=("goals", "sum"))
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


EXTRA_COUNTS = ("minutes", "npg", "assists")


def attach_extra_competition(
    seasons: pd.DataFrame, extra: pd.DataFrame, prefix: str
) -> pd.DataFrame:
    """Attach one competition's counts onto player-seasons as prefixed columns.

    A **left** join, so the ranked population is decided entirely by domestic
    play and a competition can never add a player. Missing values become
    **zero, not null**, and that is the load-bearing choice: the project's ruling
    is that never appearing in Europe is a low score rather than an unknown one.
    A null would be filled by something downstream anyway, and filled without
    anybody having decided what it meant.

    ``validate="one_to_one"`` because ``extra`` must be unique on
    ``(player_id, season)``. A single competition guarantees that on its own.
    Several competitions passed together (the tournament file mixes World Cup,
    Euro and Copa America) still satisfy it, because :func:`collapse_transfers`
    upstream groups by ``(player_id, season)`` alone, folding every competition
    a player appeared in that season into one row before this function ever
    sees it. Without the validation, a duplicated key would return the cross
    product, which is exactly the defect recorded in DEVIATIONS.md #7.

    Parameters
    ----------
    seasons
        Player-seasons, one row per ``(player_id, season)``.
    extra
        Frame conforming to :data:`gambeta.laws.EXTRA_COMP`, already unique on
        ``(player_id, season)``, whether it holds one competition or several.
    prefix
        Column prefix, for example ``"ucl"`` giving ``ucl_minutes``.
    """
    columns = ["player_id", "season", *EXTRA_COUNTS]
    renamed = extra[columns].rename(columns={c: f"{prefix}_{c}" for c in EXTRA_COUNTS})
    out = seasons.merge(renamed, on=["player_id", "season"], how="left", validate="one_to_one")
    for count in EXTRA_COUNTS:
        out[f"{prefix}_{count}"] = out[f"{prefix}_{count}"].fillna(0).astype("int64")
    return out
