#!/usr/bin/env python3
"""Plot the frozen IBL-Unspool future-session comparison."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    result = json.loads(
        (
            repository / "benchmarks/ibl-unspool-longitudinal-result-v0.1.json"
        ).read_text()
    )
    models = result["comparison"]["models"]
    time = {
        item["unit"]: item["log_loss"]
        for item in models["session_progress"]["unit_scores"]
    }
    neural = {
        item["unit"]: item["log_loss"]
        for item in models["session_progress_plus_lagged_dms"]["unit_scores"]
    }
    animals = sorted(time, key=lambda animal: time[animal] - neural[animal])
    differences = np.asarray([time[animal] - neural[animal] for animal in animals])
    comparison = result["comparison"]["pairwise_log_loss_differences"][
        "session_progress_minus_session_progress_plus_lagged_dms"
    ]["left_minus_right"]

    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "ibl-unspool-longitudinal-v1",
        }
    )
    figure, axes = plt.subplots(
        1, 2, figsize=(10.5, 4.8), gridspec_kw={"width_ratios": [1.8, 1]}
    )
    colors = np.where(differences > 0, "#0f766e", "#b45309")
    axes[0].barh(range(len(animals)), differences, color=colors)
    axes[0].axvline(0, color="#4b5563", linewidth=1)
    axes[0].set_yticks(range(len(animals)), animals)
    axes[0].set_xlabel("Session-progress minus lagged-DMS log loss")
    axes[0].set_title("Held-out session by animal", loc="left", weight="bold")

    estimate = comparison["estimate"]
    lower = comparison["lower"]
    upper = comparison["upper"]
    axes[1].errorbar(
        estimate,
        0,
        xerr=[[estimate - lower], [upper - estimate]],
        fmt="o",
        color="#6d28d9",
        capsize=5,
        markersize=7,
    )
    axes[1].axvline(0, color="#4b5563", linewidth=1)
    axes[1].set_yticks([0], ["18-animal mean"])
    axes[1].set_xlabel("Paired log-loss difference")
    axes[1].set_title("Animal bootstrap", loc="left", weight="bold")
    axes[1].text(
        0.5,
        -0.23,
        "Positive favors lagged DMS",
        transform=axes[1].transAxes,
        ha="center",
        color="#0f766e",
    )
    figure.suptitle(
        "Prior-session DMS contrast did not improve future-session prediction",
        weight="bold",
    )
    figure.tight_layout()
    output = repository / "docs/assets/ibl-unspool-longitudinal-v0.1.svg"
    figure.savefig(output, format="svg", metadata={"Date": None})
    plt.close(figure)
    svg = output.read_text(encoding="utf-8")
    output.write_text(
        "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
