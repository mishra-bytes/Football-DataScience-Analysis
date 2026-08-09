import pandas as pd

from gambeta import laws
from gambeta.scouts.elo import season_dates, tidy_elo


def test_season_dates_maps_to_january_of_the_second_year() -> None:
    d = season_dates(["0001", "0405", "2425"])
    assert d["0001"] == "2001-01-01"
    assert d["0405"] == "2005-01-01"
    assert d["2425"] == "2025-01-01"


def test_season_dates_handles_the_century_rollover() -> None:
    assert season_dates(["9900"])["9900"] == "2000-01-01"


def _snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rank": [1.0, 2.0, 3.0, 4.0],
            "country": ["ENG", "ENG", "ESP", "ENG"],
            "level": [1, 2, 1, 1],
            "elo": [1900.0, 1500.0, 1950.0, 1820.0],
        },
        index=pd.Index(["Arsenal", "Watford", "Barcelona", "Liverpool"], name="team"),
    )


def test_tidy_elo_keeps_only_english_top_flight() -> None:
    out = tidy_elo(_snapshot(), season="0405")
    assert set(out["team"]) == {"Arsenal", "Liverpool"}


def test_tidy_elo_stamps_the_season() -> None:
    out = tidy_elo(_snapshot(), season="0405")
    assert out["season"].unique().tolist() == ["0405"]


def test_tidy_elo_output_matches_the_schema() -> None:
    laws.ELO.validate(tidy_elo(_snapshot(), season="0405"))
