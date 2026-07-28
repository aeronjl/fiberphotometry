"""Render unit-separated specification curves for the frozen IBL v0.3.2 run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from figure_style import apply_publication_style, save_figure

from fiberphotometry.plotting import SpecificationCurveEntry, plot_specification_curve


def _choices(universe: dict[str, Any]) -> dict[str, str]:
    return {item["node"]: item["alternative"] for item in universe["choices"]}


def _entries(
    payload: dict[str, Any], units: str
) -> tuple[SpecificationCurveEntry, ...]:
    reference_choices = {"published_rolling", "divide_standard"}
    return tuple(
        SpecificationCurveEntry(
            universe_id=universe["universe_id"],
            estimate=universe["estimate"],
            confidence_interval=tuple(universe["confidence_interval"]),
            decisions=tuple(_choices(universe).items()),
            is_reference={item["alternative"] for item in universe["choices"]}
            == reference_choices,
        )
        for universe in payload["universes"]
        if universe["status"] == "success" and universe["units"] == units
    )


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-results-v0.3.2.json",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=repository / "docs/figures",
    )
    args = parser.parse_args()
    apply_publication_style(hashsalt="ibl-feedback-signal-only-v0.3.2")
    payload = json.loads(args.input.read_text())
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for units, stem, label in (
        ("fractional_dff", "divide", "Correct - incorrect response (fractional dF/F)"),
        (
            "acquired_fluorescence",
            "subtract",
            "Correct - incorrect response (acquired fluorescence)",
        ),
    ):
        entries = _entries(payload, units)
        if not entries:
            continue
        figure, _ = plot_specification_curve(
            entries,
            decision_order=("baseline_estimator", "normalization_window"),
            effect_label=label,
        )
        output = args.output_directory / f"ibl-feedback-signal-only-{stem}-v0.3.2.svg"
        save_figure(figure, output)


if __name__ == "__main__":
    main()
