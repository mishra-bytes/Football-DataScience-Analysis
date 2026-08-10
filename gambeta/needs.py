"""What greatness requires, and how each requirement is measured.

The definition is a list of things the best footballer must have. This module
owns that list: one column per requirement, computed per player-season, with
**higher always better** so nothing downstream needs per-requirement direction
logic — the class of bug that silently inverts one metric and poisons a ranking.

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
    note: str = ""


OUTFIELD: tuple[Requirement, ...] = (
    Requirement("scoring", "Scores goals", "season", "Non-penalty goals per 90"),
    Requirement("creation", "Creates goals", "season", "Assists per 90"),
    Requirement("finishing", "Finishes clinically", "season", "Goals per shot on target"),
    Requirement("threat", "Generates threat", "season", "Shots on target per 90"),
    Requirement("team_share", "Carries his team", "season", "Share of club goals"),
    Requirement("above_team", "Beats his team's level", "season", "Output vs ClubElo prediction"),
    Requirement("availability", "Is available", "season", "Share of team minutes"),
    Requirement("reliability", "Is relied upon", "season", "Complete matches per start"),
    Requirement("longevity", "Sustains it", "career", "Qualifying seasons"),
    Requirement("consistency", "Does not fluctuate", "career", "Negative SD of season scores"),
    Requirement("discipline", "Does not cost his team", "season", "Negative cards and fouls"),
)

KEEPER: tuple[Requirement, ...] = (
    Requirement("shot_stopping", "Stops shots", "season", "Save percentage"),
    Requirement("concedes_little", "Concedes little", "season", "Negative goals against per 90"),
    Requirement("clean_sheets", "Keeps clean sheets", "season", "Clean sheet percentage"),
    Requirement("above_team", "Beats his team's level", "season", "GA/90 vs ClubElo prediction"),
    Requirement("availability", "Is available", "season", "Share of team minutes"),
    Requirement("reliability", "Is relied upon", "season", "Complete matches per start"),
    Requirement("longevity", "Sustains it", "career", "Qualifying seasons"),
    Requirement("consistency", "Does not fluctuate", "career", "Negative SD of season scores"),
    Requirement("discipline", "Does not cost his team", "season", "Negative cards per 90"),
)


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


def _ratio(numerator: pd.Series, denominator: pd.Series) -> np.ndarray:
    """Safe ratio; a zero or missing denominator yields zero."""
    den = denominator.to_numpy(dtype=float)
    safe = np.where(den > 0, den, np.nan)
    return np.nan_to_num(numerator.to_numpy(dtype=float) / safe)


def outfield_values(df: pd.DataFrame) -> pd.DataFrame:
    """Add one column per season-level outfield requirement.

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
    out["finishing"] = _ratio(out["goals"], out["sot"].fillna(0))
    out["threat"] = _rate(out["sot"].fillna(0), minutes)
    out["team_share"] = out["team_goal_share"].fillna(0.0)
    out["availability"] = out["min_pct"].fillna(0.0) / 100.0
    out["reliability"] = _ratio(out["complete"].fillna(0), out["starts"])

    # Negated so higher is better, like every other requirement.
    cost = (
        out["red"].to_numpy(dtype=float)
        + out["second_yellow"].fillna(0).to_numpy(dtype=float)
        + _rate(out["fouls"].fillna(0), minutes)
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
    out["reliability"] = _ratio(out["mp"].fillna(0), out["starts"])
    out["discipline"] = 0.0  # keeper table carries no cards; neutral by construction
    return out


def add_above_team(
    df: pd.DataFrame, elo: pd.DataFrame, output_col: str, higher_is_better: bool = True
) -> pd.DataFrame:
    """Add ``above_team``: performance relative to what the club's strength predicts.

    Fits ``output ~ elo`` within each ``(league, season)`` and keeps the residual.
    A player at a dominant club has to beat a higher bar to score positively,
    which is the whole point — it separates the player from the side around him.

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
    out = df.merge(elo, on=["season", "team"], how="left")
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
