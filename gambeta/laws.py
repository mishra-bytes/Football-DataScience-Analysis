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

__all__ = [
    "CROSSWALK",
    "ELO",
    "PLAYER_SEASON",
    "PLAYER_SEASON_RAW",
    "RATING",
    "ValidationError",
    "pa",
]
