import numpy as np
import pytest

from fiberphotometry import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
)
from fiberphotometry.inference import (
    ResamplingPlan,
    exact_sign_flip_test,
    hierarchical_bootstrap,
)


def _paired_table() -> tuple[ObservationTable, StudyDesign, Estimand]:
    rng = np.random.default_rng(4)
    animals = np.repeat([f"a{i}" for i in range(8)], 40)
    conditions = np.tile(np.repeat(["control", "drug"], 20), 8)
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
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    return (
        table,
        design,
        Estimand("outcome", Contrast("condition", "drug", "control"), "animal"),
    )


def test_exact_sign_flip_matches_manual_enumeration() -> None:
    table, design, estimand = _paired_table()

    exact = exact_sign_flip_test(table, design, estimand, exchangeability_unit="animal")

    assert len(exact.null_distribution) == 2**8
    assert exact.p_value == np.mean(
        np.abs(exact.null_distribution) >= abs(exact.estimate)
    )


def test_bootstrap_supports_basic_and_bca_intervals() -> None:
    table, design, estimand = _paired_table()
    plan = ResamplingPlan(("animal", "event"))

    basic = hierarchical_bootstrap(
        table, design, estimand, plan, draws=100, seed=3, interval_method="basic"
    )
    bca = hierarchical_bootstrap(
        table, design, estimand, plan, draws=100, seed=3, interval_method="bca"
    )

    assert basic.interval_method == "basic"
    assert bca.interval_method == "bca"
    assert np.all(np.isfinite(bca.confidence_interval))


def test_paired_inference_rejects_incomplete_units() -> None:
    table, design, estimand = _paired_table()
    columns = dict(table.columns)
    keep = np.asarray(columns["animal"]) != "a0"
    keep |= np.asarray(columns["condition"]) == "control"
    incomplete = type(table)(
        {
            name: tuple(np.asarray(values)[keep].tolist())
            for name, values in columns.items()
        }
    )

    with pytest.raises(ValueError, match="incomplete units"):
        exact_sign_flip_test(
            incomplete, design, estimand, exchangeability_unit="animal"
        )
