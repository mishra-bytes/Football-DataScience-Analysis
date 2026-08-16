# Changelog

All notable changes to this project are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries state the measured effect, not the intent. "Improved matching" is not a
changelog entry; "83.9% → 89.3%" is.

---

## [Unreleased]

### The 2026-08-16 audit sweep, in one entry

An external audit verified every published number against `vault/` and the
fixes landed together. The measured effects, before → after:

- Continental/tournament yardstick pooled within `(season)`, no domestic
  offset: Mbappé's career continental z 14.19 → 11.22, Ronaldo's 9.61 →
  12.07, Messi 10.69 → 12.86; podium Messi–Mbappé–Ronaldo → Messi (4.84,
  +8.59σ) – Ronaldo (4.13) – Mbappé (3.94).
- Mover availability denominator capped at the largest single-club implied
  season: movers' ceiling 74.5% → 100.0%, mean +20.2pp over 2,605 transfer
  seasons; Guilherme 2017-18 52.4% → 100%.
- Qualifiers 357 → 265 of 5,508 (268 from the yardstick alone, 23 gate flips
  from the availability fix netting −3).
- Permutation caveat recomputed and aligned everywhere: 5 of 28 top-eight
  pairs at p < 0.05 two-sided, exactly one (Messi vs Benzema, p = 0.0009)
  surviving Bonferroni; every appearance now names the tested statistic
  (unweighted means of per-season scores, not the ranking's minutes-weighted
  composite).
- Henry vs Suárez keyed by player_id: the published p = 0.0467 "significant"
  was a name-collision chimera of two players called Luis Suárez; the real
  test reads p = 0.22 one-sided. The dashboard's A-vs-B tab is keyed by
  player_id too.
- labs/12's selection gap re-controlled on seasons with a successor: +0.075 →
  +0.027, bootstrap 95% interval [+0.003, +0.053].
- Awards median reported exactly (37 truncated → 38.0 of 5,508); Cannavaro
  2,263rd → 2,363rd, failing 5 of 12.
- Defender picture recomputed: top 50 = 88% forwards / 12% midfielders / 0%
  defenders, best defender 170th.
- above_team~scoring re-measured once: 0.996 everywhere (labs/15's 0.9999
  retired; smallest eigenvalue 0.003, not zero).
- Effective requirement count re-estimated: participation ratio 4.52,
  equivalent gates 5.94, 90%-variance 7.
- Identity aligned on one figure: 93.9% of the 65,069 collapsed
  player-seasons, 1,240 players unresolved.
- League offsets (means over 25 seasons): Spain −0.170 → −0.156, Italy
  −0.254 → −0.206, Germany −0.299 → −0.254, France −0.377 → −0.288; the
  1,839 transfer moves and their endpoints unchanged; re-pinning spread
  re-verified at 0.011.
- Test count corrected 236 → 278; FBref cache reconciled (625 domestic
  player pages; 634 was the domestic-era folder; 780 files, 1.49 GB now);
  index.qmd gates on twelve requirements and its limitations tell the truth
  about requirements 11 and 12.

Closing sanity statement, current headline: top three Messi 4.84 / Ronaldo
4.13 / Mbappé 3.94; 265 of 5,508 qualify; 5 of 28 top-eight pairs separable
at p < 0.05 two-sided, one after Bonferroni; Messi sits 8.59σ above the
ranked population's mean.

Branch `big-five-and-identity`. Data coverage completed, identity resolution
rebuilt, three long-pending analysis features shipped, and then four data-integrity
defects found and fixed. The book gained a data section and became one narrative
arc.

### Fixed

- **One competition, one yardstick (2026-08-16).** `continental` and
  `tournament` were z-scored within `(league, season)`, so a player's European
  output was measured against his domestic league-mates and the yardstick
  population depended on how many of them also played in Europe, a club and
  league artifact; the league-strength offset was then added on top of both
  columns, a second adjustment with no rationale. Both columns are now
  z-scored within `(season)` pooled across the Big 5 and carry no offset.
  Measured: Mbappé's career continental z **14.19 → 11.22**, Ronaldo's
  **9.61 → 12.07** (Messi highest under both, 10.69 → 12.86), which is the
  actual ordering of the two European careers. Ronaldo returns to 2nd
  (**4.04 → 4.13**, Mbappé **4.04 → 3.94** drops to 3rd), Messi **4.61 →
  4.84** with his lead over the ranked population widening **8.03σ → 8.59σ**.
  The podium change is the artifact leaving, not football changing.
  Qualifiers **357 → 268** from this change alone (265 shipped, with the
  availability fix below). Endpoints and the 1,839 transfer moves are
  unchanged; league offsets shift slightly (mean over 25 seasons): Spain
  −0.170 → **−0.156**, Italy −0.254 → **−0.206**, Germany −0.299 →
  **−0.254**, France −0.377 → **−0.288**. Zero-mass at the gate floor
  re-measured under the pooled grain: 0.00% at both floors, every
  season-level requirement still eliminates 2,203 of 5,508 (39.996%); see
  DECISION.md.
- **A mid-season mover's availability was structurally understated.**
  `collapse_transfers` recomputed `min_pct` against the **sum** of each
  club's implied full season, double-counting the overlapping calendar: no
  mover could exceed 74.5%, and Guilherme's 2017-18 (3,583 minutes, more than
  one club's entire season) read 52.4%. The denominator is now the largest
  single-club implied season, capped at 100%. Measured: 2,605 transfer
  seasons gain **+20.2pp** availability on average, movers' maximum **74.5% →
  100.0%**; 23 players cross the gate, qualifiers **268 → 265** against the
  pooled-normalisation baseline. See DECISION.md.
- **Percentile bootstrap under-covered short careers.** 74% actual against a
  nominal 95% at three seasons, and `min_seasons = 3` put exactly those careers
  in the published table. `doubt.bca` replaces it with a bias-corrected and
  accelerated interval. On `peak5`'s qualified top ten, median 95% interval
  width **0.499 → 0.512**. The widening is the defect being fixed, not a
  regression: the percentile interval was too narrow, not merely mispositioned.
- **Side-table join key was not unique.** `(league, season, team, player)` does
  not identify a player: two men called Míchel played for Rayo Vallecano in
  2002-03. Three left joins against a duplicated key returned the cross product.
  Raw rows **67,825 → 67,704**, maximum minutes **19,288 → 3,583**, maximum
  appearances **272 → 55**. Birth year joins the key and every merge is now
  `validate="one_to_one"`.
- **`min_pct` was summed across clubs.** A share is not additive, so 12
  player-seasons exceeded 100% of their team's minutes. Maximum availability
  **296.4% → 100.0%**. It is now recomputed from each club's implied total.
- **Missing values became zeros at collapse.** `groupby().sum()` returns 0 for an
  all-missing group, so 5,814 player-seasons with no recorded fouls were handed a
  clean disciplinary record. `min_count=1` keeps missing missing.
- **`complete <= starts` was a wrong invariant**, corrected to `complete <= mp`. A
  substitute who finishes a match has completed one he did not start. 9 of the 20
  flagged rows were legitimate football.

### Changed

- **Every league offset re-estimated** after the data fixes:

  | League | Before | After |
  |---|---|---|
  | England | 0.000 | 0.000 (reference) |
  | Spain | −0.163 | **−0.180** |
  | Italy | −0.213 | **−0.243** |
  | Germany | −0.227 | **−0.261** |
  | France | −0.300 | **−0.359** |

- **Qualifiers 326 → 345** of 5,508 ranked. Player-seasons 39,883 → 39,877.
- **The headline caveat moved with the data fixes.** Median award-winner rank
  61st → 64th. The pair counts first recorded here (3 → 1 at p < 0.05
  two-sided, 1 → 0 under Bonferroni) did not survive the 2026-08-16 audit's
  re-measurement: under the shipped pipeline 5 of the 28 pairs among the top
  eight are separable at p < 0.05 two-sided and exactly one, Messi against
  Benzema, survives the Bonferroni correction.
- Top eight reordered: Henry rises to 6th, Suárez ahead of Lewandowski, Haaland
  above Mbappé. Messi and Ronaldo unchanged at 1 and 2.
- **Book chapters re-run against the twelve-requirement pipeline.** An audit
  found 11 of 17 chapters still carrying ten/eleven-requirement numbers after
  `continental` and `tournament` shipped. Chapters 01-16 re-executed against
  the committed sample and 03, 05, 07-16 had their prose swept for numbers the
  new outputs contradicted (17 needed no changes). Headline effects: awards
  median winner rank 60th → 37.5th of 5,508 (the summary truncated it to 37
  until 2026-08-16); the Henry vs Suárez p-value published from this re-run,
  0.0906 → 0.0467 "flips to significant", was an artifact of the identity
  bug below (a name-keyed selection merged two players called Luis Suárez);
  against the real Suárez's player_id the test does not reach significance.
  Messi's lead over the mean 5.81 → 8.03 sigma, with Mbappé rather than
  Ronaldo second at the time;
  qualifiers under the shipped gate 445 → 357, multi-league qualifiers 173 →
  139; discipline no longer eliminates more players than any other
  requirement, every season-level requirement ties at 2,203 under the
  percentile gate.
- **The book is one arc, from a raw HTML page to the answer and back at it.**
  Thirteen chapters renumbered and retitled in reading order, in four parts:
  getting the data honest, turning data into a measure, the answer, attacking the
  answer.
- **All prose rewritten in the first person**, and every em dash removed from the
  notebooks, the book, the docs and the library docstrings.
- Test count **175 → 278**.

### Removed

- Three orphan artifacts that the pipeline no longer wrote and nothing read:
  `vault/derive/peak5.parquet`, `vault/raw/player_season_raw.parquet` and
  `vault/clean/player_season.parquet`. The last two were England-only Phase 1
  leftovers, strictly contained in `outfield_raw`.

### Added

- **A Bayesian layer** (`gambeta.bayes`): a hierarchical model of player-season
  level, with the shrinkage a short career gets estimated from the data
  instead of imposed by the pipeline's hard `cfg.min_minutes` floor. Each
  player draws his level from a population distribution whose spread is
  fitted, not assumed; a season's precision scales with its minutes rather
  than being excluded outright below the floor. Sits beside the point-estimate
  pipeline, not in place of it; see DECISION.md. Fitted on the full
  `player_season_scored.parquet` (10,039 players, 39,877 player-seasons):
  0 divergences, r_hat 1.00 on `population_sd` and `noise`, 36.1s wall time.
  Comparing the point estimate's top 50 (minutes-weighted mean of
  `season_score` on seasons at or above `cfg.min_minutes`) against the same
  players' rank under the posterior mean, **20 of 50** move by more than 5
  places once shrinkage is estimated rather than imposed. Optional extra
  (`bayes`); the rest of the suite passes with it uninstalled, `tests/test_bayes.py`
  skipped.
- **`tournament`, the twelfth requirement** (`needs.tournament_value`):
  international output at the World Cup, the Euro and Copa America, scored as
  a per-90 rate scaled by presence and saturating at a full run
  (`TOURNAMENT_FULL_RUN = 450` minutes, five matches). Copa America joined the
  World Cup and the Euro by owner ruling 2026-08-15 (the Euro covers European
  players, Copa America covers South American ones); it is registered with
  soccerdata the same way the Champions League is
  (`gambeta.scouts.fbref.register_copa_america`). Absence scores zero, not
  missing, the same ruling `continental` already carries; see DECISION.md for
  the nationality objection this requirement only partly answers. Qualifiers
  **398 → 357** of 5,508 ranked. At the 40th-percentile gate, `tournament`
  eliminates 2,203, the same share as every other season-level requirement;
  its standardised profile carries 0.00% exact-zero mass despite `tournament`
  starting from a higher raw-zero rate than `continental` did, checked rather
  than assumed; see DECISION.md. Top ten reorders: Lewandowski rises 6th →
  5th, Kane rises 8th → 6th, Suárez rises 10th → 9th; Benzema holds 7th;
  Haaland falls 5th → 8th (Norway did not qualify for a tracked tournament in
  his career); Salah drops out of the top ten (Egypt's tournament is the Africa
  Cup of Nations, out of scope), replaced by van Nistelrooy, 12th → 10th.
  Messi, Mbappé, Ronaldo and Henry hold their places at the top.
- A real defect caught before publishing, not after: fetching World Cup, Euro
  and Copa America stats one project season at a time (soccerdata indexes
  them by the tournament's own calendar year, and a batched multi-season
  request raises the moment one requested year has no data) double-counted
  the COVID-delayed 2020 Euro and 2020 Copa America editions, because both
  are still labelled `"2020"` at the source but are also matched by a query
  for the following domestic season, `"2021"`. `collapse_transfers` summed
  the duplicate as if it were a real mid-season transfer, doubling every
  2020-edition player's minutes and goals (caught by comparing a doubled
  edition's 1,436-minute ceiling against a normal edition's 690). Fixed by
  deduplicating the raw fetch before it is written; see DECISION.md. Raw
  tournament rows **8,030 → 7,307** after the fix.
- **`continental`, the eleventh requirement** (`needs.continental_value`):
  European club output, currently the Champions League, scored as a per-90
  rate scaled by presence and saturating at a full campaign
  (`CONTINENTAL_FULL_SEASON = 900` minutes). Absence from Europe scores zero,
  not missing, by ruling; see DECISION.md. Qualifiers **445 → 398** of 5,508
  ranked. At the 40th-percentile gate, `continental` eliminates 2,203, the
  same share as every other season-level requirement, checked rather than
  assumed: the column's exact-zero mass measures at 0.00% in the standardised
  profile the gate consumes, well clear of the floor, so the cut is real and
  not an artefact of the tie the requirement could in principle land on; see
  DECISION.md for the measurement. Top ten reorders: Mbappé rises 6th → 2nd,
  Lewandowski 8th → 6th, Benzema 10th → 7th, Kane falls 3rd → 8th, Suárez
  7th → 10th; Messi, Ronaldo, Henry and Haaland hold their places at the top.
- **Four data chapters**, all runnable from committed files with no network and
  no Chrome: where the data comes from, who is this player, when a zero is a lie,
  and four bugs no test could catch. The last one **computes its own verdict**
  against the published sample rather than describing a fixed state, so it cannot
  go stale or flatter itself.
- `laws` invariants and `validate="one_to_one"` guards, so this class of defect
  raises at the layer boundary instead of shipping.
- Pushed, and CI green on a real runner for the first time.

### Previously in this release

### Added

- **Ligue 1**, completing the Big 5. All five leagues now hold 5 tables × 25
  seasons; 625 FBref pages with no partial table. La Liga goalkeepers (8/25 →
  25/25) and the Bundesliga `misc` table (5/25 → 25/25) filled at the same time.
- **Named weight vectors** (`needs.ARGUMENTS`), six arguments people actually
  have about greatness, sparse by design so each states only what it emphasises.
- **Permutation test** (`doubt.permutation_test`) for claims of the form "A is
  better than B". One-sided, distribution-free, `(hits + 1) / (n + 1)` so a
  p-value is never reported as zero.
- **External validation** (`gambeta.verdict`) against Ballon d'Or, FIFA Ballon
  d'Or, FIFA World Player, The Best FIFA Men's Player and UEFA Player of the
  Year. Five awards because none spans 2000-2025 alone.
- **Dashboard controls**, argument selector, eleven weight sliders, gate
  percentile, and an "A vs B" tab reporting p-values.
- `season_score` column on `player_season_scored.parquet`: the normalised,
  offset-adjusted per-season composite. Published alongside the raw values, not
  instead of them.
- Per-birth-year Wikidata cache under `vault/raw/wikidata/`, keyed by a
  fingerprint of the query text. A full pipeline run went from ~35 minutes to
  **5**, and a repair now costs one request per changed year instead of 41.
- **Five new chapters**, each following the six-part method template:
  normalisation and shrinkage (05), the bootstrap (06), testing without a
  distribution (07), selection bias and Simpson's paradox (08), and does it
  agree with the voters (09). Book is now eleven pages.
- **The preface states the answer**, computed live from `data/sample` rather
  than transcribed: top ten, qualifier count, goalkeepers, league offsets, and
  immediately after them, how few of the 28 top-eight pairs are separable
  (recomputed at render time; 5 of 28, one after Bonferroni, under the
  2026-08-16 pipeline). Previously a reader had to open chapter 1 to find any
  result.

### Changed

- **Every league offset re-estimated** after Ligue 1 and the age fix:

  | League | Before | After |
  |---|---|---|
  | England | 0.000 | 0.000 (reference) |
  | Spain | −0.143 | −0.163 |
  | Italy | −0.212 | −0.213 |
  | Germany | −0.219 | −0.227 |
  | France | - | **−0.300** |

- **Ranking population** 4,424 → 5,508; **qualifiers** 239 → 326 (345 after
  the data-integrity fixes above).
- Identity resolution **83.9% → 93.9%** of the 65,069 collapsed
  player-seasons in `vault/clean/outfield.parquet`; unresolved players
  3,480 → 1,240. Crosswalk 114,084 → 253,241 people.
- Mbappé enters at 3rd. Messi's career becomes 18 seasons across two countries
  rather than 16 in one; his lead narrows from +6.1σ to +5.9σ.
- Goalkeeper board turns over with La Liga keepers present: Cañizares, Valdés,
  ter Stegen and Casillas displace Kahn, Ederson, Čech and Buffon from the top
  five. Neuer still leads. Qualifiers 56/232 → 75/395.
- `discipline` now measured identically in every league, second yellows and
  fouls are present everywhere, instead of degrading to reds-and-yellows where
  `misc` was missing.
- `gate.qualify_and_rank` accepts sparse weights; a requirement left out counts
  1.0 rather than raising `KeyError`.
- Wikidata crosswalk anchors on occupation (`P106 = Q937857`) with the FBref ID
  kept as an optional provenance column: **114,084 → 239,718+ candidates**.
- Label service asks for a Latin-script fallback chain rather than English only.
- `whois.normalize` folds punctuation. Apostrophes close up (`M'Boma` → `mboma`),
  hyphens open out (`Jean-Pierre` → `jean pierre`); the two cases are not the
  same and collapsing them identically loses one.

### Fixed

- **Interval overlap was used as a significance test.** Overlapping confidence
  intervals do not imply a non-significant difference; only non-overlap implies
  the reverse, because the interval for a difference is narrower than two
  individual intervals suggest. Four top-ten pairs whose intervals overlap are
  separable at p < 0.05, so the heuristic was reaching a defensible conclusion
  by invalid reasoning. README, DEVIATIONS and notebook 06 now lead with the
  test and label the overlap count as description.
- **Post-hoc one-sided p-values.** The pairwise scan reads a table sorted by
  score, so the higher scorer is always named first and the direction was chosen
  after seeing the data, anti-conservative by roughly a factor of two.
  `doubt.permutation_test` gained `two_sided`, used by the scan and by the
  dashboard's A-vs-B tab, whose dropdowns are also rank-ordered. Significant
  pairs: 5 → 3.
- **Notebook 05's regression-to-mean demonstration did not demonstrate it.** It
  bucketed z-scores by minutes and asserted the spread shrinks; measured, the
  standard deviations ran 1.01, 1.00, 0.99, 1.04, 0.88 (not monotone) and the
  maximum *rose* with minutes. Replaced by a reliability measurement: how well a
  season predicts the same player's next one, climbing 0.646 → 0.822 from the
  shortest bucket to the longest. That version earns more than the original,
  because the shrinkage weight is an estimate of exactly that quantity, so
  m0 = 900 is now checked against measured reliability rather than asserted.
- **Ages were attached by position and 94% were wrong.** `clean()` assigned
  `groupby(keys)["age"].first().to_numpy()` onto a frame built with
  `sort=False`; the orderings disagreed at every position, so 61,131 of 65,069
  player-seasons carried somebody else's age, 5.4 years out on average, 23 at
  worst. Age is a control in the league-strength regression, so the published
  offsets were fitted on scrambled data. Nothing raised, because both sides were
  the same length. Now joined on keys (`tally.add_age`), with a regression test
  whose fixture is deliberately unsorted.
- **Cached query-service timeouts were replayed on every retry.** WDQS answers
  `200 OK`, streams half the JSON, hits its 60 s cap, appends a Java stack trace
  and caches the result. `raise_for_status` passes and the parse dies at the
  identical byte every attempt. Measured on 1990: three attempts all failed at
  char 2,767,040 of 2.77 MB; the same query with a comment appended returned
  4.30 MB and 9,893 clean rows. Retries now vary the query text.
- **Whole birth-year cohorts were lost in silence.** Logged as `0 people` at INFO
  and passed over. 1985 and 1994 were lost on one run, and 1985 is when
  Cristiano Ronaldo and Luka Modrić were born, so the awards check reported the
  holder of seven honours as a player the data had never seen. A year that fails
  whole is now re-asked in two halves by birth month, and an empty cohort is
  reported at WARNING.
- **Awards counted women's winners.** Several of these award items carry women's
  recipients on Wikidata, so Birgit Prinz, Carli Lloyd and Aitana Bonmatí
  arrived counted as winners the data had failed to find, when their absence is
  correct, women's football is a declared non-goal. Query now filters on `P21`.
- Book preface still claimed Premier League only coverage, which was Phase 1 text
  that survived Phase 2. Chapter prose and dashboard captions realigned to five
  leagues and the recomputed figures.
- Two demonstrations in the new chapters were rewritten because their output
  contradicted their own captions: an effect-size example whose gap never became
  significant at any sample size shown, and a Simpson's paradox that did not
  reverse. Now p → 0.0010 as n grows, and the correlation flips +0.96 → −0.96.
- A statistical audit of the new chapters found three further faults, all fixed
  (see **Fixed** below): an unsupported claim about spread, an unsound use of
  interval overlap as a test, and post-hoc one-sided p-values.

### Known issues

- Identity resolution is **93.9%** of the 65,069 collapsed player-seasons,
  against a 95% target. What remains is
  transliteration (`Serhiy`/`Serhii`, `Alexander`/`Aliaksandr`), non-Latin
  labels, Modrić's only non-English Wikidata label is Cyrillic and cannot be
  folded onto FBref's Latin spelling, and players genuinely absent from
  Wikidata. Every further loosening trades a missing match for the risk of a
  wrong one, which is the worse error.
- **The top ten is not an ordering.** Only 5 of 28 pairwise comparisons among
  the top eight are separable at p < 0.05 two-sided, and exactly one survives
  a Bonferroni correction. More data did not fix this and more seasons will
  not; it needs more signal per season.
- `failure_summary` is near information-free by construction: a percentile gate
  eliminates exactly that share of the population on every requirement.
- Defenders remain unmeasurable. The top 50 of the ranking are 88% forwards,
  12% midfielders, 0% defenders; the best defender ranks 170th. FBref records
  no per-player defensive action before 2017-18. Cannavaro, the 2006 Ballon
  d'Or winner, ranks 2,363rd and fails 5 of 12 requirements.

---

## [0.1.0], 2026-08-10

### Added

- Phase 1: Premier League, 25 seasons, peak-5 lens with bootstrap intervals.
  All seven definition-of-done gates passed; identity resolution 96.8%.
- Phase 2: eleven requirements with gate-then-rank, four leagues, the
  transfer-based league bridge, a separate goalkeeper leaderboard, ClubElo
  residuals, and penalties excluded from goal metrics.
- Quarto book, Streamlit dashboard, DVC pipeline, GPU auto-dispatch with
  benchmarks (10-15× above the size floor).

### Fixed

- `consistency` was `-(standard deviation)`, which rewarded mediocrity: variance
  is anti-correlated with excellence, and inside a gate it disqualified Messi,
  Ronaldo, Kane, Haaland, Lewandowski, Suárez, Henry and Salah simultaneously.
  Redefined as the 20th percentile of a player's season scores.
- `reliability` was completed matches per start, which measured *being a
  forward*: Benzema, Agüero, Higuaín, Villa, Owen and Trezeguet all missed
  qualification on it alone. Redefined as starts per appearance.

Both were caught by reading output, not by a failing test.
