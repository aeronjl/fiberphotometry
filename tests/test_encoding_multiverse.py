import json

import numpy as np
import pytest

from fiberphotometry.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    EventModulationSpec,
    LinearProgressBasisSpec,
    ProgressKernelSpec,
    RaisedCosineBasisSpec,
)
from fiberphotometry.encoding_multiverse import (
    EncodingModelAlternative,
    EncodingMultiverseSpec,
    materialize_encoding_multiverse,
    run_encoding_multiverse,
)


def _sessions(
    *, different_equal_count_masks: bool = False
) -> tuple[EncodingSession, ...]:
    rng = np.random.default_rng(2107)
    sessions = []
    dt = 0.1
    for animal in range(6):
        time = np.arange(0.0, 20.0, dt)
        cue = np.arange(2.0, 18.0, 3.0)
        reward = cue + 0.7
        motion = np.sin(time * 0.5 + animal)
        pupil = np.cos(time * 0.3 + animal)
        response = 0.15 * motion + rng.normal(0.0, 0.05, len(time))
        for event_time in cue:
            index = round(event_time / dt)
            response[index : index + 3] += (0.2, 0.4, 0.15)
        for event_time in reward:
            index = round(event_time / dt)
            response[index : index + 3] += (0.6, 1.0, 0.5)
        validity = {}
        if different_equal_count_masks:
            motion_valid = np.ones(len(time), dtype=bool)
            pupil_valid = np.ones(len(time), dtype=bool)
            motion_valid[20:30] = False
            pupil_valid[80:90] = False
            validity = {"motion": motion_valid, "pupil": pupil_valid}
        sessions.append(
            EncodingSession.from_arrays(
                subject=f"mouse-{animal}",
                session="day-0",
                time=time,
                response=response,
                events={"cue": cue, "reward": reward},
                continuous_covariates={"motion": motion, "pupil": pupil},
                continuous_covariate_validity=validity,
            )
        )
    return tuple(sessions)


def _model(
    *events: EventKernelSpec,
    covariates: tuple[str, ...] = (),
    folds: int = 3,
) -> EncodingModelSpec:
    return EncodingModelSpec(
        event_kernels=events,
        continuous_covariates=covariates,
        alpha_grid=(0.1, 1.0),
        group_by="animal",
        folds=folds,
        minimum_session_coverage=0.8,
    )


def test_compares_named_models_on_identical_held_out_evidence() -> None:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    reward = EventKernelSpec("reward", (0.0, 0.2))
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative(
                "cue-only",
                "Minimal task-event model.",
                _model(cue),
            ),
            EncodingModelAlternative(
                "cue-and-reward",
                "Separate the delayed reward response from the cue.",
                _model(cue, reward),
            ),
        ),
        reference="cue-only",
        intent="exploratory",
    )

    materialized = materialize_encoding_multiverse(spec)
    result = run_encoding_multiverse(_sessions(), spec)
    comparison = next(
        item for item in result.comparisons if item.name == "cue-and-reward"
    )

    assert len({item.universe_id for item in materialized}) == 2
    assert [item.universe_id for item in materialized] == [
        item.universe_id for item in materialize_encoding_multiverse(spec)
    ]
    assert result.summary.successful_universes == 2
    assert result.summary.failed_universes == 0
    assert result.summary.directly_comparable_universes == 2
    assert comparison.status == "direct_predictive_comparison"
    assert comparison.exact_same_observations is True
    assert comparison.delta_mean_r_squared is not None
    assert comparison.delta_mean_r_squared > 0.3
    payload = json.loads(result.to_json())
    assert payload["artifact_type"] == "event_kernel_encoding_multiverse"
    assert payload["schema_version"] == "1"


def test_equal_counts_at_different_indices_are_descriptive_only() -> None:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative(
                "motion",
                "Adjust for confidence-gated motion.",
                _model(cue, covariates=("motion",)),
            ),
            EncodingModelAlternative(
                "pupil",
                "Adjust for confidence-gated pupil size.",
                _model(cue, covariates=("pupil",)),
            ),
        ),
        reference="motion",
        intent="exploratory",
    )

    result = run_encoding_multiverse(
        _sessions(different_equal_count_masks=True),
        spec,
    )
    models = {
        item.name: item.model_result
        for item in result.universes
        if item.model_result is not None
    }
    comparison = next(item for item in result.comparisons if item.name == "pupil")

    assert models["motion"].observations == models["pupil"].observations
    assert comparison.status == "descriptive_only"
    assert comparison.exact_same_observations is False
    assert comparison.delta_mean_r_squared is None
    assert result.summary.descriptive_only_universes == 1


def test_fir_and_raised_cosine_bases_compare_on_common_evidence() -> None:
    fir = EventKernelSpec("cue", (0.0, 0.4))
    cosine = EventKernelSpec(
        "cue",
        (0.0, 0.4),
        basis=RaisedCosineBasisSpec(functions=3),
    )
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative("fir", "Unconstrained lag curve.", _model(fir)),
            EncodingModelAlternative(
                "raised-cosine",
                "Lower-dimensional smooth lag curve.",
                _model(cosine),
            ),
        ),
        reference="fir",
        intent="exploratory",
    )

    result = run_encoding_multiverse(_sessions(), spec)
    comparison = next(
        item for item in result.comparisons if item.name == "raised-cosine"
    )
    cosine_result = next(
        item.model_result for item in result.universes if item.name == "raised-cosine"
    )

    assert comparison.status == "direct_predictive_comparison"
    assert comparison.delta_mean_r_squared is not None
    assert cosine_result is not None
    assert cosine_result.event_kernels[0].basis.family == "raised_cosine"
    assert len(cosine_result.event_kernels[0].basis.coefficient) == 3
    assert len(cosine_result.event_kernels[0].coefficient) == 5


def test_trial_history_kernel_is_a_named_common_evidence_alternative() -> None:
    sessions = tuple(
        EncodingSession.from_arrays(
            subject=session.subject,
            session=session.session,
            time=session.time,
            response=session.response,
            events=session.events,
            continuous_covariates=session.continuous_covariates,
            event_values={
                "cue": {
                    "outcome": tuple(
                        0.5 if index % 2 else -0.5
                        for index in range(len(session.events["cue"]))
                    )
                }
            },
        )
        for session in _sessions()
    )
    cue = EventKernelSpec("cue", (0.0, 0.4))
    history = EventKernelSpec(
        "cue-by-previous-outcome",
        (0.0, 0.4),
        source_event="cue",
        modulation=EventModulationSpec("outcome", lag_events=1),
    )
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative("cue-only", "Current cue only.", _model(cue)),
            EncodingModelAlternative(
                "cue-plus-history",
                "Add previous-outcome modulation.",
                _model(cue, history),
            ),
        ),
        reference="cue-only",
        intent="exploratory",
    )

    result = run_encoding_multiverse(sessions, spec)
    comparison = next(
        item for item in result.comparisons if item.name == "cue-plus-history"
    )
    history_result = next(
        item.model_result
        for item in result.universes
        if item.name == "cue-plus-history"
    )

    assert comparison.status == "direct_predictive_comparison"
    assert comparison.exact_same_observations is True
    assert history_result is not None
    assert history_result.event_kernels[1].modulation is not None
    assert history_result.event_kernels[1].modulation.lag_events == 1


def test_progress_kernel_is_a_named_common_evidence_alternative() -> None:
    sessions = tuple(
        EncodingSession.from_arrays(
            subject=session.subject,
            session=session.session,
            time=session.time,
            response=session.response,
            events=session.events,
            continuous_covariates=session.continuous_covariates,
            intervals={
                "cue-state": tuple(
                    (float(start), float(start + 0.5))
                    for start in session.events["cue"]
                )
            },
        )
        for session in _sessions()
    )
    cue = EventKernelSpec("cue", (0.0, 0.4))
    progress = ProgressKernelSpec(
        "cue-state-progress",
        source_interval="cue-state",
        basis=LinearProgressBasisSpec(functions=3),
    )
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative("cue-only", "Point-event model.", _model(cue)),
            EncodingModelAlternative(
                "cue-plus-progress",
                "Add within-state normalized progress.",
                EncodingModelSpec(
                    event_kernels=(cue,),
                    progress_kernels=(progress,),
                    alpha_grid=(0.1, 1.0),
                    folds=3,
                    minimum_session_coverage=0.8,
                ),
            ),
        ),
        reference="cue-only",
        intent="exploratory",
    )

    result = run_encoding_multiverse(sessions, spec)
    comparison = next(
        item for item in result.comparisons if item.name == "cue-plus-progress"
    )
    progress_result = next(
        item.model_result
        for item in result.universes
        if item.name == "cue-plus-progress"
    )

    assert comparison.status == "direct_predictive_comparison"
    assert comparison.exact_same_observations is True
    assert progress_result is not None
    assert progress_result.progress_kernels[0].source_interval == "cue-state"


def test_retains_failed_alternative_without_improving_summary() -> None:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    reward = EventKernelSpec("reward", (0.0, 0.2))
    omission = EventKernelSpec("omission", (0.0, 0.2))
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative("cue", "Cue reference.", _model(cue)),
            EncodingModelAlternative(
                "cue-reward",
                "Cue and reward model.",
                _model(cue, reward),
            ),
            EncodingModelAlternative(
                "omission",
                "Prospective omission model.",
                _model(omission),
            ),
        ),
        reference="cue",
        intent="confirmatory",
    )

    result = run_encoding_multiverse(_sessions(), spec)
    failed = next(item for item in result.universes if item.name == "omission")
    comparison = next(item for item in result.comparisons if item.name == "omission")

    assert result.summary.total_universes == 3
    assert result.summary.successful_universes == 2
    assert result.summary.failed_universes == 1
    assert failed.status == "failed"
    assert failed.error is not None
    assert "lacks event 'omission'" in failed.error
    assert comparison.status == "failed"
    assert comparison.delta_mean_r_squared is None


def test_rejects_duplicate_models_and_validation_policy_changes() -> None:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    duplicate = EncodingModelAlternative("one", "First.", _model(cue))
    with pytest.raises(ValueError, match="distinct model specs"):
        EncodingMultiverseSpec(
            alternatives=(
                duplicate,
                EncodingModelAlternative("two", "Second.", _model(cue)),
            ),
            reference="one",
            intent="exploratory",
        )

    with pytest.raises(ValueError, match="share grouping, folds"):
        EncodingMultiverseSpec(
            alternatives=(
                duplicate,
                EncodingModelAlternative(
                    "different-folds",
                    "Changes the validation target.",
                    _model(cue, folds=2),
                ),
            ),
            reference="one",
            intent="exploratory",
        )
