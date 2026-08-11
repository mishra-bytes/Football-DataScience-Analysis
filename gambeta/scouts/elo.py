"""ClubElo adapter: team strength snapshots, one per season."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from gambeta.whois import normalize


def season_dates(seasons: Sequence[str]) -> dict[str, str]:
    """Map each 4-digit season code to a mid-season sampling date.

    ``"0405"`` denotes 2004-05, so the sample is taken on 2005-01-01, roughly
    the midpoint, when a season's team strengths are informative but not yet
    contaminated by end-of-season dead rubbers.

    Codes spanning the century rollover (``"9900"`` -> 2000) follow the same rule.
    """
    out: dict[str, str] = {}
    for season in seasons:
        end = int(season[2:])
        year = 2000 + end if end < 90 else 1900 + end
        out[season] = f"{year}-01-01"
    return out


def countries_of(leagues: Sequence[str]) -> set[str]:
    """ClubElo country codes for the configured leagues.

    League ids are ``"ENG-Premier League"``, ``"ESP-La Liga"`` and so on, and
    ClubElo labels the same countries with the prefix. Deriving them means a
    league added to the config needs no change here.
    """
    return {league.split("-", 1)[0] for league in leagues}


def tidy_elo(raw: pd.DataFrame, season: str, countries: Sequence[str] | set[str]) -> pd.DataFrame:
    """Reduce a ClubElo date snapshot to the configured top flights for one season.

    This filtered to England alone until 2026-08-12, which was a Phase 1
    leftover that survived the move to the Big 5. ClubElo returned every
    country all along; the adapter discarded four of the five. The effect was
    invisible because :func:`gambeta.needs.add_above_team` fills a missing
    rating with the mean, so 85% of players were compared against a constant and
    the ``above_team`` requirement collapsed into a copy of ``scoring``.

    Parameters
    ----------
    raw
        Output of ``ClubElo.read_by_date``: indexed by team, with ``country``,
        ``level`` and ``elo`` columns.
    season
        The 4-digit season code to stamp on every row.
    countries
        ClubElo country codes to keep, from :func:`countries_of`.

    Returns
    -------
    pd.DataFrame
        Conforms to :data:`gambeta.laws.ELO`.
    """
    df = raw.reset_index()
    top_flight = df["country"].isin(set(countries)) & (df["level"] == 1)
    out = df.loc[top_flight, ["team", "elo"]].copy()
    out["season"] = season
    out["team"] = out["team"].astype(str)
    out["elo"] = out["elo"].astype("float64")
    return out[["season", "team", "elo"]].reset_index(drop=True)


def align_teams(elo: pd.DataFrame, teams: Iterable[str]) -> pd.DataFrame:
    """Remap ClubElo's team names onto the spelling FBref uses.

    The two sources disagree constantly: ClubElo's ``Bayern`` is FBref's
    ``Bayern Munich``, ``Forest`` is ``Nott'ham Forest``. Joining on the raw
    string left 67 of 217 clubs unmatched, and an unmatched club means every one
    of its players is compared against a filled-in average instead of his own
    side.

    Matched in the same tiers, and under the same rule, as player identity in
    :mod:`gambeta.whois`: exact, then folded, then one name contained in the
    other. **Ambiguity is a non-match**, because attaching the wrong club's
    strength is worse than attaching none.
    """
    known = set(teams)
    folded: dict[str, str] = {}
    tokens: dict[frozenset[str], str] = {}
    for name in known:
        folded.setdefault(normalize(name), name)
        tokens.setdefault(frozenset(normalize(name).split()), name)

    def resolve(name: str) -> str:
        if name in known:
            return name
        key = normalize(name)
        if key in folded:
            return folded[key]
        parts = frozenset(key.split())
        hits = {v for k, v in tokens.items() if parts <= k or k <= parts}
        return hits.pop() if len(hits) == 1 else name

    out = elo.copy()
    out["team"] = out["team"].map(resolve)
    # A tier can map two ClubElo rows onto one club; keep the stronger reading
    # rather than letting the join fan out.
    return out.sort_values("elo", ascending=False).drop_duplicates(["season", "team"])


class EloScout:
    """Fetch one ClubElo snapshot per season, for the configured leagues."""

    name = "clubelo"

    def __init__(self, seasons: Sequence[str], leagues: Sequence[str]) -> None:
        self.seasons = list(seasons)
        self.countries = countries_of(leagues)

    def fetch(self) -> pd.DataFrame:
        """One request per season."""
        import soccerdata as sd

        reader = sd.ClubElo()
        frames = [
            tidy_elo(reader.read_by_date(date), season, self.countries)
            for season, date in season_dates(self.seasons).items()
        ]
        return pd.concat(frames, ignore_index=True)
