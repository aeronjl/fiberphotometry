import pytest

from fiberphotometry.design import (
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    validate_design,
)


def _design() -> StudyDesign:
    return StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", nested_within="animal"),
            Unit("event", "event_id", nested_within="session"),
        ),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )


def test_design_is_open_serializable_and_validated() -> None:
    table = ObservationTable.from_columns(
        {
            "event_id": ["e1", "e2", "e3", "e4"],
            "animal": ["a", "a", "b", "b"],
            "session": ["s1", "s1", "s2", "s2"],
            "condition": ["control", "drug", "control", "drug"],
            "unmodeled_metadata": [1, 2, 3, 4],
        }
    )

    report = validate_design(table, _design())

    assert report.valid
    assert report.unit_counts == {"animal": 2, "session": 2, "event": 4}
    assert StudyDesign.from_json(_design().to_json()) == _design()


def test_design_rejects_false_nesting_and_assignment() -> None:
    table = ObservationTable.from_columns(
        {
            "event_id": ["e1", "e2"],
            "animal": ["a", "b"],
            "session": ["shared", "shared"],
            "condition": ["control", "drug"],
        }
    )
    between_animal = StudyDesign(
        observation_id="event_id",
        units=_design().units,
        factors=(Factor("condition", "condition", "categorical", "animal"),),
    )

    report = validate_design(table, between_animal)

    assert not report.valid
    assert {issue.code for issue in report.issues} == {"crossed_nesting"}
    with pytest.raises(ValueError, match="multiple"):
        report.raise_for_errors()


def test_design_rejects_factor_changes_within_assignment_unit() -> None:
    table = ObservationTable.from_columns(
        {
            "event_id": ["e1", "e2"],
            "animal": ["a", "a"],
            "session": ["s", "s"],
            "condition": ["control", "drug"],
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=_design().units,
        factors=(Factor("condition", "condition", "categorical", "animal"),),
    )

    report = validate_design(table, design)

    assert not report.valid
    assert "factor_varies_within_assignment_unit" in {
        issue.code for issue in report.issues
    }
