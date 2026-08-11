import pandas as pd

from gambeta import laws, verdict
from gambeta.scouts.wikidata import AWARDS, AWARDS_QUERY, parse_awards

BINDINGS = [
    {
        "p": {"value": "http://www.wikidata.org/entity/Q615"},
        "award": {"value": "http://www.wikidata.org/entity/Q166177"},
        "when": {"value": "2009-01-01T00:00:00Z"},
    },
    {  # same person, same award, a different year — both must survive
        "p": {"value": "http://www.wikidata.org/entity/Q615"},
        "award": {"value": "http://www.wikidata.org/entity/Q166177"},
        "when": {"value": "2010-01-01T00:00:00Z"},
    },
    {
        "p": {"value": "http://www.wikidata.org/entity/Q11571"},
        "award": {"value": "http://www.wikidata.org/entity/Q260117"},
        "when": {"value": "2014-01-01T00:00:00Z"},
    },
]


def test_parse_awards_names_the_award() -> None:
    out = parse_awards(BINDINGS)
    assert set(out["award"]) == {"Ballon d'Or", "UEFA Men's Player of the Year"}


def test_parse_awards_keeps_repeat_wins() -> None:
    """Winning twice is the whole signal; collapsing it would throw it away."""
    out = parse_awards(BINDINGS)
    assert len(out[out["qid"] == "Q615"]) == 2


def test_parse_awards_extracts_the_year() -> None:
    out = parse_awards(BINDINGS).set_index(["qid", "year"])
    assert ("Q615", 2009) in out.index


def test_parse_awards_tolerates_a_missing_year() -> None:
    """An unbound OPTIONAL comes back as an absent key, or occasionally a null."""
    absent = {k: v for k, v in BINDINGS[0].items() if k != "when"}
    assert parse_awards([absent])["year"].isna().all()
    assert parse_awards([{**BINDINGS[0], "when": None}])["year"].isna().all()


def test_parse_awards_matches_the_schema() -> None:
    laws.AWARDS.validate(parse_awards(BINDINGS))


def test_awards_query_names_every_tracked_award() -> None:
    values = " ".join(f"wd:{qid}" for qid in AWARDS)
    filled = AWARDS_QUERY.replace("__AWARDS__", values)
    for qid in AWARDS:
        assert f"wd:{qid}" in filled


def test_awards_query_is_scoped_to_mens_football() -> None:
    """Several of these award items are attached to women's winners too.

    The project covers the Big 5 men's leagues, so without this filter Birgit
    Prinz, Carli Lloyd and Aitana Bonmati arrived counted as winners our data
    had failed to find, when their absence is correct.
    """
    assert "wdt:P21 wd:Q6581097" in AWARDS_QUERY


def test_awards_span_the_whole_window() -> None:
    """No single award covers 2000-2025; the set has to, or the check has holes."""
    assert "Ballon d'Or" in AWARDS.values()
    assert "FIFA Ballon d'Or" in AWARDS.values()  # the 2010-2015 merger
    assert "The Best FIFA Men's Player" in AWARDS.values()  # 2016 onward


def _awards() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "qid": ["Q1", "Q1", "Q2", "Q3", "Q4"],
            "award": ["Ballon d'Or"] * 5,
            "year": pd.array([2005, 2006, 2010, 2015, 1985], dtype="Int64"),
        }
    )


def _ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "d"],
            "player": ["Alpha", "Bravo", "Charlie", "Delta"],
            "score": [3.0, 2.0, 1.0, 0.5],
            "qualified": [True, True, False, False],
            "worst_requirement": ["discipline", "threat", "longevity", "scoring"],
            "failed": [None, None, "longevity", "scoring, threat"],
        }
    )


def _identity() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "zz"],
            "qid": ["Q1", "Q2", "Q3", "Q9"],
        }
    )


def test_window_excludes_awards_before_the_project_starts() -> None:
    """A 1985 Ballon d'Or says nothing about a 2000-2025 ranking."""
    assert "Q4" not in set(verdict.award_winners(_awards())["qid"])


def test_repeat_winners_are_counted_not_collapsed() -> None:
    winners = verdict.award_winners(_awards()).set_index("qid")
    assert winners.loc["Q1", "honours"] == 2
    assert winners.loc["Q1", "award_years"] == "2005, 2006"


def test_winners_are_placed_in_the_ranking() -> None:
    placed = verdict.against_awards(_ranking(), _awards(), _identity())
    top = placed.set_index("player")
    assert top.loc["Alpha", "rank"] == 1
    assert top.loc["Charlie", "rank"] == 3


def test_a_winner_we_never_saw_is_kept_but_unplaced() -> None:
    """'Not in our data' and 'ranked badly' are different failures."""
    awards = pd.concat(
        [_awards(), pd.DataFrame({"qid": ["Q7"], "award": ["Ballon d'Or"], "year": [2011]})]
    )
    placed = verdict.against_awards(_ranking(), awards, _identity())
    assert placed["rank"].isna().sum() == 1


def test_summary_separates_missing_from_rejected() -> None:
    placed = verdict.against_awards(_ranking(), _awards(), _identity())
    got = verdict.summary(placed, _ranking()).set_index("measure")["value"]
    assert got["award winners in the window"] == 3
    assert got["of those, present in our data"] == 3
    assert got["of those, clearing all requirements"] == 2
    assert got["winners our gate rejects"] == 1


def test_disagreements_name_the_requirement_to_blame() -> None:
    worst = verdict.disagreements(verdict.against_awards(_ranking(), _awards(), _identity()))
    charlie = worst.set_index("player").loc["Charlie"]
    assert charlie["verdict"] == "failed: longevity"


def test_disagreements_put_the_worst_placed_winner_first() -> None:
    worst = verdict.disagreements(verdict.against_awards(_ranking(), _awards(), _identity()))
    assert worst.iloc[0]["player"] == "Charlie"
