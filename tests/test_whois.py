import pandas as pd

from gambeta import whois


def test_normalize_folds_accents_and_case() -> None:
    assert whois.normalize("Cesc Fàbregas") == "cesc fabregas"
    assert whois.normalize("Zdeněk Zikán") == "zdenek zikan"


def test_normalize_collapses_whitespace() -> None:
    assert whois.normalize("  N'Golo   Kanté ") == "n'golo kante"


def test_player_id_is_stable_across_spelling_noise() -> None:
    assert whois.player_id("Thierry Henry", 1977.0) == whois.player_id("Thierry  HENRY", 1977.0)


def test_player_id_separates_same_name_different_birth_year() -> None:
    """Paul Robinson the goalkeeper is not Paul Robinson the defender."""
    assert whois.player_id("Paul Robinson", 1979.0) != whois.player_id("Paul Robinson", 1978.0)


def test_player_id_handles_missing_birth_year() -> None:
    pid = whois.player_id("Mystery Man", None)
    assert isinstance(pid, str)
    assert pid


def _raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player": ["Thierry Henry", "Cesc Fàbregas", "Nobody Here"],
            "born": [1977.0, 1987.0, 1990.0],
        }
    )


def _crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "qid": ["Q9640", "Q170364"],
            "fbref_id": ["a1", "b2"],
            "label": ["Thierry Henry", "Cesc Fàbregas"],
            "birth_year": pd.array([1977, 1987], dtype="Int64"),
        }
    )


def test_resolve_attaches_player_id_to_every_row() -> None:
    labelled, _ = whois.resolve(_raw(), _crosswalk())
    assert labelled["player_id"].notna().all()


def test_resolve_matches_qid_on_name_and_birth_year() -> None:
    labelled, _ = whois.resolve(_raw(), _crosswalk())
    got = labelled.set_index("player")["qid"]
    assert got["Thierry Henry"] == "Q9640"
    assert got["Cesc Fàbregas"] == "Q170364"


def test_resolve_matches_across_accent_differences() -> None:
    """FBref and Wikidata do not always agree on diacritics."""
    raw = pd.DataFrame({"player": ["Cesc Fabregas"], "born": [1987.0]})
    labelled, _ = whois.resolve(raw, _crosswalk())
    assert labelled["qid"].iloc[0] == "Q170364"


def test_resolve_never_drops_an_unmatched_player() -> None:
    labelled, unresolved = whois.resolve(_raw(), _crosswalk())
    assert len(labelled) == 3, "unmatched players must survive into the output"
    assert list(unresolved["player"]) == ["Nobody Here"]


def test_resolve_refuses_a_match_on_the_wrong_birth_year() -> None:
    raw = pd.DataFrame({"player": ["Thierry Henry"], "born": [1999.0]})
    labelled, unresolved = whois.resolve(raw, _crosswalk())
    assert labelled["qid"].isna().all()
    assert len(unresolved) == 1


def test_resolve_does_not_duplicate_rows_on_merge() -> None:
    """A crosswalk with repeated (name, year) must not fan out the left side."""
    cw = pd.concat([_crosswalk(), _crosswalk().assign(qid=["Q1", "Q2"])], ignore_index=True)
    labelled, _ = whois.resolve(_raw(), cw)
    assert len(labelled) == 3


def test_resolve_reports_each_unresolved_player_once() -> None:
    raw = pd.concat([_raw(), _raw()], ignore_index=True)
    _, unresolved = whois.resolve(raw, _crosswalk())
    assert len(unresolved) == 1
