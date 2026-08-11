import dataclasses

import numpy as np
import pandas as pd

from gambeta import gate, kit, needs

CFG = kit.load()
KEYS = [r.key for r in needs.OUTFIELD]
SEASON_KEYS = needs.season_keys(needs.OUTFIELD)


def _career(player_id: str, level: float, n: int, league: str = "ENG-Premier League"):
    rows = []
    for i in range(n):
        row = {
            "player_id": player_id,
            "player": f"P-{player_id}",
            "league": league,
            "season": f"{i:02d}{i + 1:02d}",
            "minutes": 3000,
        }
        row.update(dict.fromkeys(SEASON_KEYS, level))
        rows.append(row)
    return pd.DataFrame(rows)


def _population() -> pd.DataFrame:
    """Ten players at increasing levels, all with long careers."""
    return pd.concat([_career(f"p{i}", level=float(i), n=6) for i in range(10)])


def test_profile_has_one_row_per_player() -> None:
    profile = gate.career_profile(_population(), needs.OUTFIELD, CFG)
    assert len(profile) == 10
    assert profile["player_id"].is_unique


def test_profile_records_longevity_and_leagues() -> None:
    profile = gate.career_profile(_population(), needs.OUTFIELD, CFG).set_index("player_id")
    assert profile.loc["p3", "longevity"] == 6
    assert profile.loc["p3", "leagues"] == "ENG-Premier League"


def test_profile_drops_careers_below_the_season_floor() -> None:
    short = _career("brief", level=99.0, n=1)
    profile = gate.career_profile(pd.concat([_population(), short]), needs.OUTFIELD, CFG)
    assert "brief" not in set(profile["player_id"])


def test_profile_records_multiple_leagues() -> None:
    mixed = pd.concat(
        [
            _career("mover", 5.0, 3, "ESP-La Liga"),
            _career("mover", 5.0, 3, "ITA-Serie A").assign(
                season=[f"{i:02d}{i + 1:02d}" for i in range(3, 6)]
            ),
        ]
    )
    profile = gate.career_profile(mixed, needs.OUTFIELD, CFG).set_index("player_id")
    assert profile.loc["mover", "leagues"] == "ESP-La Liga, ITA-Serie A"


def test_consistency_rewards_the_steady_player() -> None:
    """Same average, but one player has bad years and the other does not."""
    steady = _career("steady", 5.0, 6)
    swingy = _career("swingy", 5.0, 6)
    swingy[SEASON_KEYS] = np.tile([0.0, 10.0, 0.0, 10.0, 0.0, 10.0], (len(SEASON_KEYS), 1)).T
    profile = gate.career_profile(pd.concat([steady, swingy]), needs.OUTFIELD, CFG)
    profile = profile.set_index("player_id")
    assert profile.loc["steady", "consistency"] > profile.loc["swingy", "consistency"]


def test_consistency_does_not_punish_being_excellent() -> None:
    """The bug that disqualified Messi, Ronaldo, Kane, Haaland and Henry at once.

    Measured as -(standard deviation), a great player's swing between very good
    and outstanding scored *worse* than a journeyman's flat mediocrity. A floor
    must rank the great player higher: his bad season is still good.
    """
    great = _career("great", 0.0, 6)
    great[SEASON_KEYS] = np.tile([2.5, 4.0, 3.0, 4.0, 2.5, 3.5], (len(SEASON_KEYS), 1)).T
    flat = _career("flat", 0.0, 6)
    flat[SEASON_KEYS] = np.tile([-0.1, 0.1, -0.1, 0.1, -0.1, 0.1], (len(SEASON_KEYS), 1)).T

    profile = gate.career_profile(pd.concat([great, flat]), needs.OUTFIELD, CFG)
    profile = profile.set_index("player_id")
    assert profile.loc["great", "consistency"] > profile.loc["flat", "consistency"]


def test_standardise_centres_every_requirement() -> None:
    std = gate.standardise(gate.career_profile(_population(), needs.OUTFIELD, CFG), needs.OUTFIELD)
    for key in KEYS:
        assert abs(std[key].mean()) < 1e-9


def _ranked() -> pd.DataFrame:
    profile = gate.standardise(
        gate.career_profile(_population(), needs.OUTFIELD, CFG), needs.OUTFIELD
    )
    return gate.qualify_and_rank(profile, needs.OUTFIELD, CFG)


def test_ranking_puts_qualifiers_first() -> None:
    ranked = _ranked()
    assert ranked["qualified"].is_monotonic_decreasing


def test_best_player_qualifies_and_leads() -> None:
    ranked = _ranked()
    assert ranked.iloc[0]["player_id"] == "p9"
    assert bool(ranked.iloc[0]["qualified"])


def test_failures_name_the_requirements_missed() -> None:
    ranked = _ranked().set_index("player_id")
    assert ranked.loc["p0", "failed"] is not None
    assert "scoring" in str(ranked.loc["p0", "failed"])


def test_qualifiers_have_no_failed_requirements() -> None:
    ranked = _ranked()
    assert ranked.loc[ranked["qualified"], "failed"].isna().all()


def test_nobody_is_dropped_from_the_output() -> None:
    """A player who fails the gate is reported, never silently deleted."""
    assert len(_ranked()) == 10


def test_a_single_weak_requirement_fails_the_gate() -> None:
    """This is the whole point of gating rather than averaging."""
    lopsided = _career("lopsided", 9.0, 6)
    lopsided["discipline"] = -50.0
    frame = pd.concat([_population(), lopsided])
    profile = gate.standardise(gate.career_profile(frame, needs.OUTFIELD, CFG), needs.OUTFIELD)
    ranked = gate.qualify_and_rank(profile, needs.OUTFIELD, CFG).set_index("player_id")
    assert not bool(ranked.loc["lopsided", "qualified"])
    assert "discipline" in str(ranked.loc["lopsided", "failed"])


def test_raising_the_floor_disqualifies_more_players() -> None:
    profile = gate.standardise(
        gate.career_profile(_population(), needs.OUTFIELD, CFG), needs.OUTFIELD
    )
    lenient = gate.qualify_and_rank(
        profile, needs.OUTFIELD, dataclasses.replace(CFG, gate_percentile=10.0)
    )
    strict = gate.qualify_and_rank(
        profile, needs.OUTFIELD, dataclasses.replace(CFG, gate_percentile=80.0)
    )
    assert strict["qualified"].sum() < lenient["qualified"].sum()


def test_weights_change_the_ordering() -> None:
    profile = gate.standardise(
        gate.career_profile(_population(), needs.OUTFIELD, CFG), needs.OUTFIELD
    )
    equal = gate.qualify_and_rank(profile, needs.OUTFIELD, CFG)
    tilted = gate.qualify_and_rank(
        profile, needs.OUTFIELD, CFG, weights={**dict.fromkeys(KEYS, 0.0), "consistency": 1.0}
    )
    assert not equal["score"].equals(tilted["score"])


def test_failure_summary_counts_eliminations() -> None:
    summary = gate.failure_summary(_ranked(), needs.OUTFIELD)
    assert set(summary["requirement"]) == set(KEYS)
    assert summary["eliminated"].sum() > 0


def _lopsided_population() -> pd.DataFrame:
    """Ten players who are each good at different things.

    ``_population`` gives every player the same value on all eleven requirements,
    so no weighting can reorder it — useless for testing weights.
    """
    frames = []
    for i in range(10):
        career = _career(f"v{i}", level=float(i), n=6)
        for j, key in enumerate(SEASON_KEYS):
            career[key] = float(i) + ((i + 2 * j) % 5) - 2.0
        frames.append(career)
    return pd.concat(frames)


def _profile() -> pd.DataFrame:
    return gate.standardise(
        gate.career_profile(_lopsided_population(), needs.OUTFIELD, CFG), needs.OUTFIELD
    )


def test_partial_weights_leave_the_rest_at_one() -> None:
    """A caller naming one requirement must not have to spell out the other ten.

    Sliders and named arguments both produce sparse dicts; requiring a complete
    one turned a missing key into a KeyError deep inside the ranking.
    """
    ranked = gate.qualify_and_rank(_profile(), needs.OUTFIELD, CFG, weights={"scoring": 3.0})
    assert ranked["score"].notna().all()


def test_weights_do_not_change_who_qualifies() -> None:
    """The gate is a floor per requirement; weights only order the survivors.

    This is the project's central claim — 'gate, then rank' means no weighting
    can smuggle a player past a requirement they failed.
    """
    equal = gate.qualify_and_rank(_profile(), needs.OUTFIELD, CFG)
    tilted = gate.qualify_and_rank(
        _profile(), needs.OUTFIELD, CFG, weights={"scoring": 50.0, "discipline": 0.0}
    )
    assert (
        equal.set_index("player_id")["qualified"]
        .sort_index()
        .equals(tilted.set_index("player_id")["qualified"].sort_index())
    )


def test_named_arguments_use_real_requirement_keys() -> None:
    """A typo in a preset would silently weight nothing."""
    for name, vector in needs.ARGUMENTS.items():
        unknown = set(vector) - set(KEYS)
        assert not unknown, f"{name} names requirements that do not exist: {unknown}"


def test_named_arguments_produce_different_answers() -> None:
    """If two arguments rank identically, one of them is not an argument."""
    scores = {
        name: tuple(
            gate.qualify_and_rank(_profile(), needs.OUTFIELD, CFG, weights=vector)
            .set_index("player_id")["score"]
            .sort_index()
            .round(6)
        )
        for name, vector in needs.ARGUMENTS.items()
    }
    assert len(set(scores.values())) == len(scores), "some named arguments are duplicates"
