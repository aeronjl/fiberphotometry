"""Structural checks for scientist-facing documentation figures."""

from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parents[1]
GENERATED = {
    "dandi-000971-source-figure-bounded-v0.1.svg",
    "dandi-000971-reward-multiverse-v0.1.svg",
    "event-kernel-interval-coverage-v0.1.svg",
    "event-kernel-validation.svg",
    "evidence-path.svg",
    "ibl-unspool-longitudinal-v0.1.svg",
    "method-question-map.svg",
    "multiverse-robustness.svg",
    "peri-event-inference.svg",
    "population-inference-boundary.svg",
    "population-interaction-boundary.svg",
    "population-curve-boundary.svg",
    "predictor-family-contributions.svg",
    "preprocessing-sequence.svg",
    "publication-provenance.svg",
    "qc-gating.svg",
    "variable-duration-kernels.svg",
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


def test_every_plot_script_uses_shared_publication_style() -> None:
    scripts = ROOT / "scripts"
    for script in scripts.glob("plot*.py"):
        source = script.read_text()
        assert "from figure_style import" in source, script.name
        assert ".savefig(" not in source, script.name


def test_committed_svg_text_is_sans_serif_only() -> None:
    figures = (
        *((ROOT / "docs" / "assets").glob("*.svg")),
        *((ROOT / "docs" / "figures").glob("*.svg")),
    )
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        assert "Times New Roman" not in source, figure.name
        assert "serif;" not in source.replace("sans-serif;", ""), figure.name
