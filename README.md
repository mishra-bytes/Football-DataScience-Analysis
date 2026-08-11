# gambeta

Who is the best footballer of the last 25 years — and how would you actually
find out?

The second question is why the first is worth reading. This is both a ranking
and a worked textbook on the statistics behind it.

## The answer

A player must clear a floor on **all eleven requirements** to qualify at all.
326 of 5,508 players do. Ranked among them:

| # | Player | Score | σ above mean | Seasons | Leagues |
|---|---|---|---|---|---|
| 1 | **Lionel Messi** | 3.32 | **+5.9** | 18 | Spain, France |
| 2 | **Cristiano Ronaldo** | 2.94 | +5.2 | 19 | England, Spain, Italy |
| 3 | Kylian Mbappé | 2.81 | +5.0 | 9 | Spain, France |
| 4 | Erling Haaland | 2.71 | +4.8 | 6 | England, Germany |
| 5 | Harry Kane | 2.65 | +4.7 | 11 | England, Germany |

**Most of that ordering is not statistically supported.** Of the 28 pairs among
the top eight, **3 survive a two-sided permutation test** at p < 0.05, and under
a Bonferroni correction for running 28 tests, one does. Notebooks 06 and 07 make
the argument rather than burying it.

(Their confidence intervals also overlap for 42 of 45 top-ten pairs, but that is
a description and not a test — overlapping intervals do not imply a
non-significant difference, and on this data four such pairs are separable.)

**Goalkeepers** are ranked separately on their own eight requirements — Neuer,
Cañizares, Valdés, ter Stegen, Weidenfeller — because save percentage and goals
per 90 are not comparable quantities and pretending otherwise would be
dishonest.

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

**Gate, then rank.** "Must have" is read literally: a floor on every
requirement decides who qualifies, and only then are qualifiers ranked. A
weighted average alone would let a player be genuinely poor at something the
list calls mandatory and still win on volume elsewhere.

**The player is the unit, not the league.** Each player-season is normalised
inside its own league and season, then *all* of a player's seasons are pooled —
whichever leagues they happened to be in. Ronaldo's 19 seasons across three
countries are one career.

**League strength comes from transfers.** A player who changes league is the
same footballer on both sides of the move, so the change in his score measures
the gap between those leagues. Solved across thousands of moves:

| League | Strength (England = 0) | Move endpoints |
|---|---|---|
| England | 0.000 | 967 |
| Spain | −0.163 | 788 |
| Italy | −0.213 | 684 |
| Germany | −0.227 | 496 |
| France | −0.300 | 743 |

1,839 distinct transfers, each counted once at each end. **England is pinned at
zero, not measured as best** — the offsets are identified only up to a constant.
Pinning any other league instead reproduces the same gaps to within 0.013, and
England still comes out top.

The gaps are small in 2000-04 and widen from 2005 — the Premier League's
financial ascent, recovered purely from players moving. Nothing about money is
in the model.

## Quickstart

```bash
uv sync --all-groups          # add --extra gpu if you have an NVIDIA card
uv run pytest                 # 175 tests, no network required
uv run streamlit run dugout/app.py
quarto render                 # builds the book into tome/_book
```

Everything runs against `data/sample/` — 3 MB of derived aggregates — so every
figure reproduces without scraping a page.

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

Requires Chrome. Read [DATA_SOURCES.md](DATA_SOURCES.md) first — FBref restricts
bulk redistribution, which is why only derived aggregates are published here.

## The notebooks

| | |
|---|---|
| `01-who-is-the-best-footballer` | The investigation, end to end |
| `02-how-far-ahead-is-the-best` | The distribution, and why "6 sigma" is a ruler and not a probability |
| `03-method-requirements-and-gates` | Gating vs averaging, and a metric that rewarded mediocrity |
| `04-method-league-strength` | Estimating league strength from transfers, and when it fails |
| `05-method-normalisation-and-shrinkage` | Z-scores, regression to the mean, and believing a season in proportion to its size |
| `06-method-the-bootstrap` | Resampling, intervals, and why the top ten cannot be ordered |
| `07-method-testing-without-a-distribution` | Permutation tests, p-values, and the multiple-comparisons trap |
| `08-method-selection-bias` | Why transfers are not a random sample, and Simpson's paradox |

Method chapters follow one structure: **Question → Intuition → Math → Code →
Assumptions → How it breaks.** The last section is the one most tutorials skip.

## Honest limitations

- **Attacking contribution only.** FBref records no per-player defensive action
  before 2017-18, so a centre-back is invisible to six of the eleven
  requirements. The rating is named for what it measures.
- **No Champions League, no internationals.** A career here means a Big-5
  domestic league career.
- **Identity is probabilistic.** 94% of player-seasons resolve to a Wikidata
  entity; the other 1,240 players are listed, never dropped.
- **The top ten is not an ordering.** Only 3 of 28 pairs among the top eight are
  separable at p < 0.05, and one after correcting for the number of tests. The
  ranking prints an order because a table has to; the statistics support "this
  group, clear of the rest" and not much more.
- **Intervals on short careers are optimistic.** A three-season career is allowed
  into the ranking, and a percentile bootstrap at n = 3 covers the truth about
  74% of the time, not 95%.

Two bugs worth reading about, both caught by looking at output rather than by
tests: `consistency` was measured as variance, which rewarded mediocrity and
disqualified eight of the best players at once; and `reliability` was completed
matches per start, which measured *being a forward*. Both are written up in
`DEVIATIONS.md` and notebook 03.

## Roadmap

| Phase | Status |
|---|---|
| 1 — Premier League, peak-5 lens | done |
| 2 — Eleven requirements, league bridge, keepers | done |
| 2b — Big 5 complete: Ligue 1, all keepers, full `misc` | **done** |
| 3 — Bayesian era model, Monte Carlo replay, weight sliders | next |
| 4 — Champions League, internationals | see PENDING.md |

## Licence

None yet — all rights reserved. This will change before any release.
