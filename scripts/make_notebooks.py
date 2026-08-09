"""Scaffold the two Phase 1 notebooks.

Run once. The generated ``.ipynb`` files are the source of truth thereafter —
edit those, not this script. Building them through nbformat avoids hand-writing
notebook JSON, which is a reliable way to produce a corrupt file.
"""

from pathlib import Path

import nbformat as nbf

LABS = Path(__file__).resolve().parent.parent / "labs"
LABS.mkdir(exist_ok=True)


def build(path: Path, cells: list[tuple[str, str]]) -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(body) if kind == "md" else nbf.v4.new_code_cell(body)
        for kind, body in cells
    ]
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    nbf.write(nb, path)
    print(f"wrote {path.name} ({len(nb.cells)} cells)")


# --------------------------------------------------------------------------
# 01 — narrative
# --------------------------------------------------------------------------
NARRATIVE: list[tuple[str, str]] = [
    (
        "md",
        """# Who dominated the Premier League, 2000-2025?

Ask ten fans who the best Premier League player of the last twenty-five years
was and you will get ten answers, delivered with total confidence and almost no
shared definition of the question.

That is the real problem. "Best" is not one question, it is at least five:
best at their peak, best over a career, best per minute, best when it mattered,
best relative to the team around them. Those have *different answers*, and an
argument that does not say which one it means cannot be settled by evidence.

This notebook picks one definition and follows it all the way to a conclusion:

> **A player's rating is their best five consecutive seasons of goals and
> assists per 90 minutes, measured against the players they actually played
> against, discounted when the sample is small.**

That is a choice, not a discovery. By the end you will be able to see exactly
which parts of the answer depend on it.""",
    ),
    (
        "code",
        """import warnings

import matplotlib
import pandas as pd

from gambeta import tifo

warnings.filterwarnings("ignore")
matplotlib.rcParams["figure.figsize"] = (8, 5)

SAMPLE = "../data/sample"
seasons = pd.read_parquet(f"{SAMPLE}/player_season_scored.parquet")
ratings = pd.read_parquet(f"{SAMPLE}/peak5.parquet")

first = tifo.season_label(seasons["season"].min())
last = tifo.season_label(seasons["season"].max())

print(f"{len(seasons):,} player-seasons")
print(f"{seasons['season'].nunique()} seasons: {first} to {last}")
print(f"{seasons['player_id'].nunique():,} distinct players")""",
    ),
    (
        "md",
        """## What is in the data, and what is not

Before any analysis, an honest inventory. This is the single most skipped step
in data science and the one that causes the most wrong conclusions.

**Present:** goals, assists, minutes, appearances, cards, club, season — for
every player in every Premier League season from 2000-01 to 2024-25.

**Absent, and unavailable at any price:** expected goals, progressive passes,
shot-creating actions, defensive actions, pressures. None of it was recorded
before 2017-18. This is why the rating uses goals and assists: not because they
are the best measure of a footballer, but because they are the only measure that
exists across the whole period. A metric available for one era and not another
cannot compare them.

**A consequence worth stating loudly:** this rating measures attacking output.
It will rank a good striker above a great centre-back, every time. That is a
known bias, not a hidden one.""",
    ),
    ("code", """seasons.head()"""),
    (
        "md",
        """## The naive answer, and why it is wrong

Start with the obvious approach: rank by raw goals and assists per 90 minutes.

Watch what happens.""",
    ),
    (
        "code",
        """naive = (
    seasons[seasons["minutes"] >= 900]
    .nlargest(10, "ga_p90")[["player", "season", "minutes", "ga_p90"]]
    .assign(season=lambda d: d["season"].map(tifo.season_label))
)
naive""",
    ),
    (
        "md",
        """Now look at *which seasons* those come from. Scoring rates are not stable
across twenty-five years — the league changes. If goals are easier to come by in
2024 than in 2004, a raw per-90 ranking is partly a list of who played recently.""",
    ),
    (
        "code",
        """by_season = (
    seasons[seasons["minutes"] >= 900]
    .groupby("season")["ga_p90"]
    .agg(["mean", "std", "count"])
    .rename(columns={"mean": "league mean G+A/90", "std": "spread", "count": "players"})
)
by_season.index = [tifo.season_label(s) for s in by_season.index]
by_season.round(3)""",
    ),
    (
        "code",
        """ax = by_season["league mean G+A/90"].plot(
    marker="o", color=tifo.LIGHT["accent"], linewidth=2, markersize=6
)
ax.set_title("League-average goals + assists per 90, by season",
             loc="left", fontweight="bold", fontsize=12)
ax.set_xlabel("Season")
ax.set_ylabel("G+A per 90")
ax.tick_params(axis="x", rotation=60)
ax.figure.tight_layout()""",
    ),
    (
        "md",
        """The baseline moves. Any ranking built on raw rates is therefore comparing
players partly on *when they happened to play*, which is not a football
achievement.

## The fix: measure against contemporaries

The standard answer is to express each player's rate as a **standard score**
within their own season — how far above or below their peers they were, in units
of the spread among those peers. A player two standard deviations above the mean
in 2004 and one two standard deviations above the mean in 2024 were equally
dominant *relative to the football being played around them*.

The method is derived properly in the [z-scores chapter](02-z-scores-across-eras.ipynb).
Here we just use it and check that it did what we wanted.""",
    ),
    (
        "code",
        """check = (
    seasons.groupby("season")["ga_p90_z"]
    .agg(["mean", "std"])
    .round(6)
)
print("Every season now centres on zero:")
print(f"  largest absolute season mean: {check['mean'].abs().max():.2e}")
print(f"  season spreads range from {check['std'].min():.3f} to {check['std'].max():.3f}")""",
    ),
    (
        "md",
        """## The ranking

Applying the peak-five-consecutive-seasons definition to the normalized scores.

The bars are 95% bootstrap confidence intervals — a measure of how much the
answer would wobble if the same career had been played again with the same
underlying ability. **Where two players' bars overlap substantially, the data
does not separate them**, and saying one is better than the other is opinion
wearing a number.""",
    ),
    (
        "code",
        """ratings.head(15).assign(
    start=lambda d: d["start_season"].map(tifo.season_label),
    end=lambda d: d["end_season"].map(tifo.season_label),
)[["player", "score", "lo", "hi", "start", "end", "seasons_used"]].round(3)""",
    ),
    ("code", """fig = tifo.ranked_dots(ratings, top=20)"""),
    (
        "md",
        """## Where the data refuses to decide

This is the part most rankings hide. Two players whose intervals overlap are not
ranked by the evidence — they are ranked by rounding.

Below, every pair in the top ten whose intervals overlap. For those pairs, the
honest statement is "indistinguishable", not "7th and 8th".""",
    ),
    (
        "code",
        """top10 = ratings.head(10).reset_index(drop=True)
overlaps = [
    (top10.loc[i, "player"], top10.loc[j, "player"])
    for i in range(len(top10))
    for j in range(i + 1, len(top10))
    if top10.loc[i, "lo"] <= top10.loc[j, "hi"] and top10.loc[j, "lo"] <= top10.loc[i, "hi"]
]
print(f"{len(overlaps)} indistinguishable pairs in the top ten:")
for a, b in overlaps[:12]:
    print(f"  {a}  <->  {b}")""",
    ),
    (
        "md",
        """## What would change my mind

A conclusion is only worth as much as the conditions under which the author
would abandon it. Mine, specifically:

1. **Add defensive contribution.** The rating is attacking output. A version that
   valued ball recovery, duels and progressive defending would rank different
   players, and I would expect defenders and holding midfielders to move up
   sharply. The current answer is "best attacking contributor", stated as "best
   player" only because the alternative data does not exist before 2017.

2. **Weight longevity over peak.** Peak-five deliberately ignores what a player
   did outside their best window. A career-total lens would favour players with
   fifteen good seasons over those with five extraordinary ones, and that is a
   defensible preference I simply did not choose here.

3. **Include other competitions.** A Premier League–only rating cannot see the
   Champions League or international football. Players whose defining
   performances happened elsewhere are invisible to it.

4. **Adjust for team strength.** Playing in a dominant side inflates goals and
   assists. Strength-of-schedule data is ingested but not yet used by this lens;
   folding it in would compress the advantage of players at the strongest clubs.

If someone disagrees with the ranking, the productive question is not "is this
wrong" but **"which of these four would you change, and why"**. That is an
argument that can actually make progress.""",
    ),
]

# --------------------------------------------------------------------------
# 02 — method
# --------------------------------------------------------------------------
METHOD: list[tuple[str, str]] = [
    (
        "md",
        """# Z-scores across eras, and what they hide

*A method chapter. Structure: Question → Intuition → Math → Code → Assumptions →
How it breaks.*""",
    ),
    (
        "md",
        """## 1. Question

How do you compare a striker from 2003 with one from 2024, when the game they
played was not the same game?

Concretely: in some seasons goals are plentiful and in others they are scarce.
A player who scored 0.8 goals per 90 in a low-scoring season may have been more
dominant than one who scored 0.9 in a high-scoring one. Raw rates cannot see
this. We need a number that means "how far ahead of your peers were you".""",
    ),
    (
        "md",
        """## 2. Intuition

Stop measuring in goals and start measuring in **peers**.

If the typical player in your league scored 0.30 goals per 90 that season, and
the spread among players was about 0.15, then scoring 0.60 puts you two spreads
above typical. Do the same arithmetic in a different season with different
numbers and "two spreads above typical" still means the same thing: you were
unusually good by the standards of the football around you.

The unit travels across eras even though goals do not. That is the whole idea.""",
    ),
    (
        "md",
        r"""## 3. Math

For player $i$ in season $s$, with rate $x_{is}$:

$$z_{is} = \frac{x_{is} - \mu_s}{\sigma_s}$$

where $\mu_s$ and $\sigma_s$ are the mean and standard deviation of the rate
across all players in season $s$.

**Choice: population, not sample standard deviation** ($\sigma$ with $N$ in the
denominator, `ddof=0`). A season is not a sample drawn from some larger
population of that season — it is every player who played it. The whole
population is in hand, so the population formula is the correct one. With ~500
players per season the numerical difference is negligible, but the reasoning
matters more than the digits.

**The small-sample problem.** A player with 200 minutes who happened to score
twice gets a spectacular rate and therefore a spectacular $z$. This is noise, not
ability. We discount it by shrinking toward zero in proportion to playing time:

$$\hat{z}_{is} = z_{is} \cdot \frac{m_{is}}{m_{is} + m_0}$$

where $m_{is}$ is minutes played and $m_0$ is a prior strength, also in minutes.
The weight $m/(m + m_0)$ runs from 0 (no minutes, no claim) to 1 (many minutes,
take the number at face value), passing through exactly $1/2$ at $m = m_0$.

We use $m_0 = 900$ — ten full matches. A player with ten matches is credited with
half of what their raw score claims, which is about right for how much you should
believe ten games.""",
    ),
    (
        "md",
        """## 4. Code

Small enough to check by hand.""",
    ),
    (
        "code",
        """import numpy as np
import pandas as pd

from gambeta import level

toy = pd.DataFrame({
    "league": ["L"] * 4,
    "season": ["0001"] * 4,
    "player_id": list("abcd"),
    "ga_p90": [0.2, 0.4, 0.6, 0.8],
    "minutes": [3000, 3000, 3000, 3000],
})

out = level.zscore(toy, ["ga_p90"])
out[["player_id", "ga_p90", "ga_p90_z"]]""",
    ),
    (
        "md",
        """Check by hand: the mean of 0.2, 0.4, 0.6, 0.8 is 0.5. The population standard
deviation is

$$\\sigma = \\sqrt{\\tfrac{1}{4}\\left((0.3)^2 + (0.1)^2 + (0.1)^2 + (0.3)^2\\right)}
= \\sqrt{0.05} \\approx 0.2236$$

So player `d` scores $(0.8 - 0.5)/0.2236 \\approx 1.342$. Confirm:""",
    ),
    (
        "code",
        """expected = (0.8 - 0.5) / np.sqrt(0.05)
actual = out.loc[out["player_id"] == "d", "ga_p90_z"].item()
print(f"by hand: {expected:.6f}")
print(f"gambeta: {actual:.6f}")
assert np.isclose(expected, actual)""",
    ),
    (
        "md",
        """Now shrinkage. The same score, held by players with very different amounts of
football behind it:""",
    ),
    (
        "code",
        """minutes = np.array([90.0, 450.0, 900.0, 1800.0, 3600.0])
shrunk = level.shrink(np.full(5, 2.0), minutes, prior_minutes=900.0)

pd.DataFrame({
    "minutes": minutes.astype(int),
    "raw z": 2.0,
    "weight": (minutes / (minutes + 900.0)).round(3),
    "shrunk z": shrunk.round(3),
})""",
    ),
    (
        "md",
        """One match of brilliance retains a tenth of its claim. Twenty matches retain
half. Forty matches retain four-fifths. Nothing is thrown away, and nothing
small is believed.""",
    ),
    (
        "md",
        """## 5. Assumptions

Each of these could be false, and each would bite differently.

1. **Within-season distributions are comparable in shape.** A z-score of 2.0 means
   the same thing in 2004 and 2024 only if both seasons' rate distributions are
   similarly shaped. If one season is heavily skewed and the other is not, the
   same z corresponds to different percentiles.

2. **The competitive spread is stable.** Standardising divides by the spread, so a
   season where players are unusually similar inflates everyone's z-scores. If the
   league grew more unequal over time, this method partly measures inequality
   rather than ability.

3. **Minutes are a good proxy for sample size.** Shrinkage assumes 900 minutes of
   a defender and 900 minutes of a striker carry the same evidential weight for
   attacking output. They plainly do not.

4. **The population is the right comparison set.** We standardise against all
   players, including goalkeepers and centre-backs who are not trying to score.
   That drags the mean down and inflates every attacker's z-score. Standardising
   within position would be more defensible; it is not done here, and it is a
   real weakness rather than a rounding detail.""",
    ),
    (
        "md",
        """## 6. How it breaks

The failure worth understanding is that **a single outlier suppresses everyone,
including the outlier.**

The standard deviation is in the denominator. One extraordinary season inflates
it, which shrinks every z-score in that season — so a historically great campaign
can make itself, and everyone around it, look more ordinary.

Watch it happen.""",
    ),
    (
        "code",
        """normal = pd.DataFrame({
    "league": ["L"] * 5, "season": ["0001"] * 5,
    "player_id": list("abcde"),
    "ga_p90": [0.20, 0.30, 0.40, 0.50, 0.90],
    "minutes": [3000] * 5,
})

# Same league, except the best player has a genuinely historic season.
outlier = normal.copy()
outlier.loc[outlier["player_id"] == "e", "ga_p90"] = 2.50

a = level.zscore(normal, ["ga_p90"]).set_index("player_id")["ga_p90_z"]
b = level.zscore(outlier, ["ga_p90"]).set_index("player_id")["ga_p90_z"]

pd.DataFrame({"z (normal season)": a.round(3), "z (with an outlier)": b.round(3)})""",
    ),
    (
        "md",
        """Player `d` scored exactly 0.50 goals per 90 in both worlds. Their football did
not change at all. But their z-score *fell*, because someone else had a
spectacular year and widened the yardstick.

That is not a bug in the arithmetic — it is what standardisation means. But it
has a real consequence for this project: **a season containing a historic
individual campaign will systematically under-rate everyone in it, including the
player who produced it.**

### What to do about it

Three options, in increasing order of effort:

- **Report it.** State that z-scores are relative and that outlier seasons
  compress the field. Cheapest, and better than silence.
- **Use a robust scale.** Replace the standard deviation with the median absolute
  deviation, which a single extreme value barely moves.
- **Model it properly.** A hierarchical model estimates season effects and player
  ability jointly, so an outlier is explained as an unusual player rather than
  absorbed into the season's yardstick. This is the Phase 3 direction.

Phase 1 does the first. Knowing which one you are doing, and why, is the
difference between using a method and trusting it.""",
    ),
]

if __name__ == "__main__":
    build(LABS / "01-who-dominated-the-premier-league.ipynb", NARRATIVE)
    build(LABS / "02-z-scores-across-eras.ipynb", METHOD)
