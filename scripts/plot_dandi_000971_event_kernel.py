"""Plot the frozen DANDI:000971 event-kernel evidence artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("benchmarks/dandi-000971-event-kernel-v0.2/result.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/assets/dandi-000971-event-kernels-v0.2.png"),
    )
    args = parser.parse_args()
    payload = json.loads(args.result.read_text(encoding="utf-8"))
    figure, axes = plt.subplots(2, 2, figsize=(9, 5.8), sharex=True)
    colors = {"active_poke": "#5e35b1", "reward_increment": "#00897b"}
    labels = {
        "active_poke": "Active poke (common)",
        "reward_increment": "Reward increment",
    }
    for row, region in enumerate(("DMS", "DLS")):
        region_result = payload["regions"][region]
        selected = next(
            item
            for item in region_result["cross_validation"]
            if item["alpha"] == region_result["selected_alpha"]
        )
        for column, kernel in enumerate(region_result["event_kernels"]):
            axis = axes[row, column]
            axis.plot(
                kernel["lag_s"],
                kernel["coefficient"],
                color=colors[kernel["name"]],
                linewidth=2,
            )
            uncertainty = next(
                item
                for item in region_result["kernel_uncertainty"]["event_kernels"]
                if item["name"] == kernel["name"]
            )
            axis.fill_between(
                uncertainty["lag_s"],
                uncertainty["lower"],
                uncertainty["upper"],
                color=colors[kernel["name"]],
                alpha=0.18,
                linewidth=0,
                label="Pointwise grouped jackknife interval",
            )
            axis.axhline(0, color="#777777", linewidth=0.8)
            axis.axvline(0, color="#222222", linewidth=0.8, linestyle="--")
            axis.set_title(f"{region}: {labels[kernel['name']]}")
            axis.text(
                0.03,
                0.94,
                f"held-out mean R² = {selected['mean_r_squared']:.4f}",
                transform=axis.transAxes,
                va="top",
                fontsize=8,
            )
            if row == 1:
                axis.set_xlabel("Lag from event (s)")
            if column == 0:
                axis.set_ylabel("Pooled coefficient (ΔF/F)")
    figure.suptitle(
        "DANDI:000971 pooled FIR kernels with grouped-jackknife sensitivity intervals"
    )
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180, bbox_inches="tight")
    print(args.output)


if __name__ == "__main__":
    main()
