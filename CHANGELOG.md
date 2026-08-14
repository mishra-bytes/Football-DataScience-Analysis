# Changelog

All notable changes to this project are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries state the measured effect, not the intent. "Improved matching" is not a
changelog entry; "83.9% → 89.3%" is.

---

## [Unreleased]

Branch `big-five-and-identity`. Data coverage completed, identity resolution
rebuilt, three long-pending analysis features shipped, and then four data-integrity
defects found and fixed. The book gained a data section and became one narrative
arc.

### Fixed

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
- **The headline caveat got stronger, not weaker.** Of the 28 pairs among the top
  eight, pairs separable at p < 0.05 two-sided fell **3 → 1**, and under a
  Bonferroni correction **1 → 0**. Median award-winner rank 61st → 64th.
- Top eight reordered: Henry rises to 6th, Suárez ahead of Lewandowski, Haaland
  above Mbappé. Messi and Ronaldo unchanged at 1 and 2.
- **The book is one arc, from a raw HTML page to the answer and back at it.**
  Thirteen chapters renumbered and retitled in reading order, in four parts:
  getting the data honest, turning data into a measure, the answer, attacking the
  answer.
- **All prose rewritten in the first person**, and every em dash removed from the
  notebooks, the book, the docs and the library docstrings.
- Test count **175 → 236**.

### Removed

- Three orphan artifacts that the pipeline no longer wrote and nothing read:
  `vault/derive/peak5.parquet`, `vault/raw/player_season_raw.parquet` and
  `vault/clean/player_season.parquet`. The last two were England-only Phase 1
  leftovers, strictly contained in `outfield_raw`.

### Added

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
  immediately after them, the fact that only 1 of 28 pairs in the top eight are
  separable. Previously a reader had to open chapter 1 to find any result.

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
- Identity resolution **83.9% → 93.8%** of 67,825 rows; unresolved players
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

- Identity resolution is **93.8%**, against a 95% target. What remains is
  transliteration (`Serhiy`/`Serhii`, `Alexander`/`Aliaksandr`), non-Latin
  labels, Modrić's only non-English Wikidata label is Cyrillic and cannot be
  folded onto FBref's Latin spelling, and players genuinely absent from
  Wikidata. Every further loosening trades a missing match for the risk of a
  wrong one, which is the worse error.
- **The top ten is not an ordering.** Only 1 of 28 pairwise comparisons among the
  top eight are separable at p < 0.05 two-sided, and none survives a Bonferroni
  correction. More data did not fix this and more seasons will not; it needs more
  signal per season.
- **Percentile bootstrap under-covers on short careers**: 74% actual against a
  nominal 95% at three seasons, which `min_seasons = 3` admits. BCa intervals are
  the fix and are not implemented.
- `failure_summary` is near information-free by construction: a percentile gate
  eliminates exactly that share of the population on every requirement.
- Defenders remain unmeasurable. Top 50 qualifiers are 96% forwards, 4%
  midfielders, 0% defenders; the best defender ranks 122nd. FBref records no
  per-player defensive action before 2017-18. Cannavaro, the 2006 Ballon d'Or
  winner, ranks 2,707th and fails 8 of 11 requirements.

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
