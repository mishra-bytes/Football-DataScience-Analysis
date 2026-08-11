import pytest

from gambeta import laws
from gambeta.scouts import wikidata
from gambeta.scouts.wikidata import BIRTH_YEARS, QUERY, ask, parse_bindings, query_for

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


def test_query_selects_footballers_by_occupation() -> None:
    """Anchoring on the FBref ID threw away 56% of the candidates.

    The matcher joins on (name, birth year) and has never used ``fbref_id``, so
    requiring P5750 only shrank the pool — Modrić, Puyol and Weidenfeller among
    the casualties. Occupation is the correct anchor.
    """
    assert "wdt:P106 wd:Q937857" in QUERY


def test_query_keeps_the_fbref_id_but_does_not_require_it() -> None:
    assert "OPTIONAL" in QUERY
    assert "wdt:P5750" in QUERY


def test_query_asks_for_latin_script_labels_beyond_english() -> None:
    """An English-only label service silently returns the bare QID instead.

    Measured: 328 crosswalk rows were literally named ``Q483837`` and could
    never match anything.
    """
    assert 'wikibase:language "en,' in QUERY


def test_query_for_pins_one_birth_year() -> None:
    """One shot times out; the fetch pages by birth year."""
    assert "YEAR(?dob) = 1985" in query_for(1985)
    assert "YEAR(?dob) = 1986" in query_for(1986)


def test_query_for_can_narrow_to_half_a_year() -> None:
    """The biggest cohorts run 36-41s against a 60s cap and tip over under load.

    1985 was lost on two consecutive runs, and 1985 is when Cristiano Ronaldo
    and Luka Modric were born.
    """
    half = query_for(1985, (1, 6))
    assert "MONTH(?dob) >= 1" in half
    assert "MONTH(?dob) <= 6" in half
    assert "MONTH" not in query_for(1985)


def test_birth_years_cover_everyone_who_could_have_played() -> None:
    """2000-01 to 2024-25 — nobody younger than 15 or older than 45 plays."""
    assert min(BIRTH_YEARS) <= 1965
    assert max(BIRTH_YEARS) >= 2005


def test_parse_drops_rows_whose_label_is_a_bare_qid() -> None:
    """A label of ``Q483837`` is a failed lookup, not a name. It can never match."""
    out = parse_bindings(
        [
            {
                "p": {"value": "http://www.wikidata.org/entity/Q483837"},
                "pLabel": {"value": "Q483837"},
                "dob": {"value": "1985-09-09T00:00:00Z"},
            },
            *BINDINGS,
        ]
    )
    assert "Q483837" not in set(out["qid"])


class _Response:
    """Minimal stand-in for a requests response."""

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        """A mid-stream timeout still arrives as 200, so this never fires."""


_GOOD = '{"results": {"bindings": []}}'
# What the service actually returns when it times out after sending the header:
# a half-written body with a Java stack trace glued on, served with 200 OK.
_TRUNCATED = '{"results": {"bindings": [{"p": {"val\n\tat java.lang.Thread.run(Thread.java:750)\n'


def test_ask_varies_the_query_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timed-out response is cached, so an identical retry replays the corruption.

    Measured on birth year 1990: three attempts all failed at char 2,767,040 of
    the same 2.77 MB body. Appending a comment changed the cache key and the
    same query returned 9,893 clean rows.
    """
    seen: list[str] = []

    def fake_get(url: str, params: dict[str, str], **kwargs: object) -> _Response:
        seen.append(params["query"])
        return _Response(_TRUNCATED if len(seen) == 1 else _GOOD)

    monkeypatch.setattr(wikidata.requests, "get", fake_get)
    monkeypatch.setattr(wikidata, "_BACKOFF", 0.0)

    assert ask("SELECT * WHERE {}", "test") == []
    assert len(seen) == 2, "a corrupt body must be retried"
    assert seen[0] != seen[1], "the retry must not reuse the cached query key"


def test_ask_gives_up_quietly_rather_than_aborting(monkeypatch: pytest.MonkeyPatch) -> None:
    """One lost cohort beats losing the whole half-hour fetch."""
    monkeypatch.setattr(wikidata.requests, "get", lambda *a, **k: _Response(_TRUNCATED))
    monkeypatch.setattr(wikidata, "_BACKOFF", 0.0)
    assert ask("SELECT * WHERE {}", "test") == []


def test_a_cached_year_costs_no_request(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetch was all or nothing: one failed cohort meant redoing all 41."""
    calls: list[str] = []

    def fake_get(url: str, params: dict[str, str], **kwargs: object) -> _Response:
        calls.append(params["query"])
        return _Response(
            '{"results": {"bindings": [{"p": {"value": "http://www.wikidata.org/entity/Q1"},'
            ' "pLabel": {"value": "Someone"}, "dob": {"value": "1985-01-01T00:00:00Z"}}]}}'
        )

    monkeypatch.setattr(wikidata.requests, "get", fake_get)
    scout = wikidata.WikidataScout(cache_dir=tmp_path)  # type: ignore[arg-type]

    first = scout.year(1985)
    assert len(first) == 1
    assert len(calls) == 1

    second = scout.year(1985)
    assert len(second) == 1
    assert len(calls) == 1, "a cached year must not hit the network again"


def test_an_empty_year_is_not_cached(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure is something to retry, not an answer to remember."""
    monkeypatch.setattr(wikidata.requests, "get", lambda *a, **k: _Response(_TRUNCATED))
    monkeypatch.setattr(wikidata, "_BACKOFF", 0.0)
    scout = wikidata.WikidataScout(cache_dir=tmp_path)  # type: ignore[arg-type]
    assert len(scout.year(1985)) == 0
    assert not list(tmp_path.iterdir())  # type: ignore[attr-defined]


def test_changing_the_query_invalidates_the_cache() -> None:
    """A cached answer to a different question is a wrong answer, not a saving."""
    before = wikidata.query_fingerprint()
    monkey = wikidata.QUERY + "\n# a different question\n"
    after = __import__("hashlib").sha1(monkey.encode()).hexdigest()[:8]
    assert before != after


def test_parse_tolerates_a_missing_fbref_id() -> None:
    """P5750 is optional now; most footballers on Wikidata do not carry one."""
    out = parse_bindings(
        [
            {
                "p": {"value": "http://www.wikidata.org/entity/Q154397"},
                "pLabel": {"value": "Roman Weidenfeller"},
                "dob": {"value": "1980-08-06T00:00:00Z"},
            }
        ]
    )
    assert out["fbref_id"].isna().all()
    assert out["label"].iloc[0] == "Roman Weidenfeller"
