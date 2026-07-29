import json

import numpy as np
import pytest

from fiberphotometry.association_inference import AssociationSessionEstimate
from fiberphotometry.population import (
    PopulationContrastSpec,
    PopulationGroupAssignment,
    PopulationInteractionSpec,
)
from fiberphotometry.population_workflows import (
    materialize_association_population,
    materialize_state_band_power_population,
    materialize_transient_population,
)
from fiberphotometry.spectral import (
    SpectralAnalysisSpec,
    StateEpoch,
    StatePSDSession,
    state_conditioned_psd,
)
from fiberphotometry.transient_inference import TransientStudySession
from fiberphotometry.transient_product import (
    TransientQuantificationResult,
    TransientQuantificationSpec,
    TransientQuantificationSummary,
)


def _transient_session(
    subject: str, condition: str, count: int
) -> TransientStudySession:
    result = TransientQuantificationResult(
        spec=TransientQuantificationSpec(),
        variable="dff",
        detector_variable="dff",
        events=(),
        exclusions=(),
        summaries=(
            TransientQuantificationSummary(
                channel="NAc",
                analyzed_duration_s=60.0,
                count=count,
                rate_per_minute=float(count),
                median_amplitude=None,
                median_width_s=None,
                median_auc=None,
                median_interval_s=None,
            ),
        ),
        bins=None,
    )
    return TransientStudySession(subject, f"{subject}-{condition}", condition, result)


def _assignments() -> tuple[PopulationGroupAssignment, ...]:
    return tuple(
        PopulationGroupAssignment(subject, group)
        for subject, group in (
            ("c1", "control"),
            ("c2", "control"),
            ("t1", "treatment"),
            ("t2", "treatment"),
        )
    )


def _interaction_spec() -> PopulationInteractionSpec:
    return PopulationInteractionSpec(
        group_numerator="treatment",
        group_denominator="control",
        condition_numerator="post",
        condition_denominator="pre",
        draws=200,
        seed=7,
    )


def test_transient_materialization_preserves_zero_event_exposure_and_interacts() -> (
    None
):
    counts = {
        "c1": (0, 1),
        "c2": (1, 2),
        "t1": (1, 5),
        "t2": (2, 6),
    }
    sessions = [
        _transient_session(subject, condition, count)
        for subject, values in counts.items()
        for condition, count in zip(("pre", "post"), values, strict=True)
    ]

    materialized = materialize_transient_population(
        sessions,
        metric="rate_per_minute",
        channel="NAc",
        levels=("pre", "post"),
    )
    zero = next(
        item
        for item in materialized.population_estimates
        if item.unit_id == "c1" and item.level == "pre"
    )
    assert zero.estimate == (0.0,)
    assert zero.observation_count == 0
    assert zero.support == (1,)
    assert materialized.contrast(
        PopulationContrastSpec("post", "pre", "paired", draws=200)
    ).estimate == pytest.approx((2.5,))

    interaction = materialized.interaction(_assignments(), _interaction_spec())
    assert interaction.population.estimate == pytest.approx((3.0,))
    assert len(interaction.within_unit_contrasts) == 4
    assert json.loads(materialized.to_json())["schema_version"] == "1"


def test_state_band_power_materialization_uses_sessions_not_windows_as_units() -> None:
    rate = 20.0
    time = np.arange(0, 20, 1 / rate)
    epochs = (StateEpoch("post", 0, 10), StateEpoch("pre", 10, 20))
    sessions = []
    for subject, post_amplitude in {
        "c1": 1.2,
        "c2": 1.3,
        "t1": 2.0,
        "t2": 2.1,
    }.items():
        for session_index in range(2):
            values = np.where(
                time < 10,
                post_amplitude * np.sin(2 * np.pi * 3 * time),
                np.sin(2 * np.pi * 3 * time),
            )
            sessions.append(
                StatePSDSession(
                    subject,
                    f"{subject}-{session_index}",
                    state_conditioned_psd(
                        time,
                        values,
                        epochs,
                        SpectralAnalysisSpec(window_duration_s=2),
                    ),
                )
            )

    materialized = materialize_state_band_power_population(
        sessions,
        states=("pre", "post"),
        frequency_band_hz=(2.0, 4.0),
    )
    assert {item.support for item in materialized.population_estimates} == {(2,)}
    assert all(item.observation_count > 2 for item in materialized.population_estimates)
    interaction = materialized.interaction(_assignments(), _interaction_spec())
    assert interaction.population.estimate[0] > 0
    assert interaction.population.numerator_units_per_point == (2,)
    assert interaction.population.denominator_units_per_point == (2,)


def test_association_materialization_retains_pair_support_and_interacts() -> None:
    sessions = []
    values = {
        "c1": (0.1, 0.2),
        "c2": (0.2, 0.3),
        "t1": (0.1, 0.6),
        "t2": (0.2, 0.7),
    }
    for subject, (pre, post) in values.items():
        for condition, value in (("pre", pre), ("post", post)):
            for session_index in range(2):
                sessions.append(
                    AssociationSessionEstimate(
                        subject,
                        f"{subject}-{condition}-{session_index}",
                        condition,
                        "green__red",
                        "mean_coherence_1_4Hz",
                        value,
                        20,
                        "fixture",
                    )
                )

    materialized = materialize_association_population(
        sessions,
        metric="mean_coherence_1_4Hz",
        pair_id="green__red",
        levels=("pre", "post"),
    )
    assert {item.support for item in materialized.population_estimates} == {(2,)}
    assert {item.observation_count for item in materialized.population_estimates} == {
        40
    }
    interaction = materialized.interaction(_assignments(), _interaction_spec())
    assert interaction.population.estimate == pytest.approx((0.4,))


def test_population_materializers_refuse_duplicate_lower_level_identities() -> None:
    duplicate = AssociationSessionEstimate(
        "mouse", "session", "pre", "pair", "metric", 0.2, 10, "fixture"
    )
    with pytest.raises(ValueError, match="identities must be unique"):
        materialize_association_population(
            [duplicate, duplicate],
            metric="metric",
            pair_id="pair",
            levels=("pre", "post"),
        )
