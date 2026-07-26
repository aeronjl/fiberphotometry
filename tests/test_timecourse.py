import json

import numpy as np
import pytest

from fiberphotometry import infer_peri_event_contrast


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
