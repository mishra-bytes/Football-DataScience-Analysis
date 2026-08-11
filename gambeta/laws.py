"""pandera schemas — the contract between pipeline layers.

Every Parquet write validates against a schema here, and every read validates
again. An identity-resolution bug therefore surfaces as a loud failure at the
layer boundary rather than as a subtly wrong chart three layers downstream.
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

ValidationError = (pa.errors.SchemaError, pa.errors.SchemaErrors)
"""Catch-all for schema violations.

pandera raises ``SchemaError`` for a bad value but ``SchemaErrors`` for a bad
column set, and the two are siblings with no useful common base. Callers should
catch this tuple rather than having to know which one applies.
"""

_NON_NEG = Check.ge(0)
_SEASON = Check.str_length(4, 4)

PLAYER_SEASON_RAW = DataFrameSchema(
    {
        "league": Column(str),
        "season": Column(str, _SEASON),
        "team": Column(str),
        "player": Column(str),
        "nation": Column(str, nullable=True),
        "pos": Column(str, nullable=True),
        "age": Column(float, nullable=True),
        "born": Column(float, nullable=True),
        "mp": Column(int, _NON_NEG),
        "starts": Column(int, _NON_NEG),
        "minutes": Column(int, _NON_NEG),
        "goals": Column(int, _NON_NEG),
        "assists": Column(int, _NON_NEG),
        "npg": Column(int, _NON_NEG),
        "pk": Column(int, _NON_NEG),
        "pkatt": Column(int, _NON_NEG),
        "yellow": Column(int, _NON_NEG),
        "red": Column(int, _NON_NEG),
    },
    strict=True,
    coerce=True,
)
"""One row per (season, team, player), exactly as scraped. Transfers duplicate."""

PLAYER_SEASON = DataFrameSchema(
    {
        "player_id": Column(str),
        "qid": Column(str, nullable=True),
        "season": Column(str, _SEASON),
        "league": Column(str),
        "player": Column(str),
        "born": Column(float, nullable=True),
        "nation": Column(str, nullable=True),
        "pos": Column(str, nullable=True),
        "teams": Column(str),
        "minutes": Column(int, _NON_NEG),
        "mp": Column(int, _NON_NEG),
        "goals": Column(int, _NON_NEG),
        "assists": Column(int, _NON_NEG),
        "npg": Column(int, _NON_NEG),
        "yellow": Column(int, _NON_NEG),
        "red": Column(int, _NON_NEG),
    },
    strict=True,
    coerce=True,
    unique=["player_id", "season"],
)
"""One row per (player_id, season). Mid-season transfers collapsed."""

_SIDE_COLUMNS = {
    "sot": Column(float, nullable=True),
    "sot_p90": Column(float, nullable=True),
    "g_per_sot": Column(float, nullable=True),
    "min_pct": Column(float, nullable=True),
    "complete": Column(float, nullable=True),
    "subs": Column(float, nullable=True),
    "second_yellow": Column(float, nullable=True),
    "fouls": Column(float, nullable=True),
}

OUTFIELD_RAW = DataFrameSchema(
    {**PLAYER_SEASON_RAW.columns, **_SIDE_COLUMNS},
    strict=True,
    coerce=True,
)
"""`standard` joined with the shooting, playing-time and misc tables.

Side columns are nullable: a left join keeps a player whose row is missing from
a secondary table rather than dropping them from the dataset entirely.
"""

KEEPER_RAW = DataFrameSchema(
    {
        "league": Column(str),
        "season": Column(str, _SEASON),
        "team": Column(str),
        "player": Column(str),
        "nation": Column(str, nullable=True),
        "age": Column(float, nullable=True),
        "born": Column(float, nullable=True),
        "mp": Column(float, _NON_NEG, nullable=True),
        "starts": Column(float, _NON_NEG, nullable=True),
        "minutes": Column(float, _NON_NEG, nullable=True),
        "ga": Column(float, _NON_NEG, nullable=True),
        "ga90": Column(float, _NON_NEG, nullable=True),
        "sota": Column(float, _NON_NEG, nullable=True),
        "saves": Column(float, _NON_NEG, nullable=True),
        "save_pct": Column(float, nullable=True),
        "wins": Column(float, _NON_NEG, nullable=True),
        "draws": Column(float, _NON_NEG, nullable=True),
        "losses": Column(float, _NON_NEG, nullable=True),
        "clean_sheets": Column(float, _NON_NEG, nullable=True),
        "cs_pct": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)
"""Goalkeeper season table. Separate population, separate requirements."""

LEAGUE_OFFSETS = DataFrameSchema(
    {
        "league": Column(str),
        "season": Column(str, _SEASON),
        "offset": Column(float),
        "moves": Column(int, _NON_NEG),
    },
    strict=True,
    coerce=True,
    unique=["league", "season"],
)
"""League-strength offsets in z units, with the number of transfers behind each.

``moves`` is published because an offset backed by three transfers deserves less
trust than one backed by three hundred, and hiding that would be dishonest.
"""

CROSSWALK = DataFrameSchema(
    {
        "qid": Column(str, unique=True),
        "fbref_id": Column(str, nullable=True),
        "label": Column(str),
        "birth_year": Column("Int64", nullable=True),
    },
    strict=True,
    coerce=True,
)
"""Wikidata identity crosswalk, one row per person."""

AWARDS = DataFrameSchema(
    {
        "qid": Column(str),
        "award": Column(str),
        "year": Column("Int64", nullable=True),
    },
    strict=True,
    coerce=True,
)
"""Individual honours, one row per (person, award, year).

Not unique on ``qid``: winning twice is the interesting case. This is the only
table in the project that carries an outside opinion, which is exactly what
makes it worth having — every other check the project runs is internal.
"""

ELO = DataFrameSchema(
    {
        "season": Column(str, _SEASON),
        "team": Column(str),
        "elo": Column(float, Check.gt(0)),
    },
    strict=True,
    coerce=True,
    unique=["season", "team"],
)
"""Team strength snapshot, one row per (season, team)."""

RATING = DataFrameSchema(
    {
        "player_id": Column(str, unique=True),
        "player": Column(str),
        "score": Column(float),
        "lo": Column(float),
        "hi": Column(float),
        "start_season": Column(str, _SEASON),
        "end_season": Column(str, _SEASON),
        "seasons_used": Column(int, Check.gt(0)),
    },
    strict=True,
    coerce=True,
)
"""Lens output: one row per player with a point estimate and interval."""

RANKING = DataFrameSchema(
    {
        "player_id": Column(str, unique=True),
        "player": Column(str),
        "score": Column(float),
        "qualified": Column(bool),
        "failed": Column(str, nullable=True),
        "worst_requirement": Column(str, nullable=True),
        "seasons": Column(int, Check.gt(0)),
        "leagues": Column(str),
    },
    # Not strict: the frame also carries one column per requirement, and the two
    # populations have different requirement lists.
    strict=False,
    coerce=True,
)
"""Gate-and-rank output.

``failed`` lists every requirement a player missed, so the reason a great player
is absent from the ranking is a published fact rather than something a reader has
to reverse-engineer.
"""

__all__ = [
    "CROSSWALK",
    "ELO",
    "KEEPER_RAW",
    "LEAGUE_OFFSETS",
    "OUTFIELD_RAW",
    "PLAYER_SEASON",
    "PLAYER_SEASON_RAW",
    "RANKING",
    "RATING",
    "ValidationError",
    "pa",
]
