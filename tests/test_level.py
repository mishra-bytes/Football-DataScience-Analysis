import numpy as np
import pandas as pd

from gambeta import level


def _two_eras() -> pd.DataFrame:
    """A low-scoring era and a high-scoring era with identical internal spread."""
    return pd.DataFrame(
        {
            "league": ["ENG-Premier League"] * 6,
            "season": ["0001"] * 3 + ["2425"] * 3,
            "player_id": list("abcdef"),
            "ga_p90": [0.1, 0.2, 0.3, 1.1, 1.2, 1.3],
            "minutes": [3000] * 6,
        }
    )


def test_zscore_centres_each_season_on_zero() -> None:
    out = level.zscore(_two_eras(), ["ga_p90"])
    assert np.allclose(out.groupby("season")["ga_p90_z"].mean().to_numpy(), 0.0, atol=1e-12)


def test_zscore_makes_eras_comparable() -> None:
    """The best player of a low-scoring era ties the best of a high-scoring one."""
    out = level.zscore(_two_eras(), ["ga_p90"]).set_index("player_id")
    assert np.isclose(out.loc["c", "ga_p90_z"], out.loc["f", "ga_p90_z"])


def test_zscore_matches_a_hand_calculation() -> None:
    """Population sd of [0.1, 0.2, 0.3] is 0.0816..., so the top scores +1.2247."""
    out = level.zscore(_two_eras(), ["ga_p90"]).set_index("player_id")
    assert np.isclose(out.loc["c", "ga_p90_z"], np.sqrt(1.5), atol=1e-9)


def test_zscore_handles_a_zero_variance_season() -> None:
    flat = pd.DataFrame(
        {
            "league": ["L"] * 3,
            "season": ["0001"] * 3,
            "player_id": list("abc"),
            "ga_p90": [0.5, 0.5, 0.5],
            "minutes": [3000] * 3,
        }
    )
    assert (level.zscore(flat, ["ga_p90"])["ga_p90_z"] == 0.0).all()
