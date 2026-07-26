import numpy as np

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
