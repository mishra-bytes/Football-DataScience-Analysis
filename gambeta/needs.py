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
    Requirement("availability", "Is available", "season"),
    Requirement("reliability", "Sees matches out", "season"),
    Requirement("longevity", "Sustains it", "career"),
    Requirement("consistency", "Has no bad seasons", "career"),
    Requirement("discipline", "Does not cost his team", "season"),
    Requirement("continental", "Delivers in Europe", "season"),
    Requirement("tournament", "Shows up for his country", "season"),
)
"""Twelve requirements: eleven plus ``tournament``, added 2026-08-15.

``tournament`` scores international output at the World Cup, the Euro and Copa
America, the same rate-times-presence shape as ``continental``. Owner ruling
2026-08-15: Copa America joined the World Cup and the Euro because the Euro
covers European players and Copa America covers South American ones. See
:func:`tournament_value` for the shape and its limits.

``continental`` scores European club output (currently the Champions League).
The owner's ruling is that the best footballer plays the top competitions, so
never appearing in one is a low score rather than an unknown. The honest
objection is that this partly measures club selection: Totti at Roma and
Messi at Barcelona did not face the same opportunity. See
:func:`continental_value` for the mitigation.

It was ten requirements, and eleven until 2026-08-12, for an unrelated reason.

``above_team`` was the residual of scoring after regressing on the club's
ClubElo rating, meant to separate a player from the side around him. Measured,
club strength explains 0.8% of who scores inside a league-season, so the
residual correlated 0.996 with ``scoring`` and the composite counted one quality
twice. No target rescued it: the best of the other nine was ``creation`` at 1.1%.

It survives on the keeper list, where it earns its place. Club strength explains
45% of goals conceded, so a keeper's residual is genuinely his own contribution
rather than his defence's.
"""

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
    "The efficiency argument": {"finishing": 3.0, "scoring": 2.0},
    "The longevity argument": {"longevity": 4.0, "availability": 2.0, "consistency": 2.0},
    "The team-carrier argument": {"team_share": 4.0, "creation": 2.0},
    "The professional argument": {"discipline": 3.0, "availability": 3.0, "reliability": 2.0},
    "The big-nights argument": {"continental": 4.0, "team_share": 2.0},
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


def _role_relative(values: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    """Subtract the median of the player's own position.

    A usage statistic carries a mechanical role artefact: a centre-back is left
    on for ninety minutes because he is a centre-back, and a striker comes off
    because he is a striker. Neither fact is about being trusted, which is what
    the requirement is trying to measure.

    **One median per position, pooled across every league and season**, and taken
    over the ranked population rather than everyone who appeared. Both choices
    were measured against the two things that matter, how much of the positional
    gap survives and whether a season predicts the same player's next one:

    ========================================  =========  ==============
    baseline                                  role gap   predicts next
    ========================================  =========  ==============
    everyone, per league-season-position          0.233           0.511
    ranked only, per league-season-position       0.068           0.449
    ranked only, per position                     0.073           0.495
    ========================================  =========  ==============

    Including cameo appearances gives a steadier median and fails at the job:
    a thirty-minute substitute completes nothing whatever his position, so those
    rows drag every median toward zero and flatten the differences that exist
    among players who actually play. Restricting to the ranked population fixes
    that and costs stability, because a league-season-position cell can be small.
    Pooling positions across leagues and eras recovers the stability, since what
    counts as a full shift for a centre-back does not meaningfully differ between
    the 2004 Bundesliga and the 2019 Premier League. Five cells rather than five
    hundred.

    Phase 2 §8 rejected standardising *within* position, and this is not that.
    §8 forbids z-scoring **output** by position, because that finds the most
    attacking defender and presents it as defensive quality. Here a **usage**
    ratio has a role median subtracted, with no rescaling by within-position
    spread, so it cannot manufacture a quality claim. It is the same move as the
    keeper `above_team`: strip a context artefact, keep the player.
    """
    series = pd.Series(values, index=df.index)
    position = df["pos"].fillna("").str.split(",").str[0].replace("", "UNK")
    return (series - series.groupby(position).transform("median")).to_numpy(dtype=float)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> np.ndarray:
    """Safe ratio; a zero or missing denominator yields zero."""
    den = denominator.to_numpy(dtype=float)
    safe = np.where(den > 0, den, np.nan)
    return np.nan_to_num(numerator.to_numpy(dtype=float) / safe)


CONTINENTAL_FULL_SEASON = 900.0
"""Minutes that count as a full European campaign: ten matches.

A group stage is six matches and a run to the final is thirteen, so this sits
where "he was properly part of it" starts. Above it the presence term saturates,
because a deep run is the team's achievement as much as the player's and
rewarding it linearly would rank players by how far their club went.
"""


def continental_value(df: pd.DataFrame) -> np.ndarray:
    """Score European club output: a per-90 rate, scaled by how present he was.

    Absence scores zero. That is a ruling, not an oversight: the definition says
    the best footballer plays the top competitions, so never appearing in one is
    a low score rather than an unknown.

    The honest objection is that this partly measures **club selection**. A great
    player at a mid-table side never gets the chance. Two things limit the
    damage. The rate is per 90, so a player is judged on what he did with the
    minutes he had. The presence term saturates at
    :data:`CONTINENTAL_FULL_SEASON`, so a semi-final run cannot outscore a group
    stage on volume alone. What survives is the part the ruling actually wants:
    a career spent entirely outside Europe scores zero on this requirement, and
    the gate then decides what that costs.

    Returns
    -------
    np.ndarray
        Higher is better, like every other requirement column.
    """
    minutes = _column(df, "ucl_minutes").to_numpy(dtype=float)
    contributions = _column(df, "ucl_npg").to_numpy(dtype=float) + _column(
        df, "ucl_assists"
    ).to_numpy(dtype=float)
    nineties = minutes / MINUTES_PER_MATCH
    rate: np.ndarray = np.divide(
        contributions, nineties, out=np.zeros_like(contributions), where=nineties > 0
    )
    presence = np.clip(minutes / CONTINENTAL_FULL_SEASON, 0.0, 1.0)
    return rate * presence


TOURNAMENT_FULL_RUN = 450.0
"""Minutes that count as a full tournament: five matches, a quarter-final exit.

Lower than :data:`CONTINENTAL_FULL_SEASON` because a tournament is seven matches
at most. Anything higher would mean only finalists could saturate, which would
rank players by how strong their national side was.
"""


def tournament_value(df: pd.DataFrame) -> np.ndarray:
    """Score international tournament output: a per-90 rate, scaled by presence.

    Identical shape to :func:`continental_value`. Absence scores zero, for the
    same reason: never appearing at a tournament is a low score rather than an
    unknown.

    This requirement is **zero for most seasons by construction**, because none
    of the World Cup, the Euro or Copa America is played every year, and a
    given player's season never carries more than one of them: WC years fall
    on neither the Euro's nor Copa America's cycle, and a player is eligible
    for exactly one national team, so the Euro and Copa America never collide
    for the same player either. It is therefore a weaker discriminator than
    ``continental``, which a player can contribute to every year his club
    qualifies. That is a limitation to publish, not to hide.

    It also partly measures **nationality** rather than ability alone: a player
    from a small footballing nation reaches far fewer tournaments across a
    career than one from a traditional power, independent of how good either
    one is. Copa America mitigates this for South American players, who now
    have a second tournament to be measured on, but leaves it standing for
    players from confederations with no tournament in scope, such as Africa's
    or Asia's. The rate-times-presence form limits the damage the same way it
    does for ``continental``, but does not remove it.

    Returns
    -------
    np.ndarray
        Higher is better, like every other requirement column.
    """
    minutes = _column(df, "int_minutes").to_numpy(dtype=float)
    contributions = _column(df, "int_npg").to_numpy(dtype=float) + _column(
        df, "int_assists"
    ).to_numpy(dtype=float)
    nineties = minutes / MINUTES_PER_MATCH
    rate: np.ndarray = np.divide(
        contributions, nineties, out=np.zeros_like(contributions), where=nineties > 0
    )
    presence = np.clip(minutes / TOURNAMENT_FULL_RUN, 0.0, 1.0)
    return rate * presence


def outfield_values(df: pd.DataFrame) -> pd.DataFrame:
    """Add one column per season-level outfield requirement.

    ``reliability`` is **completed matches per appearance, relative to the
    player's own position**. It has been three things.

    It began as completed matches per *start*, which measured being a forward:
    Benzema, Aguero, Higuain, Villa, Owen and Trezeguet all failed qualification
    on that requirement alone, because strikers get substituted.

    It then became starts per appearance, which fixed the role bias by throwing
    away the information. A quarter of player-seasons scored exactly 1.000, so
    the requirement could not separate a squad player with twelve starts from a
    captain with thirty-eight, and it correlated 0.72 with ``availability``.

    Measured against those four faults, the current form is better on three:
    no ceiling, a role gap of 0.07 rather than 0.25, and elite players standing
    1.85 standard deviations clear rather than 0.58. The overlap with
    ``availability`` improves only from 0.62 to 0.55, and is the reason this
    requirement still has an open question against it.

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
    out["reliability"] = _role_relative(_ratio(_column(out, "complete"), out["mp"]), out)

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
    out["continental"] = continental_value(df)
    out["tournament"] = tournament_value(df)
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
