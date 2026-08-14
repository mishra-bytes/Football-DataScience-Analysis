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


def test_permutation_finds_no_difference_between_equals() -> None:
    """Two draws from the same distribution must not look separable."""
    rng = np.random.default_rng(0)
    _, p = doubt.permutation_test(rng.normal(0, 1, 12), rng.normal(0, 1, 12), n=2000, seed=1)
    assert p > 0.05


def test_permutation_detects_a_real_gap() -> None:
    better = np.array([3.0, 3.5, 3.2, 3.8, 3.1, 3.6, 3.4])
    worse = np.array([0.1, 0.3, -0.2, 0.0, 0.4, 0.2, -0.1])
    diff, p = doubt.permutation_test(better, worse, n=2000, seed=1)
    assert diff > 0
    assert p < 0.01


def test_permutation_reports_the_observed_gap() -> None:
    a = np.array([2.0, 4.0])
    b = np.array([1.0, 1.0])
    diff, _ = doubt.permutation_test(a, b, n=100, seed=1)
    assert diff == pytest.approx(2.0)


def test_permutation_is_one_sided() -> None:
    """The claim is directional, so reversing it must flip the verdict."""
    better = np.array([3.0, 3.5, 3.2, 3.8, 3.1, 3.6])
    worse = np.array([0.1, 0.3, -0.2, 0.0, 0.4, 0.2])
    _, forwards = doubt.permutation_test(better, worse, n=2000, seed=1)
    _, backwards = doubt.permutation_test(worse, better, n=2000, seed=1)
    assert forwards < 0.01
    assert backwards > 0.99


def test_permutation_never_reports_zero() -> None:
    """10,000 shuffles cannot tell 'impossible' from 'rarer than 1 in 10,000'."""
    better = np.arange(50.0) + 100.0
    worse = np.arange(50.0)
    _, p = doubt.permutation_test(better, worse, n=1000, seed=1)
    assert p > 0
    assert p == pytest.approx(1 / 1001)


def test_two_sided_is_stricter_than_one_sided() -> None:
    """Scanning a sorted table picks the direction from the data.

    A one-sided test chosen that way is anti-conservative by roughly a factor
    of two, so the exploratory pair scan must not use it.
    """
    # A modest gap, so the p-value sits well away from the 1/(n+1) floor where
    # the doubling relation is lost to the discreteness of the permutations.
    rng = np.random.default_rng(11)
    better, worse = rng.normal(0.3, 1, 40), rng.normal(0, 1, 40)
    _, one = doubt.permutation_test(better, worse, n=20_000, seed=1)
    _, two = doubt.permutation_test(better, worse, n=20_000, seed=1, two_sided=True)
    assert 0.01 < one < 0.4, "test is only meaningful away from the p-value floor"
    assert two > one
    assert two == pytest.approx(2 * one, rel=0.2)


def test_two_sided_ignores_the_direction() -> None:
    """'These differ' is the same claim whichever way round it is asked."""
    a = np.array([2.0, 2.4, 1.8, 2.2, 2.6])
    b = np.array([0.4, 0.1, 0.6, 0.3, 0.2])
    _, forwards = doubt.permutation_test(a, b, n=5_000, seed=2, two_sided=True)
    _, backwards = doubt.permutation_test(b, a, n=5_000, seed=2, two_sided=True)
    assert forwards == pytest.approx(backwards, abs=0.01)


def test_permutation_is_reproducible_for_a_fixed_seed() -> None:
    a, b = np.arange(10.0), np.arange(10.0) + 0.5
    once = doubt.permutation_test(a, b, n=500, seed=4)
    assert once == doubt.permutation_test(a, b, n=500, seed=4)


def test_permutation_refuses_a_career_of_one_season() -> None:
    """One number carries no evidence about its own variability."""
    diff, p = doubt.permutation_test(np.array([5.0]), np.arange(10.0), n=100, seed=1)
    assert np.isnan(diff) and np.isnan(p)


@pytest.mark.skipif(not gpu.HAS_GPU, reason="no CUDA GPU available")
def test_cupy_and_numpy_agree() -> None:
    """Spec section 7: parity is asserted, not assumed."""
    values = np.random.default_rng(0).normal(0, 1, 2000)
    on_cpu = doubt.bootstrap(values, n=20_000, seed=42, force_cpu=True)
    on_gpu = doubt.bootstrap(values, n=20_000, seed=42, force_cpu=False)
    assert np.allclose(on_cpu, on_gpu, atol=0.02)


def test_bca_matches_the_percentile_interval_on_symmetric_data() -> None:
    """With no skew and no bias, the correction should do almost nothing."""
    values = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    _, plo, phi = doubt.bootstrap(values, n=20_000, seed=1)
    _, blo, bhi = doubt.bca(values, n=20_000, seed=1)
    assert abs(blo - plo) < 0.15
    assert abs(bhi - phi) < 0.15


def test_bca_shifts_the_interval_on_skewed_data() -> None:
    """A right-skewed sample biases the percentile interval low. BCa moves it up."""
    values = np.array([1.0, 1.0, 1.0, 1.0, 9.0])
    _, plo, phi = doubt.bootstrap(values, n=20_000, seed=1)
    _, blo, bhi = doubt.bca(values, n=20_000, seed=1)
    assert bhi > phi, "acceleration must extend the upper tail on right skew"


def test_bca_covers_better_than_percentile_at_a_five_season_window() -> None:
    """The defect this exists to fix: percentile coverage collapses on short skewed
    careers. Five observations is the window peak5 actually resamples. At three,
    neither method covers well and BCa is measurably no better, so the claim is
    tested where it is true.
    """
    rng = np.random.default_rng(20260810)
    truth = float(np.exp(0.8**2 / 2))  # the population mean of lognormal(0, 0.8);
    # the intervals estimate the mean, so the mean is the target
    percentile_hits = bca_hits = 0
    trials = 1_000
    for i in range(trials):
        sample = rng.lognormal(mean=0.0, sigma=0.8, size=5)
        _, plo, phi = doubt.bootstrap(sample, n=2_000, seed=i)
        _, blo, bhi = doubt.bca(sample, n=2_000, seed=i)
        percentile_hits += plo <= truth <= phi
        bca_hits += blo <= truth <= bhi
    assert bca_hits > percentile_hits, (
        f"BCa {bca_hits}/{trials} must beat percentile {percentile_hits}/{trials}"
    )


def test_bca_returns_nans_for_empty_input() -> None:
    assert all(np.isnan(v) for v in doubt.bca(np.array([])))


def test_bca_returns_the_value_three_times_for_one_observation() -> None:
    assert doubt.bca(np.array([2.5])) == (2.5, 2.5, 2.5)


def test_bca_falls_back_when_every_observation_is_identical() -> None:
    """No spread means z0 is undefined. It must degrade, not raise or emit NaN."""
    est, lo, hi = doubt.bca(np.array([3.0, 3.0, 3.0, 3.0]))
    assert (est, lo, hi) == (3.0, 3.0, 3.0)


def test_bca_is_deterministic() -> None:
    values = np.array([1.0, 4.0, 2.0, 8.0, 3.0])
    assert doubt.bca(values, seed=7) == doubt.bca(values, seed=7)
