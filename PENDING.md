# Pending work

What is left undone, why, and how to finish it. Everything here is additive: the
pipeline runs correctly without any of it.

The design principle that makes this safe: **nothing hard-codes a league count, a
league list, or the presence of any optional stat table.** The league-strength
bridge solves for whichever leagues it finds, missing side-table columns are
filled with nulls rather than raising, and requirements degrade to a coarser form
instead of breaking. Enforced by tests, not by hope, see
`tests/test_bridge.py::test_offsets_solve_for_only_the_leagues_present`.

---

# Part 1, Data gaps

## 1.1 to 1.3 Closed on 2026-08-11

Every FBref table the project reads is now complete: **5 leagues × 5 tables ×
25 seasons = 625 pages**, no partial table anywhere.

| Was missing | Now |
|---|---|
| Ligue 1, no data at all | all five tables, 25 seasons |
| La Liga goalkeepers, 8 of 25 seasons | 25 of 25 |
| `misc` for Bundesliga, 5 of 25 seasons | 25 of 25, and Ligue 1 too |

Two consequences worth stating, because both moved the answer:

- **Discipline is no longer coarse.** Second yellows and fouls are present for
  every league-season, so the requirement is measured the same way everywhere
  instead of degrading to reds-and-yellows where `misc` was absent.
- **Every league offset was re-estimated.** Ligue 1 transfers add constraints
  that shift the whole solution, exactly as predicted. England stays pinned at
  0; Spain moved −0.143 → −0.163, Italy −0.212 → −0.213, Germany −0.219 →
  −0.227, and France entered at **−0.300**, the weakest of the five. The
  ranking moved with it: Mbappé enters at 3rd, Messi's career becomes 18
  seasons rather than 16, and the Spanish keepers turn the goalkeeper board
  over almost completely.

  Those offsets moved again on 2026-08-11 when the data-integrity fixes
  landed (`DEVIATIONS.md` #7 to #9). Spain is now −0.180, Italy −0.243,
  Germany −0.261 and France −0.359. The figures above are kept as the
  record of what Ligue 1 alone did.

  Part of that shift was not Ligue 1 at all. Fixing the age misalignment
  (`DEVIATIONS.md`, 2026-08-11) moved every offset again, because age is a
  control in the transfer regression and 94% of rows carried the wrong one.

Scrape cost, measured: **95 minutes** for the 162 missing pages, sequential, one
browser session per table. The pipeline itself then runs offline in ~5 minutes.

## 1.4 Identity resolution, 93.8%, against a 95% target

**1,240 players unresolved**, listed in `vault/clean/unresolved.csv`. Up from
83.9%; the remaining 1.2 points are the hard tail.

The original diagnosis was wrong and worth recording. This looked like a name
normalisation problem, and it was mostly a **query** problem: the crosswalk
selected people carrying Wikidata's FBref-ID property, which the matcher has
never joined on, and that alone discarded more than half the candidate pool.
Occupation is the correct anchor. Tiered name matching added the rest.

What is left is genuinely hard rather than merely unfinished:

- **Transliteration.** `Serhiy` against `Serhii`, `Alexander` against
  `Aliaksandr`. No fold gets these; it needs a phonetic or edit-distance tier,
  and every loosening risks a wrong match, which is worse than a missing one.
- **Non-Latin labels.** Modrić's only non-English Wikidata label is Cyrillic and
  cannot be folded onto FBref's Latin spelling. He resolves via the crosswalk's
  other rows, but the general case does not.
- **Players simply absent from Wikidata.** No amount of matching invents them.

Diminishing returns from here. The awards check is now the better instrument for
catching identity failures that matter, because it names them: it caught
Cristiano Ronaldo being unresolved within minutes of first running.

---

# Part 2, Next steps from the original plan

The Phase 1 design spec set out five phases. Phases 1 and 2 are done. What
follows is what those specs promised and this codebase does not yet have.

## Phase 3, Depth

### 3.1 The other four lenses *(spec §6.3)*

`gambeta/lens.py` contains **only `peak5`**. The spec defined five:

| Lens | Question it answers | Status |
|---|---|---|
| `peak5` | Best five consecutive seasons | **built** |
| `career` | Cumulative value across the whole career | missing |
| `per90` | Production per 90, above a minutes floor | missing |
| `biggame` | Knockout and high-stakes matches | missing, needs UCL data (4.1) |
| `teamfit` | Output relative to teammate quality | partly covered by the `above_team` requirement |

Each is a pure function `(player_seasons, cfg) -> DataFrame`. `peak5` is the
worked example to copy.

### 3.2 ~~`blend.py` (the weight-tunable composite~~) **done, 2026-08-11**

Six named vectors live in `needs.ARGUMENTS`, exposed through the dashboard. Not
a `blend.py` module: a module holding one dict earns nothing, and weights belong
beside the requirements they weight.

The result was worth having. **Messi tops every one of the six arguments**,
volume, efficiency, longevity, team-carrying, professionalism and equal weight.
The sliders were built expecting some weighting to dethrone him; none does, and
that is a stronger claim than the headline ranking makes.

### 3.3 `bayes.py`, the hierarchical era model *(spec §6.2)*

There is no shrinkage in the pipeline at all: careers are pooled weighted by
minutes and short seasons are excluded by a hard floor. A hierarchical model would
**estimate the shrinkage strength from the data** and give proper uncertainty on
every player-season, instead of the current point estimates.

PyMC + `nutpie` on CPU, minutes, not hours, at this data size. The `bayes`
extra is already declared in `pyproject.toml` and never installed.

### 3.4 Monte Carlo career replay *(spec §6.5)*

Resample match outcomes to separate skill from luck: "run this career 10,000
times". This is the piece that would let the project say how much of a ranking
gap is real and how much is variance. `doubt.bootstrap` is the pattern to follow
and already dispatches to the GPU above a size threshold.

### 3.5 ~~Permutation tests~~, **done, 2026-08-11**

`doubt.permutation_test`, with an "A vs B" dashboard tab and notebook 07.

The finding is uncomfortable and belongs in the open: **only 1 of 28 pairwise
comparisons among the top eight reach p < 0.05 two-sided**, and none survives a
Bonferroni correction. The ranking's ordering is far weaker evidence than a
sorted table implies.

Still open, and now the most defensible next step for uncertainty: **BCa
intervals**. The percentile bootstrap covers 74% at three seasons against a
nominal 95%, and `min_seasons = 3` lets those careers into the published table.

## Phase 4, Presentation

### 4.1 Champions League and internationals *(decision D3)*

The original scope was Big 5 **plus UCL plus internationals**. The Big 5 is now
complete; neither of the other two exists.

FBref's reader exposes **no Champions League at all** (`DEVIATIONS.md` #2), so
this needs a custom `league_dict.json` for soccerdata. `INT-World Cup` and
`INT-European Championship` *are* available and would be much easier, a
reasonable first step, and the only route to a `biggame` lens.

### 4.2 ~~Dashboard weight sliders~~, **done, 2026-08-11**

An argument selector, eleven weight sliders, a gate-percentile slider and an
"A vs B" significance tab. The page says so when the reader's argument changes
who comes first.

The gate slider is separate on purpose, and the separation is the teaching
point: **weights reorder qualifiers and cannot requalify anybody.** Only the
percentile moves the gate.

### 4.3 The advanced metric tier *(decision D1)*

xG, progressive passes and shot-creating actions exist from 2017-18. The two-tier
design always intended these as an **enrichment layer** shown alongside the
ranking without entering it. Nothing was built, and FBref's single-league reader
does not expose xG at all, so this needs a different source or the Big-5 combined
endpoint with its labelling repaired.

## Phase 5, The book

### 5.1 ~~Awards validation~~, **done, 2026-08-11**

`gambeta.verdict`, against five award bodies. Of 18 men's winners in the window,
16 are in our data, 10 clear all ten requirements, and the median winner ranks
60th of 5,508.

The disagreements are the output worth reading:

| Winner | Our rank | Why |
|---|---|---|
| Zidane | 104 | qualified |
| Nedvěd, Figo, Rodri | 704-1171 | failed **discipline** alone |
| Van Dijk | 1036 | failed creation |
| **Cannavaro** | **2707** | failed 8 of 11 |

Cannavaro is the honest headline: a centre-back won the 2006 Ballon d'Or and this
definition ranks him below two and a half thousand players. That is the
attacking-contribution limitation stated as a number instead of a caveat. Three
winners failing on discipline alone also sharpens the open question in Part 3
about whether fouls are weighted like unavailability.

It earned its keep immediately by catching two bugs in the checker itself,
Cristiano Ronaldo reported as "never seen" because a birth cohort failed to
fetch, and three women's winners counted as data we were missing.

### 5.2 quartodoc API reference *(spec §11)*

Planned so library docs and teaching material would be one artifact. **Never
wired up**, `_quarto.yml` has no `quartodoc` block. The dependency is declared
in the `docs` group and unused.

### 5.3 More method chapters, **four added, 2026-08-11**

Eight notebooks now. Added: normalisation and shrinkage (05), the bootstrap (06),
testing without a distribution (07), selection bias and Simpson's paradox (08).

Still unwritten, and still deserving chapters: **the identity crosswalk**, now
much the richer story, since the fix was a query bug wearing a normalisation
costume, and **gate calibration**, which has no principled answer and would be
an honest chapter about a judgement call rather than a method.

---

# Part 3, Open judgement calls

Not bugs. Decisions that need a person.

| Question | Current answer | Why it is arguable |
|---|---|---|
| How high should the gate be? | 40th percentile on all ten | 343 of 5,508 qualify. At 50 only 132 do; at 30, 824. There is no principled value, the dashboard slider now lets a reader pick their own and watch the field change. |
| How much should fouls count? | Reds + second yellows + fouls per 90, equal weight with everything else | Totti, Zlatan and Neymar fail on discipline *alone*. Defensible, or an artefact of weighting aggression like unavailability. Now that `misc` is complete this requirement bites harder than it did. |
| Is `starts / appearances` right for reliability? | Yes, after the fix | Better than completed-matches-per-start, which measured being a forward. Still says nothing about missing matches through injury, that is `availability`'s job, and the two may overlap. |
| Should keepers and outfielders ever be compared? | No, two leaderboards | The honest choice. But the project's headline question implies one answer, and this declines to give one for keepers. |

---

# Part 4, Infrastructure

| Item | Status |
|---|---|
| GitHub push | **blocked**, `gh auth login` never completed. All work is committed locally. |
| CI workflow | Written, **never executed**, it has never run against a real runner. |
| GitHub Pages deploy | Blocked on the same auth. |
| PyPI trusted publishing | Configured in the spec, never set up. Requires a licence decision first. |
| Licence | **None.** All rights reserved by default, which blocks any reuse. |
| Phase 2 git workflow | Phase 2 was committed **directly to `main`** rather than to a branch merged when green, contrary to the agreed workflow. History is clean; the process was not followed. |

---

# The limitation no amount of scraping fixes

**Outfield defenders cannot be measured defensively.** FBref records no
per-player defensive action before 2017-18, no interceptions, no tackles, no
clearances, so two thirds of the window has nothing to measure a centre-back
with. Ligue 1 did not help. `misc` did not help. Both are now collected in full,
and on the complete Big 5 the top 50 qualifiers are **96% forwards, 4%
midfielders, 0% defenders**, defenders are 41% of the ranked population and the
best of them sits 122nd.

The rating is therefore named for what it measures: **attacking contribution**.

Standardising within position would make this *worse*, not better: z-scoring
goals and assists among defenders finds the most **attacking** defender and
presents it as though it meant defensive quality. Deliberately not done, see
Phase 2 spec §8.

Fixing this properly needs event data (StatsBomb, Wyscout) and a possession-value
model such as VAEP. That is a different project, and an honest one to name rather
than to approximate badly.
