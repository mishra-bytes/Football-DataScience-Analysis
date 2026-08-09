"""FBref adapter, via soccerdata.

soccerdata 1.9.1 drives seleniumbase to get past Cloudflare, so a Chrome
installation is required for live fetches. All reshaping lives in `flatten`,
which is pure — that is where the bugs would otherwise hide, untested.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

# FBref's two-level column headers -> our flat snake_case names.
_RENAME: dict[tuple[str, str], str] = {
    ("nation", ""): "nation",
    ("pos", ""): "pos",
    ("age", ""): "age",
    ("born", ""): "born",
    ("Playing Time", "MP"): "mp",
    ("Playing Time", "Starts"): "starts",
    ("Playing Time", "Min"): "minutes",
    ("Performance", "Gls"): "goals",
    ("Performance", "Ast"): "assists",
    ("Performance", "G-PK"): "npg",
    ("Performance", "PK"): "pk",
    ("Performance", "PKatt"): "pkatt",
    ("Performance", "CrdY"): "yellow",
    ("Performance", "CrdR"): "red",
}

_INDEX = ["league", "season", "team", "player"]
_COUNTS = ["mp", "starts", "minutes", "goals", "assists", "npg", "pk", "pkatt", "yellow", "red"]
_FLOATS = ["age", "born"]
_STRINGS = ["nation", "pos"]

_ORDER = [*_INDEX, *_STRINGS, *_FLOATS, *_COUNTS]


def flatten(raw: pd.DataFrame) -> pd.DataFrame:
    """Flatten FBref's MultiIndex output into a tidy frame.

    Lifts the ``(league, season, team, player)`` row index into columns, renames
    the two-level stat headers to snake_case, drops FBref's pre-computed per-90
    columns (we recompute them from minutes), and coerces counts to integers.

    Parameters
    ----------
    raw
        Output of ``FBref.read_player_season_stats(stat_type="standard")``.

    Returns
    -------
    pd.DataFrame
        Conforms to :data:`gambeta.laws.PLAYER_SEASON_RAW`. Column order matches
        the schema exactly.
    """
    df = raw.reset_index()
    df.columns = pd.Index(
        [
            _RENAME.get(c, c[0]) if isinstance(c, tuple) else _RENAME.get((c, ""), c)
            for c in df.columns
        ]
    )
    df = df.loc[:, ~df.columns.duplicated()]

    for col in _COUNTS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    for col in _FLOATS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in _INDEX:
        df[col] = df[col].astype(str)
    for col in _STRINGS:
        df[col] = df[col].where(df[col].notna(), None)

    return df[_ORDER].reset_index(drop=True)


class FBrefScout:
    """Fetch Premier League player-season standard stats from FBref."""

    name = "fbref"

    def __init__(self, league: str, seasons: Sequence[str], data_dir: Path) -> None:
        self.league = league
        self.seasons = list(seasons)
        self.data_dir = data_dir

    def fetch(self) -> pd.DataFrame:
        """Scrape all configured seasons. Slow: roughly 50 seconds per season."""
        import soccerdata as sd

        self.data_dir.mkdir(parents=True, exist_ok=True)
        reader = sd.FBref(
            leagues=self.league,
            seasons=self.seasons,
            data_dir=self.data_dir / "FBref",
        )
        return flatten(reader.read_player_season_stats(stat_type="standard"))
