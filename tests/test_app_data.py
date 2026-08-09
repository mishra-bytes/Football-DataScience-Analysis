from pathlib import Path

import pytest

from dugout.app import filter_ratings, load_ratings

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"
pytestmark = pytest.mark.skipif(
    not (SAMPLE / "peak5.parquet").exists(),
    reason="sample dataset not built yet; run `uv run gambeta all`",
)


def test_load_ratings_reads_the_sample() -> None:
    df = load_ratings(SAMPLE)
    assert {"player", "score", "lo", "hi", "seasons_used"} <= set(df.columns)
    assert len(df) > 0


def test_filter_applies_the_minimum_seasons() -> None:
    out = filter_ratings(load_ratings(SAMPLE), min_seasons=3, search="")
    assert (out["seasons_used"] >= 3).all()


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
