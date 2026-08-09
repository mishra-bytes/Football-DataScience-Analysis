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
