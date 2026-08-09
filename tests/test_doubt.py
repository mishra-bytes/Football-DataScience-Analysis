import numpy as np
import pandas as pd
import pytest

from gambeta import doubt, gpu


def test_interval_brackets_the_estimate() -> None:
    rng = np.random.default_rng(0)
    est, lo, hi = doubt.bootstrap(rng.normal(5.0, 1.0, 500), n=2000, seed=1)
    assert lo < est < hi


def test_is_reproducible_for_a_fixed_seed() -> None:
    values = np.arange(100, dtype=float)
    assert doubt.bootstrap(values, n=1000, seed=7) == doubt.bootstrap(values, n=1000, seed=7)


def test_different_seeds_give_different_intervals() -> None:
    values = np.arange(100, dtype=float)
    assert doubt.bootstrap(values, n=1000, seed=7) != doubt.bootstrap(values, n=1000, seed=8)


def test_interval_narrows_as_the_sample_grows() -> None:
    rng = np.random.default_rng(0)
    _, lo_small, hi_small = doubt.bootstrap(rng.normal(0, 1, 50), n=2000, seed=3)
    _, lo_large, hi_large = doubt.bootstrap(rng.normal(0, 1, 5000), n=2000, seed=3)
    assert (hi_large - lo_large) < (hi_small - lo_small)


def test_single_observation_has_no_uncertainty() -> None:
    assert doubt.bootstrap(np.array([2.0]), n=100, seed=1) == (2.0, 2.0, 2.0)


def test_empty_input_yields_nan() -> None:
    assert all(np.isnan(v) for v in doubt.bootstrap(np.array([]), n=100, seed=1))


def test_estimate_is_the_sample_mean() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0])
    assert doubt.bootstrap(values, n=500, seed=1)[0] == 2.5


def test_bootstrap_groups_returns_one_row_per_group() -> None:
    df = pd.DataFrame({"g": ["a"] * 20 + ["b"] * 20, "v": list(range(40))})
    out = doubt.bootstrap_groups(df, value_col="v", group_col="g", n=500, seed=1)
    assert set(out["g"]) == {"a", "b"}
    assert (out["lo"] <= out["est"]).all()
    assert (out["est"] <= out["hi"]).all()


@pytest.mark.skipif(not gpu.HAS_GPU, reason="no CUDA GPU available")
def test_cupy_and_numpy_agree() -> None:
    """Spec section 7: parity is asserted, not assumed."""
    values = np.random.default_rng(0).normal(0, 1, 2000)
    on_cpu = doubt.bootstrap(values, n=20_000, seed=42, force_cpu=True)
    on_gpu = doubt.bootstrap(values, n=20_000, seed=42, force_cpu=False)
    assert np.allclose(on_cpu, on_gpu, atol=0.02)
