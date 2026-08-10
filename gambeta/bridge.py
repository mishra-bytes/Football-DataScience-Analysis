"""League strength, estimated from players who change league.

Within-league z-scores are not comparable across leagues: two standard deviations
above Ligue 1 is not two above the Premier League. Pooling a career across
leagues makes that error worse, so it has to be corrected.

**A player who changes league between consecutive seasons is approximately the
same footballer on both sides of the move.** So each transfer is one noisy
measurement of one league pair:

    z_after - z_before  ~  strength(old league) - strength(new league)

Thousands of moves over 25 years form a connected graph, and the offsets fall out
of a weighted least-squares fit with one league pinned as the reference. It is the
same device that makes chess ratings comparable across separate rating pools.

Offsets are estimated per **league-era block** rather than per league-season:
125 league-season parameters would be badly identified from the handful of moves
some pairs see in a single year, while one constant per league would hide 25 years
of genuine drift. Five-season blocks are the compromise, and the number of moves
behind every estimate is published so a thin one can be discounted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gambeta.kit import SEASONS, Config

BLOCK_SEASONS = 5
"""Seasons per era block. Five keeps each offset backed by enough transfers."""

_SEASON_INDEX = {season: i for i, season in enumerate(SEASONS)}


def era_block(season: str) -> int:
    """Map a season code to its five-season era block."""
    return _SEASON_INDEX.get(season, 0) // BLOCK_SEASONS


def find_moves(seasons: pd.DataFrame, score_col: str = "score") -> pd.DataFrame:
    """Find every consecutive-season league change.

    Parameters
    ----------
    seasons
        Player-seasons with ``player_id``, ``league``, ``season``, ``minutes``
        and ``score_col`` (a within-league-season standard score).
    score_col
        Column holding the normalised score to difference across the move.

    Returns
    -------
    pd.DataFrame
        One row per move: the leagues and era blocks either side, the change in
        score, the age after the move, and the weight to give the observation.
    """
    columns = [
        "player_id",
        "from_league",
        "to_league",
        "from_block",
        "to_block",
        "delta",
        "weight",
        "age",
        "season",
    ]
    if seasons.empty:
        return pd.DataFrame(columns=columns)

    df = seasons.sort_values(["player_id", "season"])
    grouped = df.groupby("player_id", sort=False)

    prev_league = grouped["league"].shift()
    prev_season = grouped["season"].shift()
    prev_score = grouped[score_col].shift()
    prev_minutes = grouped["minutes"].shift()

    consecutive = prev_season.map(_SEASON_INDEX) == df["season"].map(_SEASON_INDEX) - 1
    changed = prev_league.notna() & (prev_league != df["league"])
    moves = df[consecutive & changed].copy()

    moves["from_league"] = prev_league[consecutive & changed]
    moves["to_league"] = moves["league"]
    moves["from_block"] = prev_season[consecutive & changed].map(era_block)
    moves["to_block"] = moves["season"].map(era_block)
    moves["delta"] = moves[score_col] - prev_score[consecutive & changed]
    moves["weight"] = np.minimum(
        moves["minutes"].to_numpy(dtype=float),
        prev_minutes[consecutive & changed].to_numpy(dtype=float),
    )
    moves["age"] = moves.get("age", pd.Series(np.nan, index=moves.index))

    return moves[columns].reset_index(drop=True)


def solve_offsets(moves: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Recover league-era strength offsets by weighted least squares.

    The model fitted for each move is::

        delta = adaptation + beta * centred_age + offset[from] - offset[to]

    ``adaptation`` is a single global intercept: settling into a new league costs
    something on average, and that cost is not league strength. Age is centred and
    entered linearly because players move at different career stages and decline
    would otherwise be misread as league difficulty. Observations are weighted by
    the smaller of the two seasons' minutes, so a 200-minute season counts for
    little.

    The reference league's blocks are dropped from the design matrix, pinning them
    at zero — offsets are only ever identified up to a constant.

    Returns
    -------
    pd.DataFrame
        Conforming to :data:`gambeta.laws.LEAGUE_OFFSETS`. A positive offset means
        the league is *stronger* than the reference, so a given z-score there is
        worth more.
    """
    usable = moves[moves["weight"] > 0].dropna(subset=["delta"])
    params = [
        (league, block)
        for league in cfg.leagues
        if league != cfg.leagues[0]
        for block in range(len(SEASONS) // BLOCK_SEASONS)
    ]
    index = {p: i for i, p in enumerate(params)}

    rows = []
    targets = []
    weights = []
    ages = usable["age"].to_numpy(dtype=float)
    mean_age = np.nanmean(ages) if np.isfinite(ages).any() else 0.0

    for i, (_, move) in enumerate(usable.iterrows()):
        row = np.zeros(len(params) + 2)
        row[0] = 1.0  # adaptation intercept
        row[1] = 0.0 if not np.isfinite(ages[i]) else ages[i] - mean_age
        src = (move["from_league"], int(move["from_block"]))
        dst = (move["to_league"], int(move["to_block"]))
        if src in index:
            row[2 + index[src]] += 1.0
        if dst in index:
            row[2 + index[dst]] -= 1.0
        rows.append(row)
        targets.append(float(move["delta"]))
        weights.append(float(move["weight"]))

    counts = (
        pd.concat(
            [
                usable[["from_league", "from_block"]].rename(
                    columns={"from_league": "league", "from_block": "block"}
                ),
                usable[["to_league", "to_block"]].rename(
                    columns={"to_league": "league", "to_block": "block"}
                ),
            ]
        )
        .value_counts()
        .to_dict()
    )

    solution = np.zeros(len(params) + 2)
    if rows:
        design = np.asarray(rows)
        rhs = np.asarray(targets)
        scale = np.sqrt(np.asarray(weights))
        solution, *_ = np.linalg.lstsq(design * scale[:, None], rhs * scale, rcond=None)

    estimates = {p: float(solution[2 + i]) for p, i in index.items()}
    for block in range(len(SEASONS) // BLOCK_SEASONS):
        estimates[(cfg.leagues[0], block)] = 0.0

    return pd.DataFrame(
        [
            {
                "league": league,
                "season": season,
                "offset": estimates[(league, era_block(season))],
                "moves": int(counts.get((league, era_block(season)), 0)),
            }
            for league in cfg.leagues
            for season in cfg.seasons
        ]
    )


def apply_offsets(seasons: pd.DataFrame, offsets: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Shift each requirement's z-score by its league-season offset."""
    out = seasons.merge(
        offsets[["league", "season", "offset"]], on=["league", "season"], how="left"
    )
    shift = out["offset"].fillna(0.0).to_numpy(dtype=float)
    for col in cols:
        out[col] = out[col].to_numpy(dtype=float) + shift
    return out.drop(columns=["offset"])
