"""Capture a small real FBref sample as a test fixture.

Run once; the pickle is committed so tests never touch the network.
Two seasons 24 years apart prove `flatten` handles both ends of the range.
"""

from pathlib import Path

import soccerdata as sd

out = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
out.mkdir(parents=True, exist_ok=True)

fb = sd.FBref(leagues="ENG-Premier League", seasons=["0001", "2425"])
df = fb.read_player_season_stats(stat_type="standard")

# Take rows from both ends so both seasons are represented.
sample = df.groupby(level="season", group_keys=False).head(20)
sample.to_pickle(out / "fbref_raw.pkl")
print(f"wrote {len(sample)} rows, seasons: {sorted(sample.index.get_level_values('season').unique())}")
