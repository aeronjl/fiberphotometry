import numpy as np
import pytest

from fiberphotometry import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    unit_t_interval,
)


def paired_table(
    *, between: bool = False
) -> tuple[ObservationTable, StudyDesign, Estimand]:
    rng = np.random.default_rng(4)
    animals = np.repeat([f"a{i}" for i in range(8)], 40)
    conditions = (
        np.repeat(["control"] * 4 + ["drug"] * 4, 40)
        if between
        else np.tile(np.repeat(["control", "drug"], 20), 8)
    )
    outcome = (
        np.repeat(rng.normal(0, 1, 8), 40)
        + (conditions == "drug") * 0.5
        + rng.normal(0, 0.2, 320)
    )
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{i}" for i in range(320)],
            "animal": animals.tolist(),
            "condition": conditions.tolist(),
            "outcome": outcome.tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(
            Factor(
                "condition",
                "condition",
                "categorical",
                "animal" if between else "event",
            ),
        ),
    )
    return (
        table,
        design,
        Estimand("outcome", Contrast("condition", "drug", "control"), "animal"),
    )


def test_paired_t_interval_recovers_known_effect() -> None:
    table, design, estimand = paired_table()

    result = unit_t_interval(table, design, estimand, mode="paired")

    assert 0.45 < result.estimate < 0.55
    assert result.confidence_interval[0] > 0
    assert result.p_value < 0.001


def test_welch_interval_operates_on_units_not_events() -> None:
    table, design, estimand = paired_table(between=True)

    result = unit_t_interval(table, design, estimand, mode="welch")

    assert np.isfinite(result.standard_error)
    assert result.degrees_of_freedom < 14


def test_paired_contrast_unit_weights_sessions_equally() -> None:
    rows = []
    event = 0
    for animal, session, correct, repetitions in (
        ("a1", "s1", 10.0, 1),
        ("a1", "s2", 0.0, 9),
        ("a2", "s3", 2.0, 1),
        ("a2", "s4", 4.0, 9),
    ):
        for condition, outcome in (("correct", correct), ("incorrect", 0.0)):
            for _ in range(repetitions):
                rows.append((f"e{event}", animal, session, condition, outcome))
                event += 1
    table = ObservationTable.from_columns(
        {
            "event_id": [row[0] for row in rows],
            "animal": [row[1] for row in rows],
            "session": [row[2] for row in rows],
            "condition": [row[3] for row in rows],
            "outcome": [row[4] for row in rows],
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand(
        "outcome",
        Contrast("condition", "correct", "incorrect"),
        "animal",
        contrast_unit="session",
    )

    result = unit_t_interval(table, design, estimand, mode="paired")

    assert result.estimate == pytest.approx(4.0)
    pooled = Estimand(
        "outcome", Contrast("condition", "correct", "incorrect"), "animal"
    )
    assert unit_t_interval(
        table, design, pooled, mode="paired"
    ).estimate == pytest.approx(2.4)
