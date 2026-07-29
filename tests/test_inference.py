import numpy as np

from fipha.design import Factor, ObservationTable, StudyDesign, Unit
from fipha.inference import (
    Contrast,
    Estimand,
    PermutationPlan,
    ResamplingPlan,
    hierarchical_bootstrap,
    permutation_test,
)


def _paired_table(seed: int = 4) -> tuple[ObservationTable, StudyDesign, Estimand]:
    rng = np.random.default_rng(seed)
    animals = np.repeat([f"a{i}" for i in range(8)], 40)
    conditions = np.tile(np.repeat(["control", "drug"], 20), 8)
    animal_effect = np.repeat(rng.normal(0, 1, 8), 40)
    outcomes = animal_effect + (conditions == "drug") * 0.5 + rng.normal(0, 0.2, 320)
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{i}" for i in range(320)],
            "animal": animals.tolist(),
            "condition": conditions.tolist(),
            "outcome": outcomes.tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")
    return table, design, estimand


def test_hierarchical_bootstrap_preserves_resampled_animal_copies() -> None:
    table, design, estimand = _paired_table()

    result = hierarchical_bootstrap(
        table,
        design,
        estimand,
        ResamplingPlan(("animal", "event")),
        interval_method="percentile",
        draws=200,
        seed=9,
    )

    assert 0.45 < result.estimate < 0.55
    assert (
        result.confidence_interval[0] < result.estimate < result.confidence_interval[1]
    )
    assert len(result.distribution) == 200


def test_paired_sign_flip_uses_animal_level_differences() -> None:
    table, design, estimand = _paired_table()

    result = permutation_test(
        table,
        design,
        estimand,
        PermutationPlan("sign_flip", "animal"),
        permutations=499,
        seed=2,
    )

    assert result.p_value < 0.01


def test_shuffle_moves_labels_only_between_assignment_units() -> None:
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{i}" for i in range(12)],
            "animal": np.repeat(["a", "b", "c", "d"], 3).tolist(),
            "condition": np.repeat(["control", "control", "drug", "drug"], 3).tolist(),
            "outcome": np.repeat([0.0, 0.1, 1.0, 1.1], 3).tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(Factor("condition", "condition", "categorical", "animal"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")

    result = permutation_test(
        table,
        design,
        estimand,
        PermutationPlan("shuffle", "animal"),
        permutations=99,
        seed=1,
    )

    assert result.estimate == 1.0
    assert 0 < result.p_value <= 1


def test_between_unit_bootstrap_can_preserve_condition_strata() -> None:
    table, design, estimand = _paired_table()

    result = hierarchical_bootstrap(
        table,
        design,
        estimand,
        ResamplingPlan(("animal", "event"), strata=("condition",)),
        interval_method="percentile",
        draws=50,
        seed=4,
    )

    assert np.all(np.isfinite(result.distribution))
