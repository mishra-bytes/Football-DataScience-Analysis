# Decisions

Why this project is built the way it is. Every entry states the alternative that
was rejected, because a decision with no discarded option is not a decision.

---

## Objective

Rank the best footballer of 2000-2025 with statistics that survive hostile
scrutiny from someone whose favourite loses, **and** be readable as a statistics
textbook while doing it. The two goals constrain each other productively:
teaching forces every method to be explainable, the ranking forces every method
to be correct, because a wrong answer is obvious to a fan.

Consequence: `gambeta` is a library, not a pile of notebook cells.

**Non-goals.** Match prediction, betting, tracking data, tactical analysis,
women's football, live updating, a general scraping framework.

---

## Tech stack

| Layer | Choice | Why not the obvious alternative |
|---|---|---|
| Language | Python 3.12 | — |
| Env | `uv` | Lockfile plus resolver speed; pip has neither |
| Frames | pandas + pyarrow | Parquet is the interchange format between every stage |
| Schemas | pandera | Validation at stage boundaries beats trusting a `.csv` |
| Scraping | soccerdata 1.9.1 | Already solves FBref; writing our own is a non-goal |
| Stats | numpy, scipy-free | Nothing needed yet exceeds numpy |
| GPU | cupy-cuda12x`[ctk]`, optional | Must degrade to numpy silently, and no GPU path ships without a benchmark |
| Pipeline | DVC | Stages the scrape → clean → derive DAG |
| Book | Quarto | Renders `.ipynb` directly, so notebooks stay the single source |
| Dashboard | Streamlit | Reads the committed sample; no server, no database |
| Lint / types | ruff, mypy `--strict` | — |

**Windows-native, no WSL2.** Parallel code needs `if __name__ == "__main__"`
guards because Windows uses `spawn`.

---

## Endpoints

| Source | Endpoint | Terms |
|---|---|---|
| FBref | via soccerdata; drives Chrome through seleniumbase | Bulk redistribution restricted — raw stays local, DVC `push: false` |
| Wikidata | `https://query.wikidata.org/sparql` | CC0 |
| ClubElo | via soccerdata | Free, non-commercial |

FBref requires a real browser: soccerdata drives undetected chromedriver past
Cloudflare. Chrome is therefore a system prerequisite for ingestion only —
everything downstream reads Parquet.

---

## The one workflow that matters

```
scrape ──▶ vault/raw ──▶ clean ──▶ vault/clean ──▶ rank ──▶ vault/derive ──▶ data/sample
 (network)   (cached)    (identity)  (validated)   (stats)    (outputs)      (committed)
```

**Only `scrape` touches the network.** Everything after it reads Parquet, so
iterating on the definition never re-scrapes. This is the single most important
structural decision in the repository and everything below serves it.

`uv run gambeta all --cache-only` runs the whole chain offline in ~5 minutes.

### Caching, and why it is granular

Both network sources cache **per unit of work**, not per run:

- FBref — one HTML file per (league, season, table). 634 files, 1.19 GB.
- Wikidata — one Parquet per birth year, keyed by a hash of the query text.

Rejected: caching the finished artifact only. Measured cost of that mistake —
when 2 of 41 birth-year cohorts failed, repairing them meant re-running all 41,
about 35 minutes for four minutes of real work. A changed query must still
invalidate everything, which is what the query hash is for: **a cached answer to
a different question is a wrong answer, not a saving.**

### Three ways to run it

| Workflow | Command | When |
|---|---|---|
| Offline | `gambeta all --cache-only` | Default. Iterating on the definition. |
| Repair | delete the stale artifact, `gambeta all --cache-only` | A source changed. Only uncached units refetch. |
| Cold | `scripts/warm_all.ps1` then `gambeta all --cache-only` | New machine. ~5 hours of scraping. |

Scraping is deliberately **sequential**. soccerdata spawns ~40 Chrome processes
per session; three concurrent leagues took a 16 GB machine from 15 GB free to
0.8 GB and slowed each fetch from 30 s to 250 s. One at a time is both safer and
faster.

---

## Method decisions

### Gate, then rank

"Must have eleven things" is read literally: a floor on every requirement decides
who qualifies, and only then are qualifiers ranked.

Rejected: a weighted average. It lets a player be genuinely poor at something the
definition calls mandatory and win on volume elsewhere. The gate is what stops
that, and it is why weights are safe to expose to a reader — **no weighting can
move the gate**, only the percentile can.

### The player is the unit, not the league

Each player-season is normalised inside its own league and season, then *all* of
a player's seasons are pooled regardless of where they were played.

Rejected: ranking within a league. It answers a less interesting question and
makes players who transferred impossible to evaluate.

### League strength from transfers

A player who changes league is the same footballer on both sides of the move, so
the change in his score measures the gap between those leagues. Solved across
thousands of moves, one league pinned at zero.

Rejected: money, reputation, coefficient tables. Nothing about finance is in the
model, which is what makes it evidence when the estimates reproduce the Premier
League's post-2005 financial ascent unprompted.

### Identity: probabilistic, and never silently dropped

FBref exposes no player ID at season level, so identity is `(normalised name,
birth year)` matched against Wikidata, in tiers, with two hard rules: **the birth
year never relaxes**, and **ambiguity is a non-match**.

Rejected: anchoring the candidate pool on Wikidata's FBref-ID property. It looked
authoritative and cost 56% of the candidates, because the matcher never joined on
that ID anyway.

A player who cannot be matched is reported in `unresolved.csv`, never dropped.
Dropping raises no error and quietly deletes a career.

### Two leaderboards, not one

Keepers are ranked on their own eight requirements. Save percentage and goals per
90 are not comparable quantities and pretending otherwise would be dishonest —
even though the project's headline question implies a single answer.

### Uncertainty is reported, not hidden

Bootstrap intervals for precision, permutation tests for "A is better than B".
The permutation test assumes no distribution, because a career is five to
nineteen numbers and a t-test would assert a shape the data does not have.
Where the honest answer is "these two are not separable", that is printed.

### One outside opinion

Ballon d'Or and world-player voting is the only external check. It is not ground
truth — it rewards teammates' trophies and leans toward forwards — which is
exactly why it is compared against rather than fitted to. The output that matters
is *where it disagrees and why*.

---

## Standards

- **Conventional Commits.** Never a `Co-Authored-By` or AI attribution trailer.
- **Branch, then merge when green.** Lint, types, tests and book build all pass.
- **Deviations get written down.** When the spec cannot be followed, implement
  the closest working alternative and append to `DEVIATIONS.md` with what, why
  and impact.
- **No GPU code without a benchmark.** Spec §7.
- **`data/sample/` holds derived aggregates only**, ≤5 MB, enforced by
  pre-commit. Raw scrapes are never redistributed.
- **Notebooks are committed stripped** (nbstripout) and executed locally before
  rendering.
- **Every stochastic routine uses `Config.seed`.**

## The bug class this project keeps finding

Four defects so far — `consistency` measured as variance, `reliability` measured
as being a forward, ages attached by position, award winners not filtered to
men's football — shared one property: **plausible output, no exception, every
test passing.** None was caught by the test suite. All four were caught by
reading the answer and asking whether it made sense.

That is why the failure table, `unresolved.csv` and the awards check are
first-class outputs rather than diagnostics. They exist to make wrong answers
visible.
