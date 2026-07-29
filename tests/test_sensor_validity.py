import json

import numpy as np
import pytest

from fipha.multisignal import ChannelIdentity
from fipha.sensor_validity import (
    SensorChannelAssignment,
    SensorKinetics,
    SensorProfile,
    SensorRegistry,
    SensorValiditySpec,
    WavelengthRange,
    assess_sensor_validity,
)


def _profile(version: str = "1") -> SensorProfile:
    return SensorProfile(
        profile_id="lab-dlight-profile",
        sensor_name="dLight1.3b",
        profile_version=version,
        signal_excitation_nm=WavelengthRange(465, 475),
        emission_nm=WavelengthRange(510, 540),
        isosbestic_excitation_nm=WavelengthRange(405, 415),
        interpretation="reports fluorescence changes, not dopamine concentration",
        evidence_source="lab-profile-doi-or-protocol",
        kinetics=SensorKinetics(
            0.05,
            0.40,
            "bench characterization",
            "lab-profile-doi-or-protocol",
        ),
        linear_response_range=(-3.0, 3.0),
        linear_response_unit="dF/F",
        constraints=("do not infer sub-50-ms dynamics",),
        metadata=(("construct", "dLight1.3b"),),
    )


def _assignment(
    *,
    signal_excitation: float = 470,
    reference_excitation: float = 410,
    reference_fiber: str = "fiber-1",
    sensor_name: str = "dLight1.3b",
) -> SensorChannelAssignment:
    signal = ChannelIdentity(
        "dms-signal",
        "DMS",
        sensor_name,
        "sensor",
        "dF/F",
        excitation_wavelength_nm=signal_excitation,
        emission_wavelength_nm=525,
        detector_id="detector-1",
        fiber_id="fiber-1",
    )
    reference = ChannelIdentity(
        "dms-isosbestic",
        "DMS",
        "dLight1.3b",
        "isosbestic",
        "dF/F",
        excitation_wavelength_nm=reference_excitation,
        emission_wavelength_nm=525,
        detector_id="detector-1",
        fiber_id=reference_fiber,
    )
    return SensorChannelAssignment(
        "mouse-01",
        "session-01",
        signal,
        reference,
        "photometry-clock",
        "native_shared_clock",
        "sha256:raw-demodulated",
    )


def test_open_registry_resolves_versioned_profiles_without_closed_enum() -> None:
    first = _profile("1")
    second = _profile("2")
    registry = SensorRegistry().with_profile(first).with_profile(second)

    assert registry.resolve("lab-dlight-profile", "1") == first
    assert registry.resolve("lab-dlight-profile", "2") == second
    with pytest.raises(KeyError, match="ambiguous"):
        registry.resolve("lab-dlight-profile")
    assert json.loads(registry.to_json())["profiles"][0]["sensor_name"] == (
        "dLight1.3b"
    )


def test_sensor_assessment_passes_consistent_profile_and_reference_evidence() -> None:
    rate = 20.0
    time = np.arange(0, 60, 1 / rate)
    rng = np.random.default_rng(22)
    reference = 0.2 * np.sin(2 * np.pi * 0.25 * time) + rng.normal(0, 0.03, len(time))
    signal = (
        1.5 * reference
        + 0.1 * np.sin(2 * np.pi * time)
        + rng.normal(0, 0.03, len(time))
    )

    result = assess_sensor_validity(
        time,
        signal,
        _assignment(),
        _profile(),
        reference_values=reference,
    )

    assert result.status == "pass"
    assert result.issues == ()
    assert result.reference_metrics is not None
    assert result.isosbestic_metrics is not None
    assert result.isosbestic_metrics.signal_reference_correlation > 0.8
    assert result.signal_metrics.outside_profile_fraction == pytest.approx(0)
    assert "reports fluorescence" in result.interpretation_constraints[0]
    assert "rise=0.05s" in result.interpretation_constraints[-1]
    result.require_ready(allow_warnings=False)


def test_sensor_assessment_fails_mismatched_wavelength_fiber_and_saturation() -> None:
    time = np.arange(0, 20, 0.05)
    signal = np.ones(len(time))
    reference = np.linspace(-0.2, 0.2, len(time))
    result = assess_sensor_validity(
        time,
        signal,
        _assignment(
            signal_excitation=560,
            reference_excitation=470,
            reference_fiber="fiber-2",
            sensor_name="other-sensor",
        ),
        _profile(),
        SensorValiditySpec(detector_floor=-1, detector_ceiling=1),
        reference_values=reference,
    )

    codes = {issue.code for issue in result.issues}
    assert result.status == "fail"
    assert {
        "sensor_profile_mismatch",
        "signal_excitation_outside_profile",
        "isosbestic_excitation_outside_profile",
        "reference_fiber_mismatch",
        "detector_saturation_fraction",
        "repeated_extreme_fraction",
        "flat_step_fraction",
    } <= codes
    with pytest.raises(ValueError, match="failed"):
        result.require_ready()


def test_event_correlated_isosbestic_and_missing_reference_remain_visible() -> None:
    time = np.arange(0, 30, 0.01)
    events = np.asarray([5, 10, 15, 20, 25], dtype=float)
    rng = np.random.default_rng(3)
    reference = rng.normal(0, 0.05, len(time))
    signal = 0.5 * reference + rng.normal(0, 0.05, len(time))
    for event in events:
        selected = (time >= event) & (time < event + 0.5)
        reference[selected] += 1

    result = assess_sensor_validity(
        time,
        signal,
        _assignment(),
        _profile(),
        reference_values=reference,
        event_times=events,
    )
    assert "event_correlated_isosbestic_response" in {
        issue.code for issue in result.issues
    }
    assert result.isosbestic_metrics is not None
    assert result.isosbestic_metrics.valid_event_count == 5

    signal_only_assignment = SensorChannelAssignment(
        "mouse-01",
        "session-01",
        _assignment().signal,
        None,
        "photometry-clock",
        "native_shared_clock",
        "sha256:signal-only",
    )
    warning = assess_sensor_validity(
        time,
        signal,
        signal_only_assignment,
        _profile(),
    )
    assert warning.status == "warning"
    assert warning.issues[0].code == "isosbestic_channel_absent"

    failure = assess_sensor_validity(
        time,
        signal,
        signal_only_assignment,
        _profile(),
        SensorValiditySpec(require_isosbestic=True),
    )
    assert failure.status == "fail"
