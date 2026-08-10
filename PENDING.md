# Pending work

What is left undone, why, and how to finish it. Everything here is additive: the
pipeline runs correctly without any of it.

The design principle that makes this safe: **nothing hard-codes a league count, a
league list, or the presence of any optional stat table.** The league-strength
bridge solves for whichever leagues it finds, missing side-table columns are
filled with nulls rather than raising, and requirements degrade to a coarser form
instead of breaking. Enforced by tests, not by hope — see
`tests/test_bridge.py::test_offsets_solve_for_only_the_leagues_present`.

---

# Part 1 — Data gaps

## 1.1 Ligue 1 — not collected

**Status:** no data. Four leagues are collected: Premier League, La Liga,
Serie A, Bundesliga.

**Why:** scraping is the bottleneck. FBref forces soccerdata to drive a real
browser per page, so 25 seasons of one stat table takes ~10 minutes and cannot
be parallelised on a 16 GB machine — two concurrent lanes drove free memory to
0.5 GB and slowed each fetch from ~10 to ~28 minutes.

```bash
python scripts/warm_cache.py "FRA-Ligue 1" standard,shooting,playing_time,keeper
# then add "FRA-Ligue 1" to ACTIVE_LEAGUES in gambeta/kit.py
uv run gambeta all --cache-only
```

**Cost:** ~40 minutes. **Effect:** French players enter the ranking, and *every
league offset is re-estimated* — Ligue 1 transfers add constraints that shift the
whole solution. Expect the existing ranking to move slightly. That is the bridge
working, not a bug.

## 1.2 La Liga goalkeepers — not collected

Spain has 8 of 25 keeper seasons, so it is treated as absent and Spanish keepers
are missing from the goalkeeper leaderboard. Outfield players are unaffected.

```bash
python scripts/warm_cache.py "ESP-La Liga" keeper
uv run gambeta all --cache-only
```

**Cost:** ~10 minutes.

## 1.3 The `misc` table — partially collected

Present for England, Spain and Italy; 5 of 25 seasons for Germany. It supplies
second yellows and fouls, so **discipline is currently reds and yellows only**,
and measured slightly inconsistently across leagues. That inconsistency is the
strongest reason to finish this.

```bash
python scripts/warm_cache.py "GER-Bundesliga" misc
uv run gambeta all --cache-only
```

**Cost:** ~10 minutes per league.

## 1.4 Identity resolution is below target

**96.8%** on the Premier League alone; **85.1%** across four leagues, with
**2,566 players unresolved** and listed in `vault/clean/unresolved.csv`.

Non-English names carry more diacritic and transliteration variance, and
Wikidata's FBref-ID coverage is thinner outside England. The Phase 1 spec set a
95% gate; four leagues miss it. Worth an hour reading `unresolved.csv` for
systematic patterns — a single normalisation rule may recover hundreds.

---

# Part 2 — Next steps from the original plan

The Phase 1 design spec set out five phases. Phases 1 and 2 are done. What
follows is what those specs promised and this codebase does not yet have.

## Phase 3 — Depth

### 3.1 The other four lenses *(spec §6.3)*

`gambeta/lens.py` contains **only `peak5`**. The spec defined five:

| Lens | Question it answers | Status |
|---|---|---|
| `peak5` | Best five consecutive seasons | **built** |
| `career` | Cumulative value across the whole career | missing |
| `per90` | Production per 90, above a minutes floor | missing |
| `biggame` | Knockout and high-stakes matches | missing — needs UCL data (4.1) |
| `teamfit` | Output relative to teammate quality | partly covered by the `above_team` requirement |

Each is a pure function `(player_seasons, cfg) -> DataFrame`. `peak5` is the
worked example to copy.

### 3.2 `blend.py` — the weight-tunable composite *(decision D2)*

The original definition promised **several named weight vectors** — "the volume
argument", "the efficiency argument", "the longevity argument" — so a reader
could see who wins under each.

`gate.qualify_and_rank` already accepts a `weights` dict; nothing calls it with
anything but equal weights, and nothing exposes it. The missing piece is a module
that names and stores weight vectors, plus dashboard sliders (4.2).

### 3.3 `bayes.py` — the hierarchical era model *(spec §6.2)*

Shrinkage is currently a fixed prior of 900 minutes. A hierarchical model would
**estimate the shrinkage strength from the data** and give proper uncertainty on
every player-season, instead of the current point estimates.

PyMC + `nutpie` on CPU — minutes, not hours, at this data size. The `bayes`
extra is already declared in `pyproject.toml` and never installed.

### 3.4 Monte Carlo career replay *(spec §6.5)*

Resample match outcomes to separate skill from luck: "run this career 10,000
times". This is the piece that would let the project say how much of a ranking
gap is real and how much is variance. `doubt.bootstrap` is the pattern to follow
and already dispatches to the GPU above a size threshold.

### 3.5 Permutation tests *(spec §6.5)*

For claims of the form "A is better than B", report a p-value. Currently the
project reports point scores with no significance testing at all, which is the
weakest part of its statistical story.

## Phase 4 — Presentation

### 4.1 Champions League and internationals *(decision D3)*

The original scope was Big 5 **plus UCL plus internationals**. Neither exists.

FBref's reader exposes **no Champions League at all** (`DEVIATIONS.md` #2), so
this needs a custom `league_dict.json` for soccerdata. `INT-World Cup` and
`INT-European Championship` *are* available and would be much easier — a
reasonable first step, and the only route to a `biggame` lens.

### 4.2 Dashboard weight sliders

The dashboard has filters, a distribution tab, a keeper board and a failure
tab — but the weights are fixed. Sliders wired to `qualify_and_rank(weights=…)`
are the single highest-value addition, because they turn a decreed answer into
one the reader can argue with numerically.

### 4.3 The advanced metric tier *(decision D1)*

xG, progressive passes and shot-creating actions exist from 2017-18. The two-tier
design always intended these as an **enrichment layer** shown alongside the
ranking without entering it. Nothing was built, and FBref's single-league reader
does not expose xG at all, so this needs a different source or the Big-5 combined
endpoint with its labelling repaired.

## Phase 5 — The book

### 5.1 Awards validation *(spec §10.6)*

**The strongest available defence of the methodology, and it needs no new
scraping.** Correlate the ranking against Ballon d'Or and UEFA Player of the Year
voting, both already in Wikidata. "Does this agree with contemporaneous expert
consensus, and where it disagrees, why?" is a far better argument than any
internal consistency check.

### 5.2 quartodoc API reference *(spec §11)*

Planned so library docs and teaching material would be one artifact. **Never
wired up** — `_quarto.yml` has no `quartodoc` block. The dependency is declared
in the `docs` group and unused.

### 5.3 More method chapters

Four notebooks exist. `tome/method-template.qmd` documents the six-part structure
for adding more: normalization and shrinkage, the bootstrap, the identity
crosswalk, and the gate calibration all deserve chapters.

---

# Part 3 — Open judgement calls

Not bugs. Decisions that need a person.

| Question | Current answer | Why it is arguable |
|---|---|---|
| How high should the gate be? | 40th percentile on all eleven | 239 of 4,424 qualify. At 50 the list tightens sharply; at 30 it loosens. There is no principled value. |
| How much should fouls count? | Reds + yellows, equal weight with everything else | Totti and Zlatan fail on discipline *alone*. Defensible, or an artefact of weighting aggression like unavailability. |
| Is `starts / appearances` right for reliability? | Yes, after the fix | Better than completed-matches-per-start, which measured being a forward. Still says nothing about missing matches through injury — that is `availability`'s job, and the two may overlap. |
| Should keepers and outfielders ever be compared? | No — two leaderboards | The honest choice. But the project's headline question implies one answer, and this declines to give one for keepers. |

---

# Part 4 — Infrastructure

| Item | Status |
|---|---|
| GitHub push | **blocked** — `gh auth login` never completed. All work is committed locally. |
| CI workflow | Written, **never executed** — it has never run against a real runner. |
| GitHub Pages deploy | Blocked on the same auth. |
| PyPI trusted publishing | Configured in the spec, never set up. Requires a licence decision first. |
| Licence | **None.** All rights reserved by default, which blocks any reuse. |
| Phase 2 git workflow | Phase 2 was committed **directly to `main`** rather than to a branch merged when green, contrary to the agreed workflow. History is clean; the process was not followed. |

---

# The limitation no amount of scraping fixes

**Outfield defenders cannot be measured defensively.** FBref records no
per-player defensive action before 2017-18 — no interceptions, no tackles, no
clearances — so two thirds of the window has nothing to measure a centre-back
with. Ligue 1 does not help. `misc` does not help.

The rating is therefore named for what it measures: **attacking contribution**.

Standardising within position would make this *worse*, not better: z-scoring
goals and assists among defenders finds the most **attacking** defender and
presents it as though it meant defensive quality. Deliberately not done — see
Phase 2 spec §8.

Fixing this properly needs event data (StatsBomb, Wyscout) and a possession-value
model such as VAEP. That is a different project, and an honest one to name rather
than to approximate badly.
