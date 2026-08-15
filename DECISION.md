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
| Language | Python 3.12 | - |
| Env | `uv` | Lockfile plus resolver speed; pip has neither |
| Frames | pandas + pyarrow | Parquet is the interchange format between every stage |
| Schemas | pandera | Validation at stage boundaries beats trusting a `.csv` |
| Scraping | soccerdata 1.9.1 | Already solves FBref; writing our own is a non-goal |
| Stats | numpy, scipy-free | Nothing needed yet exceeds numpy |
| GPU | cupy-cuda12x`[ctk]`, optional | Must degrade to numpy silently, and no GPU path ships without a benchmark |
| Pipeline | DVC | Stages the scrape → clean → derive DAG |
| Book | Quarto | Renders `.ipynb` directly, so notebooks stay the single source |
| Dashboard | Streamlit | Reads the committed sample; no server, no database |
| Lint / types | ruff, mypy `--strict` | - |

**Windows-native, no WSL2.** Parallel code needs `if __name__ == "__main__"`
guards because Windows uses `spawn`.

---

## Endpoints

| Source | Endpoint | Terms |
|---|---|---|
| FBref | via soccerdata; drives Chrome through seleniumbase | Bulk redistribution restricted, raw stays local, DVC `push: false` |
| Wikidata | `https://query.wikidata.org/sparql` | CC0 |
| ClubElo | via soccerdata | Free, non-commercial |

FBref requires a real browser: soccerdata drives undetected chromedriver past
Cloudflare. Chrome is therefore a system prerequisite for ingestion only,
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

- FBref, one HTML file per (league, season, table). 634 files, 1.19 GB.
- Wikidata, one Parquet per birth year, keyed by a hash of the query text.

Rejected: caching the finished artifact only. The cost of that mistake was
measured. When 2 of 41 birth-year cohorts failed, repairing them meant re-running
all 41: about 35 minutes for four minutes of real work. A changed query must still
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

"Must have ten things" is read literally: a floor on every requirement decides
who qualifies, and only then are qualifiers ranked.

Rejected: a weighted average. It lets a player be genuinely poor at something the
definition calls mandatory and win on volume elsewhere. The gate is what stops
that, and it is why weights are safe to expose to a reader, **no weighting can
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

### The UCL match rate is judged within the Big-5 population, not overall

Champions League player-seasons match a domestic `player_id` at 75.352% overall,
but at 99.32% among rows whose club also appears in the Big-5 domestic data, and
43.66% among rows whose club never does (Shakhtar Donetsk, Dynamo Kyiv, Porto,
Benfica, Celtic and 130-odd others across all 25 seasons). The ranked population
is Big-5 only, so a UCL row for a player who never played there is expected not
to match, and is dropped at the join by design rather than by failure. 99.32% is
the number that measures whether the join itself works, and it was accepted as
such.

Rejected: expanding `kit.ACTIVE_LEAGUES` to cover Porto/Shakhtar-class clubs so
their players would resolve too. That turns a UCL side-column task into a second
domestic scrape, seasons deep, for leagues the project never set out to rank.

Rejected: loosening `whois.resolve`'s tiers to force a higher match rate. The
unmatched rows outside the Big-5 population are not spelling variants of a name
already in the crosswalk, they are different people who never played in a
tracked league, so a looser tier would manufacture false identities across the
whole project to paper over rows that were never supposed to match.

### Absence from Europe scores zero, not missing

`needs.continental_value` scores European club output (currently the Champions
League) as a per-90 rate scaled by presence, and a player who never appeared in
one gets zero on it, not a null. The ruling: the definition says the best
footballer plays the top competitions, so never appearing in one is a low score
rather than an unknown.

The honest objection, recorded because it is real: this requirement partly
measures club selection. Totti at Roma and Messi at Barcelona did not face the
same opportunity to play in Europe, and the requirement cannot separate "never
good enough" from "never given the chance." Two things limit the damage rather
than remove it. The rate is per 90, so a player is judged on what he did with
the minutes he had, not punished twice for having few of them. The presence
term (`CONTINENTAL_FULL_SEASON = 900` minutes, ten matches) saturates at a
group-stage-sized campaign, so a deep cup run cannot outscore a solid group
stage on volume alone, which keeps the requirement from rewarding the team's
achievement over the player's.

Rejected: excluding players with no European minutes from the ranked
population. That does not remove the club-selection bias, it hides it by
shrinking who gets judged at all, and it treats this requirement differently
from every other one, where a player who does not do something scores zero
rather than being dropped.

Rejected: treating a missing European record as null and imputing it (a league
mean, a position mean, or similar). A null would be filled by something
downstream anyway, filled without anybody having decided what it meant, and an
imputed value for "never played in Europe" is not a defensible estimate of what
that player would have done there.

Measured effect: at the 40th-percentile gate, `continental` eliminates 2,203 of
5,508, the same share as every other season-level requirement, which is what a
percentile floor does by construction. See CHANGELOG.md for the qualifier count
and the reordered top ten.

### `reliability` is completed matches, adjusted for position

Completed matches per appearance, minus the median of the player's own position.
It has been three definitions, and each replacement was measured rather than
argued.

Completed matches per *start* came first and measured being a forward. Benzema,
Aguero, Higuain, Villa, Owen and Trezeguet all failed qualification on that
requirement alone, because strikers get substituted.

Starts per appearance replaced it and fixed the role bias by discarding the
information. A quarter of player-seasons scored exactly 1.000, so a squad player
with twelve starts was indistinguishable from a captain with thirty-eight.

The current form was chosen against four faults at once: no ceiling (was 24.6%),
a positional gap of 0.07 (was 0.25), elite players standing 1.85 standard
deviations clear (was 0.58), and overlap with `availability` down to 0.55 (was
0.72). Completed matches per start, the original, scores 0.05 on that third
measure, which is the arithmetic confirming why it was scrapped.

Rejected: taking the positional median over every player rather than the ranked
ones. It gives a steadier baseline, measurably, but a thirty-minute substitute
completes nothing whatever his position, so those rows drag every median toward
zero and leave the positional gap at 0.23. Rejected too: a median per
league-season-position, which centres correctly but is noisy at that cell size.
One median per position, pooled across leagues and eras, keeps the correction
and recovers the stability.

Phase 2 §8 rejected standardising within position. This is not that: §8 forbids
z-scoring **output** by position, and this subtracts a median from a **usage**
ratio with no rescaling, so it cannot manufacture a quality claim.

### A requirement has to measure something the others do not

`above_team` was the residual of a player's output after regressing on his club's
ClubElo rating. Measured against the other requirements it correlated 0.996 with
`scoring`, because club strength explains 0.8% of who scores inside a
league-season, and the residual of something barely explained is the thing back
again.

Dropped from the outfield list on 2026-08-12, taking it from eleven requirements
to ten. Every composite had been counting one quality twice.

Rejected: rebuilding it against a different target. Team goals, teammate output
and every other requirement were measured, and the best of them was `creation` at
1.1%. Attacking output is individual, and no club-level baseline predicts it.

**Kept for keepers**, where the same construction explains 45% of goals conceded.
A keeper's goals-against is mostly his defence; the residual is the part that is
his.

### Two leaderboards, not one

Keepers are ranked on their own eight requirements. Save percentage and goals per
90 are not comparable quantities and pretending otherwise would be dishonest,
even though the project's headline question implies a single answer.

### Uncertainty is reported, not hidden

Bootstrap intervals for precision, permutation tests for "A is better than B".
The permutation test assumes no distribution, because a career is five to
nineteen numbers and a t-test would assert a shape the data does not have.
Where the honest answer is "these two are not separable", that is printed.

### BCa intervals, not a higher `min_seasons` floor

The percentile interval assumes the bootstrap distribution is centred on the
truth and equally spread either side. A three-season career satisfies neither:
the sample mean is a biased estimate of the level, and season scores are
right-skewed, so the interval sits too low and too narrow. Measured on this
project's own data it covers about 74% of the time against a nominal 95%, and
`min_seasons = 3` is exactly the floor that puts those careers into the
published table. `doubt.bca` corrects both faults with a bias term and an
acceleration term read off the same jackknife and bootstrap resamples, no
extra sampling needed, and no scipy dependency: `statistics.NormalDist`
already supplies the normal CDF and its inverse.

Rejected: raising `min_seasons` from 3 to 5. It would have fixed coverage by
deleting Haaland, Mbappe and every short career from the table, answering a
coverage problem by shrinking the question rather than answering it.

### One outside opinion

Ballon d'Or and world-player voting is the only external check. It is not ground
truth, because it rewards teammates' trophies and leans toward forwards, and
that is exactly why it is compared against rather than fitted to. The output that matters
is *where it disagrees and why*.

---

## Standards

- **Conventional Commits.** Never a `Co-Authored-By` or AI attribution trailer.
- **Branch, then merge when green.** Lint, types, tests and book build all pass.
- **Deviations get written down.** When the spec cannot be followed, implement
  the closest working alternative and append to `DEVIATIONS.md` with what, why
  and impact.
- **No GPU code without a benchmark.** Spec §7.
- **No data is committed at all.** `data/sample/` holds the derived aggregates
  every chapter reads, and it is gitignored along with `vault/`.

  Changed on 2026-08-12. It used to be committed on the reasoning that a reader
  should be able to re-run everything from a fresh clone, which is a real
  benefit and was traded away deliberately.

  What replaces it: **the notebooks carry their outputs**, so every number,
  table and figure is visible to a reader who never holds the data. What is
  lost: re-running the book locally needs a copy of `data/sample`, which is
  published separately if at all.

  Rejected: committing a smaller sample. A subset produces different z-scores,
  different league offsets and a different ranking, so the book would show
  numbers that no full run reproduces, which is worse than showing numbers a
  reader cannot recompute.
- **Notebooks are committed with their outputs**, executed against
  `data/sample/` before every commit.

  Reversed on 2026-08-11. They were committed stripped, via an nbstripout
  pre-commit hook, on the reasoning that outputs make diffs unreadable and bloat
  the repository. Both are true and neither turned out to matter: the whole set
  costs 623 KB and six images, and the diffs that matter are in the prose and the
  library rather than in a table of numbers.

  What decided it is that the notebooks are the blog. A stripped notebook renders
  on GitHub as code with no answers, so the reader has to install Chrome, sync a
  lockfile and run a pipeline before seeing a single number. The rendered book was
  supposed to cover that, and it does, but only for whoever builds it.

  Rejected: committing outputs for the narrative chapters only. The split would
  need explaining every time somebody added a chapter, and a rule nobody can
  state from memory is a rule that decays.
- **Every stochastic routine uses `Config.seed`.**

### Short seasons are weighted, not shrunk

A career is pooled with each season weighted by its minutes, and seasons below
`min_minutes` are excluded outright. The season's own score is never pulled
toward the mean.

Reversed on 2026-08-12, in the sense that the opposite was documented and
taught for months without ever being true. `level.shrink` implemented
empirical-Bayes shrinkage at a 900-minute prior, `Config.prior_minutes` carried
it, `params.yaml` declared it to DVC, and the era chapter taught it. Nothing in
the pipeline ever called it. Sweeping the prior from zero to ten thousand
minutes produced identical rankings, which is how it surfaced.

Rejected: wiring the shrinkage in to match the documentation. Minutes-weighted
pooling is already a correction in the same direction, and applying both would
discount a short season twice, once in its value and again in its weight.

The cost of the choice is stated rather than hidden. Weighting stops a short
season dominating a career; it does not stop one being wrong. And `consistency`
takes an unweighted twentieth percentile, so a 900-minute season gets a full
vote when a career's floor is decided. Closing that needs the hierarchical model
in `PENDING.md`, not a better constant.

## The bug class this project keeps finding

Six defects so far. `consistency` measured as variance. `reliability` measured
being a forward. Ages attached by row position. Award winners not filtered to
men's football. A side-table join key that was not unique, which fabricated a
player with 19,288 minutes. A share of team minutes summed across clubs, which
gave one player 296% of them.

All six shared one property: **plausible output, no exception, every test
passing.** Not one was caught by the test suite. The first four were caught by
reading the answer and asking whether it made sense; the last two by asserting
something the data had to satisfy and watching it raise.

That is why the failure table, `unresolved.csv` and the awards check are
first-class outputs rather than diagnostics. They exist to make wrong answers
visible.
