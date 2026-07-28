import numpy as np
import pytest

from fiberphotometry import (
    AutocorrelationSpec,
    ChannelIdentity,
    LaggedAssociationSpec,
    PopulationContrastSpec,
    PopulationGroupAssignment,
    PopulationInteractionSpec,
    PopulationUnitEstimate,
    SignalPairMetadata,
    SpectralAnalysisSpec,
    StateEpoch,
    StatePSDSession,
    autocorrelation,
    coherence_phase,
    curve_session_from_autocorrelation,
    curve_session_from_coherence,
    curve_session_from_lagged,
    curve_session_from_psd,
    curve_sessions_from_state_autocorrelation,
    curve_sessions_from_state_coherence,
    curve_sessions_from_state_psd,
    lagged_association,
    materialize_curve_population,
    state_conditioned_autocorrelation,
    state_conditioned_coherence,
    state_conditioned_psd,
    welch_psd,
)


def _pair(subject: str, session: str) -> SignalPairMetadata:
    return SignalPairMetadata(
        subject,
        session,
        "green__red",
        ChannelIdentity("green", "DMS", "dLight", "sensor", "dF/F"),
        ChannelIdentity("red", "NAc", "rDA", "sensor", "dF/F"),
        "photometry-clock",
        "native_shared_clock",
        "sha256:fixture",
    )


def _groups() -> tuple[PopulationGroupAssignment, ...]:
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
        draws=300,
        seed=8,
    )


def test_psd_curve_population_returns_full_axis_simultaneous_inference() -> None:
    rate = 20.0
    time = np.arange(0, 30, 1 / rate)
    spec = SpectralAnalysisSpec(window_duration_s=2, maximum_frequency_hz=8)
    sessions = []
    for index, subject in enumerate(("m1", "m2", "m3", "m4")):
        rng = np.random.default_rng(index)
        base = 1 + 0.05 * index
        for level, amplitude in (
            ("pre", base),
            ("post", base * (1.25 + 0.04 * index)),
        ):
            values = amplitude * np.sin(2 * np.pi * 3 * time)
            values += rng.normal(0, 0.08, len(time))
            result = welch_psd(time, values, spec, value_unit="dF/F")
            sessions.append(
                curve_session_from_psd(
                    result,
                    subject=subject,
                    session=f"{subject}-{level}",
                    level=level,
                )
            )

    materialized = materialize_curve_population(sessions, levels=("pre", "post"))
    inference = materialized.contrast(
        PopulationContrastSpec("post", "pre", "paired", draws=300, seed=3)
    )

    frequency = np.asarray(materialized.axis)
    three_hz = int(np.argmin(np.abs(frequency - 3)))
    assert materialized.axis_name == "frequency"
    assert materialized.value_unit == "dF/F^2/Hz"
    assert inference.estimate[three_hz] > 0
    assert inference.contrast_units_per_point[three_hz] == 4
    assert len(inference.simultaneous_lower) == len(frequency)
    assert all(
        item.observation_support is not None
        and len(item.observation_support) == len(frequency)
        for item in materialized.population_estimates
    )


def test_autocorrelation_materialization_sums_pairs_but_weights_sessions_equally() -> (
    None
):
    rate = 20.0
    time = np.arange(0, 20, 1 / rate)
    values = np.sin(2 * np.pi * time)
    result = autocorrelation(time, values, AutocorrelationSpec(maximum_lag_s=1.0))
    sessions = [
        curve_session_from_autocorrelation(
            result,
            subject="m1",
            session=f"pre-{index}",
            level="pre",
        )
        for index in range(2)
    ]
    sessions.append(
        curve_session_from_autocorrelation(
            result,
            subject="m1",
            session="post-0",
            level="post",
        )
    )

    materialized = materialize_curve_population(sessions, levels=("pre", "post"))
    pre = next(
        item
        for item in materialized.population_estimates
        if item.unit_id == "m1" and item.level == "pre"
    )
    assert pre.support == (2,) * len(result.lags_s)
    assert pre.observation_support == tuple(2 * item for item in result.pairs_per_lag)
    assert pre.observation_count == 2 * result.pairs_per_lag[0]
    assert pre.source_units == ("pre-0", "pre-1")


def test_coherence_curves_support_group_by_condition_interactions() -> None:
    rate = 30.0
    time = np.arange(0, 40, 1 / rate)
    spec = SpectralAnalysisSpec(window_duration_s=4, maximum_frequency_hz=8)
    sessions = []
    for index, subject in enumerate(("c1", "c2", "t1", "t2")):
        for level in ("pre", "post"):
            rng = np.random.default_rng(100 + 10 * index + (level == "post"))
            first = rng.normal(0, 1, len(time))
            second = rng.normal(0, 1, len(time))
            if subject.startswith("t") and level == "post":
                shared = np.sin(2 * np.pi * 3 * time)
                first = shared + rng.normal(0, 0.25, len(time))
                second = shared + rng.normal(0, 0.25, len(time))
            result = coherence_phase(
                time, first, second, _pair(subject, f"{subject}-{level}"), spec
            )
            sessions.append(curve_session_from_coherence(result, level))

    materialized = materialize_curve_population(sessions, levels=("pre", "post"))
    interaction = materialized.interaction(_groups(), _interaction_spec())
    frequency = np.asarray(materialized.axis)
    three_hz = int(np.argmin(np.abs(frequency - 3)))

    assert interaction.population.estimate[three_hz] > 0.5
    assert interaction.population.contrast_units_per_point[three_hz] == 4
    assert all(
        item.observation_support is not None and item.observation_support[three_hz] > 0
        for item in interaction.within_unit_contrasts
    )


def test_lag_adapter_retains_pointwise_pair_counts() -> None:
    rate = 20.0
    time = np.arange(0, 30, 1 / rate)
    rng = np.random.default_rng(21)
    first = rng.normal(size=len(time))
    second = np.roll(first, 2)
    result = lagged_association(
        time,
        first,
        second,
        _pair("m1", "session-1"),
        LaggedAssociationSpec(maximum_lag_s=0.5),
    )

    adapted = curve_session_from_lagged(result, "post")

    assert adapted.axis == result.lags_s
    assert adapted.observation_support == result.pairs_per_lag
    assert adapted.metric == "lagged_correlation:green__red"


def test_state_curve_helpers_preserve_supplied_labels() -> None:
    rate = 20.0
    time = np.arange(0, 20, 1 / rate)
    values = np.sin(2 * np.pi * 2 * time)
    epochs = (StateEpoch("active", 0, 10), StateEpoch("rest", 10, 20))
    spectral_spec = SpectralAnalysisSpec(window_duration_s=2)

    psd_sessions = curve_sessions_from_state_psd(
        StatePSDSession(
            "m1",
            "session-1",
            state_conditioned_psd(time, values, epochs, spectral_spec),
        )
    )
    autocorrelation_sessions = curve_sessions_from_state_autocorrelation(
        state_conditioned_autocorrelation(
            time, values, epochs, AutocorrelationSpec(maximum_lag_s=0.5)
        ),
        subject="m1",
        session="session-1",
    )
    coherence_sessions = curve_sessions_from_state_coherence(
        state_conditioned_coherence(
            time,
            values,
            values + 0.02 * np.cos(time),
            _pair("m1", "session-1"),
            epochs,
            spectral_spec,
        )
    )

    assert {item.level for item in psd_sessions} == {"active", "rest"}
    assert {item.level for item in autocorrelation_sessions} == {"active", "rest"}
    assert {item.level for item in coherence_sessions} == {"active", "rest"}


def test_curve_materialization_refuses_implicit_axis_interpolation() -> None:
    time = np.arange(0, 20, 0.05)
    values = np.sin(2 * np.pi * 2 * time)
    first = curve_session_from_psd(
        welch_psd(time, values, SpectralAnalysisSpec(window_duration_s=2)),
        subject="m1",
        session="pre",
        level="pre",
    )
    second = curve_session_from_psd(
        welch_psd(time, values, SpectralAnalysisSpec(window_duration_s=4)),
        subject="m1",
        session="post",
        level="post",
    )

    with pytest.raises(ValueError, match="harmonize grids prospectively"):
        materialize_curve_population([first, second], levels=("pre", "post"))


def test_population_unit_estimate_validates_pointwise_observation_support() -> None:
    with pytest.raises(ValueError, match="observation support"):
        PopulationUnitEstimate(
            "m1",
            "pre",
            (0.1, 0.2),
            (1, 1),
            ("session",),
            10,
            observation_support=(10,),
        )
