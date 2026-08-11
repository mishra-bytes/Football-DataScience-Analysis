"""What greatness requires, and how each requirement is measured.

The definition is a list of things the best footballer must have. This module
owns that list: one column per requirement, computed per player-season, with
**higher always better** so nothing downstream needs per-requirement direction
logic, which is the class of bug that silently inverts one metric and poisons a ranking.

Two requirements (longevity, consistency) are career-level by nature and are
derived in :mod:`gambeta.gate` from the per-season series this module produces.

Keepers get a parallel list because they do a different job. They are never
claimed to be comparable with outfielders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

MINUTES_PER_MATCH = 90.0


@dataclass(frozen=True)
class Requirement:
    """One thing the best player must have."""

    key: str
    label: str
    kind: Literal["season", "career"]


OUTFIELD: tuple[Requirement, ...] = (
    Requirement("scoring", "Scores goals", "season"),
    Requirement("creation", "Creates goals", "season"),
    Requirement("finishing", "Finishes clinically", "season"),
    Requirement("threat", "Generates threat", "season"),
    Requirement("team_share", "Carries his team", "season"),
    Requirement("above_team", "Beats his team's level", "season"),
    Requirement("availability", "Is available", "season"),
    Requirement("reliability", "Is picked to start", "season"),
    Requirement("longevity", "Sustains it", "career"),
    Requirement("consistency", "Has no bad seasons", "career"),
    Requirement("discipline", "Does not cost his team", "season"),
)

KEEPER: tuple[Requirement, ...] = (
    Requirement("shot_stopping", "Stops shots", "season"),
    Requirement("concedes_little", "Concedes little", "season"),
    Requirement("clean_sheets", "Keeps clean sheets", "season"),
    Requirement("above_team", "Beats his team's level", "season"),
    Requirement("availability", "Is available", "season"),
    Requirement("reliability", "Is picked to start", "season"),
    Requirement("longevity", "Sustains it", "career"),
    Requirement("consistency", "Has no bad seasons", "career"),
)
"""No discipline requirement: FBref's keeper table carries no cards, so it would
be a constant zero for every keeper. Gating on it can eliminate nobody and
averaging it in changes no ordering. A requirement that cannot discriminate is
not a requirement."""


ARGUMENTS: dict[str, dict[str, float]] = {
    "Equal weight": {},
    "The volume argument": {"scoring": 3.0, "creation": 3.0, "threat": 2.0, "team_share": 2.0},
    "The efficiency argument": {"finishing": 3.0, "scoring": 2.0, "above_team": 2.0},
    "The longevity argument": {"longevity": 4.0, "availability": 2.0, "consistency": 2.0},
    "The team-carrier argument": {"team_share": 4.0, "above_team": 3.0},
    "The professional argument": {"discipline": 3.0, "availability": 3.0, "reliability": 2.0},
}
"""Named weight vectors: the arguments people actually have about greatness.

Sparse by design: a requirement left out counts 1.0, so each vector states only
what its argument emphasises. Weights order the qualifiers and nothing else:
the gate is a floor per requirement and no weighting moves it, which is what
makes it safe to hand these to a reader with sliders.

An "Equal weight" entry that is literally empty is the honest spelling of the
default: it emphasises nothing."""


def season_keys(reqs: tuple[Requirement, ...]) -> list[str]:
    """Requirement keys computed per season."""
    return [r.key for r in reqs if r.kind == "season"]


def career_keys(reqs: tuple[Requirement, ...]) -> list[str]:
    """Requirement keys derived from the per-season series."""
    return [r.key for r in reqs if r.kind == "career"]


def _rate(numerator: pd.Series, minutes: pd.Series) -> np.ndarray:
    """Per-90 rate. Zero minutes yields zero, not a division error."""
    nineties = minutes.to_numpy(dtype=float) / MINUTES_PER_MATCH
    safe = np.where(nineties > 0, nineties, np.nan)
    return np.nan_to_num(numerator.to_numpy(dtype=float) / safe)


def _column(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    """Return a column, or a constant series when the source table was skipped.

    Side tables are optional by design: a run can omit one to save scraping time
    and backfill it later. Treating an absent column as its default keeps the
    pipeline running on a reduced requirement rather than failing outright.
    """
    if name not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return df[name].fillna(default).astype("float64")


MISC_COVERAGE = 0.8
"""Share of a league-season that must carry a figure for a `misc` term to count.

Both columns discipline draws from the `misc` table have an era where the source
simply does not have the data, and each has a different shape.

**Fouls** are absent from twelve whole league-seasons: Ligue 1 and the
Bundesliga record none at all before 2006, while England, Spain and Italy record
them from 2000. **Second yellows** run at 10 to 16% coverage until 2015 and jump
to 100% from 2016, so for most of the window a blank cannot be told apart from a
zero.

Filling either with zero claims the player was clean when the truth is that
nobody wrote it down, and this is the requirement that eliminates the most
players. Below this floor the term is dropped instead, so discipline degrades to
the cards it does have, which is the same degradation the requirement already
accepts when the `misc` table is missing outright.

Nothing is imputed. A group mean would shrink that season's spread and inflate
the z-score of everyone who *does* carry a figure, which trades a visible gap for
an invisible distortion.
"""


def _misc_term(df: pd.DataFrame, column: str, minutes: pd.Series | None = None) -> np.ndarray:
    """A `misc` column, zeroed out in league-seasons the source barely recorded.

    Passing ``minutes`` turns the column into a per-90 rate; leaving it out keeps
    the raw count, which is what a card tally wants.
    """
    if column not in df.columns:
        return np.zeros(len(df), dtype=float)
    recorded = df[column].notna()
    covered = recorded.groupby([df["league"], df["season"]]).transform("mean")
    usable = (recorded & (covered >= MISC_COVERAGE)).to_numpy()
    values = df[column].fillna(0.0)
    present = _rate(values, minutes) if minutes is not None else values.to_numpy(dtype=float)
    return np.where(usable, present, 0.0)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> np.ndarray:
    """Safe ratio; a zero or missing denominator yields zero."""
    den = denominator.to_numpy(dtype=float)
    safe = np.where(den > 0, den, np.nan)
    return np.nan_to_num(numerator.to_numpy(dtype=float) / safe)


def outfield_values(df: pd.DataFrame) -> pd.DataFrame:
    """Add one column per season-level outfield requirement.

    ``reliability`` is **starts per appearance**, not completed matches per start.
    The latter asks "did he play the full ninety", which a manager decides on
    tactics rather than trust, and it systematically punished forwards: on real
    data, Benzema, Aguero, Higuain, Villa, Owen and Trezeguet all missed
    qualification on that single requirement, because strikers get substituted.
    Being taken off no longer counts against a player; only being a substitute
    does.

    Parameters
    ----------
    df
        Player-seasons with the columns produced by
        :func:`gambeta.scouts.fbref.join_side_tables`, plus ``team_goal_share``
        from :func:`gambeta.tally.add_team_share`.

    Returns
    -------
    pd.DataFrame
        ``df`` plus a column per key in ``season_keys(OUTFIELD)`` except
        ``above_team``, which needs ClubElo and is added by :func:`add_above_team`.
    """
    out = df.copy()
    minutes = out["minutes"]

    out["scoring"] = _rate(out["npg"], minutes)
    out["creation"] = _rate(out["assists"], minutes)
    out["finishing"] = _ratio(out["goals"], _column(out, "sot"))
    out["threat"] = _rate(_column(out, "sot"), minutes)
    out["team_share"] = out["team_goal_share"].fillna(0.0)
    out["availability"] = _column(out, "min_pct") / 100.0
    out["reliability"] = _ratio(out["starts"], out["mp"])

    # Negated so higher is better, like every other requirement.
    #
    # Second yellows and fouls come from FBref's `misc` table. A run can skip it
    # to save five scrapes and backfill later, and the source itself has eras it
    # never recorded, so both terms drop out where coverage is too thin rather
    # than reading as a clean record. Red cards are present throughout, which is
    # what discipline falls back to. See MISC_COVERAGE.
    cost = (
        out["red"].to_numpy(dtype=float)
        + _misc_term(out, "second_yellow")
        + _misc_term(out, "fouls", minutes)
    )
    out["discipline"] = -cost
    return out


def keeper_values(df: pd.DataFrame) -> pd.DataFrame:
    """Add one column per season-level keeper requirement.

    Save percentage is the only requirement here that conditions on the shots
    actually faced. Clean sheets and goals-against largely measure the defence in
    front of the keeper, which is why :func:`add_above_team` matters more for
    keepers than it does for outfielders.
    """
    out = df.copy()
    out["shot_stopping"] = out["save_pct"].fillna(0.0)
    out["concedes_little"] = -out["ga90"].fillna(0.0)
    out["clean_sheets"] = out["cs_pct"].fillna(0.0)
    out["availability"] = _ratio(out["minutes"].fillna(0), out.get("team_minutes", out["minutes"]))
    out["reliability"] = _ratio(out["starts"].fillna(0), out["mp"])
    return out


def add_above_team(
    df: pd.DataFrame, elo: pd.DataFrame, output_col: str, higher_is_better: bool = True
) -> pd.DataFrame:
    """Add ``above_team``: performance relative to what the club's strength predicts.

    Fits ``output ~ elo`` within each ``(league, season)`` and keeps the residual.
    A player at a dominant club has to beat a higher bar to score positively,
    which is the whole point, because it separates the player from the side around him.

    Parameters
    ----------
    df
        Player-seasons with ``league``, ``season``, ``team``.
    elo
        Team strength conforming to :data:`gambeta.laws.ELO`.
    output_col
        Column holding the output being explained.
    higher_is_better
        ``False`` for keeper goals-against, where a negative residual is good;
        the sign is flipped so the requirement still reads higher-is-better.
    """
    # A collapsed player-season has no single `team`. It carries a
    # minutes-weighted `elo` attached during cleaning instead. Uncollapsed
    # frames (keepers) still join on the club.
    out = df.copy() if "elo" in df.columns else df.merge(elo, on=["season", "team"], how="left")
    out["elo"] = out["elo"].fillna(out["elo"].mean())

    residuals = np.zeros(len(out), dtype=float)
    for _, idx in out.groupby(["league", "season"], sort=False).indices.items():
        y = out[output_col].to_numpy(dtype=float)[idx]
        x = out["elo"].to_numpy(dtype=float)[idx]
        if len(idx) < 3 or np.allclose(x, x[0]):
            residuals[idx] = y - y.mean()
            continue
        slope, intercept = np.polyfit(x, y, 1)
        residuals[idx] = y - (slope * x + intercept)

    out["above_team"] = residuals if higher_is_better else -residuals
    return out.drop(columns=["elo"])
