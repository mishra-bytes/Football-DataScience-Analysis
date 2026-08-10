"""Streamlit dashboard: the requirement-based ranking.

Data loading and filtering live in plain functions so they can be tested; only
:func:`main` touches Streamlit.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def load_ratings(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the outfield ranking from the committed sample."""
    return pd.read_parquet(sample_dir / "ranking.parquet")


def load_keepers(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the goalkeeper ranking."""
    return pd.read_parquet(sample_dir / "keeper_ranking.parquet")


def filter_ratings(
    df: pd.DataFrame, min_seasons: int, search: str, qualified_only: bool = True
) -> pd.DataFrame:
    """Filter by career length, a name search, and whether the gate was cleared."""
    out = df[df["seasons"] >= min_seasons]
    if qualified_only:
        out = out[out["qualified"]]
    if search:
        out = out[out["player"].str.contains(search, case=False, na=False, regex=False)]
    return out


def sigma(df: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Add how many standard deviations above the population mean each player is."""
    scores = population["score"].to_numpy(dtype=float)
    spread = scores.std(ddof=0)
    out = df.copy()
    out["sigma"] = (out["score"] - scores.mean()) / (spread if spread else 1.0)
    return out


def main() -> None:  # pragma: no cover - Streamlit entry point
    """Render the dashboard."""
    import streamlit as st

    from gambeta import needs, tifo

    st.set_page_config(page_title="gambeta", layout="wide")
    st.title("Who is the best footballer of the last 25 years?")
    st.caption(
        "Eleven requirements, measured across four leagues and 25 seasons. A player must clear "
        "the floor on every one of them to qualify at all; qualifiers are then ranked."
    )

    everyone = load_ratings()

    with st.sidebar:
        st.header("Filters")
        min_seasons = st.slider("Minimum seasons", 3, 15, 3)
        search = st.text_input("Search player")
        top = st.slider("Players to chart", 5, 40, 20)
        qualified_only = st.checkbox("Qualifiers only", value=True)
        st.divider()
        st.caption(
            "Attacking contribution only. FBref records no per-player defensive action before "
            "2017-18, so defenders score near zero on six of the eleven requirements."
        )

    shown = sigma(filter_ratings(everyone, min_seasons, search, qualified_only), everyone)
    if shown.empty:
        st.warning("No players match those filters.")
        return

    best = shown.iloc[0]
    left, mid, right = st.columns(3)
    left.metric("Top of this list", best["player"], f"{best['sigma']:+.1f} sigma")
    mid.metric("Qualifiers", f"{int(everyone['qualified'].sum())} of {len(everyone):,}")
    right.metric("Careers shown", f"{len(shown):,}")

    ranking_tab, distribution_tab, keeper_tab, failure_tab = st.tabs(
        ["Ranking", "Distribution", "Goalkeepers", "Who failed, and why"]
    )

    with ranking_tab:
        st.pyplot(
            tifo.ranked_dots(
                shown.assign(lo=shown["score"], hi=shown["score"]),
                top=top,
                title="Composite of eleven requirements",
                subtitle="Era- and league-adjusted. League strength estimated from transfers.",
            )
        )
        st.dataframe(
            shown[["player", "score", "sigma", "seasons", "leagues"]].round(2),
            width="stretch",
            hide_index=True,
        )

    with distribution_tab:
        top5 = shown.head(5)
        marks = dict(zip(top5["player"], top5["score"], strict=True))
        st.pyplot(tifo.bell(everyone["score"], highlight=marks))
        st.caption(
            "The right tail is fatter than a normal distribution allows. Sigma here is a ruler "
            "for comparison, not a probability — under a normal curve the best player would be "
            "a one-in-two-billion event in a population of four thousand."
        )

    with keeper_tab:
        keepers = load_keepers()
        kq = keepers[keepers["qualified"]] if qualified_only else keepers
        st.caption(
            "Judged on their own eight requirements — save percentage, clean sheets, goals "
            "conceded. Not comparable with outfield players; the data cannot support that."
        )
        st.dataframe(
            kq[["player", "score", "seasons", "leagues"]].round(2),
            width="stretch",
            hide_index=True,
        )

    with failure_tab:
        failed = everyone[~everyone["qualified"]].copy()
        failed["missed"] = (
            failed["failed"].fillna("").apply(lambda s: len(s.split(", ")) if s else 0)
        )
        near = failed[failed["missed"] == 1].nlargest(25, "score")
        st.caption(
            "The most interesting output in the project: strong players who miss on exactly one "
            "requirement. It shows precisely where the definition bites."
        )
        st.dataframe(
            near[["player", "score", "seasons", "failed"]].round(2),
            width="stretch",
            hide_index=True,
        )
        st.bar_chart(
            pd.read_csv(SAMPLE / "failures.csv").set_index("label")["eliminated"],
            horizontal=True,
        )
        st.caption(f"Requirements applied: {', '.join(r.label for r in needs.OUTFIELD)}")


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    main()
