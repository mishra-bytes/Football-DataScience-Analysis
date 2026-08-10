"""Gate, then rank.

The definition says a player *must have* eleven things. That is read literally: a
floor on every requirement decides who qualifies, and only qualifiers are ranked.
A weighted average alone would let a player be genuinely poor at something the
list calls a requirement and still win on volume elsewhere.

The third output — which requirement each failed player missed — is a
first-class deliverable, not diagnostics. "Haaland fails longevity" is more
informative than his rank, and it is what makes the definition arguable instead
of decreed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gambeta.kit import Config
from gambeta.needs import Requirement, season_keys


def career_profile(
    seasons: pd.DataFrame, reqs: tuple[Requirement, ...], cfg: Config
) -> pd.DataFrame:
    """Pool a player's seasons into one value per requirement.

    Season-level requirements are averaged across the player's seasons weighted
    by minutes, so a 200-minute cameo cannot swing a career. Longevity and
    consistency are then derived from that same per-season series.

    Parameters
    ----------
    seasons
        Player-seasons whose requirement columns are already z-scored within
        ``(league, season)`` and league-offset adjusted.
    reqs
        The requirement list, :data:`gambeta.needs.OUTFIELD` or ``KEEPER``.
    cfg
        Supplies nothing here yet but keeps the signature uniform with the rest
        of the pipeline.

    Returns
    -------
    pd.DataFrame
        One row per player, one column per requirement, plus ``seasons`` and
        ``leagues`` describing the career behind it.
    """
    keys = season_keys(reqs)
    weights = seasons["minutes"].to_numpy(dtype=float)
    frame = seasons.assign(_w=np.where(weights > 0, weights, 1e-9))

    rows = []
    for player_id, career in frame.groupby("player_id", sort=False):
        w = career["_w"].to_numpy(dtype=float)
        pooled = {k: float(np.average(career[k].to_numpy(dtype=float), weights=w)) for k in keys}

        per_season = career[keys].mean(axis=1).to_numpy(dtype=float)
        pooled["longevity"] = float(len(career))
        # The level of his worse seasons, not the size of his swings.
        #
        # This was -(standard deviation) and it was badly wrong. An elite player
        # swings between +2.5 and +4.0, so his SD is large; a journeyman sits at
        # -0.1 every year, so his SD is near zero. Variance is anti-correlated
        # with excellence, and in a gate it disqualified Messi, Ronaldo, Kane,
        # Haaland, Lewandowski, Suárez, Henry and Salah in one stroke while
        # promoting the most featureless players in the dataset.
        #
        # A 20th percentile answers the question the requirement actually asks -
        # "did he have bad years?" - and a great player's bad year is still good.
        pooled["consistency"] = (
            float(np.percentile(per_season, 20)) if len(career) > 1 else float(per_season[0])
        )

        rows.append(
            {
                "player_id": player_id,
                "player": str(career["player"].iloc[0]),
                "seasons": int(len(career)),
                "leagues": ", ".join(sorted(career["league"].unique())),
                **pooled,
            }
        )

    profile = pd.DataFrame(rows)
    return profile[profile["seasons"] >= cfg.min_seasons].reset_index(drop=True)


def standardise(profile: pd.DataFrame, reqs: tuple[Requirement, ...]) -> pd.DataFrame:
    """Z-score every requirement across players so they share one scale.

    Without this the gate would compare a save percentage against a per-90 rate
    and the weighted mean would be dominated by whichever requirement happened to
    have the largest units.
    """
    out = profile.copy()
    for key in [r.key for r in reqs]:
        values = out[key].to_numpy(dtype=float)
        spread = values.std(ddof=0)
        out[key] = (values - values.mean()) / spread if spread > 0 else 0.0
    return out


def qualify_and_rank(
    profile: pd.DataFrame,
    reqs: tuple[Requirement, ...],
    cfg: Config,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Apply the floor to every requirement, then rank the qualifiers.

    Parameters
    ----------
    profile
        Output of :func:`standardise`.
    reqs
        The requirement list being applied.
    cfg
        Supplies ``gate_percentile``.
    weights
        Per-requirement weights for the ranking. Defaults to equal weighting.

    Returns
    -------
    pd.DataFrame
        Conforming to :data:`gambeta.laws.RANKING`, sorted with qualifiers first
        and best first within them. Non-qualifiers are retained with
        ``qualified=False`` and the requirements they missed listed in ``failed``.
    """
    keys = [r.key for r in reqs]
    w = weights or dict.fromkeys(keys, 1.0)
    floors = {
        k: float(np.percentile(profile[k].to_numpy(dtype=float), cfg.gate_percentile)) for k in keys
    }

    out = profile.copy()
    misses = pd.DataFrame(
        {k: out[k].to_numpy(dtype=float) < floors[k] for k in keys}, index=out.index
    )
    out["qualified"] = ~misses.any(axis=1)
    out["failed"] = [
        ", ".join(sorted(misses.columns[row])) if row.any() else None
        for _, row in misses.iterrows()
    ]
    out["worst_requirement"] = out[keys].idxmin(axis=1)

    total = sum(w[k] for k in keys)
    out["score"] = sum(out[k].to_numpy(dtype=float) * w[k] for k in keys) / total

    columns = [
        "player_id",
        "player",
        "score",
        "qualified",
        "failed",
        "worst_requirement",
        "seasons",
        "leagues",
    ]
    return out.sort_values(["qualified", "score"], ascending=[False, False]).reset_index(drop=True)[
        columns + keys
    ]


def failure_summary(ranking: pd.DataFrame, reqs: tuple[Requirement, ...]) -> pd.DataFrame:
    """Count how many players each requirement eliminated.

    A requirement that eliminates nobody is not doing any work; one that
    eliminates almost everybody is miscalibrated. Both are worth seeing.
    """
    labels = {r.key: r.label for r in reqs}
    failed = ranking.loc[~ranking["qualified"], "failed"].dropna()
    counts: dict[str, int] = dict.fromkeys(labels, 0)
    for entry in failed:
        for key in entry.split(", "):
            counts[key] = counts.get(key, 0) + 1

    return pd.DataFrame(
        [
            {"requirement": key, "label": labels.get(key, key), "eliminated": n}
            for key, n in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
    )
