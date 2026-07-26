from dataclasses import replace

from test_pipeline import _inputs, _spec

from fiberphotometry import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    EventSummarySpec,
    LowpassFilterOperation,
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
