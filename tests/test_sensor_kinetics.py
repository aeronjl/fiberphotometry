import json

import numpy as np
import pytest

from fiberphotometry.sensor_kinetics import (
    DifferenceOfExponentialsModel,
    KineticDeconvolutionSpec,
    KineticForwardSpec,
    KineticModelIdentity,
    SampledImpulseResponseModel,
    assess_kinetic_identifiability,
    deconvolve_sensor_response,
    kinetic_kernel,
    predict_sensor_response,
)


def _identity(*, calibrated: bool = True) -> KineticModelIdentity:
    return KineticModelIdentity(
        model_id="lab-dlight-response",
        model_version="1",
        sensor_profile_id="lab-dlight-profile",
        sensor_profile_version="2026-07",
        input_quantity="latent dopamine drive",
        input_unit="calibration a.u.",
        output_unit="dF/F",
        measurement_context="bench pulse calibration",
        evidence_source="calibration-record-17",
        coefficient_source=(
            "independently_calibrated" if calibrated else "user_declared"
        ),
        calibration_id="calibration-17" if calibrated else None,
    )


def _model(*, calibrated: bool = True) -> DifferenceOfExponentialsModel:
    return DifferenceOfExponentialsModel(
        _identity(calibrated=calibrated),
        rise_time_constant_s=0.10,
        decay_time_constant_s=0.50,
        gain=1.0,
    )


def _deconvolution_spec(**changes: object) -> KineticDeconvolutionSpec:
    values = {
        "regularization_strength": 1e-5,
        "regularization_source": "held-out calibration reconstruction",
        "nonnegative": True,
        "maximum_iterations": 3_000,
    }
    values.update(changes)
    return KineticDeconvolutionSpec(**values)  # type: ignore[arg-type]


def test_parametric_and_sampled_models_materialize_versioned_kernels() -> None:
    parametric = kinetic_kernel(_model(), 0.02)
    sampled_model = SampledImpulseResponseModel(
        identity=_identity(),
        sample_interval_s=0.1,
        response_density=(0.0, 1.0, 0.5, 0.0),
        normalization="unit_area",
        gain=2.0,
    )
    sampled = kinetic_kernel(sampled_model, 0.05)

    assert parametric.integral == pytest.approx(1.0)
    assert parametric.peak_time_s > 0
    assert sampled.integral == pytest.approx(2.0)
    assert sampled.sample_interval_s == pytest.approx(0.05)
    assert sampled.source_family == "sampled_impulse_response"

    with pytest.raises(ValueError, match="calibration_id"):
        KineticModelIdentity(
            "model",
            "1",
            "profile",
            "1",
            "input",
            "a.u.",
            "dF/F",
            "context",
            "evidence",
            "independently_calibrated",
        )


def test_forward_prediction_never_carries_state_across_a_gap() -> None:
    first_time = np.arange(0, 6, 0.02)
    second_time = np.arange(10, 16, 0.02)
    time = np.concatenate((first_time, second_time))
    latent = np.zeros(len(time))
    latent[len(first_time) - 5] = 1.0

    result = predict_sensor_response(time, latent, _model(), KineticForwardSpec())
    prediction = np.asarray(result.predicted_output)

    assert result.continuity.gap_count == 1
    assert len(result.runs) == 2
    assert np.max(prediction[-len(second_time) :]) == pytest.approx(0.0, abs=1e-12)
    assert result.runs[0].boundary_affected_sample_count > 0
    assert json.loads(result.to_json())["spec"]["initial_state"] == ("zero_at_each_run")


def test_identifiability_refuses_under_sampling_and_labels_assumed_models() -> None:
    coarse_time = np.arange(0, 30, 0.2)
    under_sampled = assess_kinetic_identifiability(
        coarse_time,
        _model(),
        _deconvolution_spec(),
    )

    assert under_sampled.status == "fail"
    assert "rise_dynamics_under_sampled" in {
        issue.code for issue in under_sampled.issues
    }
    with pytest.raises(ValueError, match="failed"):
        under_sampled.require_ready()

    fine_time = np.arange(0, 30, 0.02)
    assumed = assess_kinetic_identifiability(
        fine_time,
        _model(calibrated=False),
        _deconvolution_spec(),
    )
    assert assumed.status == "warning"
    assert "kinetic_model_not_independently_calibrated" in {
        issue.code for issue in assumed.issues
    }
    with pytest.raises(ValueError, match="warnings"):
        assumed.require_ready(allow_warnings=False)

    required = assess_kinetic_identifiability(
        fine_time,
        _model(calibrated=False),
        _deconvolution_spec(require_independent_calibration=True),
    )
    assert required.status == "fail"


def test_identifiability_detects_a_transfer_nullspace_left_by_the_penalty() -> None:
    model = SampledImpulseResponseModel(
        identity=_identity(),
        sample_interval_s=0.02,
        response_density=(1.0, -1.0),
        normalization="as_supplied",
    )
    assessment = assess_kinetic_identifiability(
        np.arange(0, 20, 0.02), model, _deconvolution_spec(smoothness_order=1)
    )

    assert assessment.status == "fail"
    assert "regularization_leaves_transfer_nullspace" in {
        issue.code for issue in assessment.issues
    }


def test_regularized_deconvolution_recovers_timing_and_reconstructs_output() -> None:
    time = np.arange(0, 20, 0.02)
    latent = np.zeros(len(time))
    event_indices = np.asarray([200, 500, 750])
    latent[event_indices] = 1.0
    forward = predict_sensor_response(time, latent, _model())
    rng = np.random.default_rng(4)
    observed = np.asarray(forward.predicted_output) + rng.normal(0, 0.0002, len(time))

    result = deconvolve_sensor_response(
        time,
        observed,
        _model(),
        _deconvolution_spec(),
    )
    recovered = np.asarray(result.latent_input)

    assert result.assessment.status == "pass"
    assert result.runs[0].reconstruction_r_squared > 0.99
    assert np.corrcoef(latent, recovered)[0, 1] > 0.70
    for event_index in event_indices:
        local = recovered[event_index - 2 : event_index + 3]
        assert np.argmax(local) in {1, 2, 3}
    assert np.min(recovered) >= -1e-12
    assert result.input_quantity == "latent dopamine drive"
    assert "not ground-truth analyte concentration" in result.interpretation
    assert result.evidence_fingerprint.startswith("sha256:")


def test_short_runs_are_excluded_while_eligible_runs_remain_solved() -> None:
    short_time = np.arange(0, 3, 0.02)
    long_time = np.arange(10, 25, 0.02)
    time = np.concatenate((short_time, long_time))
    latent = np.zeros(len(time))
    latent[len(short_time) + 200] = 1.0
    observed = np.asarray(
        predict_sensor_response(time, latent, _model()).predicted_output
    )

    result = deconvolve_sensor_response(
        time,
        observed,
        _model(),
        _deconvolution_spec(),
    )
    solved = np.asarray(result.solved)

    assert result.assessment.status == "warning"
    assert "continuity_run_too_short" in {
        issue.code for issue in result.assessment.issues
    }
    assert not np.any(solved[: len(short_time)])
    assert np.all(solved[len(short_time) :])
    assert np.all(np.isnan(np.asarray(result.latent_input)[: len(short_time)]))
    assert len(result.runs) == 1


def test_invalid_regions_split_forward_and_inverse_on_the_original_clock() -> None:
    time = np.arange(0, 30, 0.02)
    valid = np.ones(len(time), dtype=bool)
    valid[(time >= 12) & (time < 16)] = False
    latent = np.zeros(len(time))
    latent[np.argmin(np.abs(time - 11.8))] = 1.0
    latent[np.argmin(np.abs(time - 20.0))] = 1.0
    forward = predict_sensor_response(time, latent, _model(), valid=valid)

    result = deconvolve_sensor_response(
        time,
        forward.predicted_output,
        _model(),
        _deconvolution_spec(),
        valid=valid,
    )
    solved = np.asarray(result.solved)

    assert len(forward.runs) == 2
    assert len(result.assessment.runs) == 2
    assert len(result.runs) == 2
    assert not np.any(solved[~valid])
    assert np.all(np.isnan(np.asarray(result.latent_input)[~valid]))


def test_regularization_choice_is_bound_into_evidence() -> None:
    time = np.arange(0, 15, 0.02)
    latent = np.zeros(len(time))
    latent[250] = 1.0
    observed = predict_sensor_response(time, latent, _model()).predicted_output

    first = deconvolve_sensor_response(
        time, observed, _model(), _deconvolution_spec(regularization_strength=1e-5)
    )
    second = deconvolve_sensor_response(
        time, observed, _model(), _deconvolution_spec(regularization_strength=1e-3)
    )

    assert first.evidence_fingerprint != second.evidence_fingerprint
    assert first.spec.regularization_source == "held-out calibration reconstruction"
