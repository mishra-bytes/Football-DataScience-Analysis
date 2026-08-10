import numpy as np
import pandas as pd

from gambeta import bridge, kit, laws

CFG = kit.load()


def _seasons(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_era_block_buckets_five_seasons() -> None:
    assert bridge.era_block("0001") == 0
    assert bridge.era_block("0405") == 0
    assert bridge.era_block("0506") == 1
    assert bridge.era_block("2425") == 4


def test_find_moves_detects_a_league_change() -> None:
    df = _seasons(
        [
            {
                "player_id": "a",
                "league": "ESP-La Liga",
                "season": "0405",
                "score": 1.0,
                "minutes": 3000,
                "age": 25.0,
            },
            {
                "player_id": "a",
                "league": "ENG-Premier League",
                "season": "0506",
                "score": 0.4,
                "minutes": 3000,
                "age": 26.0,
            },
        ]
    )
    moves = bridge.find_moves(df)
    assert len(moves) == 1
    assert moves.iloc[0]["from_league"] == "ESP-La Liga"
    assert moves.iloc[0]["to_league"] == "ENG-Premier League"
    assert np.isclose(moves.iloc[0]["delta"], -0.6)


def test_find_moves_ignores_staying_put() -> None:
    df = _seasons(
        [
            {
                "player_id": "a",
                "league": "ENG-Premier League",
                "season": "0405",
                "score": 1.0,
                "minutes": 3000,
                "age": 25.0,
            },
            {
                "player_id": "a",
                "league": "ENG-Premier League",
                "season": "0506",
                "score": 1.2,
                "minutes": 3000,
                "age": 26.0,
            },
        ]
    )
    assert bridge.find_moves(df).empty


def test_find_moves_ignores_a_gap_year() -> None:
    """A season away from the Big 5 breaks the comparison; the player changed too."""
    df = _seasons(
        [
            {
                "player_id": "a",
                "league": "ESP-La Liga",
                "season": "0405",
                "score": 1.0,
                "minutes": 3000,
                "age": 25.0,
            },
            {
                "player_id": "a",
                "league": "ENG-Premier League",
                "season": "0607",
                "score": 0.4,
                "minutes": 3000,
                "age": 27.0,
            },
        ]
    )
    assert bridge.find_moves(df).empty


def test_find_moves_weights_by_the_smaller_season() -> None:
    df = _seasons(
        [
            {
                "player_id": "a",
                "league": "ESP-La Liga",
                "season": "0405",
                "score": 1.0,
                "minutes": 3000,
                "age": 25.0,
            },
            {
                "player_id": "a",
                "league": "ENG-Premier League",
                "season": "0506",
                "score": 0.4,
                "minutes": 500,
                "age": 26.0,
            },
        ]
    )
    assert bridge.find_moves(df).iloc[0]["weight"] == 500


def _synthetic_moves(gap: float, n: int = 40) -> pd.DataFrame:
    """Players crossing **both ways** between the reference league and a weaker one.

    Both directions are essential. The model carries a global adaptation
    intercept, which applies to every move regardless of direction, while a league
    offset flips sign with direction. With traffic one way only the two are
    perfectly collinear and the solver cannot separate them — real transfer data
    goes both ways, which is precisely what identifies them.
    """
    rows = []
    for i in range(n):
        # Weaker league -> reference: the player's score falls by `gap`.
        rows.append(
            {
                "player_id": f"out{i}",
                "league": "FRA-Ligue 1",
                "season": "0102",
                "score": 1.0 + gap,
                "minutes": 3000,
                "age": 25.0,
            }
        )
        rows.append(
            {
                "player_id": f"out{i}",
                "league": "ENG-Premier League",
                "season": "0203",
                "score": 1.0,
                "minutes": 3000,
                "age": 26.0,
            }
        )
        # Reference -> weaker league: the same player would gain `gap`.
        rows.append(
            {
                "player_id": f"in{i}",
                "league": "ENG-Premier League",
                "season": "0102",
                "score": 0.5,
                "minutes": 3000,
                "age": 25.0,
            }
        )
        rows.append(
            {
                "player_id": f"in{i}",
                "league": "FRA-Ligue 1",
                "season": "0203",
                "score": 0.5 + gap,
                "minutes": 3000,
                "age": 26.0,
            }
        )
    return _seasons(rows)


def test_solve_offsets_recovers_a_known_gap() -> None:
    """Players lose 0.5 z moving to the reference league, so that league is 0.5 stronger."""
    moves = bridge.find_moves(_synthetic_moves(gap=0.5))
    offsets = bridge.solve_offsets(moves, CFG)
    fra = offsets[(offsets["league"] == "FRA-Ligue 1") & (offsets["season"] == "0102")]
    assert np.isclose(fra["offset"].item(), -0.5, atol=0.05)


def test_one_way_traffic_cannot_identify_an_offset() -> None:
    """Documents the collinearity: adaptation and direction are inseparable one-way."""
    one_way = _seasons(
        [
            row
            for i in range(20)
            for row in (
                {
                    "player_id": f"p{i}",
                    "league": "FRA-Ligue 1",
                    "season": "0102",
                    "score": 1.5,
                    "minutes": 3000,
                    "age": 25.0,
                },
                {
                    "player_id": f"p{i}",
                    "league": "ENG-Premier League",
                    "season": "0203",
                    "score": 1.0,
                    "minutes": 3000,
                    "age": 26.0,
                },
            )
        ]
    )
    offsets = bridge.solve_offsets(bridge.find_moves(one_way), CFG)
    fra = offsets[(offsets["league"] == "FRA-Ligue 1") & (offsets["season"] == "0102")]
    # The true gap is -0.5, but half of it is absorbed by the adaptation intercept.
    assert fra["offset"].item() > -0.5


def test_reference_league_is_pinned_at_zero() -> None:
    offsets = bridge.solve_offsets(bridge.find_moves(_synthetic_moves(0.5)), CFG)
    ref = offsets[offsets["league"] == CFG.leagues[0]]
    assert (ref["offset"] == 0.0).all()


def test_offsets_cover_every_league_and_season() -> None:
    offsets = bridge.solve_offsets(bridge.find_moves(_synthetic_moves(0.3)), CFG)
    assert len(offsets) == len(CFG.leagues) * len(CFG.seasons)
    laws.LEAGUE_OFFSETS.validate(offsets)


def test_move_counts_are_published() -> None:
    """An offset backed by three transfers deserves less trust than one backed by 300."""
    offsets = bridge.solve_offsets(bridge.find_moves(_synthetic_moves(0.3, n=7)), CFG)
    fra = offsets[(offsets["league"] == "FRA-Ligue 1") & (offsets["season"] == "0102")]
    # 7 players out plus 7 in, so 14 moves touch this league-block.
    assert fra["moves"].item() == 14


def test_solve_offsets_survives_no_moves() -> None:
    offsets = bridge.solve_offsets(bridge.find_moves(_seasons([])), CFG)
    assert (offsets["offset"] == 0.0).all()
    assert (offsets["moves"] == 0).all()


def test_apply_offsets_shifts_the_named_columns() -> None:
    seasons = _seasons(
        [{"league": "FRA-Ligue 1", "season": "0405", "scoring": 1.0, "creation": 2.0}]
    )
    offsets = pd.DataFrame(
        [{"league": "FRA-Ligue 1", "season": "0405", "offset": -0.5, "moves": 10}]
    )
    out = bridge.apply_offsets(seasons, offsets, ["scoring", "creation"])
    assert out["scoring"].item() == 0.5
    assert out["creation"].item() == 1.5
