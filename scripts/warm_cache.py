"""Warm the soccerdata cache for one league: all 25 seasons, all five stat types.

    python scripts/warm_cache.py "ESP-La Liga"

**One reader per league, not per fetch.** soccerdata drives a real browser to get
past Cloudflare, and constructing a reader per (season, stat) pair opens a new
browser session each time — 125 of them per league. Doing that for five leagues
at once exhausted 15 GB of RAM and slowed each fetch from ~30 s to ~250 s. A
single reader takes the whole season list and reuses one session, so this script
opens five sessions per league instead of 125.

Everything downstream reads the cache, so `gambeta scrape` afterwards is fast and
offline. Failures are logged and retried once rather than aborting the run.
"""

from __future__ import annotations

import logging
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)

import soccerdata as sd  # noqa: E402

STAT_TYPES = ["standard", "shooting", "playing_time", "misc", "keeper"]
SEASONS = [f"{y:02d}{y + 1:02d}" for y in range(25)]
DATA = Path(__file__).resolve().parent.parent / "vault" / "raw" / "FBref"


def main(league: str) -> int:
    started = time.perf_counter()
    reader = sd.FBref(leagues=league, seasons=SEASONS, data_dir=DATA)
    failed: list[str] = []

    for stat in STAT_TYPES:
        try:
            rows = len(reader.read_player_season_stats(stat_type=stat))
            print(
                f"[{league}] {stat}: {rows} rows ({(time.perf_counter() - started) / 60:.1f} min)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - log and continue
            failed.append(stat)
            print(f"[{league}] FAIL {stat}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)

    for stat in list(failed):
        try:
            reader.read_player_season_stats(stat_type=stat)
            failed.remove(stat)
            print(f"[{league}] RETRY OK {stat}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[{league}] RETRY FAIL {stat}: {type(exc).__name__}", flush=True)

    print(
        f"[{league}] DONE in {(time.perf_counter() - started) / 60:.1f} min, "
        f"{len(failed)} permanent failures {failed}",
        flush=True,
    )
    return 0


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    raise SystemExit(main(sys.argv[1]))
