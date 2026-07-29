import json

import numpy as np
import pytest

from fipha.optogenetics import (
    OptogeneticMaskSpec,
    OptogeneticRecoverySpec,
    StimulationPulse,
    assess_optogenetic_artifacts,
    build_optogenetic_artifact_mask,
)
from fipha.spectral import SpectralAnalysisSpec, welch_psd


def test_pulse_mask_is_prospective_merged_and_composes_with_validity() -> None:
    time = np.arange(0, 10, 0.01)
    pulses = (
        StimulationPulse("p1", 2.00, 2.02, "DMS", 473, 5),
        StimulationPulse("p2", 2.10, 2.12, "DMS", 473, 5),
        StimulationPulse("p3", 8.00, 8.01, "DMS", 473, 5),
    )
    existing = np.ones(len(time), dtype=bool)
    existing[:10] = False
    spec = OptogeneticMaskSpec(pre_pulse_s=0.05, post_pulse_s=0.10)

    result = build_optogenetic_artifact_mask(
        time, pulses, spec, existing_valid=existing
    )
    repeated = build_optogenetic_artifact_mask(
        time, pulses, spec, existing_valid=existing
    )

    expected_artifact = ((time >= 1.95) & (time <= 2.22)) | (
        (time >= 7.95) & (time <= 8.11)
    )
    np.testing.assert_array_equal(result.artifact_array, expected_artifact)
    np.testing.assert_array_equal(result.valid_array, existing & ~expected_artifact)
    assert result.intervals[0].pulse_ids == ("p1", "p2")
    assert result.originally_invalid_sample_count == 10
    assert result.newly_invalid_sample_count == np.count_nonzero(
        existing & expected_artifact
    )
    assert result.mask_fingerprint == repeated.mask_fingerprint
    assert len(result.mask_fingerprint) == 64
    assert json.loads(result.to_json())["method"].startswith("prospective")

    signal = np.sin(2 * np.pi * 3 * time)
    spectrum = welch_psd(
        time,
        signal,
        SpectralAnalysisSpec(window_duration_s=1),
        valid=result.valid_array,
    )
    assert spectrum.evidence.invalid_sample_count > 10
    assert len(spectrum.evidence.runs) == 3


def test_recovery_and_negative_control_are_diagnostic_not_mask_adaptive() -> None:
    rate = 1000.0
    time = np.arange(0, 5, 1 / rate)
    pulse = StimulationPulse("laser-1", 2.0, 2.01, "DMS")
    rng = np.random.default_rng(4)
    signal = rng.normal(0, 0.01, len(time))
    control = rng.normal(0, 0.01, len(time))
    after = time >= pulse.onset_s
    signal[after] += 4 * np.exp(-(time[after] - pulse.onset_s) / 0.06)
    control[after] += 2 * np.exp(-(time[after] - pulse.onset_s) / 0.08)
    spec = OptogeneticRecoverySpec(
        assessment_duration_s=1,
        stable_duration_s=0.02,
        detector_floor=-1,
        detector_ceiling=1,
    )

    result = assess_optogenetic_artifacts(
        time,
        signal,
        (pulse,),
        spec,
        negative_control=control,
        negative_control_name="fluorophore-negative-control",
    )
    diagnostic = result.diagnostics[0]

    assert diagnostic.peak_absolute_deviation_sd > 100
    assert diagnostic.recovered
    assert diagnostic.recovery_time_from_offset_s is not None
    assert 0.2 < diagnostic.recovery_time_from_offset_s < 0.5
    assert diagnostic.saturation_fraction is not None
    assert diagnostic.saturation_fraction > 0
    assert diagnostic.control_peak_absolute_deviation_sd is not None
    assert diagnostic.control_peak_absolute_deviation_sd > 5
    assert "detector_saturation_during_assessment" in diagnostic.warnings
    assert "large_negative_control_artifact" in diagnostic.warnings
    assert result.interpretation.endswith("does_not_modify_the_mask")

    fixed_mask = build_optogenetic_artifact_mask(
        time,
        (pulse,),
        OptogeneticMaskSpec(post_pulse_s=0.05),
    )
    assert fixed_mask.intervals[0].stop_s == pytest.approx(2.06)


def test_close_pulses_censor_recovery_and_flag_contaminated_baseline() -> None:
    time = np.arange(0, 5, 0.01)
    pulses = (
        StimulationPulse("p1", 2.0, 2.01, "DMS"),
        StimulationPulse("p2", 2.25, 2.26, "DMS"),
    )
    values = np.zeros(len(time))
    values[(time >= 2.0) & (time < 2.5)] = 10

    result = assess_optogenetic_artifacts(
        time,
        values,
        pulses,
        OptogeneticRecoverySpec(
            baseline_duration_s=0.5,
            baseline_guard_s=0.02,
            assessment_duration_s=1,
            stable_duration_s=0.05,
            minimum_baseline_samples=10,
        ),
    )

    assert result.diagnostics[0].censored_by_next_pulse
    assert "recovery_censored_by_next_pulse" in result.diagnostics[0].warnings
    assert "baseline_overlaps_previous_pulse" in result.diagnostics[1].warnings


def test_mask_requires_unique_pulse_ids_and_matching_validity() -> None:
    time = np.arange(0, 2, 0.01)
    pulse = StimulationPulse("same", 1, 1.01, "DMS")
    with pytest.raises(ValueError, match="pulse IDs must be unique"):
        build_optogenetic_artifact_mask(time, (pulse, pulse))
    with pytest.raises(ValueError, match="match time"):
        build_optogenetic_artifact_mask(
            time,
            (pulse,),
            existing_valid=np.ones(len(time) - 1, dtype=bool),
        )
