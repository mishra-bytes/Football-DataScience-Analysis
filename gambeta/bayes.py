"""Hierarchical model of player-season level, with shrinkage estimated rather than assumed.

The pipeline's point estimates pool a career weighted by minutes and exclude
short seasons with a hard floor at ``cfg.min_minutes``. Both are decisions
somebody made, and neither is measured. A player with three seasons and a player
with eighteen get the same treatment, and the sensitivity sweep in chapter 14
cannot justify the floor because it is not a parameter the data speaks to.

A partially pooled model replaces both. Each player gets his own level, drawn
from a population distribution whose spread is estimated from the data, so how
far a short career is pulled toward the mean is an answer rather than a setting.
Season effects absorb era drift that the within-season z-score does not already
remove.

This does not reorder the top of the table, and it is not meant to. It makes the
uncertainty on every player honest, and it removes the minutes floor as an
unexamined choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from gambeta.kit import Config

if TYPE_CHECKING:
    import arviz as az

FULL_SEASON_MINUTES = 3420.0
"""A full season's minutes: 38 matches at 90 minutes, the same constant `lens._FULL_SEASON` uses."""


def fit(
    seasons: pd.DataFrame, cfg: Config, draws: int = 1000, tune: int = 1000
) -> az.InferenceData:
    """Fit the hierarchical player-season model.

    Parameters
    ----------
    seasons
        Player-seasons with ``player_id``, ``season``, ``minutes`` and
        ``season_score``.
    cfg
        Project config; supplies the random seed.
    draws, tune
        Passed straight to :func:`pymc.sample`.

    Returns
    -------
    az.InferenceData
        The posterior. :func:`player_effects` reduces it to one row per player.

    Notes
    -----
    ``pymc``, ``pytensor`` and ``arviz`` are imported inside this function, not
    at module level. ``bayes`` is an optional extra (``pyproject.toml``'s
    ``bayes`` group), and the rest of the suite has to keep collecting and
    passing when it is not installed; a module-level import would fail
    ``tests/test_bayes.py``'s own collection before ``pytest.importorskip``
    ever runs.
    """
    import pymc as pm
    import pytensor.tensor as pt

    players = sorted(seasons["player_id"].unique())
    season_labels = sorted(seasons["season"].unique())
    # Plural dim names: pymc rejects a variable whose name matches its own
    # dimension label ("Variable name 'player' conflicts with an existing
    # dimension name"), which the singular coords key would trigger for both
    # `player` and `season` below.
    coords = {"players": players, "seasons": season_labels}

    player_idx = seasons["player_id"].map({p: i for i, p in enumerate(players)}).to_numpy()
    season_idx = seasons["season"].map({s: i for i, s in enumerate(season_labels)}).to_numpy()
    minutes = seasons["minutes"].to_numpy(dtype=float)
    scores = seasons["season_score"].to_numpy(dtype=float)

    with pm.Model(coords=coords):
        population_sd = pm.HalfNormal("population_sd", sigma=1.0)
        player = pm.Normal("player", mu=0.0, sigma=population_sd, dims="players")
        season = pm.Normal("season", mu=0.0, sigma=0.25, dims="seasons")
        noise = pm.HalfNormal("noise", sigma=1.0)

        # Precision scales with minutes played: a 3000-minute season is a
        # sharper observation of the same quantity than a 900-minute one, which
        # is what the hard minutes floor was crudely approximating.
        weight = pt.sqrt(minutes / FULL_SEASON_MINUTES)
        pm.Normal(
            "observed",
            mu=player[player_idx] + season[season_idx],
            sigma=noise / weight,
            observed=scores,
        )
        idata = pm.sample(draws=draws, tune=tune, random_seed=cfg.seed, progressbar=False)
    return idata


def player_effects(idata: az.InferenceData, seasons: pd.DataFrame) -> pd.DataFrame:
    """Reduce the ``player`` posterior to a point estimate and an interval per player.

    ``seasons`` is not read: every player id the posterior carries already lives
    in the model's own coords, which is the index this indexes back through.
    It stays in the signature because the caller always has both in hand and a
    consistent interface is worth more than dropping one unused parameter.

    Parameters
    ----------
    idata
        The result of :func:`fit`.
    seasons
        Unused; see above.

    Returns
    -------
    pd.DataFrame
        Columns ``player_id, mean, sd, hdi_lo, hdi_hi``. The interval is a 94%
        highest-density interval, arviz's default width.
    """
    import arviz as az

    del seasons
    posterior = idata.posterior["player"]
    hdi = az.hdi(idata, var_names=["player"], prob=0.94)["player"]
    return pd.DataFrame(
        {
            "player_id": posterior["players"].to_numpy(),
            "mean": posterior.mean(dim=("chain", "draw")).to_numpy(),
            "sd": posterior.std(dim=("chain", "draw")).to_numpy(),
            "hdi_lo": hdi.sel(ci_bound="lower").to_numpy(),
            "hdi_hi": hdi.sel(ci_bound="upper").to_numpy(),
        }
    )
