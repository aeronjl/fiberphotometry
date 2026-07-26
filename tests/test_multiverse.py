from dataclasses import replace

import pytest
from test_pipeline import _inputs, _spec

from fiberphotometry import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    EventSummarySpec,
    LowpassFilterOperation,
    MultiverseReportGroup,
    MultiverseSpec,
    ReferenceDFFOperation,
    materialize_multiverse,
    run_multiverse,
)


def _multiverse(*, leave_one_out: bool = True) -> MultiverseSpec:
    base = replace(
        _spec(),
        preprocessing=(ReferenceDFFOperation(method="ols"),),
        schema_version="2",
    )
    preprocessing = DecisionNode(
        "correction",
        "preprocessing",
        (
            DecisionAlternative(
                "ols",
                "linear reference comparator",
                (ReferenceDFFOperation(method="ols"),),
            ),
            DecisionAlternative(
                "invalid_cutoff",
                "deliberate execution failure fixture",
                (
                    LowpassFilterOperation(cutoff_hz=1000),
                    ReferenceDFFOperation(method="ols"),
                ),
            ),
        ),
    )
    windows = DecisionNode(
        "window",
        "event_summary",
        (
            DecisionAlternative(
                "wide",
                "frozen half-second windows",
                EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
            ),
            DecisionAlternative(
                "narrow",
                "short response sensitivity",
                EventSummarySpec(
                    (-0.5, 0), (0, 0.25), "DMS", output_column="dms_delta"
                ),
            ),
        ),
    )
    return MultiverseSpec(
        base,
        (preprocessing, windows),
        (
            CompatibilityRule(
                (
                    ChoiceRef("correction", "invalid_cutoff"),
                    ChoiceRef("window", "narrow"),
                ),
                "fixture combination is declared scientifically incoherent",
            ),
        ),
        (ChoiceRef("correction", "ols"), ChoiceRef("window", "wide")),
        "descriptive",
        smallest_effect=0.01,
        direction="positive",
        leave_one_unit_out=leave_one_out,
    )


def test_multiverse_retains_success_failure_and_incompatibility() -> None:
    spec = _multiverse()

    first_materialization = materialize_multiverse(spec)
    second_materialization = materialize_multiverse(spec)
    result = run_multiverse(spec, _inputs())

    assert len(first_materialization) == 4
    assert [item.universe_id for item in first_materialization] == [
        item.universe_id for item in second_materialization
    ]
    assert [item.status for item in result.universes].count("success") == 2
    assert [item.status for item in result.universes].count("failed") == 1
    assert [item.status for item in result.universes].count("incompatible") == 1
    assert sum(item.is_reference for item in result.universes) == 1
    assert result.summary.reference_estimate is not None
    assert result.summary.fraction_meeting_practical_effect == 2 / 3
    assert len(result.summary.decision_summaries) == 4
    assert len(result.leave_one_out) == 4
    assert all(item.status == "success" for item in result.leave_one_out)
    assert '"total_universes": 4' in result.to_json()


def test_multiverse_retains_qc_blocked_universes() -> None:
    pass_gate = _spec().quality_gate
    block_gate = replace(pass_gate, blocking_warnings=("low_valid_fraction",))
    base = _spec()
    spec = MultiverseSpec(
        base,
        (
            DecisionNode(
                "gate",
                "quality_gate",
                (
                    DecisionAlternative("report", "report only", pass_gate),
                    DecisionAlternative("block", "block missing data", block_gate),
                ),
            ),
        ),
        (),
        (ChoiceRef("gate", "report"),),
        "descriptive",
    )

    result = run_multiverse(spec, _inputs(missing=True))

    assert [item.status for item in result.universes] == ["success", "blocked"]
    assert result.summary.blocked_universes == 1
    assert result.summary.fraction_meeting_practical_effect is None


def test_grouped_report_separates_complete_unit_families(tmp_path) -> None:
    result = run_multiverse(_multiverse(), _inputs())
    groups = (
        MultiverseReportGroup.from_choice(
            result,
            name="Reference-corrected",
            units="ΔF/F",
            node="correction",
            alternatives=("ols",),
        ),
        MultiverseReportGroup.from_choice(
            result,
            name="Failure fixture",
            units="diagnostic units",
            node="correction",
            alternatives=("invalid_cutoff",),
        ),
    )

    destination = result.write_grouped_html(
        tmp_path / "robustness.html", groups, title="Robustness audit"
    )
    html = destination.read_text()

    assert "Parallel evidence lanes preserve unit" in html
    assert "Reference-corrected" in html
    assert "Failure fixture" in html
    assert "No successful workflows in this evidence lane" in html
    assert "fixture combination is declared scientifically incoherent" in html
    assert "pooled median" not in html.lower()
    assert all(line == line.rstrip() for line in html.splitlines())


def test_grouped_report_rejects_missing_and_overlapping_universes() -> None:
    result = run_multiverse(_multiverse(), _inputs())
    ols = MultiverseReportGroup.from_choice(
        result,
        name="OLS",
        units="ΔF/F",
        node="correction",
        alternatives=("ols",),
    )

    with pytest.raises(ValueError, match="every compatible universe"):
        result.to_grouped_html((ols,))
    with pytest.raises(ValueError, match="multiple groups"):
        result.to_grouped_html((ols, replace(ols, name="Duplicate")))
