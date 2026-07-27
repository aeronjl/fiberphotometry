"""Structural checks for scientist-facing documentation figures."""

from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parents[1]
GENERATED = {
    "event-kernel-validation.svg",
    "evidence-path.svg",
    "method-question-map.svg",
    "multiverse-robustness.svg",
    "peri-event-inference.svg",
    "preprocessing-sequence.svg",
    "publication-provenance.svg",
    "qc-gating.svg",
}


def test_generated_documentation_figures_are_valid_svgs() -> None:
    assets = ROOT / "docs" / "assets"

    for name in GENERATED:
        figure = assets / name
        assert figure.is_file()
        assert (
            ElementTree.parse(figure).getroot().tag == "{http://www.w3.org/2000/svg}svg"
        )
        assert figure.stat().st_size > 1_000


def test_figure_provenance_register_covers_generated_figures() -> None:
    register = (ROOT / "docs" / "reference" / "figure-provenance.md").read_text()

    for name in GENERATED:
        assert f"`{name}`" in register
