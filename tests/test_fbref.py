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


def _two_level(rows: int = 3) -> pd.DataFrame:
    """A frame shaped like FBref's side tables: MultiIndex rows and columns."""
    index = pd.MultiIndex.from_arrays(
        [
            ["ENG-Premier League"] * rows,
            ["0405"] * rows,
            ["Arsenal"] * rows,
            [f"P{i}" for i in range(rows)],
        ],
        names=["league", "season", "team", "player"],
    )
    columns = pd.MultiIndex.from_tuples(
        [("Standard", "SoT"), ("Standard", "SoT/90"), ("Standard", "G/SoT"), ("Standard", "Sh")]
    )
    return pd.DataFrame([[10.0, 0.5, 0.2, 30.0]] * rows, index=index, columns=columns)


def test_flatten_side_returns_single_level_columns() -> None:
    """Two-level columns here caused MergeError against the flat standard table."""
    from gambeta.scouts.fbref import SIDE_TABLES, flatten_side

    out = flatten_side(_two_level(), SIDE_TABLES["shooting"])
    assert out.columns.nlevels == 1


def test_flatten_side_keeps_join_keys_and_renamed_columns() -> None:
    from gambeta.scouts.fbref import SIDE_TABLES, flatten_side

    out = flatten_side(_two_level(), SIDE_TABLES["shooting"])
    assert {"league", "season", "team", "player", "sot", "sot_p90", "g_per_sot"} <= set(out.columns)
    assert out["sot"].iloc[0] == 10.0


def test_side_table_merges_onto_standard() -> None:
    """The end-to-end shape that actually broke the pipeline."""
    from gambeta.scouts.fbref import SIDE_TABLES, flatten_side, join_side_tables

    standard = flatten(_raw())
    side = flatten_side(_two_level(), SIDE_TABLES["shooting"])
    merged = join_side_tables(standard, {"shooting": side})
    assert len(merged) == len(standard)
    assert merged.columns.nlevels == 1


def test_join_fills_columns_for_tables_that_were_skipped() -> None:
    from gambeta.scouts.fbref import SIDE_COLUMNS, join_side_tables

    merged = join_side_tables(flatten(_raw()), {})
    for column in SIDE_COLUMNS:
        assert column in merged.columns
