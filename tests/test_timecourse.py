import json

import numpy as np
import pytest

from fipha import infer_peri_event_contrast
from fipha.population import PopulationInteractionSpec
from fipha.timecourse import infer_peri_event_interaction


def _curves(seed: int = 7):
    rng = np.random.default_rng(seed)
    time = np.linspace(-1, 2, 61)
    animals = []
    sessions = []
    conditions = []
    values = []
    effect = 0.3 * np.exp(-(((time - 0.35) / 0.25) ** 2))
    for animal_index in range(10):
        animal_noise = rng.normal(0, 0.025, len(time))
        for condition in ("control", "stimulus"):
            for event_index in range(6):
                values.append(
                    animal_noise
                    + (effect if condition == "stimulus" else 0)
                    + rng.normal(0, 0.04, len(time))
                )
                animals.append(f"a{animal_index}")
                sessions.append(f"a{animal_index}:s{event_index % 2}")
                conditions.append(condition)
    return (
        np.asarray(values),
        time,
        tuple(animals),
        tuple(sessions),
        tuple(conditions),
        effect,
    )


def test_peri_event_inference_resamples_animals_and_separates_bands() -> None:
    values, time, animals, sessions, conditions, effect = _curves()

    result = infer_peri_event_contrast(
        values,
        time,
        animals=animals,
        sessions=sessions,
        conditions=conditions,
        numerator="stimulus",
        denominator="control",
        draws=500,
        seed=12,
    )

    estimate = np.asarray(result.estimate)
    pointwise_width = np.asarray(result.pointwise_upper) - np.asarray(
        result.pointwise_lower
    )
    simultaneous_width = np.asarray(result.simultaneous_upper) - np.asarray(
        result.simultaneous_lower
    )
    assert result.animal_count == 10
    assert np.max(np.abs(estimate - effect)) < 0.04
    assert np.median(simultaneous_width) > np.median(pointwise_width)
    assert result.simultaneous_critical_value > 1.96
    assert set(result.animals_per_time) == {10}
    assert json.loads(result.to_json())["method"].startswith("animal_bootstrap")
    assert len(result.session_estimates) == 40
    assert len(result.population.unit_estimates) == 20
    assert result.population.included_units == tuple(f"a{i}" for i in range(10))
    assert len(result.population.influence) == 10
    assert result.schema_version == "2"


def test_peri_event_inference_is_seeded_and_requires_animals() -> None:
    values, time, animals, sessions, conditions, _ = _curves()
    arguments = dict(
        animals=animals,
        sessions=sessions,
        conditions=conditions,
        numerator="stimulus",
        denominator="control",
        draws=100,
        seed=3,
    )
    first = infer_peri_event_contrast(values, time, **arguments)
    second = infer_peri_event_contrast(values, time, **arguments)
    assert first == second

    selected = np.asarray(animals) == "a0"
    with pytest.raises(ValueError, match="two complete animals"):
        infer_peri_event_contrast(
            values[selected],
            time,
            animals=tuple(np.asarray(animals)[selected]),
            sessions=tuple(np.asarray(sessions)[selected]),
            conditions=tuple(np.asarray(conditions)[selected]),
            numerator="stimulus",
            denominator="control",
            draws=100,
        )


def test_duplicating_events_does_not_create_inferential_precision() -> None:
    values, time, animals, sessions, conditions, _ = _curves()
    arguments = dict(
        relative_time=time,
        animals=animals,
        sessions=sessions,
        conditions=conditions,
        numerator="stimulus",
        denominator="control",
        draws=200,
        seed=5,
    )
    original = infer_peri_event_contrast(values, **arguments)
    duplicated = infer_peri_event_contrast(
        np.repeat(values, 5, axis=0),
        time,
        animals=tuple(value for value in animals for _ in range(5)),
        sessions=tuple(value for value in sessions for _ in range(5)),
        conditions=tuple(value for value in conditions for _ in range(5)),
        numerator="stimulus",
        denominator="control",
        draws=200,
        seed=5,
    )

    assert duplicated.estimate == pytest.approx(original.estimate)
    assert duplicated.standard_error == pytest.approx(original.standard_error)
    assert duplicated.simultaneous_lower == pytest.approx(original.simultaneous_lower)
    assert duplicated.simultaneous_upper == pytest.approx(original.simultaneous_upper)


def test_peri_event_inference_supports_independent_animal_groups() -> None:
    rng = np.random.default_rng(3)
    time = np.linspace(-0.5, 1.0, 16)
    values = []
    animals = []
    sessions = []
    conditions = []
    effect = 0.5 * np.exp(-(((time - 0.25) / 0.2) ** 2))
    for group, offset in (("control", 0.0), ("drug", 1.0)):
        for animal_index in range(4):
            animal = f"{group}-{animal_index}"
            animal_noise = rng.normal(0, 0.02, len(time))
            for session_index in range(2):
                for _ in range(3):
                    values.append(
                        animal_noise + offset * effect + rng.normal(0, 0.02, len(time))
                    )
                    animals.append(animal)
                    sessions.append(f"{animal}:s{session_index}")
                    conditions.append(group)

    result = infer_peri_event_contrast(
        np.asarray(values),
        time,
        animals=tuple(animals),
        sessions=tuple(sessions),
        conditions=tuple(conditions),
        numerator="drug",
        denominator="control",
        design="independent",
        draws=200,
        seed=11,
    )

    assert result.population.design == "independent"
    assert result.animal_count == 8
    assert set(result.animals_per_time) == {8}
    assert set(result.population.numerator_units_per_point) == {4}
    assert set(result.population.denominator_units_per_point) == {4}
    assert np.max(np.abs(np.asarray(result.estimate) - effect)) < 0.05
    assert len(result.session_estimates) == 16
    assert len(result.population.influence) == 8


def test_peri_event_inference_exposes_incomplete_paired_animals() -> None:
    values, time, animals, sessions, conditions, _ = _curves()
    selected = ~((np.asarray(animals) == "a9") & (np.asarray(conditions) == "control"))

    result = infer_peri_event_contrast(
        values[selected],
        time,
        animals=tuple(np.asarray(animals)[selected]),
        sessions=tuple(np.asarray(sessions)[selected]),
        conditions=tuple(np.asarray(conditions)[selected]),
        numerator="stimulus",
        denominator="control",
        draws=100,
    )

    assert result.animal_count == 9
    assert result.population.excluded_units == ("a9",)
    assert "incomplete_paired_animals_excluded" in result.warnings


def test_peri_event_interaction_uses_one_condition_difference_per_animal() -> None:
    rng = np.random.default_rng(15)
    time = np.linspace(-0.5, 1.0, 16)
    effect = 0.5 * np.exp(-(((time - 0.25) / 0.2) ** 2))
    values = []
    animals = []
    sessions = []
    groups = []
    conditions = []
    for group, multiplier in (("control", 0.3), ("drug", 0.8)):
        for animal_index in range(4):
            animal = f"{group}-{animal_index}"
            animal_noise = rng.normal(0, 0.01, len(time))
            for condition in ("pre", "post"):
                for session_index in range(2):
                    for _ in range(3):
                        values.append(
                            animal_noise
                            + (multiplier * effect if condition == "post" else 0)
                            + rng.normal(0, 0.01, len(time))
                        )
                        animals.append(animal)
                        sessions.append(f"{animal}:s{session_index}")
                        groups.append(group)
                        conditions.append(condition)
    spec = PopulationInteractionSpec(
        group_numerator="drug",
        group_denominator="control",
        condition_numerator="post",
        condition_denominator="pre",
        draws=200,
        seed=9,
    )
    arguments = dict(
        relative_time=time,
        animals=tuple(animals),
        sessions=tuple(sessions),
        groups=tuple(groups),
        conditions=tuple(conditions),
        spec=spec,
    )

    result = infer_peri_event_interaction(np.asarray(values), **arguments)
    duplicated = infer_peri_event_interaction(
        np.repeat(np.asarray(values), 4, axis=0),
        relative_time=time,
        animals=tuple(value for value in animals for _ in range(4)),
        sessions=tuple(value for value in sessions for _ in range(4)),
        groups=tuple(value for value in groups for _ in range(4)),
        conditions=tuple(value for value in conditions for _ in range(4)),
        spec=spec,
    )

    assert np.max(np.abs(np.asarray(result.estimate) - 0.5 * effect)) < 0.03
    assert result.interaction.population.included_units == tuple(
        [f"control-{index}" for index in range(4)]
        + [f"drug-{index}" for index in range(4)]
    )
    assert len(result.session_estimates) == 32
    assert duplicated.estimate == pytest.approx(result.estimate)
    assert duplicated.interaction.population.standard_error == pytest.approx(
        result.interaction.population.standard_error
    )
    assert (
        json.loads(result.to_json())["interaction"]["spec"]["group_numerator"] == "drug"
    )


def test_peri_event_interaction_rejects_group_changes_within_animal() -> None:
    values = np.zeros((4, 3))
    with pytest.raises(ValueError, match="exactly one population group"):
        infer_peri_event_interaction(
            values,
            np.asarray((-1.0, 0.0, 1.0)),
            animals=("a", "a", "b", "b"),
            sessions=("a:s", "a:s", "b:s", "b:s"),
            groups=("drug", "control", "control", "control"),
            conditions=("pre", "post", "pre", "post"),
            spec=PopulationInteractionSpec("drug", "control", "post", "pre", draws=100),
        )
