"""Scaffold the project notebooks.

Run once. The generated ``.ipynb`` files are the source of truth thereafter —
edit those, not this script. Building them through nbformat avoids hand-writing
notebook JSON, which is a reliable way to produce a corrupt file.
"""

from pathlib import Path

import nbformat as nbf

LABS = Path(__file__).resolve().parent.parent / "labs"
LABS.mkdir(exist_ok=True)

SETUP = """import warnings

import matplotlib
import numpy as np
import pandas as pd

from gambeta import needs, tifo

warnings.filterwarnings("ignore")
matplotlib.rcParams["figure.figsize"] = (10, 5.5)

SAMPLE = "../data/sample"
ranking = pd.read_parquet(f"{SAMPLE}/ranking.parquet")
seasons = pd.read_parquet(f"{SAMPLE}/player_season_scored.parquet")
offsets = pd.read_parquet(f"{SAMPLE}/league_offsets.parquet")
keepers = pd.read_parquet(f"{SAMPLE}/keeper_ranking.parquet")"""


def build(path: Path, cells: list[tuple[str, str]]) -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(body) if kind == "md" else nbf.v4.new_code_cell(body)
        for kind, body in cells
    ]
    nb.metadata = {
        "kernelspec": {
            "display_name": "gambeta (.venv 3.12)",
            "language": "python",
            "name": "gambeta",
        },
        "language_info": {"name": "python", "version": "3.12"},
    }
    nbf.write(nb, path)
    print(f"wrote {path.name} ({len(nb.cells)} cells)")


# --------------------------------------------------------------------------
NARRATIVE: list[tuple[str, str]] = [
    (
        "md",
        """# Who is the best footballer of the last 25 years?

Most arguments about the greatest player are not disagreements about facts. They
are disagreements about **what the question means**, conducted as though they
were about facts. One person means peak. Another means longevity. A third means
trophies. Nobody says which, so nobody can be wrong, and nobody moves.

This project takes a different route. Instead of arguing about the answer, it
writes down **what greatness requires** — eleven things a player must have — and
then asks who has all of them.

A player who fails any single requirement is, by this definition, not the best.
And which requirement they failed is published, so the definition can be argued
with rather than simply asserted.""",
    ),
    (
        "code",
        SETUP
        + """

first = tifo.season_label(seasons["season"].min())
last = tifo.season_label(seasons["season"].max())

print(f"{len(ranking):,} players ranked")
print(f"{len(seasons):,} player-seasons")
print(f"leagues: {', '.join(sorted(seasons['league'].unique()))}")
print(f"seasons: {first} to {last}")""",
    ),
    (
        "md",
        """## The eleven requirements

Each is measured across every season and every league, then pooled per player
weighted by minutes. All are oriented so that **higher is better** — including
discipline, which is negated at source so a clean player scores above a dirty
one without any downstream code needing to know the direction.""",
    ),
    (
        "code",
        """pd.DataFrame(
    [{"#": i + 1, "requirement": r.label, "key": r.key, "grain": r.kind}
     for i, r in enumerate(needs.OUTFIELD)]
).set_index("#")""",
    ),
    (
        "md",
        """## Gate first, then rank

"Must have" is read literally. A player has to clear the 40th percentile on
**all eleven** requirements to qualify at all. Only then are qualifiers ranked.

A weighted average alone would let a player be genuinely poor at something the
list calls mandatory and still win on volume elsewhere. The gate is what stops
that.""",
    ),
    (
        "code",
        """qualified = ranking[ranking["qualified"]]
print(f"{len(qualified)} of {len(ranking):,} players clear all eleven requirements "
      f"({100 * len(qualified) / len(ranking):.1f}%)")

qualified.head(15)[["player", "score", "seasons", "leagues"]].round(2)""",
    ),
    (
        "code",
        """fig = tifo.ranked_dots(
    qualified.assign(lo=qualified["score"], hi=qualified["score"]),
    top=20,
    title="Who has all eleven",
    subtitle="Composite of eleven requirements, era- and league-adjusted.",
)""",
    ),
    (
        "md",
        """## A career is not league-bound

Look at the `leagues` column. Ronaldo's career is England, Spain and Italy —
nineteen seasons pooled into one player, not three separate league careers.

This is the single most important structural decision in the project. Ranking
"the best player in a league" answers a different and much less interesting
question, and it makes players who moved impossible to evaluate.""",
    ),
    (
        "code",
        """multi = qualified[qualified["leagues"].str.contains(",")]
print(f"{len(multi)} of the {len(qualified)} qualifiers played in more than one league\\n")
multi.head(10)[["player", "score", "seasons", "leagues"]].round(2)""",
    ),
    (
        "md",
        """## Who fails, and on what

This is the part most rankings hide. A great player missing the cut is more
informative than one making it, because it tells you exactly where the
definition bites.""",
    ),
    (
        "code",
        """near = ranking[~ranking["qualified"]].copy()
near["missed"] = near["failed"].fillna("").apply(lambda s: len(s.split(", ")) if s else 0)

one = near[near["missed"] == 1].nlargest(12, "score")
one[["player", "score", "seasons", "failed"]].round(2)""",
    ),
    ("code", """pd.read_csv(f"{SAMPLE}/failures.csv").head(11)"""),
    (
        "md",
        """## Goalkeepers, judged on their own job

Keepers score zero on goals and assists, so under an attacking rating they rank
near the bottom — meaninglessly. They get a parallel list of eight requirements
built from save percentage, clean sheets and goals conceded.

They are **not** claimed to be comparable with outfielders. Two leaderboards, no
combined number, because the data cannot support one.""",
    ),
    (
        "code",
        """kq = keepers[keepers["qualified"]]
print(f"{len(kq)} of {len(keepers)} keepers qualify\\n")
kq.head(10)[["player", "score", "seasons", "leagues"]].round(2)""",
    ),
    (
        "md",
        """## What would change my mind

A conclusion is worth what its author would abandon it for. Mine:

1. **Defensive contribution.** FBref records no per-player defensive action
   before 2017-18, so a centre-back is invisible to requirements 1–6. This is an
   attacking-contribution rating and is named as such. Real defensive data would
   change the list completely.
2. **The gate height.** The 40th percentile is a judgement call. Raising it to 50
   would disqualify players currently sitting just inside.
3. **The weights.** Every requirement counts equally right now. Anyone who
   thinks scoring matters more than availability can say so numerically, and the
   ranking will move.
4. **Missing football.** No Champions League, no internationals, and nothing
   outside the Big 5. Careers at Sporting, Al-Nassr or Inter Miami are invisible.

The productive question is not "is this wrong" but **"which of these four would
you change, and to what"** — an argument that can actually make progress.""",
    ),
]

# --------------------------------------------------------------------------
BELL: list[tuple[str, str]] = [
    (
        "md",
        """# How far ahead is the best player?

A ranking tells you the order. It does not tell you the *gap*. Second place
might be a whisker behind or a chasm.

This chapter measures the gap properly, by looking at where every player sits in
the distribution and asking how many standard deviations separate the best from
everyone else.""",
    ),
    (
        "code",
        SETUP
        + """

scores = ranking["score"].to_numpy(dtype=float)
mu, sigma = scores.mean(), scores.std(ddof=0)
print(f"players: {len(scores):,}")
print(f"mean:    {mu:.3f}")
print(f"sd:      {sigma:.3f}")""",
    ),
    (
        "md",
        """## The distribution

Most players cluster near the middle. That is what a composite of eleven
standardised requirements should do — by construction the average player scores
about zero.

The interesting part is the right tail.""",
    ),
    (
        "code",
        """top5 = ranking.head(5)
fig = tifo.bell(
    ranking["score"],
    highlight=dict(zip(top5["player"], top5["score"], strict=True)),
    title="Every player, and how far out the best sit",
)""",
    ),
    (
        "md",
        """## Measuring the gap in sigma

A standard deviation is a natural yardstick here: it says how unusual a score is
*relative to the spread of the population itself*, so it travels across
different metrics and different eras.""",
    ),
    (
        "code",
        """head = ranking.head(10).copy()
head["sigma"] = (head["score"] - mu) / sigma
head[["player", "score", "sigma", "seasons"]].round(2)""",
    ),
    (
        "md",
        """## The claim that should make you suspicious

Under a normal distribution, extreme values are astronomically rare. Let us take
that assumption seriously and see what it predicts.""",
    ),
    (
        "code",
        """from math import erfc, sqrt

best = ranking.iloc[0]
z = (best["score"] - mu) / sigma
p = erfc(z / sqrt(2)) / 2

print(f"{best['player']} sits {z:.2f} standard deviations above the mean.")
print(f"Under a normal distribution, P(score >= that) = {p:.3e}")
print(f"That is roughly 1 player in {1 / p:,.0f}.")
print(f"\\nOur population is {len(scores):,} players.")""",
    ),
    (
        "md",
        """**One in six hundred million, from a pool of five and a half thousand.**

Taken at face value this says the best player should not exist. Something is
wrong with the assumption, not with the footballer.

## The assumption is wrong: the distribution is not normal

A normal distribution is symmetric. Football talent is not.""",
    ),
    (
        "code",
        """print(f"skewness: {pd.Series(scores).skew():.2f}   (0 = symmetric)")
print(f"kurtosis: {pd.Series(scores).kurtosis():.2f}   (0 = normal tails)")

for k in (2, 3, 4, 5, 6):
    expected = len(scores) * erfc(k / sqrt(2)) / 2
    actual = int((scores > mu + k * sigma).sum())
    print(f"  beyond {k} sigma: normal predicts {expected:8.2f}, we observe {actual:4d}")""",
    ),
    (
        "md",
        """The right tail is **much fatter than normal**. At three, four and five sigma
there are many more players than a bell curve allows.

This is not a defect in the data. It is a real property of elite performance,
and it has a name — a heavy-tailed distribution. Ability that compounds
(better players get better coaching, better teammates, more minutes, better
opponents to learn from) does not produce a symmetric bell. It produces a long
right tail where a handful of people are far beyond everyone else.

**So the honest statement is not "Messi is a 5.9-sigma player" as if that were a
probability.** It is: *under the wrong model he is impossible, and the fact that
he exists is evidence the model is wrong.*

## The gap between first and second

Sigma is still useful for comparison, as long as it is used as a ruler rather
than a probability.""",
    ),
    (
        "code",
        """gaps = ranking.head(6)[["player", "score"]].copy()
gaps["sigma"] = (gaps["score"] - mu) / sigma
gaps["gap_to_next"] = gaps["score"].diff(-1)
gaps.round(2)""",
    ),
    (
        "code",
        """first, second = ranking.iloc[0], ranking.iloc[1]
gap_sigma = (first["score"] - second["score"]) / sigma
print(f"{first['player']} to {second['player']}: {gap_sigma:.2f} sigma")
print(f"{second['player']} to {ranking.iloc[5]['player']}: "
      f"{(second['score'] - ranking.iloc[5]['score']) / sigma:.2f} sigma "
      f"(covering four players)")""",
    ),
    (
        "md",
        """## The result, stated in players rather than decimals

A lead of 0.39 means nothing on its own. The way to feel it is to take the gap
between first and second, lay it below someone else, and see **who you land
on**.""",
    ),
    (
        "code",
        '''q = ranking[ranking["qualified"]].reset_index(drop=True)
lead = q.loc[0, "score"] - q.loc[1, "score"]


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def named(i: int) -> str:
    return f"{q.loc[i, 'player']} ({ordinal(i + 1)})"


def same_distance_below(rank: int) -> int:
    """Index of the player sitting as far below `rank` as second sits below first."""
    target = q.loc[rank, "score"] - lead
    return int((q["score"] - target).abs().idxmin())


below_second = same_distance_below(1)
below_third = same_distance_below(2)

print(
    f"{named(1)} is as close to {named(0)}\\n"
    f"  as {named(below_second)} is to {named(1)},\\n"
    f"  or {named(below_third)} is to {named(2)}."
)
print(f"\\n(every one of those gaps is {lead:.2f}, or {lead / sigma:.1f} sigma)")''',
    ),
    (
        "md",
        """Read that again, because it is the finding of this chapter. The distance from
second place to first is not a photo finish — it is the same distance that
separates second place from a player **six** positions further down, and third
place from one **six** positions down.

One more way to put it: compare the lead at the top against the entire spread of
the chasing pack.""",
    ),
    (
        "code",
        """chasers = q.loc[1, "score"] - q.loc[7, "score"]
print(f"first to second:  {lead:.2f}")
print(f"second to eighth: {chasers:.2f}   (covering six players)")
print()
print("The lead of one player over the next is larger than the spread"
      if lead > chasers else "The chasing pack is more spread out than the lead")
print("across the whole of the chasing pack.")""",
    ),
    (
        "md",
        """The top of this list is not a tight race followed by a drop-off. It is one
player clear, then a cluster.

## Where each requirement puts the best player

The composite hides which requirements the gap comes from. Breaking it out shows
whether dominance is broad or narrow.""",
    ),
    (
        "code",
        """keys = [r.key for r in needs.OUTFIELD if r.key in ranking.columns]
profile = ranking.set_index("player").loc[
    [ranking.iloc[0]["player"], ranking.iloc[1]["player"]], keys
].T
profile.columns = [f"{c} (sigma)" for c in profile.columns]
profile.round(2)""",
    ),
    (
        "md",
        """## What would change my mind

- **A different composite.** These sigma figures are for the equal-weighted
  composite. Reweight the requirements and the gap changes.
- **The population defines the yardstick.** Sigma is measured against 5,508
  players who cleared the minutes threshold in the Big 5. Lower that threshold to
  include fringe players, or add a competition, and the standard deviation
  moves — which moves everyone's sigma.
- **Heavy tails cut both ways.** If the distribution is not normal, sigma is a
  descriptive ruler and nothing more. Any sentence of the form "this is a
  one-in-N-billion player" is misusing it, including one I could easily have
  written above.""",
    ),
]

# --------------------------------------------------------------------------
METHOD_GATE: list[tuple[str, str]] = [
    (
        "md",
        """# Method: requirements, gates, and a metric that rewarded mediocrity

*Question → Intuition → Math → Code → Assumptions → How it breaks*""",
    ),
    (
        "md",
        """## 1. Question

Given a list of things greatness requires, how do you combine them into one
ranking without letting a player be terrible at one of them and win anyway?

## 2. Intuition

Two obvious options, and they behave very differently.

**Average them.** Simple, robust, familiar. But it permits compensation: score
enough goals and it no longer matters that you are never available.

**Gate on them.** Require a minimum on every requirement, then rank whoever
clears the bar. This takes "must have" literally.

The project gates, because the word "must" was in the definition.""",
    ),
    (
        "md",
        r"""## 3. Math

For player $i$ and requirement $k$, with standardised score $z_{ik}$ and floor
$f_k$ set at percentile $p$ of the population:

$$\text{qualified}_i = \bigwedge_k \left( z_{ik} \ge f_k \right)$$

$$\text{score}_i = \frac{\sum_k w_k z_{ik}}{\sum_k w_k}$$

The gate is a logical AND, so it is **unforgiving by design**: eleven
requirements at the 40th percentile would admit only $0.6^{11} \approx 0.36\%$
of players if the requirements were independent. They are correlated, so the
real figure is higher — but the gate still does the bulk of the work, and the
weights $w_k$ only order the survivors.""",
    ),
    (
        "code",
        SETUP
        + """

qualified = ranking[ranking["qualified"]]
independent = 0.6 ** 11
print(f"if requirements were independent: {100 * independent:.2f}% would qualify")
print(f"actually qualified:                {100 * len(qualified) / len(ranking):.2f}%")
print("\\nrequirements are strongly correlated - being good at one predicts the others")""",
    ),
    (
        "md",
        """## 4. Code

Raising the floor tightens the gate. This is the single most consequential knob
in the project and it is a judgement call, so it is exposed rather than
buried.""",
    ),
    (
        "code",
        """from gambeta import gate, kit
import dataclasses

cfg = kit.load()
keys = [r.key for r in needs.OUTFIELD if r.key in ranking.columns]
profile = ranking[["player_id", "player", "seasons", "leagues", *keys]].copy()

for pct in (20, 30, 40, 50, 60):
    out = gate.qualify_and_rank(profile, needs.OUTFIELD, dataclasses.replace(cfg, gate_percentile=pct))
    print(f"  floor at {pct}th percentile -> {int(out['qualified'].sum()):4d} qualify")""",
    ),
    (
        "md",
        """## 5. Assumptions

1. **Every requirement is genuinely necessary.** The gate treats them as
   mandatory, so including a bad requirement does more damage here than in an
   average, where it would merely be diluted.
2. **The floor is meaningful at the same percentile for all of them.** There is
   no reason the 40th percentile of discipline is as demanding as the 40th
   percentile of scoring.
3. **Standardising across players makes them comparable.** Save percentage and
   goals per 90 are only on one scale because we forced them onto one.

## 6. How it breaks

It broke, on the first real run, in a way worth showing in full.

`consistency` was defined as **−(standard deviation of a player's season
scores)** — the intuition being that a metronome is better than a streaky
player. Watch what that does.""",
    ),
    (
        "code",
        """elite = np.array([2.5, 4.0, 3.0, 4.0, 2.5, 3.5])   # a great player's seasons
flat  = np.array([-0.1, 0.1, -0.1, 0.1, -0.1, 0.1])  # a journeyman's

print(f"elite      mean {elite.mean():+.2f}   sd {elite.std():.2f}   old score {-elite.std():+.2f}")
print(f"journeyman mean {flat.mean():+.2f}   sd {flat.std():.2f}   old score {-flat.std():+.2f}")
print("\\nThe journeyman scores far better on 'consistency'.")""",
    ),
    (
        "md",
        """**Variance is anti-correlated with excellence.** An elite player swings between
very good and outstanding, so their standard deviation is large. A journeyman
sits flat at mediocre, so theirs is near zero.

Inside a gate, that is fatal. On the first run this single requirement
disqualified Messi, Ronaldo, Kane, Haaland, Lewandowski, Suárez, Henry and Salah
simultaneously — and the top qualifier was a player nobody would nominate.

The fix was to change what the requirement measures, not its threshold.
"Does he have bad years?" is a question about a **floor**, not a spread:

$$\\text{consistency}_i = \\text{percentile}_{20}\\left(s_{i1}, \\dots, s_{iT}\\right)$$

A great player's twentieth-percentile season is still good.""",
    ),
    (
        "code",
        """print(f"elite      20th pct {np.percentile(elite, 20):+.2f}")
print(f"journeyman 20th pct {np.percentile(flat, 20):+.2f}")
print("\\nNow the great player wins, which is the point.")""",
    ),
    (
        "md",
        """### The general lesson

A metric can be perfectly correct as arithmetic and completely wrong as a
measurement. Nothing about `-std()` is a bug; it computes exactly what it says.
The error was believing that low variance means quality.

**This is why the sanity check exists.** No test caught it — every unit test
passed. It was caught by looking at the output and recognising that the answer
was absurd. Domain knowledge is a debugging tool, and on this project it was the
only one that would have worked.""",
    ),
]

# --------------------------------------------------------------------------
METHOD_BRIDGE: list[tuple[str, str]] = [
    (
        "md",
        """# Method: measuring league strength from transfers

*Question → Intuition → Math → Code → Assumptions → How it breaks*""",
    ),
    (
        "md",
        """## 1. Question

A player's season is scored against the other players in **his** league. So a
2.0 in Ligue 1 and a 2.0 in the Premier League are both "two standard deviations
above your peers" — but the peers are not equally good.

If we pool a career across leagues, as we must when players transfer, how do we
avoid rewarding whoever played in the weakest division?

## 2. Intuition

**A player who changes league is the same footballer on both sides of the
move.** So whatever happens to his score across that move is a measurement of
the difference between the two leagues.

One transfer is a noisy measurement. Thousands of transfers, forming a connected
graph over 25 years, pin down the whole system — the same device that makes
chess ratings comparable across separate rating pools.""",
    ),
    (
        "md",
        r"""## 3. Math

For a move from league $a$ to league $b$:

$$\Delta z = \alpha + \beta \cdot \text{age} + \lambda_a - \lambda_b + \varepsilon$$

- $\lambda$ are the league strengths we want, identified only **up to a
  constant**, so one league is pinned at zero
- $\alpha$ is a global adaptation term: settling into a new league costs
  something on average, and that cost is not league strength
- $\beta$ controls for age, since players move at different career stages and
  decline would otherwise be misread as league difficulty

Fitted by weighted least squares, weighting each move by the smaller of the two
seasons' minutes.""",
    ),
    (
        "code",
        SETUP
        + """

summary = offsets.groupby("league").agg(
    offset=("offset", "mean"), moves=("moves", "sum")
).sort_values("offset", ascending=False)
summary.round(3)""",
    ),
    (
        "md",
        """The Premier League is pinned at zero as the reference. Everything else is
measured against it, in the same units as the player scores.""",
    ),
    (
        "code",
        """offsets["era"] = offsets["season"].str[:2].astype(int) // 5
era = offsets.pivot_table(index="league", columns="era", values="offset", aggfunc="mean")
era.columns = ["2000-04", "2005-09", "2010-14", "2015-19", "2020-24"]
era.round(2)""",
    ),
    (
        "md",
        """## 4. Code — and the corroboration that matters

Look at the era table above. The gaps are small in 2000-04 and widen sharply
from 2005 onward.

That is the Premier League's financial ascent — and **nothing about money, TV
deals or transfer fees is in this model.** It was recovered purely from players
changing league and their scores changing with them. When an estimate reproduces
a known historical pattern it did not have access to, that is real evidence the
method works.""",
    ),
    (
        "code",
        """rank_by_moves = offsets.groupby("league")["moves"].sum().sort_values(ascending=False)
print("transfers backing each estimate:")
for lg, n in rank_by_moves.items():
    print(f"  {lg:<22} {n:>6,}")
print("\\nAn offset backed by 200 moves deserves less trust than one backed by 3,000,")
print("which is why the count is published alongside the estimate.")""",
    ),
    (
        "md",
        """## 5. Assumptions

1. **A transferring player is unchanged by the move**, apart from age and a
   common adaptation effect. Injuries, motivation and tactical fit all violate
   this individually; the hope is they average out.
2. **Transfers are not selective in a way that correlates with the gap.** They
   almost certainly are — players usually move *up* when they excel and *down*
   when they decline, which is exactly the kind of selection that biases this.
3. **League strength is constant within a five-season block.** A compromise:
   per-season offsets would be badly identified from the handful of moves some
   pairs see in one year.

## 6. How it breaks

The model has a failure mode that is invisible unless you look for it:
**with transfers in only one direction between two leagues, the adaptation term
and the league offset are perfectly collinear.**

Both apply to every move. Only their *sign behaviour* separates them — the
offset flips when the direction flips, adaptation does not. If everybody moves
one way, no amount of data separates them, and the solver will split the
difference arbitrarily.""",
    ),
    (
        "code",
        """from gambeta import bridge, kit

cfg = kit.load()

def moves_between(gap, n, both_ways):
    rows = []
    for i in range(n):
        rows += [
            {"player_id": f"o{i}", "league": "FRA-Ligue 1", "season": "0102",
             "score": 1.0 + gap, "minutes": 3000, "age": 25.0},
            {"player_id": f"o{i}", "league": "ENG-Premier League", "season": "0203",
             "score": 1.0, "minutes": 3000, "age": 26.0},
        ]
        if both_ways:
            rows += [
                {"player_id": f"i{i}", "league": "ENG-Premier League", "season": "0102",
                 "score": 0.5, "minutes": 3000, "age": 25.0},
                {"player_id": f"i{i}", "league": "FRA-Ligue 1", "season": "0203",
                 "score": 0.5 + gap, "minutes": 3000, "age": 26.0},
            ]
    return pd.DataFrame(rows)

pair = ["ENG-Premier League", "FRA-Ligue 1"]
for both in (True, False):
    m = bridge.find_moves(moves_between(0.5, 40, both))
    o = bridge.solve_offsets(m, cfg, leagues=pair)
    est = o[(o["league"] == "FRA-Ligue 1") & (o["season"] == "0102")]["offset"].item()
    label = "both directions" if both else "one direction only"
    print(f"  {label:<20} true gap -0.50, estimated {est:+.2f}")""",
    ),
    (
        "md",
        """With traffic both ways the true gap is recovered. With one-way traffic, half of
it is silently absorbed by the adaptation term and the league looks stronger
than it is.

Real transfer data flows both ways between all five leagues, which is what makes
the estimates identifiable. But a league with mostly outbound moves — a selling
league — would be systematically mis-measured, and that is a live risk rather
than a hypothetical one. Ligue 1 is the closest thing here to that case: it
sells more than it buys, and it lands lowest of the five.""",
    ),
]

if __name__ == "__main__":
    build(LABS / "01-who-is-the-best-footballer.ipynb", NARRATIVE)
    build(LABS / "02-how-far-ahead-is-the-best.ipynb", BELL)
    build(LABS / "03-method-requirements-and-gates.ipynb", METHOD_GATE)
    build(LABS / "04-method-league-strength.ipynb", METHOD_BRIDGE)
