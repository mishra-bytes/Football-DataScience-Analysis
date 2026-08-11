"""Command-line entry point: ``gambeta {scrape,clean,rank,all}``.

Each stage reads the previous stage's Parquet output. Only ``scrape`` touches the
network, so iterating on the definition never re-scrapes.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

import pandas as pd

from gambeta import bridge, gate, kit, laws, level, locker, needs, tally, verdict, whois
from gambeta.scouts.elo import EloScout, align_teams
from gambeta.scouts.fbref import FBrefScout
from gambeta.scouts.wikidata import AwardsScout, WikidataScout

log = logging.getLogger("gambeta")

RAW_OUTFIELD = "outfield_raw.parquet"
RAW_KEEPER = "keeper_raw.parquet"
RAW_ELO = "elo.parquet"
RAW_CROSSWALK = "crosswalk.parquet"
RAW_AWARDS = "awards.parquet"
CLEAN_OUTFIELD = "outfield.parquet"
CLEAN_KEEPER = "keeper.parquet"
UNRESOLVED = "unresolved.csv"
OFFSETS = "league_offsets.parquet"
RANKING = "ranking.parquet"
KEEPER_RANKING = "keeper_ranking.parquet"
FAILURES = "failures.csv"
SEASON_SCORES = "player_season_scored.parquet"
AWARDS_PLACED = "award_winners.csv"
AWARDS_SUMMARY = "awards_agreement.csv"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="gambeta", description="Football player analysis pipeline"
    )
    parser.add_argument("stage", choices=["scrape", "clean", "rank", "all"])
    parser.add_argument("--seasons", nargs="+", default=None, help="Season codes, e.g. 0001 0102")
    parser.add_argument("--leagues", nargs="+", default=None, help="League ids")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Never fetch: skip any stat table not already cached",
    )
    return parser


def scrape(
    cfg: kit.Config, seasons: Sequence[str], leagues: Sequence[str], cache_only: bool = False
) -> None:
    """Fetch every source into ``vault/raw/``.

    Reads the warmed cache when present. A league with no cached data is skipped
    with a warning rather than aborting the run, so the pipeline works on a
    partial Big 5 and picks up a league the moment its cache exists.
    """
    log.info("fetching %d leagues x %d seasons", len(leagues), len(seasons))
    outfield, keeper = FBrefScout(leagues, seasons, cfg.raw, cache_only=cache_only).fetch()
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

    # ClubElo and Wikidata have no per-file cache of their own, so under
    # --cache-only an existing output is reused rather than re-fetched.
    if not (cache_only and (cfg.raw / RAW_ELO).exists()):
        locker.write(
            EloScout(seasons, leagues).fetch(), cfg.raw / RAW_ELO, laws.ELO, source="clubelo"
        )
    if not (cache_only and (cfg.raw / RAW_CROSSWALK).exists()):
        locker.write(
            WikidataScout(cache_dir=cfg.raw / "wikidata").fetch(),
            cfg.raw / RAW_CROSSWALK,
            laws.CROSSWALK,
            source="wikidata",
        )
    if not (cache_only and (cfg.raw / RAW_AWARDS).exists()):
        locker.write(
            AwardsScout().fetch(), cfg.raw / RAW_AWARDS, laws.AWARDS, source="wikidata-awards"
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
    collapsed = tally.add_age(collapsed, labelled)

    # Club strength has to be attached before the transfer collapse, while rows
    # still name a club. A player who moved mid-season gets the minutes-weighted
    # blend of both clubs, which is what "the team around him" actually was.
    elo = align_teams(locker.read(cfg.raw / RAW_ELO, laws.ELO), labelled["team"])
    per_club = labelled.merge(elo, on=["season", "team"], how="left")
    per_club["_weighted"] = per_club["elo"] * per_club["minutes"]
    blended = per_club.groupby(["player_id", "season"], as_index=False).agg(
        _weighted=("_weighted", "sum"), _minutes=("minutes", "sum")
    )
    blended["elo"] = blended["_weighted"] / blended["_minutes"].replace(0, pd.NA)
    collapsed = collapsed.merge(
        blended[["player_id", "season", "elo"]], on=["player_id", "season"], how="left"
    )
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
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Normalise, bridge, pool, gate and rank one population.

    Returns the ranking, the league offsets, and the per-season frame behind
    them. The third is not a by-product: comparing two careers season by season
    (as :func:`gambeta.doubt.permutation_test` does) is only meaningful on
    these normalised, offset-adjusted numbers, never on the raw per-90s.
    """
    keys = needs.season_keys(reqs)
    scored = _normalise(df, keys)
    scored["score"] = scored[keys].mean(axis=1)

    # Solve for the leagues actually in the data, not the configured Big 5, so a
    # partial dataset works and a league added later needs no code change.
    present = sorted(scored["league"].dropna().unique())
    offsets = bridge.solve_offsets(bridge.find_moves(scored), cfg, leagues=present)
    scored = bridge.apply_offsets(scored, offsets, keys)

    # Recomputed after the bridge. `find_moves` needs the pre-offset score to
    # see the gap a transfer opens; everything downstream needs the post-offset
    # one, which is the series `career_profile` actually pools.
    scored["score"] = scored[keys].mean(axis=1)

    profile = gate.standardise(gate.career_profile(scored, reqs, cfg), reqs)
    return gate.qualify_and_rank(profile, reqs, cfg), offsets, scored


def rank(cfg: kit.Config) -> None:
    """Apply the requirement list, gate, and rank both populations."""
    outfield = pd.read_parquet(cfg.clean / CLEAN_OUTFIELD)
    keeper = pd.read_parquet(cfg.clean / CLEAN_KEEPER)
    elo = align_teams(locker.read(cfg.raw / RAW_ELO, laws.ELO), keeper["team"])

    # No above_team for outfielders: club strength does not predict individual
    # attacking output, so the residual was a copy of `scoring`. See needs.OUTFIELD.
    values = needs.outfield_values(outfield)
    values = values[values["minutes"] >= cfg.min_minutes]
    ranking, offsets, scored = _rank_group(values, needs.OUTFIELD, cfg)

    # Published alongside the raw per-season values, not instead of them: the
    # raw columns answer "what did he do", `season_score` answers "how good was
    # that, here, then", and only the second can be compared between careers.
    values = values.merge(
        scored[["player_id", "season", "score"]].rename(columns={"score": "season_score"}),
        on=["player_id", "season"],
        how="left",
    )

    # A keeper's "full season" is the most minutes anyone played in that league-season.
    keeper["team_minutes"] = keeper.groupby(["league", "season"])["minutes"].transform("max")
    kv = needs.keeper_values(keeper)
    kv = needs.add_above_team(kv, elo, "concedes_little")
    kv = kv[kv["minutes"] >= cfg.min_minutes]
    keeper_ranking, _, _ = _rank_group(kv, needs.KEEPER, cfg)

    cfg.derive.mkdir(parents=True, exist_ok=True)
    locker.write(ranking, cfg.derive / RANKING, laws.RANKING, source="gate.outfield")
    locker.write(keeper_ranking, cfg.derive / KEEPER_RANKING, laws.RANKING, source="gate.keeper")
    values.to_parquet(cfg.derive / SEASON_SCORES, index=False)
    locker.write(offsets, cfg.derive / OFFSETS, laws.LEAGUE_OFFSETS, source="bridge")
    gate.failure_summary(ranking, needs.OUTFIELD).to_csv(cfg.derive / FAILURES, index=False)

    # The only outside opinion the project consults. Optional, because the
    # ranking stands without it, but when it is present, disagreeing with the
    # Ballon d'Or is a claim that should be made in public with reasons.
    if (cfg.raw / RAW_AWARDS).exists():
        awards = locker.read(cfg.raw / RAW_AWARDS, laws.AWARDS)
        placed = verdict.against_awards(ranking, awards, values[["player_id", "qid"]])
        placed.to_csv(cfg.derive / AWARDS_PLACED, index=False)
        agreement = verdict.summary(placed, ranking)
        agreement.to_csv(cfg.derive / AWARDS_SUMMARY, index=False)
        log.warning(
            "awards: %s",
            " | ".join(f"{r.measure} {r.value}" for r in agreement.itertuples()),
        )

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
        scrape(cfg, seasons, leagues, cache_only=args.cache_only)
    if args.stage in ("clean", "all"):
        clean(cfg)
    if args.stage in ("rank", "all"):
        rank(cfg)
    return 0


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    raise SystemExit(main())
