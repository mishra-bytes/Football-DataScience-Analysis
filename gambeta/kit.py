"""Project configuration: paths, season range, and modelling thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SEASONS: tuple[str, ...] = tuple(f"{y:02d}{y + 1:02d}" for y in range(25))
"""Seasons 2000-01 ("0001") through 2024-25 ("2425")."""

LEAGUES: tuple[str, ...] = (
    "ENG-Premier League",
    "ESP-La Liga",
    "ITA-Serie A",
    "GER-Bundesliga",
    "FRA-Ligue 1",
)
"""The Big 5. Fetched per league, never via the combined reader.

The combined endpoint returns all five but leaves Bundesliga's league label null
in every season, and merges Ligue 1 into the same null group before 2017. Since
the label decides which population a player-season is normalised against, a
mislabelled row does not just lose a league — it normalises Bayern players
against the wrong peers and corrupts the transfer bridge too.
"""

REFERENCE_LEAGUE = "ENG-Premier League"
"""League pinned at zero when solving for league-strength offsets."""

STAT_TYPES: tuple[str, ...] = ("standard", "shooting", "playing_time", "misc", "keeper")
"""Every season-level table FBref exposes for a single league."""


@dataclass(frozen=True)
class Config:
    """Immutable project configuration.

    Attributes
    ----------
    root
        Repository root. All other paths derive from it.
    min_minutes
        Minimum minutes in a season for a player-season to enter a rating.
    min_seasons
        Minimum seasons in a player's peak window for them to be ranked at all.
        A one-season "best five consecutive seasons" is not a peak-five, and a
        single observation yields a zero-width interval that reads as certainty
        when it is the least certain estimate on the page.
    prior_minutes
        Strength of the empirical-Bayes shrinkage prior, in minutes.
    seed
        Global random seed for every stochastic routine.
    """

    root: Path
    raw: Path
    clean: Path
    derive: Path
    sample: Path
    league: str = REFERENCE_LEAGUE
    leagues: tuple[str, ...] = LEAGUES
    seasons: tuple[str, ...] = SEASONS
    min_minutes: int = 900
    min_seasons: int = 3
    prior_minutes: float = 900.0
    gate_percentile: float = 40.0
    seed: int = 20260810


def load(root: Path | None = None) -> Config:
    """Build a :class:`Config` rooted at ``root`` (default: repository root)."""
    root = (root or Path(__file__).resolve().parent.parent).resolve()
    vault = root / "vault"
    return Config(
        root=root,
        raw=vault / "raw",
        clean=vault / "clean",
        derive=vault / "derive",
        sample=root / "data" / "sample",
    )
