import pandas as pd

from gambeta import kit, laws, lens

CFG = kit.load()


def _career(player_id: str, scores: list[float], start: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [player_id] * len(scores),
            "player": [f"P{player_id}"] * len(scores),
            "season": [f"{y:02d}{y + 1:02d}" for y in range(start, start + len(scores))],
            "score": scores,
            "minutes": [3000] * len(scores),
        }
    )


def test_peak5_picks_the_best_consecutive_window() -> None:
    df = _career("a", [0.0, 0.0, 5.0, 5.0, 5.0, 5.0, 5.0, 0.0])
    out = lens.peak5(df, CFG, window=5).set_index("player_id")
    assert out.loc["a", "score"] == 5.0
    assert out.loc["a", "start_season"] == "0203"
    assert out.loc["a", "end_season"] == "0607"


def test_peak5_requires_consecutive_seasons() -> None:
    """A gap year must break the window rather than being silently bridged."""
    df = pd.concat([_career("a", [9.0, 9.0]), _career("a", [9.0, 9.0, 9.0], start=6)])
    out = lens.peak5(df, CFG, window=5)
    assert out.iloc[0]["seasons_used"] == 3, "longest consecutive run is 3 seasons"


def test_peak5_handles_a_career_shorter_than_the_window() -> None:
    out = lens.peak5(_career("a", [4.0, 6.0]), CFG, window=5).set_index("player_id")
    assert out.loc["a", "score"] == 5.0
    assert out.loc["a", "seasons_used"] == 2


def test_peak5_handles_a_single_season_career() -> None:
    out = lens.peak5(_career("a", [3.0]), CFG, window=5).set_index("player_id")
    assert out.loc["a", "score"] == 3.0
    assert out.loc["a", "seasons_used"] == 1


def test_peak5_ranks_multiple_players_descending() -> None:
    df = pd.concat([_career("a", [1.0] * 5), _career("b", [3.0] * 5)])
    out = lens.peak5(df, CFG, window=5)
    assert list(out["player_id"]) == ["b", "a"]


def test_peak5_prefers_the_longer_window_on_a_tie() -> None:
    """Five seasons at 2.0 beats two seasons at 2.0 when the means are equal."""
    out = lens.peak5(_career("a", [2.0] * 5), CFG, window=5).set_index("player_id")
    assert out.loc["a", "seasons_used"] == 5


def test_peak5_output_matches_the_rating_schema() -> None:
    df = pd.concat([_career("a", [1.0] * 6), _career("b", [2.0] * 6)])
    laws.RATING.validate(lens.peak5(df, CFG, window=5))


def test_peak5_attaches_confidence_intervals() -> None:
    row = lens.peak5(_career("a", [1.0, 2.0, 3.0, 4.0, 5.0]), CFG, window=5).iloc[0]
    assert row["lo"] <= row["score"] <= row["hi"]


def test_peak5_is_deterministic() -> None:
    df = _career("a", [1.0, 2.0, 3.0, 4.0, 5.0])
    pd.testing.assert_frame_equal(lens.peak5(df, CFG), lens.peak5(df, CFG))
