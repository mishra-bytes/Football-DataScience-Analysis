"""Warm the FBref cache for the Champions League, one page at a time.

soccerdata does not ship the Champions League: its FBref reader knows the Big 5
plus the World Cup and the Euros. Registering it takes one entry in
``league_dict.json``, and the entry has to name the competition exactly as
FBref's index does, which is **"UEFA Champions League"** and not "Champions
League". Getting that string wrong returns an empty frame rather than an error,
which cost an afternoon.

Run this before ``gambeta all``. It only fetches what is missing, so it is safe
to re-run after an interruption, and each page lands in the same
``vault/raw/FBref`` cache the domestic scrape uses.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gambeta import kit  # noqa: E402
from gambeta.scouts.fbref import SIDE_TABLES, UCL_FBREF_NAME, UCL_LEAGUE, register_ucl  # noqa: E402

log = logging.getLogger("warm_ucl")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = kit.load()
    register_ucl()

    import soccerdata as sd

    tables = ["standard", *SIDE_TABLES, "keeper"]
    total = len(cfg.seasons) * len(tables)
    done = 0
    for season in cfg.seasons:
        for table in tables:
            done += 1
            try:
                reader = sd.FBref(leagues=UCL_LEAGUE, seasons=season, data_dir=cfg.raw / "FBref")
                frame = reader.read_player_season_stats(stat_type=table)
                log.info("[%3d/%d] %s %s -> %d rows", done, total, season, table, len(frame))
            except Exception as exc:  # noqa: BLE001
                # A missing table for one season is expected: FBref did not
                # publish `misc` for every early Champions League campaign.
                log.warning("[%3d/%d] %s %s -> %s", done, total, season, table, exc)

    registered = json.loads(
        (Path.home() / "soccerdata" / "config" / "league_dict.json").read_text()
    )
    log.info("done. %s registered as %r", UCL_LEAGUE, registered[UCL_LEAGUE]["FBref"])
    assert registered[UCL_LEAGUE]["FBref"] == UCL_FBREF_NAME


if __name__ == "__main__":
    main()
