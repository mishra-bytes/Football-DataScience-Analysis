"""External validation: does the ranking agree with the people who were there?

Every other check in this project is internal. The gate is consistent with the
requirement list, the requirement list is consistent with the definition, the
bootstrap is consistent with the data — and all of that could be internally
perfect while measuring the wrong thing entirely.

Ballon d'Or and world-player voting is the one available outside opinion. It is
not ground truth: it rewards trophies won by teammates, it is swayed by World
Cups this project cannot see, and it has its own well-known biases toward
forwards and toward whoever won the Champions League. That is precisely why it
is worth comparing against rather than fitting to. Agreement is evidence the
method measures something real; **disagreement is the more interesting output**,
because each disagreement has a nameable cause — and this module names it.
"""

from __future__ import annotations

import pandas as pd

WINDOW = (2000, 2025)
"""Award years the project could possibly reproduce, matching its seasons."""


def award_winners(awards: pd.DataFrame, window: tuple[int, int] = WINDOW) -> pd.DataFrame:
    """Distinct people who won any of the tracked awards inside the window.

    Returns
    -------
    pd.DataFrame
        Columns ``qid, honours, award_years, awards_won``.
    """
    lo, hi = window
    inside = awards[awards["year"].between(lo, hi, inclusive="both")]
    return (
        inside.groupby("qid")
        .agg(
            honours=("award", "size"),
            award_years=("year", lambda s: ", ".join(str(y) for y in sorted(set(s)))),
            awards_won=("award", lambda s: ", ".join(sorted(set(s)))),
        )
        .reset_index()
    )


def against_awards(
    ranking: pd.DataFrame,
    awards: pd.DataFrame,
    identity: pd.DataFrame,
    window: tuple[int, int] = WINDOW,
) -> pd.DataFrame:
    """Place every award winner inside our ranking.

    Parameters
    ----------
    ranking
        Output of :func:`gambeta.gate.qualify_and_rank`, sorted best first.
    awards
        Honours conforming to :data:`gambeta.laws.AWARDS`.
    identity
        Any frame carrying both ``player_id`` and ``qid`` — the per-season table
        is the obvious one. The ranking is keyed by ``player_id`` and the awards
        by ``qid``, and nothing else bridges them.
    window
        Award years to consider.

    Returns
    -------
    pd.DataFrame
        One row per winner we can locate, with where our ranking put them.
        Winners we cannot locate are dropped here and counted by
        :func:`summary`, because "we never saw this player" and "we ranked this
        player badly" are different failures and must not be added together.
    """
    winners = award_winners(awards, window)
    bridge = identity[["player_id", "qid"]].dropna().drop_duplicates()

    placed = ranking.reset_index(drop=True).assign(rank=lambda d: d.index + 1)
    merged = winners.merge(bridge, on="qid", how="left").merge(
        placed[
            ["player_id", "player", "rank", "score", "qualified", "worst_requirement", "failed"]
        ],
        on="player_id",
        how="left",
    )
    return merged.sort_values("honours", ascending=False).reset_index(drop=True)


def summary(placed: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    """Headline agreement figures, one metric per row.

    Kept deliberately blunt. A single correlation coefficient would hide the
    thing worth knowing, which is *how many* of the players contemporaries voted
    best are excluded outright by this definition.
    """
    found = placed[placed["rank"].notna()]
    qualified = found[found["qualified"].fillna(False).astype(bool)]
    total = len(ranking)
    top_slice = max(int(round(0.01 * total)), 1)

    rows = [
        ("award winners in the window", len(placed)),
        ("of those, present in our data", len(found)),
        ("of those, clearing all requirements", len(qualified)),
        ("median rank of a winner", int(found["rank"].median()) if len(found) else 0),
        (f"winners inside our top {top_slice}", int((found["rank"] <= top_slice).sum())),
        ("winners our gate rejects", int(len(found) - len(qualified))),
    ]
    return pd.DataFrame(rows, columns=["measure", "value"])


def disagreements(placed: pd.DataFrame, worst: int = 15) -> pd.DataFrame:
    """The winners this definition treats worst, and the requirement to blame.

    This is the output to read. A method that cannot say *why* it disagrees with
    the consensus is not defensible; one that says "Kaká, rejected on longevity"
    has made an argument that can be examined and rebutted.
    """
    found = placed[placed["rank"].notna()].copy()
    found["verdict"] = [
        "qualified" if q else f"failed: {f}"
        for q, f in zip(
            found["qualified"].fillna(False).astype(bool), found["failed"].fillna("—"), strict=True
        )
    ]
    return found.nlargest(worst, "rank")[
        ["player", "honours", "award_years", "rank", "verdict", "worst_requirement"]
    ].reset_index(drop=True)
