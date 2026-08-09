# gambeta

Era-normalized football player analysis — and a worked textbook on the statistics
behind it.

Two things at once: **who the best Premier League players of the last twenty-five
years were**, and **how you would actually find out**. The second is the reason
the first is worth reading.

> **Phase 1 of five.** Premier League only, 2000-01 to 2024-25, one rating lens.
> See [Roadmap](#roadmap).

## The current answer

Ranked by best five consecutive seasons of goals and assists per 90, measured
against contemporaries in the same season:

| # | Player | Score | 95% interval | Peak window |
|---|---|---|---|---|
| 1 | Erling Haaland | 2.67 | 1.80 – 3.94 | 2022-23 to 2024-25 |
| 2 | Thierry Henry | 2.59 | 2.24 – 2.94 | 2002-03 to 2006-07 |
| 3 | Sergio Agüero | 2.43 | 1.83 – 3.08 | 2013-14 to 2017-18 |
| 4 | Mohamed Salah | 2.17 | 1.69 – 2.74 | 2020-21 to 2024-25 |
| 5 | Harry Kane | 2.03 | 1.17 – 2.89 | 2016-17 to 2020-21 |

**And the finding that matters more than the order:** 44 of the 45 possible pairs
in the top ten have overlapping intervals. This lens **cannot separate the top
ten**. Anyone who tells you confidently that one of these is third and another
seventh is reporting an opinion, not a measurement.

## Quickstart

```bash
uv sync --all-groups          # add --extra gpu if you have an NVIDIA card
uv run pytest                 # 116 tests, no network required
uv run streamlit run dugout/app.py
quarto render                 # builds the book into tome/_book
```

Everything runs against `data/sample/` — a small committed set of derived
aggregates — so you can reproduce every figure without scraping a single page.

## Rebuilding the data from source

```bash
uv run gambeta all            # scrape -> clean -> derive, roughly 25 minutes
```

Requires Chrome (soccerdata drives it to get past Cloudflare). Read
[DATA_SOURCES.md](DATA_SOURCES.md) first — FBref restricts bulk redistribution,
which is why only derived aggregates are published here.

Or run the stages individually:

```bash
uv run gambeta scrape --seasons 0001 0102
uv run gambeta clean
uv run gambeta derive
```

DVC stages the same DAG, so `uv run dvc repro` re-runs only what changed —
editing the normalization re-derives without re-scraping 25 seasons.

## How it works

| Module | Responsibility |
|---|---|
| `gambeta/kit.py` | Configuration: paths, seasons, thresholds, seed |
| `gambeta/scouts/` | One adapter per source — FBref, ClubElo, Wikidata |
| `gambeta/whois.py` | Player identity across 25 years of name variants |
| `gambeta/laws.py` | pandera schemas — the contract between layers |
| `gambeta/locker.py` | Parquet store with provenance manifests |
| `gambeta/tally.py` | Per-90 rates, transfer collapsing, share of club output |
| `gambeta/level.py` | Era normalization: z-scores and minutes shrinkage |
| `gambeta/lens.py` | The peak-5 rating |
| `gambeta/doubt.py` | Bootstrap confidence intervals (GPU when it pays) |
| `gambeta/tifo.py` | Charts, validated for colour-vision deficiency |

Three rules hold the design together:

1. **The Parquet store is the seam.** Nothing downstream of ingestion touches the
   network, so a broken scraper breaks ingestion, not analysis.
2. **Notebooks import from the package; they never implement.** That is what keeps
   `gambeta` a library rather than extracted notebook cells.
3. **Unmatched players are reported, never dropped.** Silently discarding an
   unmatched row does not error — it quietly deletes a career.

## Honest limitations

- **Attacking output only.** Defenders and holding midfielders are systematically
  undervalued. This is a known bias, stated rather than buried.
- **No advanced statistics before 2017-18.** Expected goals and progressive
  actions were never recorded for 2003-04, by anyone. The rating therefore uses
  what exists across the whole period.
- **Premier League only.** No Champions League, no internationals, no other
  league. A player whose best work happened elsewhere is invisible here.
- **Identity is probabilistic.** 96.8% of player-seasons resolve to a Wikidata
  entity; the remainder are listed in `vault/clean/unresolved.csv`.

Every measured gate result is recorded in [DEVIATIONS.md](DEVIATIONS.md),
including the ones that surprised me.

## Roadmap

| Phase | Adds |
|---|---|
| **1** | Premier League 2000-2025, one lens — **done** |
| 2 | All Big 5 leagues plus internationals, both metric tiers |
| 3 | Bayesian era model, four more lenses, composite index, Monte Carlo replay |
| 4 | Full visualization system, dashboard with live weight sliders |
| 5 | The complete book |

## Licence

None yet — all rights reserved. This will change before any release.
