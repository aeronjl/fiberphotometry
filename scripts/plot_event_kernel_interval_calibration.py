"""Plot the frozen event-kernel interval-coverage benchmark v0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from figure_style import apply_publication_style, save_figure

ROOT = Path(__file__).parents[1]
DEFAULT_INPUT = ROOT / "benchmarks" / "event-kernel-interval-coverage-v0.1.json"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "event-kernel-interval-coverage-v0.1.svg"
PURPLE = "#563d7c"
TEAL = "#23877c"
AMBER = "#c47a2c"
INK = "#26212e"
MUTED = "#7b7484"

LABELS = {
    "balanced_gaussian": "Balanced\nGaussian",
    "kernel_heterogeneity": "Kernel\nheterogeneity",
    "autocorrelated_residuals": "AR(1)\nresiduals",
    "overlapping_selected_model": "Overlapping +\nselected ridge",
    "blockwise_missingness": "Blockwise\nmissingness",
    "normalized_progress": "Normalized\nprogress",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    scenarios = payload["scenarios"]
    summaries = payload["summaries"]
    pointwise = np.asarray(
        [summaries[item]["pointwise_family_coverage"] for item in scenarios]
    )
    simultaneous = np.asarray(
        [summaries[item]["simultaneous_family_coverage"] for item in scenarios]
    )
    marginal = np.asarray(
        [summaries[item]["marginal_pointwise_coverage"] for item in scenarios]
    )

    apply_publication_style(hashsalt="event-kernel-interval-coverage-v0.1")
    figure, axis = plt.subplots(figsize=(11.4, 4.8))
    x = np.arange(len(scenarios))
    width = 0.29
    axis.bar(
        x - width / 2,
        pointwise,
        width,
        color=AMBER,
        label="Whole-family coverage from pointwise bands",
    )
    bars = axis.bar(
        x + width / 2,
        simultaneous,
        width,
        color=TEAL,
        label="Candidate simultaneous family coverage",
    )
    axis.scatter(
        x,
        marginal,
        color=PURPLE,
        marker="D",
        s=28,
        zorder=3,
        label="Marginal pointwise coverage",
    )
    axis.axhline(
        0.85,
        color=INK,
        linestyle="--",
        linewidth=1.2,
        label="Frozen simultaneous gate (85%)",
    )
    for index, bar in enumerate(bars):
        color = AMBER if simultaneous[index] < 0.85 else TEAL
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.012,
            f"{simultaneous[index]:.1%}",
            ha="center",
            va="bottom",
            color=color,
            weight="bold" if simultaneous[index] < 0.85 else "normal",
        )
    axis.set(
        title="Whole-model coverage across frozen scenarios",
        ylabel="Repeated-study coverage",
        xticks=x,
        xticklabels=[LABELS[item] for item in scenarios],
        ylim=(0.55, 1.01),
    )
    axis.grid(axis="y", color="#f0edf3")
    axis.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncols=2,
        fontsize=8,
    )
    figure.tight_layout()
    save_figure(figure, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
