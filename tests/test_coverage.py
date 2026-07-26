import json

import pytest

from fiberphotometry import EventCoverageRecord, assess_event_coverage


def test_event_coverage_preserves_stages_and_hierarchical_imbalance() -> None:
    records = (
        EventCoverageRecord("c1", "correct", "a1", "s1", True, True, "complete"),
        EventCoverageRecord("c2", "correct", "a1", "s1", False, False, "edge"),
        EventCoverageRecord(
            "i1", "incorrect", "a1", "s1", True, False, "response_intersects_gap"
        ),
        EventCoverageRecord("i2", "incorrect", "a1", "s1", True, True, "complete"),
    )

    report = assess_event_coverage(records)

    assert (report.total.candidate, report.total.gated, report.total.complete) == (
        4,
        3,
        2,
    )
    assert report.total.gate_retention == 0.75
    assert report.total.completion_retention == pytest.approx(2 / 3)
    assert dict(report.gate_dispositions) == {"edge": 1}
    assert dict(report.preprocessing_dispositions) == {"response_intersects_gap": 1}
    assert "condition_dependent_gate_retention" in report.warnings
    assert "session_level_condition_dependent_completion_retention" in report.warnings
    payload = json.loads(report.to_json())
    assert payload["sessions"][0]["name"] == "s1"


def test_event_coverage_rejects_impossible_or_ambiguous_records() -> None:
    impossible = EventCoverageRecord(
        "e1", "correct", "a1", "s1", False, True, "complete"
    )
    with pytest.raises(ValueError, match="ineligible"):
        assess_event_coverage((impossible,))

    duplicate = EventCoverageRecord(
        "e1", "incorrect", "a1", "s2", True, True, "complete"
    )
    with pytest.raises(ValueError, match="unique"):
        assess_event_coverage((duplicate, duplicate))
