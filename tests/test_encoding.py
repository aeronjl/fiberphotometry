import json

import numpy as np
import pytest

from fiberphotometry.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    _build_design,
    _residual_metrics,
    fit_event_kernel_model,
)


def _simulated_sessions() -> tuple[EncodingSession, ...]:
    rng = np.random.default_rng(481)
    sessions = []
    dt = 0.1
    cue_kernel = np.array([0.25, 0.8, 1.2, 0.7, 0.2])
    reward_kernel = np.array([-0.2, 0.4, 0.9, 0.45])
    for animal_index in range(8):
        for session_index in range(2):
            time = np.arange(0.0, 40.0, dt)
            cue = np.arange(3.0, 36.0, 4.0) + 0.1 * (animal_index % 2)
            reward = cue + 0.5 + 0.1 * (session_index % 2)
            motion = np.sin(time * 0.7 + animal_index) + rng.normal(0, 0.15, len(time))
            response = 0.35 * motion + 0.05 * animal_index
            cue_scale = 1 + 0.04 * (animal_index - 3.5)
            reward_scale = 1 - 0.03 * (animal_index - 3.5)
            for event_time in cue:
                index = round(event_time / dt)
                response[index - 1 : index + 4] += cue_scale * cue_kernel
            for event_time in reward:
                index = round(event_time / dt)
                response[index : index + 4] += reward_scale * reward_kernel
            response += rng.normal(0, 0.08, len(time))
            sessions.append(
                EncodingSession.from_arrays(
                    subject=f"mouse-{animal_index}",
                    session=f"day-{session_index}",
                    time=time,
                    response=response,
                    events={"cue": cue, "reward": reward},
                    continuous_covariates={"motion": motion},
                )
            )
    return tuple(sessions)


def test_recovers_overlapping_event_kernels_with_animal_held_out_cv() -> None:
    result = fit_event_kernel_model(
        _simulated_sessions(),
        EncodingModelSpec(
            event_kernels=(
                EventKernelSpec("cue", (-0.1, 0.3)),
                EventKernelSpec("reward", (0.0, 0.3)),
            ),
            continuous_covariates=("motion",),
            alpha_grid=(0.0, 0.1, 1.0),
            group_by="animal",
            folds=4,
        ),
    )

    assert result.animals == 8
    assert result.sessions == 16
    assert result.groups == 8
    assert result.sample_interval_s == pytest.approx(0.1)
    kernels = {kernel.name: kernel for kernel in result.event_kernels}
    assert kernels["cue"].lag_s == pytest.approx((-0.1, 0.0, 0.1, 0.2, 0.3))
    assert kernels["cue"].coefficient == pytest.approx(
        (0.25, 0.8, 1.2, 0.7, 0.2), abs=0.04
    )
    assert kernels["reward"].coefficient == pytest.approx(
        (-0.2, 0.4, 0.9, 0.45), abs=0.04
    )
    motion = result.continuous_coefficients[0]
    assert motion.name == "motion"
    assert motion.coefficient / motion.training_standard_deviation == pytest.approx(
        0.35, abs=0.02
    )
    selected = next(
        item for item in result.cross_validation if item.alpha == result.selected_alpha
    )
    assert selected.mean_r_squared > 0.8
    held_out = [group for fold in selected.folds for group in fold.held_out_groups]
    assert sorted(held_out) == [f"mouse-{index}" for index in range(8)]
    assert len(held_out) == len(set(held_out))
    payload = json.loads(result.to_json())
    assert payload["artifact_type"] == "event_kernel_encoding_result"
    assert payload["schema_version"] == "2"
    uncertainty = {
        kernel.name: kernel for kernel in result.kernel_uncertainty.event_kernels
    }
    assert result.kernel_uncertainty.omitted_groups == tuple(
        f"mouse-{index}" for index in range(8)
    )
    assert uncertainty["cue"].lower[2] < 1.2 < uncertainty["cue"].upper[2]
    assert uncertainty["reward"].lower[2] < 0.9 < uncertainty["reward"].upper[2]
    assert len(result.residual_diagnostics.groups) == 8
    assert result.residual_diagnostics.pooled_observations == result.observations


def test_session_grouping_uses_compound_identity_and_never_crosses_boundaries() -> None:
    sessions = _simulated_sessions()[:4]
    result = fit_event_kernel_model(
        sessions,
        EncodingModelSpec(
            event_kernels=(EventKernelSpec("cue", (0.0, 0.2)),),
            group_by="session",
            folds=2,
        ),
    )

    held_out = {
        group
        for alpha in result.cross_validation
        for fold in alpha.folds
        for group in fold.held_out_groups
    }
    assert held_out == {
        "mouse-0/day-0",
        "mouse-0/day-1",
        "mouse-1/day-0",
        "mouse-1/day-1",
    }

    time = np.arange(5.0)
    boundary_sessions = tuple(
        EncodingSession.from_arrays(
            subject=f"animal-{index}",
            session="recording",
            time=time,
            response=np.arange(5.0),
            events={"pulse": (4.0,) if index == 0 else ()},
        )
        for index in range(2)
    )
    design = _build_design(
        boundary_sessions,
        EncodingModelSpec(
            event_kernels=(EventKernelSpec("pulse", (0.0, 2.0)),),
            group_by="session",
            folds=2,
        ),
    )
    assert design.values[4].toarray().ravel().tolist() == [1.0, 0.0, 0.0]
    assert design.values[5:8].nnz == 0


def test_rejects_irregular_sampling_and_absent_declared_events() -> None:
    session = _simulated_sessions()[0]
    irregular = EncodingSession.from_arrays(
        subject=session.subject,
        session=session.session,
        time=np.concatenate((session.time[:100], session.time[100:] + 0.02)),
        response=session.response,
        events=session.events,
        continuous_covariates=session.continuous_covariates,
    )
    spec = EncodingModelSpec(event_kernels=(EventKernelSpec("cue", (0.0, 0.2)),))
    with pytest.raises(ValueError, match="requires regular sampling"):
        fit_event_kernel_model((irregular,), spec)

    empty = EncodingSession.from_arrays(
        subject="mouse-extra",
        session="day-0",
        time=session.time,
        response=session.response,
        events={"omission": ()},
    )
    absent_spec = EncodingModelSpec(
        event_kernels=(EventKernelSpec("omission", (0.0, 0.2)),)
    )
    with pytest.raises(ValueError, match="no occurrences"):
        fit_event_kernel_model(
            (
                empty,
                empty.__class__.from_arrays(
                    subject="mouse-other",
                    session="day-0",
                    time=empty.time,
                    response=empty.response,
                    events={"omission": ()},
                ),
            ),
            absent_spec,
        )


def test_residual_diagnostics_detect_autocorrelation_and_reset_sessions() -> None:
    rng = np.random.default_rng(91)
    white = rng.normal(size=400)
    autoregressive = np.zeros(400)
    innovations = rng.normal(size=400)
    for index in range(1, len(autoregressive)):
        autoregressive[index] = 0.85 * autoregressive[index - 1] + innovations[index]
    sessions = np.asarray(["first"] * 200 + ["second"] * 200)
    white_metrics = _residual_metrics(white, np.zeros(400), sessions)
    ar_metrics = _residual_metrics(autoregressive, np.zeros(400), sessions)

    assert white_metrics[-2] is not None
    assert ar_metrics[-2] is not None
    assert white_metrics[-1] is not None
    assert ar_metrics[-1] is not None
    assert ar_metrics[-2] > white_metrics[-2] + 0.7
    assert ar_metrics[-1] < white_metrics[-1] - 1.0

    boundary_residual = np.asarray([0.0, 1.0, 2.0, 100.0, 101.0, 102.0])
    boundary_sessions = np.asarray(["a", "a", "a", "b", "b", "b"])
    metrics = _residual_metrics(boundary_residual, np.zeros(6), boundary_sessions)
    expected_difference_sum = 4.0
    assert metrics[-1] == pytest.approx(
        expected_difference_sum / float(boundary_residual @ boundary_residual)
    )
