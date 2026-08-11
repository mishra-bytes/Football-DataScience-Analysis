from pathlib import Path

import pytest

from dugout.app import filter_ratings, load_keepers, load_ratings, reweight, sigma
from gambeta import needs

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"
pytestmark = pytest.mark.skipif(
    not (SAMPLE / "ranking.parquet").exists(),
    reason="sample dataset not built yet; run `uv run gambeta all`",
)


def test_load_ratings_reads_the_sample() -> None:
    df = load_ratings(SAMPLE)
    assert {"player", "score", "qualified", "seasons", "leagues"} <= set(df.columns)
    assert len(df) > 0


def test_load_keepers_reads_the_sample() -> None:
    assert len(load_keepers(SAMPLE)) > 0


def test_filter_applies_the_minimum_seasons() -> None:
    out = filter_ratings(load_ratings(SAMPLE), min_seasons=5, search="")
    assert (out["seasons"] >= 5).all()


def test_filter_defaults_to_qualifiers_only() -> None:
    out = filter_ratings(load_ratings(SAMPLE), min_seasons=3, search="")
    assert out["qualified"].all()


def test_filter_can_include_non_qualifiers() -> None:
    df = load_ratings(SAMPLE)
    everyone = filter_ratings(df, min_seasons=3, search="", qualified_only=False)
    just_qualifiers = filter_ratings(df, min_seasons=3, search="", qualified_only=True)
    assert len(everyone) > len(just_qualifiers)


def test_filter_search_is_case_insensitive() -> None:
    df = load_ratings(SAMPLE)
    name = str(df.iloc[0]["player"])
    assert len(filter_ratings(df, min_seasons=1, search=name.lower())) >= 1


def test_filter_returns_empty_for_no_match() -> None:
    out = filter_ratings(load_ratings(SAMPLE), min_seasons=1, search="zzzznotaplayer")
    assert out.empty


def test_filter_does_not_mutate_the_input() -> None:
    df = load_ratings(SAMPLE)
    before = len(df)
    filter_ratings(df, min_seasons=5, search="a")
    assert len(df) == before


def test_sigma_puts_the_best_player_far_above_the_mean() -> None:
    df = load_ratings(SAMPLE)
    out = sigma(df.head(1), df)
    assert out["sigma"].iloc[0] > 3.0


def test_sigma_survives_a_zero_spread_population() -> None:
    df = load_ratings(SAMPLE).head(3).copy()
    df["score"] = 1.0
    assert sigma(df, df)["sigma"].notna().all()


def test_reweight_reproduces_the_published_ranking_at_equal_weights() -> None:
    """The dashboard must not quietly disagree with the committed answer."""
    published = load_ratings(SAMPLE)
    again = reweight(published, needs.OUTFIELD)
    assert list(again["player"].head(10)) == list(published["player"].head(10))
    assert int(again["qualified"].sum()) == int(published["qualified"].sum())


def test_reweight_changes_the_order_but_not_the_qualifiers() -> None:
    published = load_ratings(SAMPLE)
    tilted = reweight(published, needs.OUTFIELD, weights={"longevity": 5.0, "scoring": 0.0})
    assert int(tilted["qualified"].sum()) == int(published["qualified"].sum())
    assert list(tilted["player"].head(10)) != list(published["player"].head(10))


def test_raising_the_gate_in_the_dashboard_shrinks_the_field() -> None:
    published = load_ratings(SAMPLE)
    strict = reweight(published, needs.OUTFIELD, gate_percentile=60.0)
    assert int(strict["qualified"].sum()) < int(published["qualified"].sum())


def test_every_named_argument_runs_against_the_real_data() -> None:
    published = load_ratings(SAMPLE)
    for name, vector in needs.ARGUMENTS.items():
        out = reweight(published, needs.OUTFIELD, weights=vector)
        assert out["score"].notna().all(), name


def test_reweight_works_for_keepers_on_their_own_requirements() -> None:
    keepers = load_keepers(SAMPLE)
    again = reweight(keepers, needs.KEEPER)
    assert list(again["player"].head(5)) == list(keepers["player"].head(5))
