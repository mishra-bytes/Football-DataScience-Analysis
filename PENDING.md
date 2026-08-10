# Pending work

What was deliberately left undone, why, and exactly how to finish it. Everything
here is additive: the pipeline runs correctly without any of it, and each item
slots in without code changes unless stated otherwise.

The design principle that makes this safe: **nothing hard-codes a league count, a
league list, or the presence of any optional stat table.** The league-strength
bridge solves for whichever leagues it finds in the data, missing side-table
columns are filled with nulls rather than raising, and requirements degrade to a
coarser form instead of breaking. This is enforced by tests, not by hope — see
`tests/test_bridge.py::test_offsets_solve_for_only_the_leagues_present` and
`tests/test_needs.py`.

---

## 1. Ligue 1 — not collected

**Status:** no data at all. Four leagues are collected: Premier League, La Liga,
Serie A, Bundesliga.

**Why:** scraping is the bottleneck of this project. FBref forces soccerdata to
drive a real browser per page, so 25 seasons of one stat table takes ~10 minutes
and cannot safely be parallelised on a 16 GB machine — two concurrent lanes drove
free memory to 0.5 GB and slowed each fetch from ~10 min to ~28 min. Ligue 1 was
dropped to get the rest of the project moving.

**To add it:**

```bash
python scripts/warm_cache.py "FRA-Ligue 1" standard,shooting,playing_time,keeper
```

Then add `"FRA-Ligue 1"` to `ACTIVE_LEAGUES` in `gambeta/kit.py` and re-run:

```bash
uv run gambeta all
```

**Cost:** ~40 minutes of scraping, single lane.

**What changes when it lands:** French players enter the ranking; the league
bridge gains a fifth node and every offset is re-estimated, because Ligue 1
transfers add constraints that shift the whole solution slightly. Expect the
existing rankings to move a little — that is the bridge working, not a bug.

## 2. La Liga goalkeeper table — not collected

**Status:** Spain has `standard`, `shooting`, `playing_time` and `misc`, but not
`keeper`.

**Effect:** Spanish goalkeepers are absent from the goalkeeper leaderboard.
Outfield players are unaffected.

**To add it:**

```bash
python scripts/warm_cache.py "ESP-La Liga" keeper
uv run gambeta all
```

**Cost:** ~10 minutes.

## 3. The `misc` stat table — partially collected

**Status:** collected for the Premier League, La Liga and Serie A. Not collected
for the Bundesliga (or Ligue 1, which has nothing at all).

**Effect:** `misc` supplies second yellow cards and fouls. Without it the
**discipline** requirement is computed from red and yellow cards alone. The
requirement still works and still discriminates; it is simply coarser. Because
the table is present for three leagues and absent for one, discipline is
currently measured slightly inconsistently across leagues — the strongest reason
to finish this item.

**To add it:**

```bash
python scripts/warm_cache.py "GER-Bundesliga" misc
uv run gambeta all
```

**Cost:** ~10 minutes per league.

---

## Deferred by design, not by time

These were scoped out in the design specs and are genuine future phases rather
than loose ends.

| Item | Where it was decided | Note |
|---|---|---|
| Bayesian hierarchical era model | Phase 1 spec §6.2 | Would replace fixed-strength shrinkage with shrinkage estimated from the data. PyMC + nutpie, CPU. |
| The other four lenses and the weight-tunable composite | Phase 1 spec D2 | `peak5` still exists and is tested; `career`, `per90`, `biggame` and `teamfit` were never built. |
| Monte Carlo career replay | Phase 1 spec §6.5 | Separating skill from luck. |
| Champions League and international football | Phase 2 spec §6 | FBref's reader exposes no Champions League at all (`DEVIATIONS.md` #2). Would need a custom `league_dict.json`. |
| Awards correlation check | Phase 1 spec §10.6 | Validate the ranking against Ballon d'Or and UEFA Player of the Year voting. The single strongest available defence of the methodology, and it needs no new scraping — Wikidata has the awards. |
| StatsBomb event data and VAEP | Phase 1 brainstorm | Rejected as out of scope; would finally allow defenders to be measured. |
| GitHub push and Pages deployment | Phase 1 report | Blocked on `gh auth login`, which has never completed. Everything is committed locally. |

## The limitation that no amount of scraping fixes

**Outfield defenders still cannot be measured defensively.** FBref records no
per-player defensive action before 2017-18 — no interceptions, no tackles, no
clearances — so two thirds of the window has nothing to measure a centre-back
with. Adding Ligue 1 does not help. Adding `misc` does not help.

The rating is therefore named for what it measures: **attacking contribution**.
Standardising within position would make this worse rather than better, because
z-scoring goals and assists among defenders finds the most *attacking* defender
and presents it as though it meant defensive quality. That is deliberately not
done. See Phase 2 spec §8.
