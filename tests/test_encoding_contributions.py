import json

import numpy as np
import pytest

from fiberphotometry.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    RaisedCosineBasisSpec,
)
from fiberphotometry.encoding_contributions import (
    PredictorFamilyContributionSpec,
    PredictorFamilyDropSpec,
    PredictorFamilyGroupDelta,
    _paired_dispersion,
    assess_predictor_family_contributions,
)
from fiberphotometry.encoding_multiverse import (
    EncodingModelAlternative,
    EncodingMultiverseSpec,
    run_encoding_multiverse,
)


def _sessions(*, masked_motion: bool = False) -> tuple[EncodingSession, ...]:
    rng = np.random.default_rng(817)
    sessions = []
    dt = 0.1
    for animal in range(6):
        time = np.arange(0.0, 24.0, dt)
        cue = np.arange(2.0, 22.0, 3.0)
        reward = cue + 0.7
        motion = np.sin(time * 0.7 + animal * 0.3)
        response = 0.35 * motion + rng.normal(0.0, 0.04, len(time))
        for event_time in cue:
            index = round(event_time / dt)
            response[index : index + 3] += (0.2, 0.4, 0.2)
        for event_time in reward:
            index = round(event_time / dt)
            response[index : index + 3] += (0.5, 0.9, 0.4)
        validity = {}
        if masked_motion:
            motion_valid = np.ones(len(time), dtype=bool)
            motion_valid[30:42] = False
            validity = {"motion": motion_valid}
        sessions.append(
            EncodingSession.from_arrays(
                subject=f"mouse-{animal}",
                session="day-0",
                time=time,
                response=response,
                events={"cue": cue, "reward": reward},
                continuous_covariates={"motion": motion},
                continuous_covariate_validity=validity,
            )
        )
    return tuple(sessions)


def _model(
    *events: EventKernelSpec,
    covariates: tuple[str, ...] = (),
    alpha_grid: tuple[float, ...] = (0.1, 1.0),
) -> EncodingModelSpec:
    return EncodingModelSpec(
        event_kernels=events,
        continuous_covariates=covariates,
        alpha_grid=alpha_grid,
        group_by="animal",
        folds=3,
        minimum_session_coverage=0.8,
    )


def _multiverse(
    *, smooth_reduced_cue: bool = False, changed_alpha: bool = False
) -> EncodingMultiverseSpec:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    reduced_cue = (
        EventKernelSpec(
            "cue",
            (0.0, 0.2),
            basis=RaisedCosineBasisSpec(functions=2),
        )
        if smooth_reduced_cue
        else cue
    )
    reward = EventKernelSpec("reward", (0.0, 0.2))
    return EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative(
                "full",
                "Cue, reward, and movement.",
                _model(cue, reward, covariates=("motion",)),
            ),
            EncodingModelAlternative(
                "without-movement",
                "Literal movement-family drop.",
                _model(
                    reduced_cue,
                    reward,
                    alpha_grid=(0.1, 1.0, 10.0) if changed_alpha else (0.1, 1.0),
                ),
            ),
            EncodingModelAlternative(
                "without-reward",
                "Literal reward-family drop.",
                _model(cue, covariates=("motion",)),
            ),
        ),
        reference="full",
        intent="exploratory",
    )


def _contribution_spec() -> PredictorFamilyContributionSpec:
    return PredictorFamilyContributionSpec(
        full_model="full",
        families=(
            PredictorFamilyDropSpec(
                family="movement",
                reduced_model="without-movement",
                removed_predictors=("motion",),
                rationale="Ask whether movement improves held-out prediction.",
            ),
            PredictorFamilyDropSpec(
                family="reward events",
                reduced_model="without-reward",
                removed_predictors=("reward",),
                rationale="Ask whether reward events improve held-out prediction.",
            ),
        ),
    )


def test_reports_paired_predictive_deltas_for_literal_family_drops() -> None:
    multiverse = run_encoding_multiverse(_sessions(), _multiverse())

    result = assess_predictor_family_contributions(multiverse, _contribution_spec())
    movement, reward = result.comparisons

    assert movement.status == "paired_predictive_comparison"
    assert movement.exact_same_observations is True
    assert movement.delta_mean_r_squared is not None
    assert movement.delta_mean_r_squared > 0.1
    assert movement.full_universe_id != movement.reduced_universe_id
    assert movement.full_selected_alpha in (0.1, 1.0)
    assert movement.reduced_selected_alpha in (0.1, 1.0)
    assert len(movement.group_deltas) == 6
    assert movement.group_dispersion is not None
    assert movement.group_dispersion.method == "paired_group_t_dispersion_uncalibrated"
    assert movement.group_dispersion.groups == 6
    assert movement.group_dispersion.calibrated is False
    assert movement.group_dispersion.simultaneous is False
    assert movement.group_dispersion.simultaneous_comparisons == 2
    assert movement.group_dispersion.nominal_level == 0.95
    assert "positively dependent" in movement.group_dispersion.dependence
    assert "multiplicity" in movement.group_dispersion.multiplicity
    assert reward.status == "paired_predictive_comparison"
    assert reward.delta_mean_r_squared is not None
    assert reward.delta_mean_r_squared > 0.1
    payload = json.loads(result.to_json())
    assert payload["artifact_type"] == "predictor_family_contribution_result"
    assert payload["schema_version"] == "1"


def _dispersion_coverage(correlation: float, trials: int = 2_000) -> float:
    rng = np.random.default_rng(20260728)
    groups = 6
    truth = 0.05
    scale = 0.02
    covered = 0
    for _ in range(trials):
        shared = rng.normal(0.0, np.sqrt(correlation))
        private = rng.normal(0.0, np.sqrt(1.0 - correlation), groups)
        values = truth + scale * (shared + private)
        deltas = tuple(
            PredictorFamilyGroupDelta(
                group=f"animal-{index}",
                observations=200,
                full_r_squared=0.4 + float(value),
                reduced_r_squared=0.4,
                delta_r_squared=float(value),
            )
            for index, value in enumerate(values)
        )
        summary = _paired_dispersion(deltas, 0.95, 1)
        covered += summary.range_lower <= truth <= summary.range_upper
    return covered / trials


def test_paired_group_range_under_covers_when_held_out_deltas_are_dependent() -> None:
    independent = _dispersion_coverage(0.0)
    dependent = _dispersion_coverage(0.6)

    assert 0.93 < independent < 0.97
    assert dependent < 0.75

    summary = _paired_dispersion(
        tuple(
            PredictorFamilyGroupDelta(
                group=f"animal-{index}",
                observations=200,
                full_r_squared=0.4 + value,
                reduced_r_squared=0.4,
                delta_r_squared=value,
            )
            for index, value in enumerate((0.04, 0.05, 0.06, 0.05, 0.07, 0.03))
        ),
        0.95,
        3,
    )

    assert summary.calibrated is False
    assert summary.simultaneous is False
    assert summary.method == "paired_group_t_dispersion_uncalibrated"
    assert summary.simultaneous_comparisons == 3
    assert not hasattr(summary, "confidence_level")


def test_different_complete_case_evidence_is_descriptive_only() -> None:
    multiverse = run_encoding_multiverse(_sessions(masked_motion=True), _multiverse())

    result = assess_predictor_family_contributions(multiverse, _contribution_spec())
    movement = result.comparisons[0]

    assert movement.status == "descriptive_only"
    assert movement.exact_same_observations is False
    assert movement.delta_mean_r_squared is None
    assert movement.group_deltas == ()
    assert movement.group_dispersion is None


def test_rejects_changed_shared_predictors_or_tuning_policy() -> None:
    with pytest.raises(ValueError, match="changes shared predictor definitions"):
        assess_predictor_family_contributions(
            run_encoding_multiverse(_sessions(), _multiverse(smooth_reduced_cue=True)),
            _contribution_spec(),
        )

    with pytest.raises(ValueError, match="changes model or tuning policy"):
        assess_predictor_family_contributions(
            run_encoding_multiverse(_sessions(), _multiverse(changed_alpha=True)),
            _contribution_spec(),
        )


def test_rejects_inaccurate_removed_predictor_declaration() -> None:
    spec = PredictorFamilyContributionSpec(
        full_model="full",
        families=(
            PredictorFamilyDropSpec(
                family="movement",
                reduced_model="without-movement",
                removed_predictors=("reward",),
                rationale="Intentionally inaccurate declaration.",
            ),
        ),
    )

    with pytest.raises(ValueError, match="literal model difference"):
        assess_predictor_family_contributions(
            run_encoding_multiverse(_sessions(), _multiverse()), spec
        )


def test_retains_failed_full_or_reduced_model() -> None:
    sessions = tuple(
        EncodingSession.from_arrays(
            subject=session.subject,
            session=session.session,
            time=session.time,
            response=session.response,
            events={"reward": session.events["reward"]},
            continuous_covariates={},
        )
        for session in _sessions()
    )
    cue = EventKernelSpec("cue", (0.0, 0.2))
    reward = EventKernelSpec("reward", (0.0, 0.2))
    multiverse = run_encoding_multiverse(
        sessions,
        EncodingMultiverseSpec(
            alternatives=(
                EncodingModelAlternative(
                    "full", "Cue and reward.", _model(cue, reward)
                ),
                EncodingModelAlternative("cue-only", "Cue only.", _model(cue)),
            ),
            reference="full",
            intent="exploratory",
        ),
    )
    spec = PredictorFamilyContributionSpec(
        full_model="full",
        families=(
            PredictorFamilyDropSpec(
                family="reward",
                reduced_model="cue-only",
                removed_predictors=("reward",),
                rationale="Retain an infeasible declared comparison.",
            ),
        ),
    )

    comparison = assess_predictor_family_contributions(multiverse, spec).comparisons[0]

    assert comparison.status == "failed"
    assert comparison.delta_mean_r_squared is None
    assert comparison.group_deltas == ()
    assert "lacks event 'cue'" in comparison.reason
