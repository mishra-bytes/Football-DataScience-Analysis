"""Command-line entry point: ``gambeta {scrape,clean,derive,all}``.

Three stages, each reading the previous stage's Parquet output. Only ``scrape``
touches the network, so iterating on the analysis never re-scrapes.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from gambeta import kit, laws, lens, level, locker, tally, whois
from gambeta.scouts.elo import EloScout
from gambeta.scouts.fbref import FBrefScout
from gambeta.scouts.wikidata import WikidataScout

log = logging.getLogger("gambeta")

RAW_PLAYERS = "player_season_raw.parquet"
RAW_ELO = "elo.parquet"
RAW_CROSSWALK = "crosswalk.parquet"
CLEAN_PLAYERS = "player_season.parquet"
UNRESOLVED = "unresolved.csv"
SCORED = "player_season_scored.parquet"
PEAK5 = "peak5.parquet"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="gambeta", description="Football player analysis pipeline"
    )
    parser.add_argument("stage", choices=["scrape", "clean", "derive", "all"])
    parser.add_argument(
        "--seasons", nargs="+", default=None, help="Season codes, e.g. 0001 0102"
    )
    return parser


def scrape(cfg: kit.Config, seasons: Sequence[str]) -> None:
    """Fetch every source into ``vault/raw/``. Slow: roughly 50 s per season."""
    log.info("scraping %d seasons of %s", len(seasons), cfg.league)
    players = FBrefScout(cfg.league, seasons, cfg.raw).fetch()
    locker.write(
        players,
        cfg.raw / RAW_PLAYERS,
        laws.PLAYER_SEASON_RAW,
        source="fbref",
        extra={"seasons": list(seasons)},
    )

    log.info("fetching ClubElo snapshots")
    locker.write(EloScout(seasons).fetch(), cfg.raw / RAW_ELO, laws.ELO, source="clubelo")

    log.info("fetching Wikidata crosswalk")
    locker.write(
        WikidataScout().fetch(), cfg.raw / RAW_CROSSWALK, laws.CROSSWALK, source="wikidata"
    )


def clean(cfg: kit.Config) -> None:
    """Resolve identity and collapse transfers into ``vault/clean/``."""
    raw = locker.read(cfg.raw / RAW_PLAYERS, laws.PLAYER_SEASON_RAW)
    crosswalk = locker.read(cfg.raw / RAW_CROSSWALK, laws.CROSSWALK)

    labelled, unresolved = whois.resolve(raw, crosswalk)
    resolved_pct = 100.0 * labelled["qid"].notna().mean()
    log.warning(
        "identity resolved: %.1f%% of %d rows (%d players unresolved)",
        resolved_pct,
        len(labelled),
        len(unresolved),
    )

    cfg.clean.mkdir(parents=True, exist_ok=True)
    unresolved.to_csv(cfg.clean / UNRESOLVED, index=False)

    collapsed = tally.collapse_transfers(labelled)
    locker.write(
        collapsed[list(laws.PLAYER_SEASON.columns)],
        cfg.clean / CLEAN_PLAYERS,
        laws.PLAYER_SEASON,
        source="clean",
        extra={
            "identity_resolved_pct": round(resolved_pct, 2),
            "unresolved_players": int(len(unresolved)),
        },
    )


def derive(cfg: kit.Config) -> None:
    """Compute metrics, normalize by era, and rank into ``vault/derive/``."""
    clean_df = locker.read(cfg.clean / CLEAN_PLAYERS, laws.PLAYER_SEASON)
    raw = locker.read(cfg.raw / RAW_PLAYERS, laws.PLAYER_SEASON_RAW)
    crosswalk = locker.read(cfg.raw / RAW_CROSSWALK, laws.CROSSWALK)

    # add_team_share needs per-club rows, which only exist before collapsing.
    raw_ids, _ = whois.resolve(raw, crosswalk)

    rated = level.score(tally.add_team_share(tally.add_rates(clean_df), raw_ids), cfg)
    cfg.derive.mkdir(parents=True, exist_ok=True)
    rated.to_parquet(cfg.derive / SCORED, index=False)

    eligible = rated[rated["minutes"] >= cfg.min_minutes]
    log.info(
        "ranking %d player-seasons above the %d-minute threshold",
        len(eligible),
        cfg.min_minutes,
    )
    locker.write(
        lens.peak5(eligible, cfg),
        cfg.derive / PEAK5,
        laws.RATING,
        source="lens.peak5",
        extra={"min_minutes": cfg.min_minutes, "seed": cfg.seed},
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a pipeline stage. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    cfg = kit.load()
    seasons = args.seasons or list(cfg.seasons)

    if args.stage in ("scrape", "all"):
        scrape(cfg, seasons)
    if args.stage in ("clean", "all"):
        clean(cfg)
    if args.stage in ("derive", "all"):
        derive(cfg)
    return 0


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    raise SystemExit(main())
