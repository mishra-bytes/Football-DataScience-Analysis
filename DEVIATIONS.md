# Deviations from the design spec

Each entry records a point where implementation could not follow
`docs/superpowers/specs/2026-08-10-gambeta-design.md`, what was done instead, and the impact.

## 1. Identity resolution does not use an FBref-ID key join

**Spec:** §8.2 — "Join FBref data on `fbref_id` — an exact key join, not fuzzy matching."

**Reality:** `FBref.read_player_season_stats()` returns the player *name* as part of the row
index. No FBref player ID is exposed by any season-level method in soccerdata 1.9.1.

**Substitute:** Match on `(normalized_name, born)` and enrich with a Wikidata QID where both the
normalized name and the birth year agree.

**Impact:** Identity is probabilistic rather than exact. Measured on a four-season sample of
1,859 distinct players, only 3 names collided, and all 3 were separated by birth year.
Unresolved players are written to `vault/clean/unresolved.csv` and reported — never dropped.

## 2. No Champions League data available

**Spec:** D3 — competitions are "Big 5 domestic leagues + UCL + internationals".

**Reality:** `FBref.available_leagues()` returns no Champions League entry. Available leagues are
the Big 5, `Big 5 European Leagues Combined`, `INT-World Cup`, `INT-European Championship`, and
`INT-Women's World Cup`.

**Substitute:** None needed — UCL is outside Phase 1 scope regardless.

**Impact:** Phase 2 will need a custom `league_dict.json` for soccerdata to reach UCL data, or
the `biggame` lens must be restricted to international tournaments. Flagged now so Phase 2
planning accounts for it.

## 3. CuPy needs the `[ctk]` extra on a machine without a CUDA toolkit

**Spec:** §7 — `cupy-cuda12x` as the GPU optional extra.

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

**Spec:** §6.3 — "best five *consecutive* seasons", with no stated floor.

**Reality:** On real data the lens ranked Patrick Bamford 9th, Edinson Cavani 10th and
Zlatan Ibrahimović 12th — each on a **single season**, each with `lo == hi == score`. Two
failures at once: a one-season "best five consecutive seasons" is a category error, and
bootstrapping one observation returns a zero-width interval that renders as perfect confidence
on the least reliable estimate in the table.

**Substitute:** `Config.min_seasons = 3`. Players whose longest consecutive run is shorter are
excluded from the rating, mirroring the existing `min_minutes` threshold rather than inventing a
new mechanism.

**Impact:** 2,428 ranked players becomes 965. No zero-width intervals remain (asserted by test).
Players with genuinely short Premier League careers — Haaland has three seasons — still rank,
but nobody is ranked on a sample of one.

## 6. Quarto book config lives at the repository root

**Spec:** §5.1 — book files under `tome/`.

**Reality:** Quarto cannot reliably reference chapters above its project directory, and it
requires the book home page to be `index.qmd` at the project root.

**Substitute:** `_quarto.yml` and `index.qmd` sit at the repository root; `tome/` keeps the
remaining book sources and receives the rendered output in `tome/_book`.

**Impact:** Two extra files at the repository root. The alternative — duplicating notebooks into
`tome/` — would have broken the single-source-of-truth rule in §5.2.

---

# Gate results

Measured on the real run, 2026-08-10. Recorded whether or not they cleared, per the agreed
policy of reporting honestly rather than stopping.

| Definition-of-done item | Target | Measured | Result |
|---|---|---|---|
| 1. Schema-validated Parquet with manifests | — | 13,724 rows, 25/25 seasons, no gaps | **PASS** |
| 2. Identity resolution | ≥ 95% | **96.8%** (179 players unresolved, all listed) | **PASS** |
| 3. Ranking with bootstrap intervals | — | 965 players, 0 zero-width intervals | **PASS** |
| 4. CuPy/NumPy parity | asserted | test executed, not skipped | **PASS** |
| 5. Notebooks execute; book builds | — | 2 notebooks, 0 errors, 4 pages rendered | **PASS** |
| 6. Streamlit runs against Parquet | — | health `ok`, main page HTTP 200 | **PASS** |
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
signal per season — more metrics, not more seasons.

---

# Benchmarks

Spec §7 forbids GPU code without a measurement. Bootstrap, 10,000 resamples,
RTX 4050 Laptop (6 GB) against a Ryzen CPU:

| Array size | CPU | Auto-dispatch | Speedup | Path taken |
|---|---|---|---|---|
| 5 | 0.001 s | 0.000 s | — | CPU (below `GPU_MIN_ELEMENTS`) |
| 2,000 | 0.159 s | 0.015 s | 10.6x | GPU |
| 20,000 | 1.927 s | 0.128 s | 15.1x | GPU |

The floor is doing real work: `lens.peak5` bootstraps careers of 2-5 seasons,
thousands of times. Dispatching those to the GPU would be slower than NumPy, so
`doubt.GPU_MIN_ELEMENTS` keeps them on the CPU.
