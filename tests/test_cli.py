from pathlib import Path

import pandas as pd
import pytest

from gambeta import cli, kit, laws, locker


def _outfield_rows(league: str, season: str, players: list[dict]) -> pd.DataFrame:
    """Minimal schema-valid OUTFIELD_RAW rows, one per player override dict."""
    base = {
        "nation": None,
        "pos": None,
        "age": 25.0,
        "mp": 10,
        "starts": 10,
        "minutes": 900,
        "goals": 5,
        "assists": 3,
        "npg": 4,
        "pk": 1,
        "pkatt": 1,
        "yellow": 0,
        "red": 0,
        "sot": float("nan"),
        "sot_p90": float("nan"),
        "g_per_sot": float("nan"),
        "min_pct": float("nan"),
        "complete": float("nan"),
        "subs": float("nan"),
        "second_yellow": float("nan"),
        "fouls": float("nan"),
    }
    rows = [{**base, "league": league, "season": season, **player} for player in players]
    return pd.DataFrame(rows)[list(laws.OUTFIELD_RAW.columns)]


def _fixture_config(tmp_path: Path) -> kit.Config:
    """A minimal Config backed by just enough raw data for ``clean()`` to run end to end."""
    cfg = kit.Config(
        root=tmp_path,
        raw=tmp_path / "raw",
        clean=tmp_path / "clean",
        derive=tmp_path / "derive",
        sample=tmp_path / "sample",
    )
    players = [
        {"player": "Lionel Messi", "born": 1987.0, "team": "Barcelona"},
        {"player": "Karim Benzema", "born": 1987.0, "team": "Real Madrid"},
    ]
    locker.write(
        _outfield_rows("ESP-La Liga", "2223", players),
        cfg.raw / cli.RAW_OUTFIELD,
        laws.OUTFIELD_RAW,
        source="test",
    )

    keeper = pd.DataFrame(
        [
            {
                "league": "ESP-La Liga",
                "season": "2223",
                "team": "Barcelona",
                "player": "Keeper One",
                "nation": None,
                "age": 28.0,
                "born": 1994.0,
                "mp": 10.0,
                "starts": 10.0,
                "minutes": 900.0,
                "ga": 8.0,
                "ga90": 0.8,
                "sota": 40.0,
                "saves": 32.0,
                "save_pct": 80.0,
                "wins": 6.0,
                "draws": 2.0,
                "losses": 2.0,
                "clean_sheets": 4.0,
                "cs_pct": 40.0,
            }
        ]
    )
    locker.write(keeper, cfg.raw / cli.RAW_KEEPER, laws.KEEPER_RAW, source="test")

    crosswalk = pd.DataFrame(
        {
            "qid": pd.Series([], dtype="object"),
            "fbref_id": pd.Series([], dtype="object"),
            "label": pd.Series([], dtype="object"),
            "birth_year": pd.Series([], dtype="Int64"),
        }
    )
    locker.write(crosswalk, cfg.raw / cli.RAW_CROSSWALK, laws.CROSSWALK, source="test")

    elo = pd.DataFrame(
        {
            "season": ["2223", "2223"],
            "team": ["Barcelona", "Real Madrid"],
            "elo": [1900.0, 2000.0],
        }
    )
    locker.write(elo, cfg.raw / cli.RAW_ELO, laws.ELO, source="test")

    # Literal filename, not `cli.RAW_CONTINENTAL`: that constant does not exist
    # yet on the RED run this fixture also serves, and the value is fixed by
    # the brief regardless.
    continental_players = [
        {"player": "Lionel Messi", "born": 1987.0, "team": "PSG"},
        {"player": "Karim Benzema", "born": 1987.0, "team": "Real Madrid"},
    ]
    locker.write(
        _outfield_rows("UEFA-Champions League", "2223", continental_players),
        cfg.raw / "continental_raw.parquet",
        laws.OUTFIELD_RAW,
        source="test",
    )

    return cfg


def test_clean_writes_a_schema_valid_continental_frame(tmp_path: Path) -> None:
    """UCL rows resolve to the same player_id as the domestic rows, or they are useless."""
    cfg = _fixture_config(tmp_path)  # existing helper in this file
    cli.clean(cfg)
    frame = locker.read(cfg.clean / cli.CLEAN_CONTINENTAL, laws.EXTRA_COMP)
    assert set(frame["comp"]) == {"UEFA-Champions League"}
    assert (
        frame["player_id"].isin(pd.read_parquet(cfg.clean / cli.CLEAN_OUTFIELD)["player_id"]).all()
    )


def test_parser_accepts_each_stage() -> None:
    for stage in ("scrape", "clean", "rank", "all"):
        assert cli.build_parser().parse_args([stage]).stage == stage


def test_parser_accepts_a_league_subset() -> None:
    args = cli.build_parser().parse_args(["scrape", "--leagues", "ESP-La Liga"])
    assert args.leagues == ["ESP-La Liga"]


def test_parser_rejects_an_unknown_stage() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["nonsense"])


def test_parser_defaults_to_the_full_season_range() -> None:
    assert cli.build_parser().parse_args(["scrape"]).seasons is None


def test_parser_accepts_a_season_subset() -> None:
    args = cli.build_parser().parse_args(["scrape", "--seasons", "0001", "0102"])
    assert args.seasons == ["0001", "0102"]


def test_parser_requires_a_stage() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])
