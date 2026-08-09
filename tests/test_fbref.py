from pathlib import Path

import pandas as pd

from gambeta import laws
from gambeta.scouts.fbref import flatten

FIXTURE = Path(__file__).parent / "fixtures" / "fbref_raw.pkl"


def _raw() -> pd.DataFrame:
    return pd.read_pickle(FIXTURE)


def test_flatten_produces_schema_valid_frame() -> None:
    laws.PLAYER_SEASON_RAW.validate(flatten(_raw()))


def test_flatten_lifts_index_into_columns() -> None:
    out = flatten(_raw())
    for col in ("league", "season", "team", "player"):
        assert col in out.columns


def test_flatten_renames_stat_columns() -> None:
    out = flatten(_raw())
    assert {"minutes", "goals", "assists", "npg", "yellow", "red"} <= set(out.columns)


def test_flatten_drops_precomputed_per90_columns() -> None:
    """We recompute rates from minutes, so FBref's own per-90 columns must go."""
    out = flatten(_raw())
    assert not any("90" in c and c != "nineties" for c in out.columns)


def test_flatten_drops_no_rows() -> None:
    raw = _raw()
    assert len(flatten(raw)) == len(raw)


def test_flatten_column_order_matches_the_schema() -> None:
    assert list(flatten(_raw()).columns) == list(laws.PLAYER_SEASON_RAW.columns)


def test_flatten_handles_both_eras() -> None:
    """The 2000-01 and 2024-25 seasons must both survive identically."""
    out = flatten(_raw())
    assert set(out["season"]) == {"0001", "2425"}


def test_flatten_yields_integer_counting_stats() -> None:
    out = flatten(_raw())
    for col in ("minutes", "goals", "assists", "mp"):
        assert out[col].dtype.kind == "i", f"{col} should be an integer count"
