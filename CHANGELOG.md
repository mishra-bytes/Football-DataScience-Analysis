# Changelog

All notable changes to this project are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries state the measured effect, not the intent. "Improved matching" is not a
changelog entry; "83.9% → 89.3%" is.

---

## [Unreleased]

Branch `big-five-and-identity`. Data coverage completed, identity resolution
rebuilt, and three long-pending analysis features shipped.

### Added

- **Ligue 1**, completing the Big 5. All five leagues now hold 5 tables × 25
  seasons; 625 FBref pages with no partial table. La Liga goalkeepers (8/25 →
  25/25) and the Bundesliga `misc` table (5/25 → 25/25) filled at the same time.
- **Named weight vectors** (`needs.ARGUMENTS`) — six arguments people actually
  have about greatness, sparse by design so each states only what it emphasises.
- **Permutation test** (`doubt.permutation_test`) for claims of the form "A is
  better than B". One-sided, distribution-free, `(hits + 1) / (n + 1)` so a
  p-value is never reported as zero.
- **External validation** (`gambeta.verdict`) against Ballon d'Or, FIFA Ballon
  d'Or, FIFA World Player, The Best FIFA Men's Player and UEFA Player of the
  Year. Five awards because none spans 2000-2025 alone.
- **Dashboard controls** — argument selector, eleven weight sliders, gate
  percentile, and an "A vs B" tab reporting p-values.
- `season_score` column on `player_season_scored.parquet`: the normalised,
  offset-adjusted per-season composite. Published alongside the raw values, not
  instead of them.
- Per-birth-year Wikidata cache under `vault/raw/wikidata/`, keyed by a
  fingerprint of the query text.

### Changed

- **Every league offset re-estimated** after Ligue 1 and the age fix:

  | League | Before | After |
  |---|---|---|
  | England | 0.000 | 0.000 (reference) |
  | Spain | −0.143 | −0.163 |
  | Italy | −0.212 | −0.213 |
  | Germany | −0.219 | −0.227 |
  | France | — | **−0.300** |

- **Ranking population** 4,424 → 5,508; **qualifiers** 239 → 326.
- Mbappé enters at 3rd. Messi's career becomes 18 seasons across two countries
  rather than 16 in one; his lead narrows from +6.1σ to +5.9σ.
- Goalkeeper board turns over with La Liga keepers present: Cañizares, Valdés,
  ter Stegen and Casillas displace Kahn, Ederson, Čech and Buffon from the top
  five. Neuer still leads. Qualifiers 56/232 → 75/395.
- `discipline` now measured identically in every league — second yellows and
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

- **Ages were attached by position and 94% were wrong.** `clean()` assigned
  `groupby(keys)["age"].first().to_numpy()` onto a frame built with
  `sort=False`; the orderings disagreed at every position, so 61,131 of 65,069
  player-seasons carried somebody else's age — 5.4 years out on average, 23 at
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
  and passed over. 1985 and 1994 were lost on one run — and 1985 is when
  Cristiano Ronaldo and Luka Modrić were born, so the awards check reported the
  holder of seven honours as a player the data had never seen. A year that fails
  whole is now re-asked in two halves by birth month, and an empty cohort is
  reported at WARNING.
- **Awards counted women's winners.** Several of these award items carry women's
  recipients on Wikidata, so Birgit Prinz, Carli Lloyd and Aitana Bonmatí
  arrived counted as winners the data had failed to find, when their absence is
  correct — women's football is a declared non-goal. Query now filters on `P21`.
- Identity resolution **83.9% → 89.3%** of 67,825 rows.
- Book preface still claimed Premier League–only coverage, which was Phase 1 text
  that survived Phase 2. Chapter prose and dashboard captions realigned to five
  leagues and the recomputed figures.

### Known issues

- Identity resolution is **89.3%**, against a 95% target. Remaining failures are
  players genuinely absent from Wikidata, plus transliteration variance
  (`Serhiy`/`Serhii`, `Alexander`/`Aliaksandr`). Modrić resolves only via the
  crosswalk; his sole non-English Wikidata label is Cyrillic and cannot be folded
  onto FBref's Latin spelling.
- `failure_summary` is near information-free by construction: a percentile gate
  eliminates exactly that share of the population on every requirement.
- Defenders remain unmeasurable. Top 50 qualifiers are 96% forwards, 4%
  midfielders, 0% defenders; the best defender ranks 122nd. FBref records no
  per-player defensive action before 2017-18. Cannavaro, the 2006 Ballon d'Or
  winner, ranks 2,707th and fails 8 of 11 requirements.

---

## [0.1.0] — 2026-08-10

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
