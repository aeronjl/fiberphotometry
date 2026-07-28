"""Render documentation figures from committed public-data result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from figure_style import apply_publication_style, save_figure

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmarks/dandi-000971-tutorial-v0.1/multiverse.json"
OUTPUT = ROOT / "docs/assets/dandi-000971-reward-multiverse-v0.1.svg"


def _label(universe: dict[str, Any]) -> str:
    alternatives = [choice["alternative"] for choice in universe["choices"]]
    preprocessing = alternatives[0].replace("_", " · ")
    window = alternatives[1].replace("ms", " ms")
    return f"{preprocessing} · {window}"


def main() -> None:
    """Plot the frozen DANDI reward multiverse without reaccessing source data."""
    apply_publication_style(hashsalt="fiberphotometry-public-evidence-v1")
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    universes = sorted(payload["universes"], key=lambda item: item["estimate"])

    figure, axis = plt.subplots(figsize=(8.8, 4.8))
    for position, universe in enumerate(universes):
        estimate = universe["estimate"]
        lower, upper = universe["confidence_interval"]
        color = "#6d28d9" if universe["is_reference"] else "#0f766e"
        axis.errorbar(
            estimate,
            position,
            xerr=[[estimate - lower], [upper - estimate]],
            fmt="o",
            color=color,
            capsize=3,
            markersize=6 if universe["is_reference"] else 5,
        )

    axis.axvline(0, color="#b45309", linestyle="--", linewidth=1)
    axis.set_yticks(range(len(universes)), [_label(item) for item in universes])
    axis.set_xlabel("Rewarded - unrewarded DMS response (fractional dF/F)")
    axis.set_title(
        "Six-animal public NWB robustness analysis", loc="left", weight="bold"
    )
    axis.text(
        1,
        1.02,
        "purple = declared reference",
        transform=axis.transAxes,
        ha="right",
        color="#6d28d9",
        fontsize=8,
    )
    axis.grid(axis="x", color="#e7e5e4", linewidth=0.7)
    figure.tight_layout()
    save_figure(figure, OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
