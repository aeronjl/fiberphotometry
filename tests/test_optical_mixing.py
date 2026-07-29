import json

import numpy as np
import pytest

from fipha.multisignal import ChannelIdentity
from fipha.optical_mixing import (
    MixingCoefficientSource,
    OpticalComponent,
    OpticalMixingCalibrationSpec,
    OpticalMixingChannel,
    OpticalMixingDesign,
    OpticalUnmixingSpec,
    assess_optical_mixing_design,
    calibrate_optical_mixing,
    extract_unmixed_component,
    unmix_optical_signals,
)


def _channel(
    channel_id: str, excitation_nm: float, emission_nm: float
) -> ChannelIdentity:
    return ChannelIdentity(
        channel_id=channel_id,
        site="DMS",
        sensor="dLight+control",
        role="sensor" if excitation_nm == 470 else "reference",
        unit="photons/s",
        excitation_wavelength_nm=excitation_nm,
        emission_wavelength_nm=emission_nm,
        detector_id=f"detector-{channel_id}",
        fiber_id="fiber-1",
    )


def _design(
    *, source: MixingCoefficientSource = "externally_calibrated"
) -> OpticalMixingDesign:
    components = (
        OpticalComponent("dopamine_sensor", "sensor", "a.u."),
        OpticalComponent("hemoglobin_absorption", "hemodynamic", "a.u."),
    )
    return OpticalMixingDesign(
        components=components,
        channels=(
            OpticalMixingChannel(_channel("green-470", 470, 525), (1.0, -0.5), 10),
            OpticalMixingChannel(_channel("green-405", 405, 525), (0.8, -0.2), 20),
            OpticalMixingChannel(_channel("red-560", 560, 600), (0.2, -1.0), 30),
        ),
        coefficient_source=source,
        calibration_id="phantom-2026-07",
    )


def _signals() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = np.arange(0.0, 20.0, 0.1)
    sources = np.column_stack(
        (np.sin(2 * np.pi * 0.7 * time), 0.5 * np.cos(2 * np.pi * 0.08 * time))
    )
    design = _design()
    matrix = np.asarray([row.coefficients for row in design.channels])
    offsets = np.asarray([row.offset for row in design.channels])
    observations = sources @ matrix.T + offsets
    return time, sources, observations


def test_calibrated_overdetermined_design_recovers_sources_and_holdouts() -> None:
    time, sources, observations = _signals()
    result = unmix_optical_signals(time, observations, _design())

    assert result.assessment.status == "pass"
    assert result.assessment.rank == 2
    assert result.assessment.overdetermined
    assert result.assessment.leave_one_channel_out_identifiable
    assert np.asarray(result.component_values) == pytest.approx(sources)
    assert np.asarray(result.reconstructed_channel_values) == pytest.approx(
        observations
    )
    assert np.asarray(result.residual_channel_values) == pytest.approx(
        np.zeros_like(observations), abs=1e-12
    )
    assert result.solved_sample_count == len(time)
    assert result.unsolved_sample_count == 0
    assert all(
        item.r_squared == pytest.approx(1) for item in result.holdout_diagnostics
    )
    assert all(
        item.root_mean_square_error == pytest.approx(0, abs=1e-12)
        for item in result.holdout_diagnostics
    )
    assert json.loads(result.to_json())["schema_version"] == "1"


def test_independent_known_component_calibration_recovers_matrix_and_offsets() -> None:
    rng = np.random.default_rng(22)
    known = rng.normal(size=(250, 2))
    expected = _design()
    matrix = np.asarray([row.coefficients for row in expected.channels])
    offsets = np.asarray([row.offset for row in expected.channels])
    measured = known @ matrix.T + offsets

    calibration = calibrate_optical_mixing(
        known,
        measured,
        expected.components,
        tuple(row.channel for row in expected.channels),
        "independent-phantom-22",
    )

    recovered = np.asarray([row.coefficients for row in calibration.design.channels])
    recovered_offsets = np.asarray([row.offset for row in calibration.design.channels])
    assert recovered == pytest.approx(matrix)
    assert recovered_offsets == pytest.approx(offsets)
    assert calibration.design.coefficient_source == "externally_calibrated"
    assert calibration.assessment.status == "pass"
    assert all(
        item.r_squared == pytest.approx(1) for item in calibration.channel_diagnostics
    )
    assert json.loads(calibration.to_json())["schema_version"] == "1"


def test_calibration_refuses_collinear_known_components() -> None:
    first = np.linspace(-1, 1, 50)
    known = np.column_stack((first, 2 * first))
    measured = np.column_stack((first, first + 1, 2 - first))
    expected = _design()

    with pytest.raises(ValueError, match="rank deficient"):
        calibrate_optical_mixing(
            known,
            measured,
            expected.components,
            tuple(row.channel for row in expected.channels),
            "collinear-calibration",
            OpticalMixingCalibrationSpec(minimum_samples=20),
        )


def test_missing_channel_patterns_are_solved_only_when_still_identifiable() -> None:
    time, sources, observations = _signals()
    valid = np.ones_like(observations, dtype=bool)
    valid[20:40, 2] = False
    valid[80:90, 1:] = False
    observations[100, 0] = np.nan

    result = unmix_optical_signals(time, observations, _design(), valid=valid)

    recovered = np.asarray(result.component_values)
    assert recovered[:80] == pytest.approx(sources[:80])
    assert np.all(np.isnan(recovered[80:90]))
    assert recovered[100] == pytest.approx(sources[100])
    assert result.solved_sample_count == len(time) - 10
    by_pattern = {item.pattern_id: item for item in result.availability_patterns}
    assert by_pattern["110"].solved
    assert by_pattern["100"].exclusion_reason == (
        "fewer_available_channels_than_components"
    )
    assert by_pattern["011"].solved


def test_timestamp_gap_is_retained_without_interpolation_or_compression() -> None:
    first = np.arange(0.0, 5.0, 0.1)
    second = np.arange(10.0, 15.0, 0.1)
    time = np.concatenate((first, second))
    sources = np.column_stack((np.sin(time), np.cos(time)))
    design = _design()
    matrix = np.asarray([row.coefficients for row in design.channels])
    offsets = np.asarray([row.offset for row in design.channels])
    observations = sources @ matrix.T + offsets

    result = unmix_optical_signals(time, observations, design)

    assert result.gap_count == 1
    assert result.time_s == tuple(time)
    assert len(result.component_values) == len(time)
    assert np.asarray(result.component_values) == pytest.approx(sources)


def test_rank_deficiency_is_refused_before_outcomes_are_used() -> None:
    design = OpticalMixingDesign(
        components=(
            OpticalComponent("sensor", "sensor", "a.u."),
            OpticalComponent("blood", "hemodynamic", "a.u."),
        ),
        channels=(
            OpticalMixingChannel(_channel("one", 470, 525), (1.0, 1.0)),
            OpticalMixingChannel(_channel("two", 405, 525), (2.0, 2.0)),
        ),
        coefficient_source="externally_calibrated",
        calibration_id="bad-calibration",
    )
    assessment = assess_optical_mixing_design(design)

    assert assessment.status == "error"
    assert assessment.rank == 1
    assert "rank_deficient_mixing_matrix" in {issue.code for issue in assessment.issues}
    with pytest.raises(ValueError, match="rank_deficient_mixing_matrix"):
        unmix_optical_signals(np.arange(10.0), np.ones((10, 2)), design)


def test_full_rank_but_ill_conditioned_matrix_is_refused() -> None:
    design = OpticalMixingDesign(
        components=(
            OpticalComponent("sensor", "sensor", "a.u."),
            OpticalComponent("blood", "hemodynamic", "a.u."),
        ),
        channels=(
            OpticalMixingChannel(_channel("one", 470, 525), (1.0, 1.0)),
            OpticalMixingChannel(_channel("two", 405, 525), (1.0, 1.0 + 1e-8)),
        ),
        coefficient_source="externally_calibrated",
        calibration_id="unstable-calibration",
    )

    assessment = assess_optical_mixing_design(
        design, OpticalUnmixingSpec(maximum_condition_number=100)
    )

    assert assessment.rank == 2
    assert assessment.status == "error"
    assert "ill_conditioned_mixing_matrix" in {
        issue.code for issue in assessment.issues
    }


def test_wavelength_and_calibration_provenance_are_explicit_gates() -> None:
    missing = ChannelIdentity("unknown", "DMS", "sensor", "sensor", "a.u.")
    design = OpticalMixingDesign(
        components=(OpticalComponent("sensor", "sensor", "a.u."),),
        channels=(OpticalMixingChannel(missing, (1.0,)),),
        coefficient_source="user_declared",
        calibration_id="exploratory-values",
    )
    assessment = assess_optical_mixing_design(design)
    codes = {issue.code for issue in assessment.issues}

    assert assessment.status == "error"
    assert "missing_excitation_wavelength" in codes
    assert "missing_emission_wavelength" in codes
    assert "coefficients_not_externally_calibrated" in codes

    relaxed = assess_optical_mixing_design(
        design, OpticalUnmixingSpec(require_wavelength_metadata=False)
    )
    assert relaxed.status == "warning"
    assert {issue.code for issue in relaxed.issues} == {
        "coefficients_not_externally_calibrated",
        "leave_one_channel_out_not_identifiable",
    }


def test_square_design_can_unmix_but_cannot_claim_holdout_validation() -> None:
    full = _design()
    design = OpticalMixingDesign(
        full.components,
        full.channels[:2],
        full.coefficient_source,
        full.calibration_id,
    )
    assessment = assess_optical_mixing_design(design)
    assert assessment.status == "warning"
    assert not assessment.leave_one_channel_out_identifiable

    time, sources, _ = _signals()
    matrix = np.asarray([row.coefficients for row in design.channels])
    offsets = np.asarray([row.offset for row in design.channels])
    result = unmix_optical_signals(time, sources @ matrix.T + offsets, design)
    assert np.asarray(result.component_values) == pytest.approx(sources)
    assert all(
        item.exclusion_reason == "heldout_submatrix_rank_deficient"
        for item in result.holdout_diagnostics
    )

    with pytest.raises(ValueError, match="leave_one_channel_out_not_identifiable"):
        unmix_optical_signals(
            time,
            sources @ matrix.T + offsets,
            design,
            OpticalUnmixingSpec(require_leave_one_channel_out=True),
        )


def test_component_extraction_retains_calibration_identity_and_validity() -> None:
    time, sources, observations = _signals()
    result = unmix_optical_signals(time, observations, _design())
    series = extract_unmixed_component(result, "dopamine_sensor")

    assert series.values == pytest.approx(sources[:, 0])
    assert all(series.valid)
    assert series.component.role == "sensor"
    assert series.mixing_calibration_id == "phantom-2026-07"
    assert series.evidence_fingerprint == result.evidence_fingerprint
    with pytest.raises(KeyError, match="unknown optical component"):
        extract_unmixed_component(result, "not-present")
