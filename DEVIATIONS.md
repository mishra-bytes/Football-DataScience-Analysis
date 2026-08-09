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

## 3. FBref scraping requires a Chrome installation

**Spec:** §10.2 assumed plain HTTP scraping with rate limiting.

**Reality:** soccerdata 1.9.1 drives `seleniumbase` with an undetected chromedriver to get past
Cloudflare. The driver is downloaded automatically on first use.

**Substitute:** None. Chrome is now a system prerequisite for live ingestion.

**Impact:** Scraping is slower than anticipated (~50 s per season, so ~21 minutes for 25
seasons) and cannot run on a machine without Chrome. Analysis is unaffected: everything
downstream reads Parquet, so only re-ingestion needs the browser.
