from pathlib import Path

import pandas as pd
import pytest

from gambeta import laws
from gambeta.scouts import fbref
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


def test_flatten_clips_a_negative_count_to_zero() -> None:
    """FBref's own G-PK goes negative on some old rows: a penalty recorded with
    no matching goal. A negative count is never real, whatever the source."""
    raw = _raw().copy()
    raw.iloc[0, raw.columns.get_loc(("Performance", "G-PK"))] = -1
    out = flatten(raw)
    assert out["npg"].iloc[0] == 0


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
        # Every FBref season table publishes Born, and the join needs it: name
        # plus club does not identify a player.
        [
            ("born", ""),
            ("Standard", "SoT"),
            ("Standard", "SoT/90"),
            ("Standard", "G/SoT"),
            ("Standard", "Sh"),
        ]
    )
    return pd.DataFrame([[1980.0, 10.0, 0.5, 0.2, 30.0]] * rows, index=index, columns=columns)


def _namesakes(born: tuple[float, float], **stats: list[float]) -> pd.DataFrame:
    """Two players sharing a name at one club — the Míchel case, flat."""
    return pd.DataFrame(
        {
            "league": ["ESP-La Liga"] * 2,
            "season": ["0203"] * 2,
            "team": ["Rayo Vallecano"] * 2,
            "player": ["Michel"] * 2,
            "born": list(born),
            **stats,
        }
    )


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


def test_join_does_not_multiply_rows_for_players_sharing_a_name() -> None:
    """Two Míchels at Rayo Vallecano in 2002-03. Birth year is what separates them.

    Without it the merge returned the cross product and fabricated a player with
    19,288 minutes in a 38-match season.
    """
    from gambeta.scouts.fbref import join_side_tables

    standard = _namesakes((1975.0, 1977.0), minutes=[2411.0, 122.0])
    side = _namesakes((1975.0, 1977.0), sot=[10.0, 2.0])

    merged = join_side_tables(standard, {"shooting": side})

    assert len(merged) == 2
    assert merged.loc[merged["born"] == 1975.0, "sot"].item() == 10.0


def test_join_refuses_a_key_it_cannot_separate() -> None:
    """Same name, same club, same birth year: stop rather than guess."""
    from gambeta.scouts.fbref import join_side_tables

    standard = _namesakes((1975.0, 1975.0), minutes=[2411.0, 122.0])
    side = _namesakes((1975.0, 1975.0), sot=[10.0, 2.0])

    with pytest.raises(pd.errors.MergeError):
        join_side_tables(standard, {"shooting": side})


def test_join_keeps_side_data_for_players_with_no_birth_year() -> None:
    """A merge never matches NaN to NaN, which would silently strip side columns."""
    from gambeta.scouts.fbref import join_side_tables

    standard = _namesakes((float("nan"), 1977.0), minutes=[2411.0, 122.0])
    side = _namesakes((float("nan"), 1977.0), sot=[10.0, 2.0])

    merged = join_side_tables(standard, {"shooting": side})

    assert len(merged) == 2
    assert merged["sot"].notna().all()


def test_join_fills_columns_for_tables_that_were_skipped() -> None:
    from gambeta.scouts.fbref import SIDE_COLUMNS, join_side_tables

    merged = join_side_tables(flatten(_raw()), {})
    for column in SIDE_COLUMNS:
        assert column in merged.columns


def test_scout_defaults_to_every_stat_type() -> None:
    scout = fbref.FBrefScout(["ENG-Premier League"], ["2223"], data_dir=Path("."))
    assert scout.stat_types == fbref.SIDE_TABLES.keys() | {"standard", "keeper"}


def test_scout_can_be_restricted_to_standard_only() -> None:
    """UCL publishes no reliable side tables, so asking for them wastes a browser session."""
    scout = fbref.FBrefScout(
        ["UEFA-Champions League"], ["2223"], data_dir=Path("."), stat_types=("standard",)
    )
    assert scout.stat_types == {"standard"}
