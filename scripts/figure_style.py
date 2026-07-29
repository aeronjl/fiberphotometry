"""Shared publication-quality styling for documentation and evidence figures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt

PURPLE = "#563D7C"
TEAL = "#147D72"
AMBER = "#B56B20"
RED = "#B24745"
BLUE = "#376795"
INK = "#26212E"
MUTED = "#6F6878"
GRID = "#E8E4EC"


def apply_publication_style(*, hashsalt: str = "fiberphotometry-figures-v1") -> None:
    """Apply the deterministic, sans-serif-only project figure standard.

    ``hashsalt`` seeds the SVG element identifiers matplotlib emits. It is an
    arbitrary constant whose only requirement is that it never changes: every
    committed figure was generated under these salts, so renaming them would
    rewrite the identifiers in each SVG for no reader-visible gain. They are
    deliberately kept at the package's former name.
    """
    mpl.rcParams.update(
        {
            "axes.edgecolor": "#CBC5D2",
            "axes.labelcolor": INK,
            "axes.linewidth": 0.8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "figure.facecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "font.size": 9,
            "legend.frameon": False,
            "lines.linewidth": 1.5,
            "mathtext.default": "regular",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.dpi": 300,
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "svg.hashsalt": hashsalt,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )


def save_figure(
    figure: plt.Figure,
    path: Path,
    *,
    close: bool = True,
    **kwargs: Any,
) -> None:
    """Save vector-first figures reproducibly and normalize generated SVG text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {"bbox_inches": "tight", "facecolor": "white"}
    if path.suffix.lower() == ".svg":
        options.update({"format": "svg", "metadata": {"Date": None}})
    else:
        options["dpi"] = 300
    options.update(kwargs)
    figure.savefig(path, **options)
    if close:
        plt.close(figure)
    if path.suffix.lower() == ".svg":
        svg = path.read_text(encoding="utf-8")
        path.write_text(
            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
            encoding="utf-8",
        )
