import pandas as pd
import pandera.pandas as pa
import pytest

from gambeta import laws


def _raw_row() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"],
            "season": ["0405"],
            "team": ["Arsenal"],
            "player": ["Thierry Henry"],
            "nation": ["FRA"],
            "pos": ["FW"],
            "age": [27.0],
            "born": [1977.0],
            "mp": [32],
            "starts": [32],
            "minutes": [2853],
            "goals": [25],
            "assists": [12],
            "npg": [20],
            "pk": [5],
            "pkatt": [6],
            "yellow": [1],
            "red": [0],
        }
    )


def test_raw_schema_accepts_valid_frame() -> None:
    laws.PLAYER_SEASON_RAW.validate(_raw_row())


def test_raw_schema_rejects_negative_minutes() -> None:
    bad = _raw_row()
    bad.loc[0, "minutes"] = -1
    with pytest.raises(pa.errors.SchemaError):
        laws.PLAYER_SEASON_RAW.validate(bad)


def test_raw_schema_rejects_missing_column() -> None:
    with pytest.raises(pa.errors.SchemaError):
        laws.PLAYER_SEASON_RAW.validate(_raw_row().drop(columns=["goals"]))


def test_raw_schema_allows_missing_nation_and_born() -> None:
    sparse = _raw_row()
    sparse.loc[0, "nation"] = None
    sparse.loc[0, "born"] = None
    laws.PLAYER_SEASON_RAW.validate(sparse)


def test_crosswalk_requires_unique_qid() -> None:
    dupe = pd.DataFrame(
        {
            "qid": ["Q615", "Q615"],
            "fbref_id": ["d70ce98e", "d70ce98e"],
            "label": ["Lionel Messi", "Lionel Messi"],
            "birth_year": pd.array([1987, 1987], dtype="Int64"),
        }
    )
    with pytest.raises(pa.errors.SchemaError):
        laws.CROSSWALK.validate(dupe)


def test_player_season_rejects_duplicate_player_season() -> None:
    row = {
        "player_id": "abc",
        "qid": "Q1",
        "season": "0405",
        "league": "ENG-Premier League",
        "player": "Someone",
        "born": 1980.0,
        "nation": "ENG",
        "pos": "FW",
        "teams": "Arsenal",
        "minutes": 900,
        "mp": 10,
        "goals": 5,
        "assists": 2,
        "npg": 5,
        "yellow": 1,
        "red": 0,
    }
    with pytest.raises(pa.errors.SchemaError):
        laws.PLAYER_SEASON.validate(pd.DataFrame([row, row]))
