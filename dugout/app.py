"""Streamlit dashboard: the requirement-based ranking.

Data loading and filtering live in plain functions so they can be tested; only
:func:`main` touches Streamlit.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd

from gambeta import doubt, gate, kit, needs

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def load_ratings(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the outfield ranking from the committed sample."""
    return pd.read_parquet(sample_dir / "ranking.parquet")


def load_keepers(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the goalkeeper ranking."""
    return pd.read_parquet(sample_dir / "keeper_ranking.parquet")


def load_seasons(sample_dir: Path = SAMPLE) -> pd.DataFrame:
    """Load the per-season table behind the ranking."""
    return pd.read_parquet(sample_dir / "player_season_scored.parquet")


def head_to_head(
    seasons: pd.DataFrame, a: str, b: str, n: int = 10_000
) -> tuple[float, float] | None:
    """Do these two careers differ by more than chance would produce?

    **Two-sided**, and that is not a detail. Both dropdowns are populated in rank
    order, so whichever pair a reader picks, the direction of the difference was
    decided by the ranking rather than by them. A one-sided test in a direction
    the data chose is anti-conservative by roughly a factor of two.

    Returns ``None`` when the sample predates the normalised season score, rather
    than inventing an answer from the raw per-90 values, which are not comparable
    across eras or leagues.
    """
    if "season_score" not in seasons.columns:
        return None
    scores = seasons.dropna(subset=["season_score"])
    left = scores.loc[scores["player"] == a, "season_score"].to_numpy()
    right = scores.loc[scores["player"] == b, "season_score"].to_numpy()
    return doubt.permutation_test(left, right, n=n, two_sided=True)


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


def reweight(
    ranking: pd.DataFrame,
    reqs: tuple[needs.Requirement, ...],
    weights: dict[str, float] | None = None,
    gate_percentile: float | None = None,
) -> pd.DataFrame:
    """Re-run the gate and the ranking under a different argument.

    The published ranking already carries one standardised column per
    requirement, which is the whole input :func:`gambeta.gate.qualify_and_rank`
    needs — so the reader can change the weights and see the answer move without
    the pipeline, the scrape or the z-scoring being touched.

    Weights cannot move the gate. Requalifying is the *percentile's* job, and it
    is offered separately because it is the one genuinely arbitrary number in the
    definition.
    """
    cfg = kit.load()
    if gate_percentile is not None:
        cfg = dataclasses.replace(cfg, gate_percentile=gate_percentile)
    keys = [r.key for r in reqs]
    profile = ranking[["player_id", "player", "seasons", "leagues", *keys]].copy()
    return gate.qualify_and_rank(profile, reqs, cfg, weights=weights)


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

    from gambeta import tifo

    st.set_page_config(page_title="gambeta", layout="wide")
    st.title("Who is the best footballer of the last 25 years?")
    st.caption(
        "Eleven requirements, measured across the Big 5 leagues and 25 seasons. A player must "
        "clear the floor on every one of them to qualify at all; qualifiers are then ranked."
    )

    published = load_ratings()

    with st.sidebar:
        st.header("Filters")
        min_seasons = st.slider("Minimum seasons", 3, 15, 3)
        search = st.text_input("Search player")
        top = st.slider("Players to chart", 5, 40, 20)
        qualified_only = st.checkbox("Qualifiers only", value=True)

        st.divider()
        st.header("Make your own argument")
        st.caption(
            "Every requirement counts equally by default. That is a choice, not a "
            "fact — change it and watch the order move."
        )
        argument = st.selectbox("Start from", list(needs.ARGUMENTS))
        preset = needs.ARGUMENTS[argument]
        with st.expander("Weight each requirement", expanded=False):
            weights = {
                r.key: st.slider(r.label, 0.0, 5.0, float(preset.get(r.key, 1.0)), 0.5)
                for r in needs.OUTFIELD
            }
        gate_percentile = st.slider(
            "Gate: percentile every requirement must clear",
            0.0,
            80.0,
            float(kit.load().gate_percentile),
            5.0,
            help="The one genuinely arbitrary number in the definition. Weights cannot "
            "move the gate; only this can.",
        )

        st.divider()
        st.caption(
            "Attacking contribution only. FBref records no per-player defensive action before "
            "2017-18, so defenders score near zero on six of the eleven requirements."
        )

    everyone = reweight(published, needs.OUTFIELD, weights, gate_percentile)
    shown = sigma(filter_ratings(everyone, min_seasons, search, qualified_only), everyone)
    if shown.empty:
        st.warning("No players match those filters.")
        return

    best = shown.iloc[0]
    left, mid, right = st.columns(3)
    left.metric("Top of this list", best["player"], f"{best['sigma']:+.1f} sigma")
    mid.metric("Qualifiers", f"{int(everyone['qualified'].sum())} of {len(everyone):,}")
    right.metric("Careers shown", f"{len(shown):,}")

    # The point of the sliders is to be able to disagree with the headline and
    # see what it costs, so say plainly when the reader has changed the answer.
    was = published[published["qualified"]].iloc[0]["player"]
    now = everyone[everyone["qualified"]].iloc[0]["player"] if everyone["qualified"].any() else None
    if now is None:
        st.error("Nobody clears every requirement at that gate.")
    elif now != was:
        st.info(f"Under this argument the best player is **{now}**, not {was}.")

    ranking_tab, argue_tab, distribution_tab, keeper_tab, failure_tab = st.tabs(
        ["Ranking", "A vs B", "Distribution", "Goalkeepers", "Who failed, and why"]
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

    with argue_tab:
        st.caption(
            "Pick two players. Their seasons are pooled and dealt back out at random "
            "ten thousand times; the p-value is how often chance alone opens a gap as "
            "large as the real one. No distribution is assumed — a career is a dozen "
            "numbers, which is far too few to take a bell curve on trust. The test is "
            "two-sided, because these lists are in rank order and so the direction of "
            "any difference was chosen by the ranking rather than by you."
        )
        names = list(everyone.loc[everyone["qualified"], "player"])
        if len(names) < 2:
            st.warning("Not enough qualifiers to compare.")
        else:
            pick_a, pick_b = st.columns(2)
            a = pick_a.selectbox("Compare this player", names, index=0)
            b = pick_b.selectbox("against", names, index=1)
            result = head_to_head(load_seasons(), a, b)
            if result is None:
                st.warning("Rebuild the sample (`uv run gambeta all`) to enable this test.")
            elif any(pd.isna(v) for v in result):
                st.warning("One of those careers is too short to test.")
            else:
                diff, p = result
                st.metric(f"{a} minus {b}, per season", f"{diff:+.3f}")
                if p < 0.05:
                    st.success(f"p = {p:.4f} — the gap is larger than chance comfortably explains.")
                else:
                    st.info(
                        f"p = {p:.3f} — on this evidence these two are **not separable**. "
                        "That is a finding, not a failure: it says the argument about who "
                        "is better cannot be settled by these numbers."
                    )
                st.caption(
                    "One comparison at a time. Working through many pairs is 45 tests "
                    "on the top ten, and at a 5% threshold roughly two come out "
                    "'significant' on noise alone."
                )

    with distribution_tab:
        top5 = shown.head(5)
        marks = dict(zip(top5["player"], top5["score"], strict=True))
        st.pyplot(tifo.bell(everyone["score"], highlight=marks))
        st.caption(
            "The right tail is fatter than a normal distribution allows. Sigma here is a ruler "
            "for comparison, not a probability — under a normal curve the best player would be "
            "a one-in-six-hundred-million event in a population of five and a half thousand."
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
        # Recomputed, not read from failures.csv: the reader may have moved the
        # gate, and a chart of the published floor would then be describing a
        # different definition from the one on screen.
        st.bar_chart(
            gate.failure_summary(everyone, needs.OUTFIELD).set_index("label")["eliminated"],
            horizontal=True,
        )
        st.caption(
            f"At the {gate_percentile:.0f}th percentile every requirement eliminates the same "
            "share of the population by construction — that is what a percentile floor does. "
            "The interesting column is *which* players, above."
        )


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    main()
