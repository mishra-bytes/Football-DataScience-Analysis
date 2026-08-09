from gambeta import laws
from gambeta.scouts.wikidata import QUERY, parse_bindings

BINDINGS = [
    {
        "p": {"value": "http://www.wikidata.org/entity/Q615"},
        "fbref": {"value": "d70ce98e"},
        "pLabel": {"value": "Lionel Messi"},
        "dob": {"value": "1987-06-24T00:00:00Z"},
    },
    {  # same person, second citizenship -> must collapse to one row
        "p": {"value": "http://www.wikidata.org/entity/Q615"},
        "fbref": {"value": "d70ce98e"},
        "pLabel": {"value": "Lionel Messi"},
        "dob": {"value": "1987-06-24T00:00:00Z"},
    },
    {
        "p": {"value": "http://www.wikidata.org/entity/Q150268"},
        "fbref": {"value": "7ba6d84e"},
        "pLabel": {"value": "David de Gea"},
        "dob": {"value": "1990-11-07T00:00:00Z"},
    },
]


def test_parse_deduplicates_multiple_citizenships() -> None:
    out = parse_bindings(BINDINGS)
    assert len(out) == 2
    assert out["qid"].is_unique


def test_parse_strips_the_entity_uri_prefix() -> None:
    assert set(parse_bindings(BINDINGS)["qid"]) == {"Q615", "Q150268"}


def test_parse_extracts_birth_year() -> None:
    out = parse_bindings(BINDINGS).set_index("qid")
    assert out.loc["Q615", "birth_year"] == 1987


def test_parse_tolerates_missing_date_of_birth() -> None:
    out = parse_bindings(
        [
            {
                "p": {"value": "http://www.wikidata.org/entity/Q1"},
                "fbref": {"value": "x"},
                "pLabel": {"value": "No Birthday"},
            }
        ]
    )
    assert out["birth_year"].isna().all()


def test_parse_output_matches_the_schema() -> None:
    laws.CROSSWALK.validate(parse_bindings(BINDINGS))


def test_parse_handles_empty_results() -> None:
    out = parse_bindings([])
    assert len(out) == 0
    assert list(out.columns) == ["qid", "fbref_id", "label", "birth_year"]


def test_query_targets_the_fbref_property() -> None:
    assert "wdt:P5750" in QUERY
