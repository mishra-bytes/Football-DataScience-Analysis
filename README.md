# gambeta

Who is the best footballer of the last 25 years, and how would you actually find
out?

The second question is why the first is worth reading. This is both a ranking
and a worked textbook on the statistics behind it.

## The answer

A player must clear a floor on **all eleven requirements** to qualify at all.
342 of 5,508 players do. Ranked among them:

| # | Player | Score | σ above mean | Seasons | Leagues |
|---|---|---|---|---|---|
| 1 | **Lionel Messi** | 3.32 | **+5.9** | 18 | Spain, France |
| 2 | **Cristiano Ronaldo** | 2.93 | +5.2 | 19 | England, Spain, Italy |
| 3 | Kylian Mbappé | 2.75 | +4.9 | 9 | Spain, France |
| 4 | Erling Haaland | 2.72 | +4.8 | 6 | England, Germany |
| 5 | Harry Kane | 2.68 | +4.7 | 11 | England, Germany |

**Almost none of that ordering is statistically supported.** Of the 28 pairs
among the top eight, **1 survives a two-sided permutation test** at p < 0.05,
and under a Bonferroni correction for running 28 tests, **none does**. Chapters
10 and 11 make that argument rather than burying it.

(Their confidence intervals also overlap for 44 of 45 top-ten pairs, but that is
a description and not a test. Overlapping intervals do not imply a
non-significant difference, and on this data five of those pairs are separable
anyway.)

**Goalkeepers** are ranked separately on their own eight requirements. Neuer,
Cañizares, Valdés, ter Stegen and Weidenfeller lead, and they get their own
board because save percentage and goals per 90 are not comparable quantities and
pretending otherwise would be dishonest.

## What "best" means here

Eleven requirements, each measurable across all 25 seasons and every league:

| | Requirement | Measured by |
|---|---|---|
| 1 | Scores goals | non-penalty goals / 90 |
| 2 | Creates goals | assists / 90 |
| 3 | Finishes clinically | goals per shot on target |
| 4 | Generates threat | shots on target / 90 |
| 5 | Carries his team | share of club goals |
| 6 | Beats his team's level | output vs what ClubElo predicts for that club |
| 7 | Is available | share of team minutes |
| 8 | Is picked to start | starts / appearances |
| 9 | Sustains it | qualifying seasons |
| 10 | Has no bad seasons | 20th percentile of his season scores |
| 11 | Does not cost his team | negative cards and fouls |

**Gate, then rank.** "Must have" is read literally. A floor on every requirement
decides who qualifies, and only then are qualifiers ranked. A weighted average
alone would let a player be genuinely poor at something the list calls mandatory
and still win on volume elsewhere.

**The player is the unit, not the league.** Each player-season is normalised
inside its own league and season, then *all* of a player's seasons are pooled,
whichever leagues they happened to be in. Ronaldo's 19 seasons across three
countries are one career.

**League strength comes from transfers.** A player who changes league is the
same footballer on both sides of the move, so the change in his score measures
the gap between those leagues. Solved across thousands of moves:

| League | Strength (England = 0) | Move endpoints |
|---|---|---|
| England | 0.000 | 967 |
| Spain | −0.180 | 788 |
| Italy | −0.243 | 684 |
| Germany | −0.261 | 496 |
| France | −0.359 | 743 |

1,839 distinct transfers, each counted once at each end. **England is pinned at
zero, not measured as best**, because the offsets are identified only up to a
constant. Pinning any other league instead reproduces the same gaps to within
0.013, and England still comes out top.

The gaps are small in 2000-04 and widen from 2005, which is the Premier League's
financial ascent recovered purely from players moving. Nothing about money is in
the model.

## Quickstart

```bash
uv sync --all-groups          # add --extra gpu if you have an NVIDIA card
uv run pytest                 # 236 tests, no network required
uv run streamlit run dugout/app.py
quarto render                 # builds the book into tome/_book
```

Everything runs against `data/sample/`, which is 3.6 MB of derived aggregates,
so every figure reproduces without scraping a page.

### Running the notebooks

Register the project environment as a Jupyter kernel once:

```bash
uv run python -m ipykernel install --user --name gambeta --display-name "gambeta (.venv 3.12)"
```

Without it, editors resolve the notebooks' kernel to your *global* interpreter,
which has no `gambeta` installed, and every import fails.

### Rebuilding the data

```bash
uv run gambeta all                 # scrape -> clean -> rank
uv run gambeta all --cache-only    # never fetch; use only what is cached
```

Requires Chrome. Read [DATA_SOURCES.md](DATA_SOURCES.md) first, because FBref
restricts bulk redistribution, which is why only derived aggregates are
published here.

## The book

One arc, running from a raw HTML page through to the answer and then back at it.

**Getting the data, and making it honest**

| | |
|---|---|
| `01-where-the-data-comes-from` | Scraping, caching, Parquet, schemas, and why none of it is a download |
| `02-who-is-this-player` | Identity resolution, name folding, and collapsing a transfer season |
| `03-when-a-zero-is-a-lie` | Missing data, and why the same fill is free in one place and damaging in another |
| `04-four-bugs-no-test-could-catch` | Validation, invariants, and the class of bug that passes every test |

**Turning data into a measure**

| | |
|---|---|
| `05-what-greatness-requires` | Gating vs averaging, and a metric that rewarded mediocrity |
| `06-comparing-players-across-eras` | Z-scores, regression to the mean, and believing a season in proportion to its size |
| `07-comparing-players-across-leagues` | Estimating league strength from transfers, and when it fails |

**The answer**

| | |
|---|---|
| `08-who-is-the-best-footballer` | The investigation, end to end |
| `09-how-far-ahead-is-the-best` | The distribution, and why "6 sigma" is a ruler and not a probability |

**Attacking the answer**

| | |
|---|---|
| `10-how-much-of-this-is-luck` | Resampling, intervals, and why the top ten cannot be ordered |
| `11-can-we-tell-them-apart` | Permutation tests, p-values, and the multiple-comparisons trap |
| `12-who-is-missing-from-this-data` | Why transfers are not a random sample, and Simpson's paradox |
| `13-does-it-agree-with-the-voters` | The one outside opinion, and where it disagrees |
| `14-does-the-answer-depend-on-my-choices` | Sensitivity to the four constants, and the one that turned out to do nothing |
| `15-how-many-things-is-this-measuring` | Correlation between the requirements, and how many the gate really tests |

Method chapters follow one structure: **Question, Intuition, Math, Code,
Assumptions, How it breaks.** The last section is the one most tutorials skip.

## Honest limitations

- **Attacking contribution only.** FBref records no per-player defensive action
  before 2017-18, so a centre-back is invisible to six of the eleven
  requirements. The rating is named for what it measures.
- **No Champions League, no internationals.** A career here means a Big-5
  domestic league career.
- **Identity is probabilistic.** 93.9% of player-seasons resolve to a Wikidata
  entity. The other 1,240 players are listed, never dropped.
- **Eleven requirements are not eleven independent tests.** They behave like
  about 5.4, and two of them overlap badly: `above_team` correlates 0.9999 with
  `scoring`, and `reliability` 0.72 with `availability`. Chapter 15 measures it.
- **The top ten is not an ordering.** Only 1 of 28 pairs among the top eight is
  separable at p < 0.05, and none after correcting for the number of tests. The
  ranking prints an order because a table has to. The statistics support "this
  group, clear of the rest" and not much more.
- **Intervals on short careers are optimistic.** A three-season career is allowed
  into the ranking, and a percentile bootstrap at n = 3 covers the truth about
  74% of the time, not 95%.
- **Discipline does not mean the same thing in every era.** FBref recorded no
  fouls at all in Ligue 1 or the Bundesliga before 2006, so in those twelve
  league-seasons the requirement is cards only. Chapter 03 measures what that
  does and what it does not.

Six defects have shipped so far, and every one of them produced plausible
output, raised no exception and passed every test. `consistency` was measured as
variance, which rewarded mediocrity and disqualified eight of the best players at
once. `reliability` was completed matches per start, which measured *being a
forward*. Ages were attached by row position rather than by player. Award winners
were not filtered to men's football. A side-table join key was not unique, which
fabricated a player with 19,288 minutes in a 38-match season. And a share of team
minutes was summed across clubs, which gave one player 296% of his team's
minutes. They are written up in `DEVIATIONS.md` and in chapters 03, 04 and 05.

## Roadmap

| Phase | Status |
|---|---|
| 1 - Premier League, peak-5 lens | done |
| 2 - Eleven requirements, league bridge, keepers | done |
| 2b - Big 5 complete: Ligue 1, all keepers, full `misc` | done |
| 2c - Data integrity: join keys, share arithmetic, missingness | **done** |
| 3 - Bayesian era model, Monte Carlo replay, weight sliders | next |
| 4 - Champions League, internationals | see PENDING.md |

## Licence

None yet, all rights reserved. This will change before any release.
