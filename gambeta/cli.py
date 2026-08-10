"""Command-line entry point: ``gambeta {scrape,clean,rank,all}``.

Each stage reads the previous stage's Parquet output. Only ``scrape`` touches the
network, so iterating on the definition never re-scrapes.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

import pandas as pd

from gambeta import bridge, gate, kit, laws, level, locker, needs, tally, whois
from gambeta.scouts.elo import EloScout
from gambeta.scouts.fbref import FBrefScout
from gambeta.scouts.wikidata import WikidataScout

log = logging.getLogger("gambeta")

RAW_OUTFIELD = "outfield_raw.parquet"
RAW_KEEPER = "keeper_raw.parquet"
RAW_ELO = "elo.parquet"
RAW_CROSSWALK = "crosswalk.parquet"
CLEAN_OUTFIELD = "outfield.parquet"
CLEAN_KEEPER = "keeper.parquet"
UNRESOLVED = "unresolved.csv"
OFFSETS = "league_offsets.parquet"
RANKING = "ranking.parquet"
KEEPER_RANKING = "keeper_ranking.parquet"
FAILURES = "failures.csv"
SEASON_SCORES = "player_season_scored.parquet"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="gambeta", description="Football player analysis pipeline"
    )
    parser.add_argument("stage", choices=["scrape", "clean", "rank", "all"])
    parser.add_argument("--seasons", nargs="+", default=None, help="Season codes, e.g. 0001 0102")
    parser.add_argument("--leagues", nargs="+", default=None, help="League ids")
    return parser


def scrape(cfg: kit.Config, seasons: Sequence[str], leagues: Sequence[str]) -> None:
    """Fetch every source into ``vault/raw/``.

    Reads the warmed cache when present. A league with no cached data is skipped
    with a warning rather than aborting the run, so the pipeline works on a
    partial Big 5 and picks up a league the moment its cache exists.
    """
    log.info("fetching %d leagues x %d seasons", len(leagues), len(seasons))
    outfield, keeper = FBrefScout(leagues, seasons, cfg.raw).fetch()
    got = sorted(outfield["league"].dropna().unique())
    missing = [lg for lg in leagues if lg not in got]
    if missing:
        log.warning("no data for %s - continuing without them", ", ".join(missing))

    locker.write(
        outfield,
        cfg.raw / RAW_OUTFIELD,
        laws.OUTFIELD_RAW,
        source="fbref",
        extra={"leagues": list(leagues), "seasons": list(seasons)},
    )
    locker.write(keeper, cfg.raw / RAW_KEEPER, laws.KEEPER_RAW, source="fbref-keeper")
    locker.write(EloScout(seasons).fetch(), cfg.raw / RAW_ELO, laws.ELO, source="clubelo")
    locker.write(
        WikidataScout().fetch(), cfg.raw / RAW_CROSSWALK, laws.CROSSWALK, source="wikidata"
    )


def clean(cfg: kit.Config) -> None:
    """Resolve identity and collapse mid-season transfers."""
    crosswalk = locker.read(cfg.raw / RAW_CROSSWALK, laws.CROSSWALK)
    outfield = locker.read(cfg.raw / RAW_OUTFIELD, laws.OUTFIELD_RAW)
    keeper = locker.read(cfg.raw / RAW_KEEPER, laws.KEEPER_RAW)

    labelled, unresolved = whois.resolve(outfield, crosswalk)
    log.warning(
        "identity resolved: %.1f%% of %d rows (%d players unresolved)",
        100.0 * labelled["qid"].notna().mean(),
        len(labelled),
        len(unresolved),
    )
    cfg.clean.mkdir(parents=True, exist_ok=True)
    unresolved.to_csv(cfg.clean / UNRESOLVED, index=False)

    collapsed = tally.collapse_transfers(labelled)
    collapsed = tally.add_team_share(collapsed, labelled)
    collapsed["age"] = labelled.groupby(["player_id", "season"])["age"].first().to_numpy()
    collapsed.to_parquet(cfg.clean / CLEAN_OUTFIELD, index=False)

    keeper_labelled, _ = whois.resolve(keeper, crosswalk)
    keeper_labelled.to_parquet(cfg.clean / CLEAN_KEEPER, index=False)
    log.info("clean: %d outfield rows, %d keeper rows", len(collapsed), len(keeper_labelled))


def _normalise(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Z-score each requirement within its (league, season), in place of the raw value."""
    out = level.zscore(df, keys)
    for key in keys:
        out[key] = out[f"{key}_z"]
    return out.drop(columns=[f"{key}_z" for key in keys])


def _rank_group(
    df: pd.DataFrame, reqs: tuple[needs.Requirement, ...], cfg: kit.Config
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalise, bridge, pool, gate and rank one population."""
    keys = needs.season_keys(reqs)
    scored = _normalise(df, keys)
    scored["score"] = scored[keys].mean(axis=1)

    # Solve for the leagues actually in the data, not the configured Big 5, so a
    # partial dataset works and a league added later needs no code change.
    present = sorted(scored["league"].dropna().unique())
    offsets = bridge.solve_offsets(bridge.find_moves(scored), cfg, leagues=present)
    scored = bridge.apply_offsets(scored, offsets, keys)

    profile = gate.standardise(gate.career_profile(scored, reqs, cfg), reqs)
    return gate.qualify_and_rank(profile, reqs, cfg), offsets


def rank(cfg: kit.Config) -> None:
    """Apply the requirement list, gate, and rank both populations."""
    elo = locker.read(cfg.raw / RAW_ELO, laws.ELO)
    outfield = pd.read_parquet(cfg.clean / CLEAN_OUTFIELD)
    keeper = pd.read_parquet(cfg.clean / CLEAN_KEEPER)

    values = needs.add_above_team(needs.outfield_values(outfield), elo, "scoring")
    values = values[values["minutes"] >= cfg.min_minutes]
    ranking, offsets = _rank_group(values, needs.OUTFIELD, cfg)

    # A keeper's "full season" is the most minutes anyone played in that league-season.
    keeper["team_minutes"] = keeper.groupby(["league", "season"])["minutes"].transform("max")
    kv = needs.keeper_values(keeper)
    kv = needs.add_above_team(kv, elo, "concedes_little")
    kv = kv[kv["minutes"] >= cfg.min_minutes]
    keeper_ranking, _ = _rank_group(kv, needs.KEEPER, cfg)

    cfg.derive.mkdir(parents=True, exist_ok=True)
    locker.write(ranking, cfg.derive / RANKING, laws.RANKING, source="gate.outfield")
    locker.write(keeper_ranking, cfg.derive / KEEPER_RANKING, laws.RANKING, source="gate.keeper")
    values.to_parquet(cfg.derive / SEASON_SCORES, index=False)
    locker.write(offsets, cfg.derive / OFFSETS, laws.LEAGUE_OFFSETS, source="bridge")
    gate.failure_summary(ranking, needs.OUTFIELD).to_csv(cfg.derive / FAILURES, index=False)

    log.warning(
        "outfield: %d qualified of %d ranked | keepers: %d of %d",
        int(ranking["qualified"].sum()),
        len(ranking),
        int(keeper_ranking["qualified"].sum()),
        len(keeper_ranking),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a pipeline stage. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    cfg = kit.load()
    seasons = args.seasons or list(cfg.seasons)
    leagues = args.leagues or list(cfg.leagues)

    if args.stage in ("scrape", "all"):
        scrape(cfg, seasons, leagues)
    if args.stage in ("clean", "all"):
        clean(cfg)
    if args.stage in ("rank", "all"):
        rank(cfg)
    return 0


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    raise SystemExit(main())
