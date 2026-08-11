# Data sources and terms

| Source | Used for | Terms |
|---|---|---|
| **FBref** (Sports Reference) | Player-season stats, Big 5 domestic leagues 2000-01 to 2024-25 | Bulk redistribution is restricted. Raw scrapes stay local in `vault/raw/`, which DVC marks `push: false`. Only derived aggregates are published. |
| **ClubElo** | Team strength ratings, one snapshot per season | Free for non-commercial use. |
| **Wikidata** | Player identity crosswalk — QID, label, date of birth (P569), selected by occupation (P106) with the FBref ID (P5750) kept as optional provenance; plus individual honours (P166) for the five awards used to validate the ranking | CC0. No restriction. |

## What is published

`data/sample/` is committed to git and contains **derived aggregates only**: z-scores, per-90
rates, and rating outputs. It never contains verbatim source tables.

This is a deliberate constraint, not an accident of convenience — see design spec §3.4. The
distinction that matters is between redistributing someone else's data and publishing your own
analysis of it.

## Reproducing the data

Everything in `data/sample/` can be rebuilt from source:

```bash
uv run gambeta all
```

This requires Chrome (see `DEVIATIONS.md` #3). A cold cache is 625 FBref pages —
5 leagues × 5 tables × 25 seasons — at roughly 45 seconds each, so budget about
five hours, plus another 40 minutes for the Wikidata crosswalk. Warm the cache
one league at a time with `scripts/warm_all.ps1`.

Both sources cache **per unit of work**, not per run: one HTML file per
league-season-table, one Parquet per birth year. So the cold cost is paid once
and `uv run gambeta all --cache-only` then rebuilds everything offline in five
minutes, and a repair refetches only what actually failed.
