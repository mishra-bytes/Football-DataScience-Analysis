# Data sources and terms

| Source | Used for | Terms |
|---|---|---|
| **FBref** (Sports Reference) | Player-season standard stats, Premier League 2000-01 to 2024-25 | Bulk redistribution is restricted. Raw scrapes stay local in `vault/raw/`, which DVC marks `push: false`. Only derived aggregates are published. |
| **ClubElo** | Team strength ratings, one snapshot per season | Free for non-commercial use. |
| **Wikidata** | Player identity crosswalk — QID, FBref ID (P5750), label, date of birth (P569) | CC0. No restriction. |

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

This requires Chrome (see `DEVIATIONS.md` #3) and takes roughly 25 minutes.
