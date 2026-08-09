"""Uncertainty: bootstrap confidence intervals.

Every published ranking carries an interval. Where two players' intervals
overlap, the project says so rather than reporting a spurious ordering — which
is the difference between an analysis and a hot take.
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
