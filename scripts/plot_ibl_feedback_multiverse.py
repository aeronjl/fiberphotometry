"""Render the frozen IBL feedback specification curve from its JSON artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from figure_style import apply_publication_style, save_figure

from fiberphotometry.plotting import SpecificationCurveEntry, plot_specification_curve


def load_entries(payload: dict[str, Any]) -> tuple[SpecificationCurveEntry, ...]:
    reference = payload["reference_estimate"]
    return tuple(
        SpecificationCurveEntry(
            universe_id=universe["id"],
            estimate=universe["estimate"],
            confidence_interval=tuple(universe["confidence_interval"]),
            decisions=(
                ("correction", universe["correction"]),
                ("window", universe["window"]),
            ),
            is_reference=universe["estimate"] == reference,
        )
        for universe in payload["universes"]
    )


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-multiverse-v0.1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "docs/figures/ibl-feedback-specification-curve-v0.1.svg",
    )
    args = parser.parse_args()
    apply_publication_style(hashsalt="ibl-feedback-multiverse-v0.1")
    payload = json.loads(args.input.read_text())
    figure, _ = plot_specification_curve(
        load_entries(payload),
        decision_order=("correction", "window"),
        effect_label="Correct - incorrect response (dF/F)",
    )
    save_figure(figure, args.output)


if __name__ == "__main__":
    main()
