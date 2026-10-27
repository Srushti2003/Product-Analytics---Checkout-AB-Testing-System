"""Chart helpers. One consistent style for every figure in the report."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"     # series 1
ORANGE = "#eb6834"   # series 2
AQUA = "#1baf7a"     # series 3
NEUTRAL = "#8a8983"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 22,
        "axes.labelsize": 10.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "font.family": "DejaVu Sans",
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "legend.labelcolor": TEXT_2,
        "figure.dpi": 150,
    }
)


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:+.{digits}f}%"


def fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.025, text, transform=ax.transAxes, color=TEXT_2, fontsize=9.5, va="bottom")


def forest(ax, labels, estimates, cis, colors=None, ref=0.0, annotate=None):
    """Horizontal point-and-interval plot of relative lifts."""
    y = np.arange(len(labels))[::-1]
    colors = colors or [BLUE] * len(labels)
    for yi, est, (lo, hi), c in zip(y, estimates, cis, colors):
        ax.plot([lo * 100, hi * 100], [yi, yi], color=c, lw=2.2, solid_capstyle="round")
        ax.plot(est * 100, yi, "o", ms=8, color=c, mec=SURFACE, mew=2)
    ax.axvline(ref * 100, color=NEUTRAL, lw=1, ls="--", zorder=0)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, color=TEXT)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    if annotate:
        for yi, txt in zip(y, annotate):
            ax.annotate(txt, xy=(1.0, yi), xycoords=("axes fraction", "data"),
                        xytext=(8, 0), textcoords="offset points", va="center",
                        fontsize=9, color=TEXT_2)
    return ax


def save(fig, path) -> None:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
