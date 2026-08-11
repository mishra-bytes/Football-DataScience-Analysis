import pandas as pd

from gambeta import whois


def test_normalize_folds_accents_and_case() -> None:
    assert whois.normalize("Cesc Fàbregas") == "cesc fabregas"
    assert whois.normalize("Zdeněk Zikán") == "zdenek zikan"


def test_normalize_collapses_whitespace() -> None:
    assert whois.normalize("  N'Golo   Kanté ") == "ngolo kante"


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


# --------------------------------------------------------------------------
# Fallback matching. FBref and Wikidata render the same person differently far
# more often than they disagree about who exists: 90% of unmatched players had
# a name absent from the crosswalk under its exact spelling, and most of those
# were present under another. Every tier below is gated on the birth year and
# on the candidate being unique — a fallback that guesses is worse than none.


def test_normalize_strips_punctuation() -> None:
    """FBref writes M'Boma; Wikidata writes Mboma."""
    assert whois.normalize("Patrick M'Boma") == whois.normalize("Patrick Mboma")
    assert whois.normalize("Jean-Pierre Papin") == whois.normalize("Jean Pierre Papin")


def test_resolve_matches_when_wikidata_carries_an_extra_surname() -> None:
    """Iván Kaviedes on FBref is Iván Kaviedes Toaquiza on Wikidata."""
    raw = pd.DataFrame({"player": ["Iván Kaviedes"], "born": [1977.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q1"],
            "fbref_id": ["a"],
            "label": ["Iván Kaviedes Toaquiza"],
            "birth_year": pd.array([1977], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].iloc[0] == "Q1"


def test_resolve_matches_when_fbref_carries_the_extra_name() -> None:
    """Containment has to work in both directions: Yakubu Aiyegbeni is Yakubu."""
    raw = pd.DataFrame({"player": ["Yakubu Aiyegbeni"], "born": [1982.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q2"],
            "fbref_id": ["b"],
            "label": ["Yakubu"],
            "birth_year": pd.array([1982], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].iloc[0] == "Q2"


def test_resolve_matches_a_shortened_forename() -> None:
    """Matt Upson is Matthew Upson: same surname, same year, same initial."""
    raw = pd.DataFrame({"player": ["Matt Upson"], "born": [1979.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q3"],
            "fbref_id": ["c"],
            "label": ["Matthew Upson"],
            "birth_year": pd.array([1979], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].iloc[0] == "Q3"


def test_resolve_refuses_an_ambiguous_containment_match() -> None:
    """Two candidates in the same birth year means no match, not a coin flip."""
    raw = pd.DataFrame({"player": ["Danny Ward"], "born": [1991.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q4", "Q5"],
            "fbref_id": ["d", "e"],
            "label": ["Danny Ward Senior", "Danny Ward Junior"],
            "birth_year": pd.array([1991, 1991], dtype="Int64"),
        }
    )
    labelled, unresolved = whois.resolve(raw, cw)
    assert labelled["qid"].isna().all()
    assert len(unresolved) == 1


def test_resolve_refuses_an_ambiguous_initial_match() -> None:
    """Two Wards born the same year, both 'D' — the initial tier must decline."""
    raw = pd.DataFrame({"player": ["Danny Ward"], "born": [1991.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q4", "Q5"],
            "fbref_id": ["d", "e"],
            "label": ["Daniel Ward", "Dominic Ward"],
            "birth_year": pd.array([1991, 1991], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].isna().all()


def test_fallback_never_crosses_a_birth_year() -> None:
    """The year is the only hard evidence there is; a fallback may not relax it."""
    raw = pd.DataFrame({"player": ["Matt Upson"], "born": [1979.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q6"],
            "fbref_id": ["f"],
            "label": ["Matthew Upson"],
            "birth_year": pd.array([1988], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].isna().all()


def test_exact_match_wins_over_a_fallback_candidate() -> None:
    raw = pd.DataFrame({"player": ["Ronaldo"], "born": [1976.0]})
    cw = pd.DataFrame(
        {
            "qid": ["Q7", "Q8"],
            "fbref_id": ["g", "h"],
            "label": ["Ronaldo", "Ronaldo Luís Nazário de Lima"],
            "birth_year": pd.array([1976, 1976], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].iloc[0] == "Q7"


def test_fallback_does_not_fire_without_a_birth_year() -> None:
    raw = pd.DataFrame({"player": ["Matt Upson"], "born": [float("nan")]})
    cw = pd.DataFrame(
        {
            "qid": ["Q9"],
            "fbref_id": ["i"],
            "label": ["Matthew Upson"],
            "birth_year": pd.array([1979], dtype="Int64"),
        }
    )
    labelled, _ = whois.resolve(raw, cw)
    assert labelled["qid"].isna().all()


def test_fallback_keeps_the_output_the_same_length() -> None:
    raw = pd.DataFrame(
        {"player": ["Iván Kaviedes", "Iván Kaviedes", "Nobody"], "born": [1977.0, 1977.0, 1990.0]}
    )
    cw = pd.DataFrame(
        {
            "qid": ["Q1"],
            "fbref_id": ["a"],
            "label": ["Iván Kaviedes Toaquiza"],
            "birth_year": pd.array([1977], dtype="Int64"),
        }
    )
    labelled, unresolved = whois.resolve(raw, cw)
    assert len(labelled) == 3
    assert list(unresolved["player"]) == ["Nobody"]
