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

"Must have twelve things" is read literally: a floor on every requirement
decides who qualifies, and only then are qualifiers ranked.

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

A percentile floor eliminates the same share on every column only when the
column has no large tie mass sitting exactly at the floor value; `<` is false
against a tie, so a floor landing inside one cuts nobody, which is what
`test_a_requirement_with_a_mass_at_the_floor_eliminates_nobody` in
`tests/test_gate.py` documents. Most Big-5 careers never play in Europe, so
this was worth checking rather than assuming. Measured directly on the
standardised profile the gate consumes (`vault/derive/ranking.parquet`'s
`continental` column, the same one `gate.failure_summary` reads): the
exact-zero mass is **0.00%** of the 5,508 careers, because the per-season
z-score is computed within each `(league, season)` group before the career is
pooled, and every group's zero-value players inherit that group's own mean and
spread, not a shared one. A raw zero stops being one shared number well before
the gate ever sees a `continental` column, so the 40th-percentile floor
(-0.344) sits cleanly above the population rather than inside a tied mass, and
`continental` eliminates 2,203 of 5,508 (39.996%, exactly the same share as
every other season-level requirement) genuinely, not by an artefact of ties.
`gate.failure_summary` counts each requirement's eliminations independently
per column rather than weighted by overlap with the other ten, so nine
identical counts at one gate percentile is the expected shape of that
function's output, not a sign every requirement failed the same players. See
CHANGELOG.md for the qualifier count and the reordered top ten.

### The tournament requirement measures nationality more than club selection does, and Copa America only shrinks that, it does not close it

`needs.tournament_value` scores World Cup, Euro and Copa America output with the
same rate-times-presence shape as `continental_value`, and it partly measures
**nationality**. A Welshman can reach two tournaments in a career; a Brazilian,
twelve. That gap has nothing to do with which of the two is the better player.
The rate-times-presence form limits the damage the same way it limits the
club-selection objection on `continental`: a player is judged on what he did
with the minutes he had, not punished twice for having few of them, and
presence saturates at `TOURNAMENT_FULL_RUN = 450` minutes so a deep run cannot
outscore a solid group stage on volume alone. It does not remove the bias.

Rejected: normalising by the national side's own qualification record (matches
played, or tournaments reached, by the country as a whole). That would have
made the requirement measure the team even more directly than it already does,
trading a player-level nationality bias for a team-level one, which is a worse
trade, not a fix.

Owner ruling 2026-08-15: Copa America joined the World Cup and the Euro,
reasoning that the Euro already covers European players and Copa America
covers South American ones. This is a genuine, partial mitigation, not a
resolution. South American players now have a second tournament, roughly every
two to four years since FBref's player-level coverage of the competition
begins in 2015, to be measured on. It leaves the underlying objection standing
for players from confederations with no tournament in scope: the Africa Cup of
Nations and the Asian Cup remain out (the owner's ruling scopes competitions
to UCL, the World Cup, the Euro and Copa America only, and nothing beyond
them), so an African or Asian great is still judged on the World Cup alone,
the same single quadrennial opportunity every player outside Europe and South
America gets. Adding a fourth and fifth confederation's tournament was not
part of this ruling and was not built.

Measured the same way `continental`'s zero mass was checked, because
`tournament` starts from an even higher raw-zero rate (a career only touches a
World Cup, a Euro or a Copa America in a minority of its seasons): the
standardised profile the gate consumes carries **0.00%** exact-zero mass on
`tournament` too, for the identical reason, the per-season z-score is computed
within each `(league, season)` group before the career is pooled, so a raw
zero stops being one shared number before the gate ever sees the column. The
40th-percentile floor eliminates 2,203 of 5,508 (39.996%), exactly the same
share as every other season-level requirement, genuinely rather than by a tied
mass at the floor. See CHANGELOG.md for the qualifier count and the top ten.

### A COVID-delayed tournament edition is mislabelled at the source, and this project's alignment inherits the mislabelling

FBref keeps the 2020 Euro and the 2020 Copa America under the season label
`"2020"` even though both were actually played in June-July 2021, because that
is the tournament's official branding, not its calendar. `align_tournament_seasons`
is a mechanical `year -> season` transform with no knowledge of that history, so
it places both editions in domestic season `"1920"` (2019-20), the season that
had just finished when the tournaments were *originally* scheduled, not `"2021"`
(2020-21), the season that had just finished when they were *actually* played
and the squads were actually picked. This is implemented exactly as the brief
specifies and was not changed, per this project's rule that a disagreement with
a given implementation is recorded, not silently routed around; the effect on
any one player's `tournament` value is a one-season misattribution, not a
wrong number, since the minutes and goals themselves are correct, only their
season label is arguably one year early.

### A per-season tournament fetch can double-count a COVID-delayed edition, and this is a real defect, fixed

The World Cup and the Euro are known to soccerdata without registration, but
querying them for a full 25-season span in one batched call raises: soccerdata
indexes them by the tournament's own calendar year, and any requested year
with no tournament is a hard `KeyError` on a `.loc` lookup with no partial
match. Fetching one project season at a time, converted to soccerdata's
calendar-year label, avoids that. The 2020 Euro and 2020 Copa America break
even this: because both are still labelled `"2020"` but were played in 2021,
a query for calendar year **"2021"** (from domestic season `"2021"`) matches
the *same* underlying page as a query for **"2020"** (from domestic season
`"1920"`), so both project-season iterations of the fetch loop pulled in an
identical copy of that edition's roster. `collapse_transfers` cannot tell an
exact duplicate from a genuine mid-season transfer and sums both, which
doubled every 2020-edition player's minutes, goals and assists (caught by a
sanity check: Euro "1920" carried a max of 1,436 minutes against a same-shape
single-fetch Euro edition's ceiling of 690, almost exactly double). Fixed by
deduplicating the raw fetch on `(league, season, team, player, born)`, the
same identity key `join_side_tables`'s own duplicate-key fix uses elsewhere in
this project (`fbref.py:307`), before it is ever written to
`tournament_raw.parquet`. Row count after dedup: 8,030 -> 7,307.

Rejected: discovering each tournament's actual valid season labels up front
(one extra soccerdata call per competition) and fetching each one exactly
once, which would prevent the duplicate fetch rather than clean it up after
the fact. Not built: it is a second reader abstraction for a defect a
one-line `drop_duplicates` already closes completely, and this project's own
run rules ask for the smallest fix that works where the plan leaves a gap
open, not the most architecturally satisfying one.

### `reliability` is completed matches, adjusted for position

Completed matches per appearance, minus the median of the player's own position.
It has been three definitions, and each replacement was measured rather than
argued.

Completed matches per *start* came first and measured being a forward. Benzema,
Agüero, Higuaín, Villa, Owen and Trezeguet all failed qualification on that
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

### `teamfit` is not the fifth lens

The lens spec named five: `peak5`, `career`, `per90`, `biggame` and `teamfit`.
Only four are built. `teamfit` would have ranked careers by `above_team`, the
same club-strength residual measured directly above and already shown to
correlate 0.996 with `scoring` on outfielders, because club strength explains
0.8% of who scores inside a league-season and the residual of something barely
explained is the thing back again. A lens built on it would not answer a new
question; it would restate `per90` or `career` under a different name while
looking, from the selector, like a fifth independent argument.

Rejected: building it anyway, against `above_team` or against a different
target. The requirement-level version of exactly this search already ran
(`creation` was the best alternative target found, at 1.1%) and found nothing
that survives being regressed on club strength. Re-running that search inside
a lens would not change the answer, only the label on the same restated
number.

Rejected: building `teamfit` against `above_team` for keepers only, where the
residual construction is real signal (45% of goals conceded). The lens set
ranks the outfield population; a lens that only ever has one entrant is not a
lens.

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
deleting Haaland, Mbappé and every short career from the table, answering a
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

### The Bayesian layer sits beside the point-estimate pipeline, not in place of it

`gambeta.bayes` is the hierarchical model the previous entry pointed to: each
player draws his level from a population distribution whose spread is
estimated from the data, so how far a short career is pulled toward the mean
is measured rather than set by `cfg.min_minutes`. It reads the same
`player_season_scored.parquet` the pipeline already writes and produces a
posterior, nothing downstream of `rank()` changes and no published number in
the book moves.

Rejected: making the posterior mean the published score. Replacing the
point estimate would invalidate every number already in the book at once, on
the strength of one new model that has not been through the same scrutiny
(the awards check, the permutation tests, the failure table) the rest of the
pipeline has. The two also answer slightly different questions: the pipeline's
score pools a career by minutes with a hard floor, the model's posterior mean
pools it through an estimated population spread with no floor at all, and
collapsing them into one number would hide that difference rather than state
it. Comparing the point-estimate top 50 (minutes-weighted mean of
`season_score` on qualifying seasons) against the same players' order under
the posterior mean, 20 of 50 move by more than 5 places, which is exactly the
scale of disagreement a reader should be able to see, not one that should be
silently resolved by picking a side.

`bayes` is optional (`pyproject.toml`'s `bayes` extra: `pymc`, `nutpie`,
`arviz`), and the rest of the suite passes with it uninstalled,
`tests/test_bayes.py` skipping via `pytest.importorskip("pymc")`.

### `arviz` is floored at 1.0, which raised the Python floor to 3.12

`bayes.player_effects` uses `az.hdi`'s 1.x-only `prob=` keyword and `ci_bound`
coordinate; unconstrained, the resolver on Python 3.11 picked 0.23, which
predates both and breaks it silently rather than raising. Flooring the extra
at `arviz>=1.0` fixes that, but `arviz>=1.0` itself only supports Python 3.12+,
which `uv lock` refuses to solve against the project's prior `>=3.11` floor.

Rejected: marker-gating `arviz` to `python_version >= '3.12'` and leaving the
`bayes` extra installable, but silently without `arviz`, on 3.11. That trades
one silent breakage (a stale API) for another (a missing import), and the dev
environment already assumed 3.12: `mypy` targets it and `.python-version`
pins it. `requires-python` is now `>=3.12`, matching what was already true in
practice.

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
