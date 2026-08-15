import numpy as np
import pandas as pd
import pytest

from gambeta import bayes, kit

pytest.importorskip("pymc")  # the extra is optional; the suite must pass without it
CFG = kit.load()


def _synthetic(rng: np.random.Generator) -> pd.DataFrame:
    """Twenty players with known true levels, observed with noise."""
    rows = []
    for i in range(20):
        truth = (i - 10) / 4.0
        for s in range(6):
            rows.append(
                {
                    "player_id": f"p{i}",
                    "season": f"{s:02d}{s + 1:02d}",
                    "minutes": 3000,
                    "season_score": truth + rng.normal(0, 0.5),
                    "_truth": truth,
                }
            )
    return pd.DataFrame(rows)


def test_fit_recovers_the_true_player_levels() -> None:
    df = _synthetic(np.random.default_rng(20260810))
    effects = bayes.player_effects(bayes.fit(df, CFG, draws=400, tune=400), df)
    merged = effects.merge(df.groupby("player_id")["_truth"].first(), on="player_id")
    assert np.corrcoef(merged["mean"], merged["_truth"])[0, 1] > 0.95


def test_shrinkage_pulls_a_short_career_toward_the_mean() -> None:
    """The whole point: three seasons should be trusted less than eighteen."""
    df = _synthetic(np.random.default_rng(1))
    short = df[df["player_id"] == "p19"].head(2)
    df = pd.concat([df[df["player_id"] != "p19"], short])
    effects = bayes.player_effects(bayes.fit(df, CFG, draws=400, tune=400), df).set_index(
        "player_id"
    )
    raw = df[df["player_id"] == "p19"]["season_score"].mean()
    assert abs(effects.loc["p19", "mean"]) < abs(raw)


def test_a_short_career_gets_a_wider_interval() -> None:
    df = _synthetic(np.random.default_rng(2))
    df = pd.concat([df[df["player_id"] != "p3"], df[df["player_id"] == "p3"].head(2)])
    effects = bayes.player_effects(bayes.fit(df, CFG, draws=400, tune=400), df).set_index(
        "player_id"
    )
    assert effects.loc["p3", "sd"] > effects.loc["p4", "sd"]
