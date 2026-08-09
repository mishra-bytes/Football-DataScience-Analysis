"""Streamlit dashboard: browse the peak-5 ratings.

Phase 1 is deliberately a skeleton. The weight sliders that make the composite
index interactive arrive in Phase 4, once there is more than one lens to weight —
a slider controlling a single lens would be theatre.

Data-loading and filtering live in plain functions so they can be tested; only
:func:`main` touches Streamlit.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def load_ratings(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the peak-5 ratings table from the committed sample."""
    return pd.read_parquet(sample_dir / "peak5.parquet")


def filter_ratings(df: pd.DataFrame, min_seasons: int, search: str) -> pd.DataFrame:
    """Filter by minimum seasons in the peak window and a name search.

    Parameters
    ----------
    df
        Ratings table.
    min_seasons
        Keep players whose peak window spans at least this many seasons.
    search
        Case-insensitive substring match on player name. Empty means no filter.
    """
    out = df[df["seasons_used"] >= min_seasons]
    if search:
        out = out[out["player"].str.contains(search, case=False, na=False, regex=False)]
    return out


def main() -> None:  # pragma: no cover - Streamlit entry point
    """Render the dashboard."""
    import streamlit as st

    from gambeta import tifo

    st.set_page_config(page_title="gambeta", layout="wide")
    st.title("Premier League, 2000–2025")
    st.caption(
        "Ranked by best five consecutive seasons, era-adjusted. Bars are 95% bootstrap "
        "intervals — where two players' bars overlap, the data does not resolve the order "
        "between them."
    )

    df = load_ratings()

    with st.sidebar:
        st.header("Filters")
        min_seasons = st.slider("Minimum seasons in peak window", 1, 5, 3)
        search = st.text_input("Search player")
        top = st.slider("Players to chart", 5, 40, 20)
        st.divider()
        st.caption(
            "Attacking output only: goals and assists per 90, era-adjusted. "
            "Defenders and holding midfielders are systematically undervalued."
        )

    shown = filter_ratings(df, min_seasons, search)

    if shown.empty:
        st.warning("No players match those filters.")
        return

    st.pyplot(tifo.ranked_dots(shown, top=top))
    st.dataframe(shown, width="stretch", hide_index=True)


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    main()
