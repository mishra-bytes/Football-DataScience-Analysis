"""FBref adapter, via soccerdata.

soccerdata 1.9.1 drives seleniumbase to get past Cloudflare, so a Chrome
installation is required for live fetches. All reshaping lives in `flatten`,
which is pure. That is where the bugs would otherwise hide, untested.
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

_NO_BORN = -1.0
"""Stand-in for an unknown birth year while joining.

A merge never matches NaN against NaN, so leaving it missing would silently
strip every side-table column from those rows, the exact failure this project
refuses to ship. 36 of 67,825 rows are affected.
"""

_COUNTS = ["mp", "starts", "minutes", "goals", "assists", "npg", "pk", "pkatt", "yellow", "red"]
_FLOATS = ["age", "born"]
_STRINGS = ["nation", "pos"]

_ORDER = [*_INDEX, *_STRINGS, *_FLOATS, *_COUNTS]

# One rename map per FBref season table. Only the columns this project needs and
# that are populated across all 25 seasons are listed; see the spec's verified
# availability table for what was excluded and why.
_RENAME_SHOOTING: dict[tuple[str, str], str] = {
    ("Standard", "SoT"): "sot",
    ("Standard", "SoT/90"): "sot_p90",
    ("Standard", "G/SoT"): "g_per_sot",
}

_RENAME_PLAYING_TIME: dict[tuple[str, str], str] = {
    ("Playing Time", "Min%"): "min_pct",
    ("Starts", "Compl"): "complete",
    ("Subs", "Subs"): "subs",
}

_RENAME_MISC: dict[tuple[str, str], str] = {
    ("Performance", "2CrdY"): "second_yellow",
    ("Performance", "Fls"): "fouls",
}

_RENAME_KEEPER: dict[tuple[str, str], str] = {
    ("nation", ""): "nation",
    ("age", ""): "age",
    ("born", ""): "born",
    ("Playing Time", "MP"): "mp",
    ("Playing Time", "Starts"): "starts",
    ("Playing Time", "Min"): "minutes",
    ("Performance", "GA"): "ga",
    ("Performance", "GA90"): "ga90",
    ("Performance", "SoTA"): "sota",
    ("Performance", "Saves"): "saves",
    ("Performance", "Save%"): "save_pct",
    ("Performance", "W"): "wins",
    ("Performance", "D"): "draws",
    ("Performance", "L"): "losses",
    ("Performance", "CS"): "clean_sheets",
    ("Performance", "CS%"): "cs_pct",
}

SIDE_TABLES: dict[str, dict[tuple[str, str], str]] = {
    "shooting": _RENAME_SHOOTING,
    "playing_time": _RENAME_PLAYING_TIME,
    "misc": _RENAME_MISC,
}
"""Tables joined onto `standard` by (league, season, team, player)."""


def _flat_columns(raw: pd.DataFrame, rename: dict[tuple[str, str], str]) -> pd.DataFrame:
    """Reset the index and collapse FBref's two-level headers to flat names.

    Selecting index columns straight off a two-level-column frame keeps them
    two-level, which later fails a merge against a flat frame with
    ``MergeError: Not allowed to merge between different levels``. Every reader
    must therefore flatten headers *before* selecting anything.
    """
    df = raw.reset_index()
    df.columns = pd.Index(
        [
            rename.get(
                col if isinstance(col, tuple) else (col, ""),
                col[0] if isinstance(col, tuple) else col,
            )
            for col in df.columns
        ]
    )
    return df.loc[:, ~df.columns.duplicated()]


def flatten_side(raw: pd.DataFrame, rename: dict[tuple[str, str], str]) -> pd.DataFrame:
    """Flatten a secondary FBref table down to its join keys plus renamed columns.

    Unlike :func:`flatten`, nothing is coerced to a fixed schema, because these tables
    contribute a handful of numeric columns each and are merged onto `standard`.

    Parameters
    ----------
    raw
        Output of ``read_player_season_stats`` for one of :data:`SIDE_TABLES`.
    rename
        Two-level column header to snake_case name.
    """
    df = _flat_columns(raw, rename)
    out = df[_INDEX].astype(str).copy()
    # Carried for the join, not for the data: `(league, season, team, player)`
    # is not unique and birth year is what separates two players of the same
    # name at the same club. Every FBref season table publishes it.
    out["born"] = pd.to_numeric(df["born"], errors="coerce").astype("float64")
    for name in rename.values():
        if name in df.columns:
            out[name] = pd.to_numeric(df[name], errors="coerce").astype("float64")
    return out.reset_index(drop=True)


def flatten_keeper(raw: pd.DataFrame) -> pd.DataFrame:
    """Flatten the goalkeeper table into a tidy frame.

    Keepers are a separate population with their own requirements, so this is a
    separate table rather than extra columns on the outfield one.
    """
    df = _flat_columns(raw, _RENAME_KEEPER)
    out = df[_INDEX].astype(str).copy()

    for name in _RENAME_KEEPER.values():
        if name not in df.columns:
            continue
        if name == "nation":
            out[name] = df[name].where(df[name].notna(), None)
        else:
            out[name] = pd.to_numeric(df[name], errors="coerce").astype("float64")

    return out.reset_index(drop=True)


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


SIDE_COLUMNS = tuple(name for rename in SIDE_TABLES.values() for name in rename.values())
"""Every column the side tables contribute, whether or not they were fetched."""


def _agrees(values: pd.Series) -> bool:
    """True when every non-null value in the column is the same one."""
    known = values.dropna()
    return bool(known.empty or (known == known.iloc[0]).all())


def _fuse_split_records(df: pd.DataFrame, key: list[str], *, strict: bool) -> pd.DataFrame:
    """Reduce rows repeating a key to one, taking the largest value per column.

    FBref splits one player's record across two rows, in two different shapes.

    In `standard` it happens once in 67,705 rows: Emanuele Torrasi appears at
    Milan in 2017-18 as rows 507 and 508, agreeing on nation, position, age,
    birth year, one appearance and six minutes.

    In the side tables it is commoner and asymmetric. Sinan Kurt's 2014-15
    playing time is one row holding his single substitute appearance and another
    holding his unused-substitute count, each null where the other carries data.

    ``strict`` decides what a disagreement means. **`standard` defines who
    exists**, so two rows there that differ are two different people, and they
    are left in place for the caller's one-to-one check to stop on rather than
    silently merged. A side table cannot introduce anybody, because every row of it has
    to land on a `standard` row already known to be unique, so there the split
    record is simply reassembled.
    """
    repeated = df.duplicated(key, keep=False)
    if not repeated.any():
        return df

    stats = [c for c in df.columns if c not in key]
    dupes = df[repeated]
    if strict:
        dupes = dupes.groupby(key, sort=False).filter(
            lambda group: all(_agrees(group[c]) for c in stats)
        )
        if dupes.empty:
            return df

    fused = dupes.groupby(key, as_index=False, sort=False)[stats].max()
    return pd.concat([df.drop(index=dupes.index), fused], ignore_index=True)[df.columns]


def join_side_tables(standard: pd.DataFrame, sides: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge the secondary tables onto `standard` by (league, season, team, player).

    Left joins throughout: a player missing from a side table keeps their standard
    row with nulls, rather than vanishing from the dataset. Dropping them silently
    is the failure mode this project cares most about avoiding.

    Columns from side tables that were not fetched are filled with nulls, so a run
    that deliberately skips one (to save scraping time and backfill it later)
    still produces a schema-valid frame.

    The join key includes birth year, and ``validate="one_to_one"`` enforces that
    it is unique. Without both, two players sharing a name at one club return the
    cross product rather than a lookup: two players called Míchel at Rayo
    Vallecano in 2002-03 became sixteen rows across three joins, one of them
    carrying 19,288 minutes in a 38-match season. Nothing raised, no schema
    rejected it, and every downstream per-90 divided by it.
    """
    key = [*_INDEX, "_born_key"]
    keyed_standard = standard.assign(_born_key=standard["born"].fillna(_NO_BORN))
    out = _fuse_split_records(keyed_standard, key, strict=True)
    for frame in sides.values():
        keyed = frame.assign(_born_key=frame["born"].fillna(_NO_BORN)).drop(columns="born")
        side = _fuse_split_records(keyed, key, strict=False)
        out = out.merge(side, on=key, how="left", validate="one_to_one")
    out = out.drop(columns="_born_key")
    for column in SIDE_COLUMNS:
        if column not in out.columns:
            # NaN, not pd.NA: pandas 3 refuses the latter in a float64 Series.
            out[column] = pd.Series(float("nan"), index=out.index, dtype="float64")
    return out


class FBrefScout:
    """Fetch player-season stats from FBref for one or more leagues.

    Fetches per league, never via the Big 5 combined reader: that endpoint leaves
    Bundesliga's league label null in every season and merges Ligue 1 into the
    same null group before 2017, which would normalise players against the wrong
    peer population.
    """

    name = "fbref"

    def __init__(
        self,
        leagues: Sequence[str],
        seasons: Sequence[str],
        data_dir: Path,
        cache_only: bool = False,
    ) -> None:
        self.leagues = list(leagues)
        self.seasons = list(seasons)
        self.data_dir = data_dir
        self.cache_only = cache_only

    def cached(self, league: str, stat: str) -> bool:
        """Is **every** requested season of this (league, stat) already on disk?

        Completeness matters, not mere presence. soccerdata fetches whatever is
        missing, so a table cached for 8 of 25 seasons would silently trigger 17
        page loads, turning an offline run into half an hour of browser
        automation. A partially cached table counts as absent.
        """
        pattern = f"players_{league}_*_{stat}.html"
        return len(list((self.data_dir / "FBref").glob(pattern))) >= len(self.seasons)

    def _skip(self, league: str, stat: str) -> bool:
        return self.cache_only and not self.cached(league, stat)

    def _reader(self, league: str) -> object:
        import soccerdata as sd

        self.data_dir.mkdir(parents=True, exist_ok=True)
        return sd.FBref(leagues=league, seasons=self.seasons, data_dir=self.data_dir / "FBref")

    def fetch(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return ``(outfield, keeper)`` frames covering every configured league.

        Slow on a cold cache, roughly 15 minutes per league per stat table. Reads
        entirely from cache once :mod:`scripts.warm_cache` has run.
        """
        outfield_parts: list[pd.DataFrame] = []
        keeper_parts: list[pd.DataFrame] = []

        for league in self.leagues:
            reader = self._reader(league)
            read = reader.read_player_season_stats  # type: ignore[attr-defined]

            if self._skip(league, "standard"):
                continue
            try:
                standard = flatten(read(stat_type="standard"))
            except Exception:  # noqa: BLE001, PERF203 - league not collected
                # No data for this league. Skip it rather than abort: the
                # pipeline is designed to run on whatever leagues exist.
                continue

            sides = {}
            for name, rename in SIDE_TABLES.items():
                if self._skip(league, name):
                    continue
                try:
                    sides[name] = flatten_side(read(stat_type=name), rename)
                except Exception:  # noqa: BLE001, PERF203 - optional table
                    # Not fetched yet, or unavailable. join_side_tables nulls the
                    # columns so the run continues on a reduced requirement set.
                    continue
            outfield_parts.append(join_side_tables(standard, sides))

            if self._skip(league, "keeper"):
                continue
            try:
                keeper_parts.append(flatten_keeper(read(stat_type="keeper")))
            except Exception:  # noqa: BLE001 - optional per league
                continue

        if not outfield_parts:
            raise RuntimeError(f"no data found for any of: {', '.join(self.leagues)}")

        return (
            pd.concat(outfield_parts, ignore_index=True),
            pd.concat(keeper_parts, ignore_index=True) if keeper_parts else pd.DataFrame(),
        )
