# gambeta

Who is the best footballer of the last 25 years — and how would you actually
find out?

The second question is why the first is worth reading. This is both a ranking
and a worked textbook on the statistics behind it.

## The answer

A player must clear a floor on **all eleven requirements** to qualify at all.
239 of 4,424 players do. Ranked among them:

| # | Player | Score | σ above mean | Seasons | Leagues |
|---|---|---|---|---|---|
| 1 | **Lionel Messi** | 3.44 | **+6.1** | 16 | Spain |
| 2 | **Cristiano Ronaldo** | 2.90 | +5.2 | 19 | England, Spain, Italy |
| 3 | Erling Haaland | 2.63 | +4.7 | 6 | England, Germany |
| 4 | Harry Kane | 2.58 | +4.6 | 11 | England, Germany |
| 5 | Thierry Henry | 2.55 | +4.5 | 10 | England, Spain |

**Goalkeepers** are ranked separately on their own eight requirements — Neuer,
Ederson, Čech, van der Sar, Alisson — because save percentage and goals per 90
are not comparable quantities and pretending otherwise would be dishonest.

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

| League | Strength (England = 0) | Backed by |
|---|---|---|
| England | 0.000 | 3,365 moves |
| Spain | −0.143 | 3,005 |
| Italy | −0.212 | 2,640 |
| Germany | −0.219 | 1,880 |

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

Everything runs against `data/sample/` — 2 MB of derived aggregates — so every
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

Method chapters follow one structure: **Question → Intuition → Math → Code →
Assumptions → How it breaks.** The last section is the one most tutorials skip.

## Honest limitations

- **Attacking contribution only.** FBref records no per-player defensive action
  before 2017-18, so a centre-back is invisible to six of the eleven
  requirements. The rating is named for what it measures.
- **Four leagues, not five.** Ligue 1 was never collected — see
  [PENDING.md](PENDING.md).
- **No Champions League, no internationals.** A career here means a Big-5
  domestic league career.
- **Identity is probabilistic.** 85% of player-seasons resolve to a Wikidata
  entity; the rest are listed, never dropped.

Two bugs worth reading about, both caught by looking at output rather than by
tests: `consistency` was measured as variance, which rewarded mediocrity and
disqualified eight of the best players at once; and `reliability` was completed
matches per start, which measured *being a forward*. Both are written up in
`DEVIATIONS.md` and notebook 03.

## Roadmap

| Phase | Status |
|---|---|
| 1 — Premier League, peak-5 lens | done |
| 2 — Four leagues, eleven requirements, league bridge, keepers | **done** |
| 3 — Bayesian era model, Monte Carlo replay, weight sliders | next |
| 4 — Ligue 1, Champions League, internationals | see PENDING.md |

## Licence

None yet — all rights reserved. This will change before any release.
