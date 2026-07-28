"""Plot the committed DANDI:000251 transient-validation result."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from figure_style import apply_publication_style, save_figure

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmarks/dandi-000251-transients-results-v0.1.json"
OUTPUT = ROOT / "docs/assets/dandi-000251-transient-robustness-v0.1.png"


def main() -> None:
    apply_publication_style(hashsalt="dandi-000251-transients-v0.1")
    payload = json.loads(RESULT.read_text())
    universe_ids = list(payload["aggregate"]["external_enrichment"])
    labels = [
        item.replace("global_mad", "global")
        .replace("rolling_mad", "rolling")
        .replace("-median", "\nmedian")
        .replace("-minimum", "\nminimum")
        for item in universe_ids
    ]
    colors = ["#6750A4" if "median" in item else "#00897B" for item in universe_ids]
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)

    positions = np.arange(len(universe_ids))
    for session_index, session in enumerate(payload["sessions"]):
        rates = [
            session["universes"][universe_id]["summary"]["rate_per_minute"]
            for universe_id in universe_ids
        ]
        marker = "o" if session["condition"] == "standard" else "^"
        axes[0].plot(
            positions,
            rates,
            marker=marker,
            color="#58606B",
            alpha=0.38,
            linewidth=0.8,
            markersize=4,
            label=session["condition"] if session_index < 2 else None,
        )
    axes[0].set_title("A  Event-rate sensitivity", loc="left", fontweight="bold")
    axes[0].set_ylabel("Accepted events / minute")
    axes[0].legend(frameon=False, fontsize=8)

    observed = []
    null_low = []
    null_high = []
    for universe_id in universe_ids:
        item = payload["aggregate"]["external_enrichment"][universe_id]
        observed.append(item["mean_teleport_hit_fraction"])
        null_low.append(item["null_95_interval"][0])
        null_high.append(item["null_95_interval"][1])
    axes[1].vlines(positions, null_low, null_high, color="#A7ABB3", linewidth=5)
    axes[1].scatter(positions, observed, c=colors, s=48, zorder=3)
    axes[1].set_title("B  Post-teleport construct test", loc="left", fontweight="bold")
    axes[1].set_ylabel("Mean animal hit fraction")
    axes[1].text(
        0.02,
        0.98,
        "bars: circular-shift null 95% interval",
        transform=axes[1].transAxes,
        va="top",
        fontsize=8,
        color="#58606B",
    )

    jaccard = [
        item["jaccard"]
        for item in payload["aggregate"]["agreement"]["pairwise_session_comparisons"]
    ]
    axes[2].hist(jaccard, bins=np.linspace(0, 0.5, 21), color="#6750A4", alpha=0.85)
    median = payload["aggregate"]["agreement"]["median_jaccard"]
    axes[2].axvline(median, color="#D1495B", linewidth=2)
    axes[2].set_title("C  Cross-universe peak agreement", loc="left", fontweight="bold")
    axes[2].set_xlabel("Pairwise tolerant Jaccard")
    axes[2].set_ylabel("Session x universe pairs")
    axes[2].text(
        median + 0.01,
        axes[2].get_ylim()[1] * 0.9,
        f"median {median:.3f}",
        color="#D1495B",
        fontsize=9,
    )

    for axis in axes[:2]:
        axis.set_xticks(positions, labels, rotation=38, ha="right", fontsize=8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#E5E1EE", linewidth=0.8)
    axes[2].spines[["top", "right"]].set_visible(False)
    figure.suptitle(
        "DANDI:000251 — detector choices dominate the retained public-data result",
        fontsize=15,
        fontweight="bold",
    )
    save_figure(figure, OUTPUT)


if __name__ == "__main__":
    main()
