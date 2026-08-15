import dataclasses

import pandas as pd

from gambeta import kit, laws, lens

CFG = kit.load()
NO_FLOOR = dataclasses.replace(CFG, min_seasons=1)


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
    out = lens.peak5(_career("a", [4.0, 6.0]), NO_FLOOR, window=5).set_index("player_id")
    assert out.loc["a", "score"] == 5.0
    assert out.loc["a", "seasons_used"] == 2


def test_peak5_handles_a_single_season_career() -> None:
    out = lens.peak5(_career("a", [3.0]), NO_FLOOR, window=5).set_index("player_id")
    assert out.loc["a", "score"] == 3.0
    assert out.loc["a", "seasons_used"] == 1


def test_peak5_excludes_careers_below_the_season_floor() -> None:
    """A one-season 'best five consecutive seasons' is a category error."""
    out = lens.peak5(_career("a", [9.0]), CFG, window=5)
    assert out.empty


def test_peak5_floor_does_not_exclude_a_qualifying_career() -> None:
    out = lens.peak5(_career("a", [1.0, 2.0, 3.0]), CFG, window=5)
    assert len(out) == 1
    assert out.iloc[0]["seasons_used"] == 3


def test_peak5_floor_stops_a_one_season_wonder_outranking_a_sustained_peak() -> None:
    """The real-data failure: one huge season beat five good ones."""
    flash = _career("flash", [9.0])
    sustained = _career("sustained", [3.0] * 5)
    out = lens.peak5(pd.concat([flash, sustained]), CFG, window=5)
    assert list(out["player_id"]) == ["sustained"]


def test_peak5_never_emits_a_zero_width_interval() -> None:
    """A degenerate interval reads as certainty on the least certain estimate."""
    df = pd.concat([_career("a", [1.0]), _career("b", [1.0, 2.0, 3.0, 4.0])])
    out = lens.peak5(df, CFG, window=5)
    assert (out["hi"] > out["lo"]).all()


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


def test_career_rewards_volume_that_peak5_ignores() -> None:
    """Ten good seasons must beat five identical ones. peak5 cannot see the difference."""
    long_career = _career("long", [3.0] * 10)
    short_career = _career("short", [3.0] * 5)
    out = lens.career(pd.concat([long_career, short_career]), CFG)
    assert list(out["player_id"]) == ["long", "short"]


def test_peak5_cannot_separate_what_career_separates() -> None:
    """The control for the test above: this is why the lens exists."""
    both = pd.concat([_career("long", [3.0] * 10), _career("short", [3.0] * 5)])
    peaks = lens.peak5(both, CFG).set_index("player_id")["score"]
    assert peaks["long"] == peaks["short"]


def test_per90_ignores_career_length_entirely() -> None:
    out = lens.per90(pd.concat([_career("long", [3.0] * 10), _career("short", [3.0] * 3)]), CFG)
    assert out["score"].nunique() == 1  # noqa: PD101


def test_per90_weights_by_minutes() -> None:
    """A 3000-minute season must count for more than a 900-minute one."""
    df = _career("a", [1.0, 5.0])
    df["minutes"] = [3000, 900]
    assert lens.per90(df, NO_FLOOR).iloc[0]["score"] < 3.0


def test_biggame_scores_only_the_continental_column() -> None:
    df = _career("a", [1.0] * 5)
    df["continental"] = [4.0] * 5
    assert lens.biggame(df, CFG).iloc[0]["score"] == 4.0


def test_biggame_excludes_a_player_who_never_played_in_europe() -> None:
    """Ranking a career of zeros by its continental output is meaningless, not zero."""
    df = _career("a", [3.0] * 5)
    df["continental"] = [0.0] * 5
    assert lens.biggame(df, CFG).empty


def test_every_lens_matches_the_rating_schema() -> None:
    df = pd.concat([_career("a", [1.0] * 6), _career("b", [2.0] * 6)])
    df["continental"] = 1.5
    for name, fn in lens.LENSES.items():
        laws.RATING.validate(fn(df, CFG)), name


def test_every_lens_is_deterministic() -> None:
    df = _career("a", [1.0, 2.0, 3.0, 4.0, 5.0])
    df["continental"] = 2.0
    for fn in lens.LENSES.values():
        pd.testing.assert_frame_equal(fn(df, CFG), fn(df, CFG))
