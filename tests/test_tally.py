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


def test_age_lands_on_the_right_player() -> None:
    """Ages were attached by position, and the two orderings never matched.

    ``collapse_transfers`` groups with ``sort=False``; a plain ``groupby`` sorts.
    On the real data that put somebody else's age on 61,131 of 65,069
    player-seasons, out by 5.4 years on average. Nothing raised, because the two
    sequences were the same length.
    """
    # Insertion order deliberately unsorted, so a positional assignment breaks.
    labelled = pd.DataFrame(
        {
            "player_id": ["zzz", "aaa", "mmm"],
            "season": ["0405", "0405", "0405"],
            "age": [34.0, 19.0, 27.0],
        }
    )
    collapsed = pd.DataFrame({"player_id": ["zzz", "aaa", "mmm"], "season": ["0405"] * 3})

    got = tally.add_age(collapsed, labelled).set_index("player_id")["age"]
    assert got["zzz"] == 34.0
    assert got["aaa"] == 19.0
    assert got["mmm"] == 27.0


def test_age_survives_a_mid_season_transfer() -> None:
    """Two rows for one player-season must collapse to a single age."""
    labelled = _labelled().assign(age=[24.0, 24.0, 19.0])
    collapsed = tally.collapse_transfers(labelled)
    got = tally.add_age(collapsed, labelled)
    assert len(got) == len(collapsed)
    assert got.set_index("player_id")["age"]["aaa"] == 24.0


def test_age_is_null_when_the_source_has_none() -> None:
    labelled = _labelled().assign(age=[float("nan")] * 3)
    got = tally.add_age(tally.collapse_transfers(labelled), labelled)
    assert got["age"].isna().all()


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
