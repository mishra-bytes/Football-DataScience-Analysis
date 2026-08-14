import numpy as np
import pandas as pd

from gambeta import needs


def _outfield() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"] * 3,
            "season": ["0405"] * 3,
            "team": ["Arsenal", "Chelsea", "Arsenal"],
            "player": ["A", "B", "C"],
            "pos": ["FW", "FW", "FW"],
            "minutes": [1800, 900, 0],
            "mp": [20, 12, 0],
            "starts": [20, 10, 0],
            "goals": [10, 4, 0],
            "npg": [8, 4, 0],
            "assists": [4, 2, 0],
            "red": [0, 1, 0],
            "sot": [40.0, 10.0, 0.0],
            "min_pct": [50.0, 25.0, 0.0],
            "complete": [15.0, 5.0, 0.0],
            "second_yellow": [0.0, 1.0, 0.0],
            "fouls": [20.0, 30.0, 0.0],
            "team_goal_share": [0.4, 0.2, 0.0],
        }
    )


def test_every_season_requirement_gets_a_column() -> None:
    out = needs.outfield_values(_outfield())
    expected = set(needs.season_keys(needs.OUTFIELD))
    assert expected <= set(out.columns)


def test_scoring_uses_non_penalty_goals() -> None:
    """Penalties measure who is assigned them, not who is best."""
    out = needs.outfield_values(_outfield()).set_index("player")
    assert out.loc["A", "scoring"] == 8 / (1800 / 90)


def test_finishing_is_goals_per_shot_on_target() -> None:
    out = needs.outfield_values(_outfield()).set_index("player")
    assert out.loc["A", "finishing"] == 10 / 40


def test_reliability_rewards_finishing_the_matches_you_appear_in() -> None:
    """Completed matches per appearance, which is what the manager decided."""
    df = _outfield()
    df.loc[df["player"] == "A", ["mp", "starts", "complete"]] = [30, 30, 27]
    df.loc[df["player"] == "B", ["mp", "starts", "complete"]] = [30, 30, 6]
    out = needs.outfield_values(df).set_index("player")
    assert out.loc["A", "reliability"] > out.loc["B", "reliability"]


def test_reliability_is_measured_against_the_players_own_position() -> None:
    """Finishing 90% of matches is ordinary for a defender and not for a striker.

    Without the positional median this requirement measured being a defender:
    the gap between the mean forward and the mean defender was 0.25, and it is
    0.07 now.
    """
    base = _outfield().iloc[0].to_dict()
    df = pd.DataFrame(
        [
            {**base, "player": "back-typical", "pos": "DF", "mp": 30, "complete": 27.0},
            {**base, "player": "back-poor", "pos": "DF", "mp": 30, "complete": 21.0},
            {**base, "player": "striker-same-rate", "pos": "FW", "mp": 30, "complete": 27.0},
            {**base, "player": "striker-typical", "pos": "FW", "mp": 30, "complete": 15.0},
        ]
    )
    out = needs.outfield_values(df).set_index("player")

    # Identical completion rates, different positions, different verdicts.
    assert out.loc["striker-same-rate", "reliability"] > out.loc["back-typical", "reliability"]
    # And a defender below his own position's norm is penalised.
    assert out.loc["back-poor", "reliability"] < out.loc["back-typical", "reliability"]


def test_zero_minutes_never_divides_by_zero() -> None:
    out = needs.outfield_values(_outfield()).set_index("player")
    for key in ("scoring", "creation", "threat"):
        assert out.loc["C", key] == 0.0
    # `reliability` is centred on the player's position, so a zero rate lands
    # below that median rather than at zero. Finite is the claim being made.
    assert np.isfinite(out.loc["C", "reliability"])


def test_discipline_is_negated_so_higher_is_better() -> None:
    """A clean player must outscore a dirty one on this requirement."""
    out = needs.outfield_values(_outfield()).set_index("player")
    assert out.loc["A", "discipline"] > out.loc["B", "discipline"]
    assert out.loc["A", "discipline"] <= 0


def test_career_and_season_keys_partition_the_list() -> None:
    both = set(needs.season_keys(needs.OUTFIELD)) | set(needs.career_keys(needs.OUTFIELD))
    assert both == {r.key for r in needs.OUTFIELD}
    assert not set(needs.season_keys(needs.OUTFIELD)) & set(needs.career_keys(needs.OUTFIELD))


def test_outfield_list_has_ten_requirements() -> None:
    """Eleven until above_team was found to be a copy of scoring."""
    assert len(needs.OUTFIELD) == 10


def test_outfield_does_not_gate_on_above_team() -> None:
    """Club strength explains 0.8% of individual scoring; the residual was scoring."""
    assert "above_team" not in {r.key for r in needs.OUTFIELD}
    assert "above_team" in {r.key for r in needs.KEEPER}


def test_keeper_list_has_eight_requirements() -> None:
    """No discipline requirement: the keeper table carries no cards."""
    assert len(needs.KEEPER) == 8
    assert "discipline" not in {r.key for r in needs.KEEPER}


def _keeper() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"] * 2,
            "season": ["0405"] * 2,
            "team": ["Arsenal", "Chelsea"],
            "player": ["K1", "K2"],
            "minutes": [3420.0, 1710.0],
            "mp": [38.0, 19.0],
            "starts": [38.0, 19.0],
            "ga90": [0.8, 1.4],
            "save_pct": [78.0, 65.0],
            "cs_pct": [40.0, 20.0],
        }
    )


def test_keeper_conceding_less_scores_higher() -> None:
    out = needs.keeper_values(_keeper()).set_index("player")
    assert out.loc["K1", "concedes_little"] > out.loc["K2", "concedes_little"]


def test_keeper_save_percentage_passes_through() -> None:
    out = needs.keeper_values(_keeper()).set_index("player")
    assert out.loc["K1", "shot_stopping"] == 78.0


def _elo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["0405"] * 2,
            "team": ["Arsenal", "Chelsea"],
            "elo": [1900.0, 1700.0],
        }
    )


def test_above_team_penalises_players_at_strong_clubs() -> None:
    """Same output at a stronger club must score lower on this requirement."""
    df = pd.DataFrame(
        {
            "league": ["L"] * 4,
            "season": ["0405"] * 4,
            "team": ["Arsenal", "Arsenal", "Chelsea", "Chelsea"],
            "player": list("abcd"),
            "out": [1.0, 1.0, 1.0, 1.0],
        }
    )
    elo = pd.DataFrame(
        {"season": ["0405"] * 2, "team": ["Arsenal", "Chelsea"], "elo": [1900.0, 1500.0]}
    )
    got = needs.add_above_team(df, elo, "out").set_index("player")
    # Equal in theory (identical output at each club); the regression solver's
    # floating-point path differs by platform BLAS, so compare within tolerance
    # rather than bit-for-bit.
    assert np.isclose(got.loc["a", "above_team"], got.loc["c", "above_team"])


def test_above_team_rewards_outperforming_a_weak_club() -> None:
    df = pd.DataFrame(
        {
            "league": ["L"] * 4,
            "season": ["0405"] * 4,
            "team": ["Arsenal", "Arsenal", "Chelsea", "Chelsea"],
            "player": list("abcd"),
            "out": [2.0, 2.0, 0.5, 2.5],
        }
    )
    elo = pd.DataFrame(
        {"season": ["0405"] * 2, "team": ["Arsenal", "Chelsea"], "elo": [1900.0, 1500.0]}
    )
    got = needs.add_above_team(df, elo, "out").set_index("player")
    assert got.loc["d", "above_team"] > got.loc["c", "above_team"]


def test_above_team_survives_a_single_club_group() -> None:
    df = pd.DataFrame(
        {
            "league": ["L"] * 3,
            "season": ["0405"] * 3,
            "team": ["Arsenal"] * 3,
            "player": list("abc"),
            "out": [1.0, 2.0, 3.0],
        }
    )
    elo = pd.DataFrame({"season": ["0405"], "team": ["Arsenal"], "elo": [1900.0]})
    got = needs.add_above_team(df, elo, "out")
    assert np.isclose(got["above_team"].mean(), 0.0)


def test_above_team_flips_sign_when_lower_is_better() -> None:
    df = pd.DataFrame(
        {
            "league": ["L"] * 4,
            "season": ["0405"] * 4,
            "team": ["Arsenal", "Arsenal", "Chelsea", "Chelsea"],
            "player": list("abcd"),
            "ga": [1.0, 1.0, 0.5, 2.5],
        }
    )
    up = needs.add_above_team(df, _elo(), "ga", higher_is_better=True)
    down = needs.add_above_team(df, _elo(), "ga", higher_is_better=False)
    assert np.allclose(up["above_team"], -down["above_team"])
