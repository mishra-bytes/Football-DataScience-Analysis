"""Charts.

Two forms, each chosen for the job the data does:

* :func:`ranked_dots`, magnitude with uncertainty. A dot plot, not a bar chart,
  because the quantity is a standard score with a meaningful zero *and* an
  interval; bars would imply a length that starts at zero and hide the interval.
* :func:`bump`, change in rank over time.

Both modes are **selected, not flipped**: the dark palette is its own set of
steps chosen for the dark surface, not a lightness inversion of the light one.

Palette provenance
------------------
Colours are the validated reference categorical palette. Verified with the
data-viz validator on this exact ordering:

* light, adjacent pairs, 8 slots: CVD ΔE 9.1, normal-vision ΔE 19.6, PASS
* dark, adjacent pairs, 8 slots: CVD ΔE 8.4, normal-vision ΔE 19.3, PASS
* all-pairs: only the first three slots clear the floors in both modes

Because a bump chart's lines cross, any two series can end up adjacent, so it is
an all-pairs form. Series are therefore capped at eight and every line carries a
legend entry; colour is never the sole identity channel. Three light-mode slots
sit below 3:1 against the light surface, which the visible labels relieve.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

MAX_SERIES = 8
"""Hard cap. A ninth series is never a generated hue. Fold it or facet."""

DOTS_SUBTITLE = "Bars are 95% bootstrap intervals. Where they overlap, the order is not resolved."

LIGHT: dict[str, Any] = {
    "surface": "#fcfcfb",
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "accent": "#2a78d6",
    "series": (
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#4a3aa7",
        "#e34948",
    ),
    # One hue, light to dark, for magnitude. Lightness is monotonic by
    # construction (OKLab L 0.96 down to 0.35) and asserted in the tests.
    "sequential": ("#eaf2fb", "#c6dcf4", "#95c0ea", "#5f9fdd", "#2a78d6", "#1c56a0", "#123a6d"),
    # Two hues with a neutral midpoint, for polarity. Each arm is monotonic
    # toward the centre, which is the lightest step on a light surface.
    "diverging": ("#8c3d12", "#c86a35", "#eb9e6f", "#e6e5df", "#7fb0e4", "#3a7fd0", "#1b4d8f"),
}

DARK: dict[str, Any] = {
    "surface": "#1a1a19",
    "primary": "#ffffff",
    "secondary": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "accent": "#3987e5",
    "series": (
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#008300",
        "#9085e9",
        "#e66767",
    ),
    # Selected for the dark surface, not inverted from the light steps: the
    # ramp climbs away from the surface (L 0.27 to 0.81) rather than toward it.
    "sequential": ("#16273c", "#1d3b5f", "#245285", "#2a6bad", "#3987e5", "#6ba7ee", "#9dc6f5"),
    # The neutral midpoint is the *darkest* step here, so "no signal" recedes
    # into the surface instead of glowing out of it.
    "diverging": ("#e08a5a", "#d9703a", "#a85428", "#3a3a38", "#2d6bb0", "#3987e5", "#79b0ef"),
}


def matrix(
    frame: pd.DataFrame,
    *,
    title: str,
    subtitle: str | None = None,
    diverging: bool = False,
    fmt: str = "{:.2f}",
    label_if: float | None = None,
    scale: tuple[float, float] | None = None,
    dark: bool = False,
) -> Figure:
    """Heatmap of a small labelled table: a correlation matrix, a coverage grid.

    The form is right when every cell is a comparable magnitude and the reader
    needs to find blocks rather than read individual numbers. Below roughly a
    hundred cells the values are worth printing on top, which is why this labels
    selectively rather than relying on colour alone.

    Parameters
    ----------
    frame
        Rows and columns are the axes; values are the magnitude.
    diverging
        ``True`` when the value has a sign and zero means something, which picks
        the two-hue ramp with a neutral midpoint and centres the scale on zero.
        ``False`` picks the single-hue ramp for a plain magnitude.
    fmt
        Format for the printed cell values.
    label_if
        Print a value only when ``abs(value)`` reaches this, so a dense grid
        stays readable. ``None`` labels every cell.
    scale
        ``(low, high)`` limits. Defaults to the data's range, or to a symmetric
        range about zero when ``diverging``.
    """
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    colours = palette(dark)
    steps = colours["diverging" if diverging else "sequential"]
    cmap = LinearSegmentedColormap.from_list("gambeta", list(steps))

    values = frame.to_numpy(dtype=float)
    if scale is not None:
        low, high = scale
    elif diverging:
        edge = float(np.nanmax(np.abs(values)))
        low, high = -edge, edge
    else:
        low, high = float(np.nanmin(values)), float(np.nanmax(values))
    norm = Normalize(vmin=low, vmax=high)

    height = max(3.0, 0.42 * len(frame) + 2.2)
    fig, ax = plt.subplots(figsize=(min(12.0, 0.75 * len(frame.columns) + 4.5), height))
    fig.patch.set_facecolor(colours["surface"])
    ax.set_facecolor(colours["surface"])

    # A 2px surface gap between cells, so adjacent blocks read as separate marks.
    ax.pcolormesh(values, cmap=cmap, norm=norm, edgecolors=colours["surface"], linewidth=2.0)
    ax.invert_yaxis()
    ax.set_aspect("equal" if len(frame) == len(frame.columns) else "auto")

    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            if np.isnan(value) or (label_if is not None and abs(value) < label_if):
                continue
            # Text is ink, never the series colour: pick whichever of the two
            # inks the cell can carry.
            shade = norm(value)
            far = shade > 0.72 or (diverging and shade < 0.28)
            ax.text(
                col + 0.5,
                row + 0.5,
                fmt.format(value),
                ha="center",
                va="center",
                fontsize=8,
                color=colours["surface"] if far else colours["primary"],
            )

    ax.set_xticks(np.arange(len(frame.columns)) + 0.5)
    ax.set_xticklabels(frame.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(np.arange(len(frame)) + 0.5)
    ax.set_yticklabels(frame.index, fontsize=9)
    ax.tick_params(length=0, colors=colours["secondary"])
    for spine in ax.spines.values():
        spine.set_visible(False)

    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, fraction=0.03, pad=0.02)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, colors=colours["secondary"], labelsize=8)

    # The subtitle is offset in points, not axes fractions: a short wide figure
    # makes an axes-relative offset tiny and the two lines collide.
    ax.set_title(title, color=colours["primary"], fontsize=13, loc="left", pad=30)
    if subtitle:
        ax.annotate(
            subtitle,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(0, 8),
            textcoords="offset points",
            color=colours["secondary"],
            fontsize=9,
            va="bottom",
        )
    fig.tight_layout()
    return fig


def palette(dark: bool = False) -> dict[str, Any]:
    """Return the colour roles for the selected mode."""
    return DARK if dark else LIGHT


def season_label(season: str) -> str:
    """Render a 4-digit season code for humans: ``"0001"`` becomes ``"2000-01"``.

    Axis ticks reading ``0001`` are meaningless to anyone who has not memorised
    the internal encoding, which for a teaching artifact is most readers.
    """
    start = int(season[:2])
    century = 2000 if start < 90 else 1900
    return f"{century + start}-{season[2:]}"


def apply_theme(dark: bool = False) -> None:
    """Apply the project's matplotlib defaults. Safe to call repeatedly."""
    c = palette(dark)
    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 120,
            "figure.facecolor": c["surface"],
            "axes.facecolor": c["surface"],
            "savefig.facecolor": c["surface"],
            "font.size": 10,
            "text.color": c["primary"],
            "axes.labelcolor": c["secondary"],
            "xtick.color": c["muted"],
            "ytick.color": c["muted"],
            "axes.edgecolor": c["axis"],
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": c["grid"],
            "grid.linewidth": 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "legend.labelcolor": c["secondary"],
        }
    )


def ranked_dots(
    df: pd.DataFrame,
    top: int = 20,
    title: str = "Peak five seasons, era-adjusted",
    subtitle: str = DOTS_SUBTITLE,
    dark: bool = False,
) -> Figure:
    """Horizontal dot plot of ranked scores with confidence intervals.

    One series, so no legend: the title names the quantity. Ranking is encoded by
    vertical position and uncertainty by bar length, so the chart survives
    greyscale printing and colour-vision deficiency without relying on hue.

    Parameters
    ----------
    df
        Columns ``player``, ``score``, ``lo``, ``hi``.
    top
        Number of players to show, best first.
    dark
        Select the dark palette.
    """
    apply_theme(dark)
    c = palette(dark)

    shown = df.nlargest(min(top, len(df)), "score").iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.32 * max(len(shown), 1) + 1.7))
    positions = range(len(shown))

    # hlines yields a LineCollection, which takes `capstyle` (Line2D's is
    # `solid_capstyle`). Rounded ends keep the interval reading as a range.
    ax.hlines(
        positions,
        shown["lo"],
        shown["hi"],
        color=c["muted"],
        linewidth=3,
        alpha=0.5,
        capstyle="round",
    )
    ax.plot(
        shown["score"],
        positions,
        "o",
        color=c["accent"],
        markersize=7,
        linestyle="none",
        markeredgecolor=c["surface"],
        markeredgewidth=1.5,  # 2px surface ring
    )

    ax.set_yticks(list(positions))
    ax.set_yticklabels(shown["player"])
    ax.set_xlabel("Standard deviations above the season mean")
    # pad lifts the title clear of the subtitle; without it the two overlap.
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=c["primary"], pad=26)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=8, color=c["muted"])
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def bell(
    values: pd.Series,
    highlight: dict[str, float] | None = None,
    title: str = "Where every player sits",
    xlabel: str = "Composite score (standard deviations)",
    bins: int = 60,
    dark: bool = False,
) -> Figure:
    """Distribution of a score across every player, with named players marked.

    Overlays the normal curve implied by the data's own mean and standard
    deviation. Where the histogram sits above that curve in the right tail, the
    distribution has more extreme performers than a normal would produce, which
    is the interesting claim about football, not a defect of the chart.

    Parameters
    ----------
    values
        One score per player.
    highlight
        ``{player name: score}`` to mark with a labelled rule, annotated with how
        many standard deviations above the mean they sit.
    bins
        Histogram bin count.
    """
    apply_theme(dark)
    c = palette(dark)

    data = values.to_numpy(dtype=float)
    data = data[np.isfinite(data)]
    mu, sigma = float(data.mean()), float(data.std(ddof=0))

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(data, bins=bins, color=c["accent"], alpha=0.55, edgecolor=c["surface"], linewidth=0.5)

    grid = np.linspace(data.min(), data.max(), 400)
    normal = np.exp(-0.5 * ((grid - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    counts, edges = np.histogram(data, bins=bins)
    ax.plot(
        grid,
        normal * len(data) * (edges[1] - edges[0]),
        color=c["muted"],
        linewidth=2,
        linestyle="--",
        label="Normal curve with the same mean and spread",
    )

    for offset, (name, score) in enumerate(
        sorted((highlight or {}).items(), key=lambda kv: -kv[1])
    ):
        z = (score - mu) / sigma
        ax.axvline(score, color=c["primary"], linewidth=1.2, alpha=0.8)
        ax.annotate(
            f"{name}  {z:+.1f}σ",
            xy=(score, counts.max() * (0.92 - 0.11 * offset)),
            xytext=(-8, 0),
            textcoords="offset points",
            ha="right",
            fontsize=9,
            color=c["primary"],
            fontweight="bold",
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Players")
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=c["primary"], pad=26)
    ax.text(
        0,
        1.015,
        f"{len(data):,} players | mean {mu:.2f}, standard deviation {sigma:.2f}",
        transform=ax.transAxes,
        fontsize=8,
        color=c["muted"],
    )
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


def bump(
    df: pd.DataFrame,
    top: int = MAX_SERIES,
    title: str = "Rank by season",
    dark: bool = False,
) -> Figure:
    """Bump chart tracking each player's rank across seasons.

    Capped at :data:`MAX_SERIES` because crossing lines make this an all-pairs
    form, where the palette guarantees separation for fewer slots than the
    adjacent case. Every series is named in the legend, so identity never rests
    on colour alone.

    Parameters
    ----------
    df
        Columns ``season``, ``player``, ``rank``.
    top
        Keep players who reach this rank or better in at least one season.
    dark
        Select the dark palette.
    """
    apply_theme(dark)
    c = palette(dark)

    best_rank = df.groupby("player")["rank"].transform("min")
    kept = df.loc[best_rank <= top]
    order = kept.groupby("player")["rank"].min().sort_values().index[:MAX_SERIES]

    fig, ax = plt.subplots(figsize=(10, 5))
    for slot, player in enumerate(order):
        line = kept[kept["player"] == player].sort_values("season")
        ax.plot(
            line["season"],
            line["rank"],
            marker="o",
            markersize=7,
            linewidth=2,
            color=c["series"][slot],
            label=str(player),
            markeredgecolor=c["surface"],
            markeredgewidth=1.5,
        )

    ax.invert_yaxis()
    ax.set_ylabel("Rank")
    ax.set_xlabel("Season")
    ticks = sorted(kept["season"].unique())
    ax.set_xticks(ticks)
    ax.set_xticklabels([season_label(s) for s in ticks])
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=c["primary"])
    if len(order) >= 2:
        ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig
