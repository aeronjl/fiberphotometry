import json

import numpy as np
import pytest
from scipy import signal

from fipha.multisignal import (
    BlockPermutationSpec,
    ChannelIdentity,
    CrosstalkDiagnosticSpec,
    LaggedAssociationSpec,
    SignalPairMetadata,
    SpatialCoordinate,
    assess_crosstalk,
    lagged_association,
)


def _pair(
    *,
    first_excitation: float = 470,
    second_excitation: float = 560,
    shared_detector: bool = False,
) -> SignalPairMetadata:
    first = ChannelIdentity(
        "dms-green",
        "DMS",
        "dLight1.3b",
        "sensor",
        "dF/F",
        excitation_wavelength_nm=first_excitation,
        emission_wavelength_nm=525,
        detector_id="detector-1",
        fiber_id="fiber-1",
        coordinate=SpatialCoordinate(1200, 800, -3200, space="CCF"),
    )
    second = ChannelIdentity(
        "nacc-red",
        "NAcC",
        "rDA3m",
        "sensor",
        "dF/F",
        excitation_wavelength_nm=second_excitation,
        emission_wavelength_nm=600,
        detector_id="detector-1" if shared_detector else "detector-2",
        fiber_id="fiber-2",
    )
    return SignalPairMetadata(
        "mouse-01",
        "session-01",
        "dms-green__nacc-red",
        first,
        second,
        "photometry-clock",
        "native_shared_clock",
        "sha256:preprocessing",
    )


def _gapped_delayed_signals() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rate = 50.0
    first_time = np.arange(0, 20, 1 / rate)
    second_time = np.arange(30, 50, 1 / rate)
    time = np.concatenate((first_time, second_time))
    rng = np.random.default_rng(12)
    first = signal.lfilter([1], [1, -0.85], rng.normal(size=len(time)))
    second = np.empty_like(first)
    delay = 5
    for start, stop in ((0, len(first_time)), (len(first_time), len(time))):
        second[start : start + delay] = rng.normal(size=delay)
        second[start + delay : stop] = first[start : stop - delay]
    return time, first, second


def test_lagged_association_recovers_delay_without_crossing_gap() -> None:
    time, first, second = _gapped_delayed_signals()
    result = lagged_association(
        time,
        first,
        second,
        _pair(),
        LaggedAssociationSpec(
            maximum_lag_s=0.5,
            blocked_permutation=BlockPermutationSpec(
                block_duration_s=4,
                resamples=200,
                seed=8,
            ),
        ),
    )

    assert result.peak_lag_s == pytest.approx(0.1)
    assert result.peak_correlation > 0.99
    zero_index = result.lags_s.index(0.0)
    peak_index = int(np.argmax(np.abs(result.correlation)))
    assert result.pairs_per_lag[zero_index] == 2000
    assert result.pairs_per_lag[peak_index] == 1990
    assert result.evidence.continuity.gap_count == 1
    assert len(result.evidence.continuity.runs) == 2
    assert result.blocked_permutation is not None
    assert result.blocked_permutation.complete_block_count == 10
    assert result.blocked_permutation.maximum_absolute_pvalue < 0.05
    assert json.loads(result.to_json())["lag_convention"].startswith("positive")


def test_declared_covariates_are_residualized_within_each_run() -> None:
    rate = 20.0
    time = np.arange(0, 60, 1 / rate)
    rng = np.random.default_rng(41)
    movement = np.sin(2 * np.pi * 0.3 * time) + rng.normal(0, 0.2, len(time))
    first = 2 * movement + rng.normal(0, 0.4, len(time))
    second = -1.5 * movement + rng.normal(0, 0.4, len(time))
    spec = LaggedAssociationSpec(maximum_lag_s=0.5)

    raw = lagged_association(time, first, second, _pair(), spec)
    residual = lagged_association(
        time,
        first,
        second,
        _pair(),
        spec,
        covariates=movement[:, np.newaxis],
        covariate_names=("movement_energy",),
    )

    assert raw.zero_lag_correlation < -0.8
    assert abs(residual.zero_lag_correlation) < 0.1
    assert residual.residualization is not None
    assert residual.residualization.covariate_names == ("movement_energy",)
    assert residual.residualization.runs[0].active_covariates == ("movement_energy",)
    assert residual.residualization.runs[0].first_r_squared > 0.9
    assert residual.residualization.runs[0].second_r_squared > 0.8


def test_crosstalk_diagnostics_combine_metadata_control_and_signal_flags() -> None:
    rate = 20.0
    time = np.arange(0, 40, 1 / rate)
    rng = np.random.default_rng(9)
    control = signal.lfilter([1], [1, -0.9], rng.normal(size=len(time)))
    first = control + rng.normal(0, 0.1, len(time))
    second = 1.1 * control + rng.normal(0, 0.1, len(time))
    pair = _pair(
        first_excitation=470,
        second_excitation=480,
        shared_detector=True,
    )

    result = assess_crosstalk(
        time,
        first,
        second,
        pair,
        CrosstalkDiagnosticSpec(maximum_lag_s=0.5),
        shared_control=control,
        control_name="motion-control",
    )

    codes = {flag.code for flag in result.flags}
    assert result.status == "review"
    assert result.shared_detector is True
    assert result.excitation_separation_nm == pytest.approx(10)
    assert {
        "shared_detector",
        "close_excitation_wavelengths",
        "high_zero_lag_association",
        "near_zero_lag_peak",
        "shared_control_loading",
    } <= codes
    assert result.first_control_correlation is not None
    assert result.first_control_correlation > 0.9
    assert result.control_residualized_zero_lag_correlation is not None
    assert abs(result.control_residualized_zero_lag_correlation) < 0.2
    assert "cannot_establish" in json.loads(result.to_json())["interpretation"]


def test_pair_metadata_requires_distinct_explicit_channels() -> None:
    channel = ChannelIdentity("same", "DMS", "dLight", "sensor", "dF/F")
    with pytest.raises(ValueError, match="distinct channel IDs"):
        SignalPairMetadata(
            "mouse",
            "session",
            "pair",
            channel,
            channel,
            "clock",
            "native_shared_clock",
            "fingerprint",
        )

    with pytest.raises(ValueError, match="align sample for sample"):
        lagged_association(
            np.arange(20),
            np.arange(20),
            np.arange(19),
            _pair(),
        )
