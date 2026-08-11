"""Uncertainty: bootstrap confidence intervals and permutation tests.

Every published ranking carries an interval. Where two players' intervals
overlap, the project says so rather than reporting a spurious ordering — which
is the difference between an analysis and a hot take.

The interval answers "how precisely do we know this player's level?". The
permutation test answers the question people actually argue about — "is A
better than B, or is that gap what two equal players look like?" — and it
answers it without assuming a distribution, which matters when a career is
five numbers long.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gambeta import gpu

GPU_MIN_ELEMENTS = 1_000_000
"""Below this resample-matrix size, NumPy wins.

Kernel-launch and host-to-device transfer overhead dominate small problems, and
this project calls ``bootstrap`` thousands of times on five-element careers.
Dispatching those to the GPU would be slower, not faster — hence the floor.
"""


def bootstrap(
    values: np.ndarray,
    n: int = 10_000,
    seed: int = 20260810,
    alpha: float = 0.05,
    force_cpu: bool = False,
) -> tuple[float, float, float]:
    """Bootstrap the mean of ``values``.

    Parameters
    ----------
    values
        Observations to resample.
    n
        Number of bootstrap resamples.
    seed
        Random seed. A fixed seed makes the result exactly reproducible.
    alpha
        Two-sided significance level; 0.05 gives a 95% interval.
    force_cpu
        Use NumPy even when a GPU is present. Used by the parity test.

    Returns
    -------
    tuple of float
        ``(estimate, lower, upper)``. Empty input yields NaNs; a single
        observation yields that value three times, since one data point
        carries no information about its own uncertainty.
    """
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        return (float("nan"),) * 3
    if data.size == 1:
        return float(data[0]), float(data[0]), float(data[0])

    use_gpu = gpu.HAS_GPU and not force_cpu and (n * data.size) >= GPU_MIN_ELEMENTS
    xp = gpu.xp if use_gpu else np

    arr = xp.asarray(data)
    rng = xp.random.default_rng(seed)
    resampled = arr[rng.integers(0, arr.size, size=(n, arr.size))].mean(axis=1)

    host = gpu.asnumpy(resampled) if use_gpu else np.asarray(resampled)
    lo, hi = np.percentile(host, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(data.mean()), float(lo), float(hi)


def permutation_test(
    a: np.ndarray,
    b: np.ndarray,
    n: int = 10_000,
    seed: int = 20260810,
    two_sided: bool = False,
) -> tuple[float, float]:
    """Test "A is better than B" by shuffling the two careers together.

    Under the null hypothesis the two players are equally good, which means a
    season belongs to either career equally well. So the seasons are pooled,
    dealt back out at the original career lengths, and the difference in means
    recomputed. The p-value is how often chance alone produces a gap at least as
    large as the real one.

    Nothing here assumes normality, which is the point: a career is five to
    nineteen numbers, the score distribution is visibly skewed, and a t-test
    would be asserting a shape the data does not have.

    **One-sided by default**, because a claim like "Henry was better than Suárez"
    is directional and stated before looking. Swapping the arguments tests the
    opposite claim.

    **Use ``two_sided=True`` when the direction came from the data.** Scanning
    every pair in a table sorted by score means ``a`` is always the higher
    scorer, so the direction was chosen after seeing the answer — and a
    one-sided test picked that way is anti-conservative by roughly a factor of
    two. On the top eight of this ranking it reports 5 significant pairs where
    the two-sided test reports 3.

    Parameters
    ----------
    a, b
        Per-season scores for the two players, already normalised within
        ``(league, season)`` and league-offset adjusted, so the numbers are
        comparable across eras and divisions.
    n
        Number of random reallocations.
    seed
        Random seed; a fixed seed makes the p-value exactly reproducible.
    two_sided
        Test "these differ" rather than "a beats b", by comparing absolute
        differences. Required whenever the direction was picked post hoc.

    Returns
    -------
    tuple of float
        ``(observed difference in means, p-value)``. The p-value uses the
        ``(hits + 1) / (n + 1)`` correction, so it is never reported as zero —
        10,000 shuffles cannot distinguish "impossible" from "rarer than 1 in
        10,000", and printing ``p = 0`` would claim it can. Fewer than two
        seasons on either side yields NaN: there is nothing to shuffle.
    """
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if left.size < 2 or right.size < 2:
        return float("nan"), float("nan")

    observed = float(left.mean() - right.mean())
    pooled = np.concatenate([left, right])
    rng = np.random.default_rng(seed)

    draws = rng.permuted(np.tile(pooled, (n, 1)), axis=1)
    diffs = draws[:, : left.size].mean(axis=1) - draws[:, left.size :].mean(axis=1)
    extreme = np.abs(diffs) >= abs(observed) if two_sided else diffs >= observed
    p = float((1 + int(extreme.sum())) / (n + 1))
    return observed, p


def bootstrap_groups(
    df: pd.DataFrame,
    value_col: str,
    group_col: str,
    n: int = 10_000,
    seed: int = 20260810,
) -> pd.DataFrame:
    """Bootstrap the mean of ``value_col`` separately within each group.

    Returns
    -------
    pd.DataFrame
        Columns ``<group_col>, est, lo, hi``.
    """
    rows = []
    for key, group in df.groupby(group_col, sort=False):
        est, lo, hi = bootstrap(group[value_col].to_numpy(), n=n, seed=seed)
        rows.append({group_col: key, "est": est, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)
