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
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)

import psutil  # noqa: E402
import soccerdata as sd  # noqa: E402

STAT_TYPES = ["standard", "shooting", "playing_time", "misc", "keeper"]
SEASONS = [f"{y:02d}{y + 1:02d}" for y in range(25)]
DATA = Path(__file__).resolve().parent.parent / "vault" / "raw" / "FBref"
BROWSERS = {"chrome.exe", "chromedriver.exe", "uc_driver.exe"}


def reap_browsers() -> int:
    """Kill this process's own browser descendants and report how many died.

    soccerdata's ``BaseSeleniumReader`` has ``_init_webdriver`` and **no close or
    quit method** — it opens browsers and never closes them, so ~40 Chrome
    processes accumulate per session and are only reclaimed when the owning
    process dies. Measured mid-run: Chrome held 5.42 GB while every DataFrame in
    flight held 0.31 GB.

    Reaping only our *own* descendants is what makes this safe to run while a
    second lane is scraping — a global Chrome kill would take down its live
    session, and killing the user's own browser along with it.
    """
    killed = 0
    for child in psutil.Process(os.getpid()).children(recursive=True):
        try:
            if child.name().lower() in BROWSERS:
                child.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    psutil.wait_procs(psutil.Process(os.getpid()).children(recursive=True), timeout=5)
    return killed


def main(league: str) -> int:
    started = time.perf_counter()
    failed: list[str] = []

    for stat in STAT_TYPES:
        # A fresh reader per table, with the previous one's browsers reaped, so
        # peak memory is one session rather than one per table for the league.
        try:
            reader = sd.FBref(leagues=league, seasons=SEASONS, data_dir=DATA)
            rows = len(reader.read_player_season_stats(stat_type=stat))
            print(
                f"[{league}] {stat}: {rows} rows ({(time.perf_counter() - started) / 60:.1f} min)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - log and continue
            failed.append(stat)
            print(f"[{league}] FAIL {stat}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
        finally:
            print(f"[{league}] reaped {reap_browsers()} browser processes", flush=True)

    for stat in list(failed):
        try:
            sd.FBref(leagues=league, seasons=SEASONS, data_dir=DATA).read_player_season_stats(
                stat_type=stat
            )
            failed.remove(stat)
            print(f"[{league}] RETRY OK {stat}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[{league}] RETRY FAIL {stat}: {type(exc).__name__}", flush=True)
        finally:
            reap_browsers()

    print(
        f"[{league}] DONE in {(time.perf_counter() - started) / 60:.1f} min, "
        f"{len(failed)} permanent failures {failed}",
        flush=True,
    )
    return 0


if __name__ == "__main__":  # Windows uses spawn; guard the entry point.
    raise SystemExit(main(sys.argv[1]))
