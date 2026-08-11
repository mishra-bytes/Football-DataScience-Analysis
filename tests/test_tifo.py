import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from gambeta import tifo  # noqa: E402


def _ratings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player": [f"Player {i}" for i in range(30)],
            "score": [3.0 - i * 0.1 for i in range(30)],
            "lo": [2.8 - i * 0.1 for i in range(30)],
            "hi": [3.2 - i * 0.1 for i in range(30)],
        }
    )


def _seasons() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["0001", "0102", "0203"] * 3,
            "player": ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
            "rank": [1, 2, 3, 2, 1, 1, 3, 3, 2],
        }
    )


def test_ranked_dots_returns_a_figure() -> None:
    assert isinstance(tifo.ranked_dots(_ratings()), Figure)


def test_ranked_dots_limits_to_top_n() -> None:
    fig = tifo.ranked_dots(_ratings(), top=10)
    assert len(fig.axes[0].get_yticklabels()) == 10


def test_ranked_dots_shows_the_best_player_last_on_the_y_axis() -> None:
    """Highest score must sit at the top of the chart, i.e. last in draw order."""
    fig = tifo.ranked_dots(_ratings(), top=5)
    labels = [t.get_text() for t in fig.axes[0].get_yticklabels()]
    assert labels[-1] == "Player 0"


def test_ranked_dots_handles_fewer_rows_than_top() -> None:
    assert isinstance(tifo.ranked_dots(_ratings().head(3), top=20), Figure)


def test_ranked_dots_handles_an_empty_frame() -> None:
    empty = _ratings().head(0)
    assert isinstance(tifo.ranked_dots(empty), Figure)


def test_bump_returns_a_figure() -> None:
    assert isinstance(tifo.bump(_seasons()), Figure)


def test_bump_inverts_the_rank_axis() -> None:
    """Rank 1 belongs at the top."""
    ax = tifo.bump(_seasons()).axes[0]
    bottom, top = ax.get_ylim()
    assert bottom > top


def test_bump_labels_seasons_readably() -> None:
    labels = [t.get_text() for t in tifo.bump(_seasons()).axes[0].get_xticklabels()]
    assert labels[0] == "2000-01"


def test_season_label_expands_the_code() -> None:
    assert tifo.season_label("0001") == "2000-01"
    assert tifo.season_label("2425") == "2024-25"


def test_season_label_handles_the_century_rollover() -> None:
    assert tifo.season_label("9900") == "1999-00"


def test_dark_mode_uses_a_different_surface() -> None:
    """Dark is a selected palette, not an inversion of the light one."""
    assert tifo.palette(dark=True)["surface"] != tifo.palette(dark=False)["surface"]
    assert tifo.palette(dark=True)["accent"] != tifo.palette(dark=False)["accent"]


def test_ranked_dots_renders_in_dark_mode() -> None:
    assert isinstance(tifo.ranked_dots(_ratings(), dark=True), Figure)


def test_bump_never_exceeds_the_series_cap() -> None:
    """A ninth series must never get a generated hue."""
    many = pd.DataFrame(
        {
            "season": ["0001", "0102"] * 12,
            "player": [f"P{i}" for i in range(12) for _ in range(2)],
            "rank": list(range(1, 13)) * 2,
        }
    )
    assert len(tifo.bump(many, top=12).axes[0].lines) <= tifo.MAX_SERIES


def test_bell_returns_a_figure() -> None:
    import numpy as np

    values = pd.Series(np.random.default_rng(0).normal(0, 1, 500))
    assert isinstance(tifo.bell(values), Figure)


def test_bell_annotates_highlighted_players_with_sigma() -> None:
    import numpy as np

    values = pd.Series(np.random.default_rng(0).normal(0, 1, 500))
    fig = tifo.bell(values, highlight={"Someone": 4.0})
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert any("Someone" in t and "σ" in t for t in texts)


def test_bell_survives_non_finite_values() -> None:
    import numpy as np

    values = pd.Series([1.0, 2.0, np.nan, np.inf, 3.0])
    assert isinstance(tifo.bell(values, bins=5), Figure)


def test_apply_theme_is_idempotent() -> None:
    tifo.apply_theme()
    tifo.apply_theme()


def _oklab_lightness(hex_colour: str) -> float:
    """OKLab L for a hex colour, so ramp claims are checked not asserted."""
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    r, g, b = linear
    long_ = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    medium = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    short = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return float(0.2104542553 * long_ + 0.7936177850 * medium - 0.0040720468 * short)


@pytest.mark.parametrize("dark", [False, True])
def test_sequential_ramp_is_monotonic_in_lightness(dark: bool) -> None:
    """A magnitude ramp that doubles back reads as two different magnitudes."""
    steps = [_oklab_lightness(c) for c in tifo.palette(dark)["sequential"]]
    assert steps == sorted(steps) or steps == sorted(steps, reverse=True)


@pytest.mark.parametrize("dark", [False, True])
def test_diverging_ramp_turns_once_at_the_middle(dark: bool) -> None:
    """Each arm runs one way, and the turn is the neutral midpoint."""
    steps = [_oklab_lightness(c) for c in tifo.palette(dark)["diverging"]]
    middle = len(steps) // 2
    left, right = steps[: middle + 1], steps[middle:]
    assert left == sorted(left) or left == sorted(left, reverse=True)
    assert right == sorted(right) or right == sorted(right, reverse=True)
    # The turn is at the centre, not somewhere along an arm.
    assert steps[middle] == max(steps) or steps[middle] == min(steps)


def test_matrix_labels_only_what_it_is_asked_to() -> None:
    """A dense grid stays readable because small cells go unlabelled."""
    frame = pd.DataFrame([[1.0, 0.05], [0.05, 1.0]], index=["a", "b"], columns=["a", "b"])
    fig = tifo.matrix(frame, title="t", diverging=True, label_if=0.5)
    printed = {text.get_text() for ax in fig.axes for text in ax.texts}
    assert "1.00" in printed
    assert "0.05" not in printed


def test_matrix_centres_a_diverging_scale_on_zero() -> None:
    """Otherwise an all-positive matrix would paint zero as the extreme."""
    frame = pd.DataFrame([[0.2, 0.8]], index=["a"], columns=["x", "y"])
    fig = tifo.matrix(frame, title="t", diverging=True)
    bar = fig.axes[-1]
    low, high = bar.get_ylim()
    assert low == pytest.approx(-high)
