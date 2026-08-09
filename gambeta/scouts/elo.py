"""ClubElo adapter: team strength snapshots, one per season."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def season_dates(seasons: Sequence[str]) -> dict[str, str]:
    """Map each 4-digit season code to a mid-season sampling date.

    ``"0405"`` denotes 2004-05, so the sample is taken on 2005-01-01 — roughly
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


def tidy_elo(raw: pd.DataFrame, season: str) -> pd.DataFrame:
    """Reduce a ClubElo date snapshot to English top-flight teams for one season.

    Parameters
    ----------
    raw
        Output of ``ClubElo.read_by_date``: indexed by team, with ``country``,
        ``level`` and ``elo`` columns.
    season
        The 4-digit season code to stamp on every row.

    Returns
    -------
    pd.DataFrame
        Conforms to :data:`gambeta.laws.ELO`.
    """
    df = raw.reset_index()
    english_top_flight = (df["country"] == "ENG") & (df["level"] == 1)
    out = df.loc[english_top_flight, ["team", "elo"]].copy()
    out["season"] = season
    out["team"] = out["team"].astype(str)
    out["elo"] = out["elo"].astype("float64")
    return out[["season", "team", "elo"]].reset_index(drop=True)


class EloScout:
    """Fetch one ClubElo snapshot per season."""

    name = "clubelo"

    def __init__(self, seasons: Sequence[str]) -> None:
        self.seasons = list(seasons)

    def fetch(self) -> pd.DataFrame:
        """One request per season."""
        import soccerdata as sd

        reader = sd.ClubElo()
        frames = [
            tidy_elo(reader.read_by_date(date), season)
            for season, date in season_dates(self.seasons).items()
        ]
        return pd.concat(frames, ignore_index=True)
