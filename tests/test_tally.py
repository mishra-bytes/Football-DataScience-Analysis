import pandas as pd

from gambeta import tally


def _labelled() -> pd.DataFrame:
    """One player who transferred mid-season, plus one who did not."""
    return pd.DataFrame(
        {
            "player_id": ["aaa", "aaa", "bbb"],
            "qid": ["Q1", "Q1", "Q2"],
            "league": ["ENG-Premier League"] * 3,
            "season": ["0405", "0405", "0405"],
            "player": ["Mover Man", "Mover Man", "Stayer"],
            "born": [1980.0, 1980.0, 1985.0],
            "nation": ["ENG", "ENG", "FRA"],
            "pos": ["FW", "FW", "MF"],
            "team": ["Arsenal", "Chelsea", "Arsenal"],
            "minutes": [900, 900, 1800],
            "mp": [10, 10, 20],
            "goals": [5, 3, 4],
            "assists": [1, 1, 6],
            "npg": [5, 3, 4],
            "yellow": [1, 0, 2],
            "red": [0, 0, 0],
        }
    )


def test_collapse_sums_stats_across_clubs() -> None:
    out = tally.collapse_transfers(_labelled()).set_index("player_id")
    assert out.loc["aaa", "minutes"] == 1800
    assert out.loc["aaa", "goals"] == 8
    assert out.loc["aaa", "mp"] == 20


def test_collapse_yields_one_row_per_player_season() -> None:
    out = tally.collapse_transfers(_labelled())
    assert len(out) == 2
    assert out.duplicated(subset=["player_id", "season"]).sum() == 0


def test_collapse_joins_club_names() -> None:
    out = tally.collapse_transfers(_labelled()).set_index("player_id")
    assert out.loc["aaa", "teams"] == "Arsenal, Chelsea"


def test_collapse_preserves_player_metadata() -> None:
    out = tally.collapse_transfers(_labelled()).set_index("player_id")
    assert out.loc["bbb", "player"] == "Stayer"
    assert out.loc["bbb", "nation"] == "FRA"
    assert out.loc["bbb", "qid"] == "Q2"


def test_rates_are_per_ninety_minutes() -> None:
    out = tally.add_rates(tally.collapse_transfers(_labelled())).set_index("player_id")
    assert out.loc["aaa", "goals_p90"] == 8 / (1800 / 90)
    assert out.loc["aaa", "ga_p90"] == 10 / (1800 / 90)


def test_rates_are_zero_for_zero_minutes() -> None:
    df = tally.collapse_transfers(_labelled())
    df.loc[df["player_id"] == "bbb", "minutes"] = 0
    out = tally.add_rates(df).set_index("player_id")
    assert out.loc["bbb", "goals_p90"] == 0.0
    assert out.loc["bbb", "ga_p90"] == 0.0


def test_team_share_is_a_fraction_of_club_output() -> None:
    collapsed = tally.add_rates(tally.collapse_transfers(_labelled()))
    out = tally.add_team_share(collapsed, _labelled()).set_index("player_id")
    # Arsenal scored 5 + 4 = 9; Stayer contributed 4.
    assert out.loc["bbb", "team_goal_share"] == 4 / 9


def test_team_share_stays_within_bounds_for_transfers() -> None:
    collapsed = tally.add_rates(tally.collapse_transfers(_labelled()))
    out = tally.add_team_share(collapsed, _labelled())
    assert out["team_goal_share"].between(0.0, 1.0).all()


def test_team_share_survives_a_goalless_club() -> None:
    raw = _labelled()
    raw["goals"] = 0
    collapsed = tally.add_rates(tally.collapse_transfers(raw))
    out = tally.add_team_share(collapsed, raw)
    assert (out["team_goal_share"] == 0.0).all()
