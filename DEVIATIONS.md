# Deviations from the design spec

Each entry records a point where implementation could not follow
`docs/superpowers/specs/2026-08-10-gambeta-design.md`, what was done instead, and the impact.

## 1. Identity resolution does not use an FBref-ID key join

**Spec:** §8.2 ("Join FBref data on `fbref_id`) an exact key join, not fuzzy matching."

**Reality:** `FBref.read_player_season_stats()` returns the player *name* as part of the row
index. No FBref player ID is exposed by any season-level method in soccerdata 1.9.1.

**Substitute:** Match on `(normalized_name, born)` and enrich with a Wikidata QID where both the
normalized name and the birth year agree.

**Impact:** Identity is probabilistic rather than exact. Measured on a four-season sample of
1,859 distinct players, only 3 names collided, and all 3 were separated by birth year.
Unresolved players are written to `vault/clean/unresolved.csv` and reported, never dropped.

## 2. No Champions League data available *(superseded 2026-08-12)*

**Spec:** D3, competitions are "Big 5 domestic leagues + UCL + internationals".

**Reality:** `FBref.available_leagues()` returns no Champions League entry. Available leagues are
the Big 5, `Big 5 European Leagues Combined`, `INT-World Cup`, `INT-European Championship`, and
`INT-Women's World Cup`.

**Substitute:** None needed, UCL is outside Phase 1 scope regardless.

**Impact:** Phase 2 will need a custom `league_dict.json` for soccerdata to reach UCL data, or
the `biggame` lens must be restricted to international tournaments. Flagged now so Phase 2
planning accounts for it.

**Superseded, 2026-08-12.** The diagnosis read "no Champions League entry" as "no Champions
League data", and that was the wrong conclusion from a true observation. `available_leagues()`
only lists competitions soccerdata already knows about; it says nothing about what FBref itself
serves. The Champions League is one entry in soccerdata's `league_dict.json` away, and the entry
has to name the competition exactly as FBref's own index does, **"UEFA Champions League"**, not
"Champions League": the wrong name returns an empty frame rather than raising, which is what kept
this looking unavailable for longer than it was. `register_ucl()` (`gambeta/scouts/fbref.py`)
writes that entry idempotently. UCL is now ingested as columns on a domestic player-season, never
as rows in the ranked population, see `DECISION.md` and `PENDING.md` §4.1.

## 3. CuPy needs the `[ctk]` extra on a machine without a CUDA toolkit

**Spec:** §7, `cupy-cuda12x` as the GPU optional extra.

**Reality:** Plain `cupy-cuda12x` allocates and reduces on the GPU fine, but
`cupy.random` JIT-compiles kernels through nvrtc and fails with *"Failed to find CUDA headers"*
on a machine with only an NVIDIA driver and no CUDA toolkit.

**Substitute:** The extra is declared as `cupy-cuda12x[ctk]`, which vendors the toolkit headers.

**Impact:** None to the design; the GPU extra is simply larger to install. Recorded so the next
person does not spend an hour on the same error.

## 4. FBref scraping requires a Chrome installation

**Spec:** §10.2 assumed plain HTTP scraping with rate limiting.

**Reality:** soccerdata 1.9.1 drives `seleniumbase` with an undetected chromedriver to get past
Cloudflare. The driver is downloaded automatically on first use.

**Substitute:** None. Chrome is now a system prerequisite for live ingestion.

**Impact:** Scraping is slower than anticipated (~50 s per season, so ~21 minutes for 25
seasons) and cannot run on a machine without Chrome. Analysis is unaffected: everything
downstream reads Parquet, so only re-ingestion needs the browser.

## 5. `peak5` gained a minimum-seasons floor

**Spec:** §6.3, "best five *consecutive* seasons", with no stated floor.

**Reality:** On real data the lens ranked Patrick Bamford 9th, Edinson Cavani 10th and
Zlatan Ibrahimović 12th, each on a **single season**, each with `lo == hi == score`. Two
failures at once: a one-season "best five consecutive seasons" is a category error, and
bootstrapping one observation returns a zero-width interval that renders as perfect confidence
on the least reliable estimate in the table.

**Substitute:** `Config.min_seasons = 3`. Players whose longest consecutive run is shorter are
excluded from the rating, mirroring the existing `min_minutes` threshold rather than inventing a
new mechanism.

**Impact:** 2,428 ranked players becomes 965. No zero-width intervals remain (asserted by test).
Players with genuinely short Premier League careers (Haaland has three seasons) still rank,
but nobody is ranked on a sample of one.

## 6. Quarto book config lives at the repository root

**Spec:** §5.1, book files under `tome/`.

**Reality:** Quarto cannot reliably reference chapters above its project directory, and it
requires the book home page to be `index.qmd` at the project root.

**Substitute:** `_quarto.yml` and `index.qmd` sit at the repository root; `tome/` keeps the
remaining book sources and receives the rendered output in `tome/_book`.

**Impact:** Two extra files at the repository root. The alternative, duplicating notebooks into
`tome/`, would have broken the single-source-of-truth rule in §5.2.

---

## 7. The side-table join key was not unique

**Spec:** §3.2, merge the secondary FBref tables onto `standard` by
`(league, season, team, player)`.

**Reality:** that key does not identify a player. Two men called Míchel played for Rayo
Vallecano in 2002-03, and FBref lists both. A left join against a duplicated key returns the
cross product, so across three side tables two rows became sixteen. The published data carried
121 fabricated rows, one of them a player with **19,288 minutes and 272 appearances** in a
38-match season.

**Substitute:** birth year joins the key, and every merge is declared
`validate="one_to_one"` so a repeated key raises instead of multiplying. Two source quirks
surfaced once it did: FBref lists Emanuele Torrasi twice at Milan in 2017-18, and splits Sinan
Kurt's 2014-15 playing time across an appearance row and an unused-substitute row.
`_fuse_split_records` reassembles those, and refuses to merge rows that disagree in `standard`,
because `standard` is what decides who exists.

**Impact:** 67,825 raw rows to 67,704. Maximum minutes 19,288 to 3,583. Every league offset
re-estimated. Nothing raised before the fix, no schema rejected it, and every per-90 rate
computed from those rows divided by an invented denominator.

---

## 8. A share of team minutes was summed across clubs

**Spec:** §4.1, collapse mid-season transfers by summing counting stats.

**Reality:** `min_pct` was in that list, and a percentage is not additive. A player at two clubs
had his two shares added, so 12 player-seasons exceeded 100% of their team's minutes, the worst
at **296.4%**. The availability requirement read that as a virtue.

**Substitute:** `min_pct` is removed from the summed columns and recomputed. Each club's implied
total minutes is recovered from the share it came with, those are summed, and the real share is
taken against the total.

**Impact:** maximum availability 296.4% to 100.0%. The requirement now means what its name says.

---

## 9. Missing values became zeros at collapse

**Spec:** §4.1, sum counting stats per player-season.

**Reality:** `groupby().sum()` returns 0 for an all-missing group. FBref recorded no fouls at all
in Ligue 1 or the Bundesliga before 2006, so 5,814 player-seasons were handed a clean
disciplinary record they had not earned, in the requirement that eliminates more players than
any other.

**Substitute:** `min_count=1` on the aggregation, so an entirely missing group stays missing, and
a `FOUL_COVERAGE` floor below which the fouls term is dropped rather than filled.

**Impact on fouls: none.** Because scores are z-scored within `(league, season)`, a fill
covering an entire group cancels out, and all twelve affected league-seasons are exactly that
shape. The coverage guard changes **zero fouls rows**. Of the 610 rows distorted in
partly-covered league-seasons, only **48 clear the 900-minute floor** and reach the ranking, at
a median of 32 minutes each. Group-mean imputation was considered and rejected on that
measurement rather than on principle.

**Impact on second yellows: the reason the guard exists.** The same guard extended to
`second_yellow` changes **1,799 rows**. That column runs at 10 to 16% coverage until 2015 and
100% from 2016, so for fifteen seasons a player who picked up a second yellow was penalised
while nine in ten of his peers' second yellows were never recorded at all. The guard was
reasoned out for fouls, where it does nothing, and turned out to matter for the column that was
never examined. Chapter 03 says so in those terms.

---

## 10. `complete <= starts` is not an invariant

**Spec:** none. This was an invariant added while writing chapter 04.

**Reality:** it reads like arithmetic and is a claim about football. A substitute who comes on and
is still on the pitch at the final whistle has completed a match he did not start, and FBref
counts him. The bound is appearances, not starts.

**Substitute:** `complete <= mp`.

**Impact:** 20 rows violated the wrong bound, 9 of them legitimate football. Under the corrected
bound 11 rows remain, and those are FBref disagreeing with itself: Cannavaro's 2000-01 is 29
appearances, 29 starts and 31 completed matches. Recorded here because a wrong invariant does
not sit quietly, it accuses correct data of being broken.

## 11. PyMC on Windows needs a working 64-bit C compiler

**Reality:** `pymc.sample` fails to build its C backend on a stock Windows machine with no
compiler on `PATH`. A system install of mingw-w64 (64-bit) was required on the dev machine before
the `bayes` extra would run. Recorded so the next Windows contributor does not rediscover it.

---

# Gate results

Measured on the real run, 2026-08-10. Recorded whether or not they cleared, per the agreed
policy of reporting honestly rather than stopping.

| Definition-of-done item | Target | Measured | Result |
|---|---|---|---|
| 1. Schema-validated Parquet with manifests | - | 13,724 rows, 25/25 seasons, no gaps | **PASS** |
| 2. Identity resolution | ≥ 95% | **96.8%** (179 players unresolved, all listed) | **PASS** |
| 3. Ranking with bootstrap intervals | - | 965 players, 0 zero-width intervals | **PASS** |
| 4. CuPy/NumPy parity | asserted | test executed, not skipped | **PASS** |
| 5. Notebooks execute; book builds | - | 2 notebooks, 0 errors, 4 pages rendered | **PASS** |
| 6. Streamlit runs against Parquet | - | health `ok`, main page HTTP 200 | **PASS** |
| 7. pytest / ruff / mypy --strict | all clean | 116 passed, 95.3% cov; ruff clean; mypy clean | **PASS** |

Scrape wall-clock: roughly 18 minutes for 25 seasons plus ClubElo and Wikidata.

## An honest finding, not a failure

**44 of the 45 possible pairs in the top ten have overlapping confidence intervals.**

Bootstrapping a five-season window means resampling five numbers, which produces wide bands. The
consequence is that this lens, on this data, **cannot statistically separate the top ten players**.
Only one pair in the top ten is distinguishable.

That is the correct answer to report, and it is more interesting than a false ordering would have
been: it says the argument about who is second versus seventh is not resolvable with goals and
assists over five seasons, however confidently it is conducted. Narrowing those bands needs more
signal per season, more metrics, not more seasons.

---

# Gate results, complete Big 5, 2026-08-11

The three data gaps in `PENDING.md` Part 1 were filled (Ligue 1 in full, La Liga
keepers, Bundesliga `misc`) and the whole pipeline re-run from the cache.

| Definition-of-done item | Target | Measured | Result |
|---|---|---|---|
| 1. FBref cache complete | 5 × 5 × 25 | 625 of 625 pages, no partial table | **PASS** |
| 2. Identity resolution | ≥ 95% | **93.8%** (1,240 players unresolved, all listed) | **FAIL** |
| 3. Ranking | - | 5,508 ranked, 342 qualified, 39,877 player-seasons | **PASS** |
| 4. Notebooks execute; book builds | - | 8 notebooks, 0 errors, 10 pages rendered | **PASS** |
| 5. Streamlit runs against the sample | - | health `ok`, main page HTTP 200 | **PASS** |
| 6. pytest / ruff / mypy --strict | all clean | 231 passed, 90.6% cov; ruff clean; mypy clean | **PASS** |
| 7. External validation | - | 16 of 18 award winners located, 10 qualify | **new** |

Scrape wall-clock: 95 minutes for the 162 missing FBref pages. The Wikidata
crosswalk took roughly 40 minutes on a cold cache and now costs nothing, being
stored one Parquet per birth year.

**Item 2 still fails, and the route there is worth recording.** It first got
*worse* (four leagues resolved 85.1%, five resolved 83.9%) which read as Ligue 1
adding harder names. That reading was wrong. The real cause was the crosswalk
query anchoring on Wikidata's FBref-ID property, which the matcher never joined
on and which excluded more than half the candidate pool. Fixing the anchor and
adding tiered name matching took it to 93.8%.

The remaining 1.2 points are transliteration (`Serhiy`/`Serhii`), non-Latin
labels, and players genuinely absent from Wikidata. Every further loosening
trades a missing match for a risk of a wrong one, and a wrong QID is worse,
because a missing one is reported and a wrong one is not.

## What adding Ligue 1 did to the answer

Recorded because the effect was predicted in `PENDING.md` before it was measured,
which makes it worth checking against.

- **Every offset moved.** England pinned at 0; Spain −0.143 → −0.153, Italy
  −0.212 → −0.205, Germany −0.219 → −0.218. France entered at **−0.283**, the
  weakest of the five, backed by 3,715 moves.
- **The top of the ranking changed less than expected.** Mbappé enters at 3rd
  and pushes everyone below him down one; Ronaldo (the Brazilian) drops out of
  the top ten to 11th. Nobody else moved rank. Two careers grew a French
  prefix or suffix: Messi is now 18 seasons across Spain and France rather than
  16 in Spain, Benzema 17 rather than 14. Messi's lead narrows from +6.1σ to
  +5.9σ.
- **The goalkeeper board turned over almost completely.** With La Liga keepers
  present, Cañizares (2nd), Valdés (3rd), ter Stegen (4th) and Casillas (6th)
  displace Kahn, Ederson, Čech and Buffon from the top five. Neuer still leads.
  Qualifiers went from 56 of 232 to 75 of 395.

## An honest finding, and a correction to how it was argued

Phase 1 reported that 44 of 45 pairs in the top ten had overlapping bootstrap
intervals, and concluded the lens "cannot statistically separate the top ten".

**The conclusion stands; the reasoning behind it did not.** Overlapping
confidence intervals do not imply a non-significant difference. Non-overlap
implies significance, but the converse fails, because the interval for a
difference is narrower than two individual intervals suggest, standard errors
combine in quadrature. Measured on this data, four pairs whose intervals overlap
are separable at p < 0.05, so the heuristic was giving the right answer for the
wrong reason.

Re-argued with an actual test: of the 28 pairs among the top eight, **3 reach
p < 0.05 two-sided**, and none survives a Bonferroni correction for 28 tests.

Two further corrections from the same audit:

- **One-sided p-values were reported for pairs drawn from a sorted table.** The
  direction was therefore chosen after seeing the data, which is
  anti-conservative by roughly a factor of two, 5 significant pairs became 3
  once the scan was made two-sided. `doubt.permutation_test` grew a `two_sided`
  option and the exploratory scan uses it; a pre-specified directional claim
  still uses one.
- **The percentile bootstrap under-covers badly on short careers.** At three
  seasons (which `min_seasons = 3` permits into the ranking) a nominal 95%
  interval contains the truth 74% of the time. BCa would narrow the gap; more
  seasons would close it.

More data did not resolve the top of the table, and that is the correct outcome
to report rather than a disappointment. Narrowing those bands needs more signal
per season, not more seasons.
- **Discipline bites harder.** Complete `misc` means second yellows and fouls
  per 90 are measured the same way in every league instead of degrading to
  reds-and-yellows where the table was missing.

The gate itself is unchanged: 321 of 5,508 qualify at the 40th percentile, 5.8%,
against 0.60% if the ten requirements were independent.

---

# Benchmarks

Spec §7 forbids GPU code without a measurement. Bootstrap, 10,000 resamples,
RTX 4050 Laptop (6 GB) against a Ryzen CPU:

| Array size | CPU | Auto-dispatch | Speedup | Path taken |
|---|---|---|---|---|
| 5 | 0.001 s | 0.000 s | - | CPU (below `GPU_MIN_ELEMENTS`) |
| 2,000 | 0.159 s | 0.015 s | 10.6x | GPU |
| 20,000 | 1.927 s | 0.128 s | 15.1x | GPU |

The floor is doing real work: `lens.peak5` bootstraps careers of 2-5 seasons,
thousands of times. Dispatching those to the GPU would be slower than NumPy, so
`doubt.GPU_MIN_ELEMENTS` keeps them on the CPU.
