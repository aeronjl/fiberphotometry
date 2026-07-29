import pytest

from fiberphotometry.transient_inference import (
    SessionAggregation,
    TransientAnimalInferenceSpec,
    TransientStudySession,
    infer_transient_animals,
)
from fiberphotometry.transient_product import (
    QuantifiedTransient,
    TransientQuantificationResult,
    TransientQuantificationSpec,
    TransientQuantificationSummary,
)


def _event(identifier: str, amplitude: float) -> QuantifiedTransient:
    return QuantifiedTransient(
        candidate_id=identifier,
        detection_family="pasta",
        channel="NAc",
        sample_index=10,
        peak_time=1.0,
        detection_value=amplitude,
        detection_threshold=0.1,
        detection_score=amplitude,
        peak_value=amplitude,
        baseline=0.0,
        amplitude=amplitude,
        onset_half_height_time=0.9,
        offset_half_height_time=1.2,
        rise_half_height_s=0.1,
        fall_half_height_s=0.2,
        full_width_half_height_s=0.3,
        auc_above_baseline=0.2 * amplitude,
        previous_interval_s=None,
    )


def _session(
    subject: str,
    condition: str,
    *,
    session_index: int = 1,
    count: int,
    duration: float,
    amplitudes: tuple[float, ...] = (),
) -> TransientStudySession:
    events = tuple(
        _event(f"{subject}:{condition}:{index}", value)
        for index, value in enumerate(amplitudes)
    )
    result = TransientQuantificationResult(
        spec=TransientQuantificationSpec(),
        variable="dff",
        detector_variable="dff",
        events=events,
        exclusions=(),
        summaries=(
            TransientQuantificationSummary(
                channel="NAc",
                analyzed_duration_s=duration,
                count=count,
                rate_per_minute=60 * count / duration,
                median_amplitude=None,
                median_width_s=None,
                median_auc=None,
                median_interval_s=None,
            ),
        ),
        bins=None,
    )
    return TransientStudySession(
        subject=subject,
        session=f"{subject}-{condition}-{session_index}",
        condition=condition,
        result=result,
    )


def _unequal_exposure_sessions() -> list[TransientStudySession]:
    return [
        _session("m1", "control", session_index=1, count=10, duration=600),
        _session("m1", "control", session_index=2, count=6, duration=60),
        _session("m1", "control", session_index=3, count=2, duration=60),
        _session("m1", "drug", count=8, duration=60),
        _session("m2", "control", count=3, duration=60),
        _session("m2", "drug", count=9, duration=60),
    ]


def _rate_spec(aggregation: SessionAggregation | None) -> TransientAnimalInferenceSpec:
    return TransientAnimalInferenceSpec(
        metric="rate_per_minute",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="paired",
        session_aggregation=aggregation,
        bootstrap_resamples=100,
        permutation_resamples=100,
        seed=4,
    )


def test_session_aggregation_changes_reported_rates_instead_of_being_ignored() -> None:
    sessions = _unequal_exposure_sessions()

    pooled = infer_transient_animals(sessions, _rate_spec(None))
    mean_rate = infer_transient_animals(sessions, _rate_spec("mean"))
    median_rate = infer_transient_animals(sessions, _rate_spec("median"))

    def control(result: object) -> float:
        assert isinstance(result, type(pooled))
        return next(
            estimate.value
            for estimate in result.estimates
            if estimate.subject == "m1" and estimate.condition == "control"
        )

    assert control(pooled) == pytest.approx(60 * 18 / 720)
    assert control(mean_rate) == pytest.approx((1 + 6 + 2) / 3)
    assert control(median_rate) == pytest.approx(2.0)
    assert control(mean_rate) != pytest.approx(control(median_rate))
    assert pooled.estimate != pytest.approx(mean_rate.estimate)
    assert mean_rate.estimate != pytest.approx(median_rate.estimate)
    assert pooled.session_aggregation == "exposure_weighted"
    assert mean_rate.session_aggregation == "mean"


def test_exposure_weighted_aggregation_is_refused_for_kinetic_metrics() -> None:
    sessions = [
        _session("m1", "control", count=1, duration=60, amplitudes=(1.0,)),
        _session("m1", "drug", count=1, duration=60, amplitudes=(2.0,)),
        _session("m2", "control", count=1, duration=60, amplitudes=(1.5,)),
        _session("m2", "drug", count=1, duration=60, amplitudes=(2.5,)),
    ]
    spec = TransientAnimalInferenceSpec(
        metric="amplitude",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="paired",
        session_aggregation="exposure_weighted",
        bootstrap_resamples=100,
        permutation_resamples=100,
    )

    with pytest.raises(ValueError, match="defined only for"):
        infer_transient_animals(sessions, spec)


def test_paired_rate_inference_pools_exposure_then_resamples_animals() -> None:
    sessions = [
        _session("m1", "control", session_index=1, count=1, duration=30),
        _session("m1", "control", session_index=2, count=1, duration=30),
        _session("m1", "drug", count=4, duration=60),
        _session("m2", "control", count=3, duration=60),
        _session("m2", "drug", count=6, duration=60),
        _session("m3", "control", count=4, duration=60),
        _session("m3", "drug", count=8, duration=60),
    ]
    spec = TransientAnimalInferenceSpec(
        metric="rate_per_minute",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="paired",
        bootstrap_resamples=500,
        permutation_resamples=500,
        seed=4,
    )

    result = infer_transient_animals(sessions, spec)

    assert result.estimate == pytest.approx(3.0)
    assert result.animals_a == result.animals_b == ("m1", "m2", "m3")
    animal = next(
        estimate
        for estimate in result.estimates
        if estimate.subject == "m1" and estimate.condition == "control"
    )
    assert animal.session_count == 2
    assert animal.event_count == 2
    assert animal.analyzed_duration_s == 60
    assert animal.value == 2
    assert result.permutation_resamples == 8
    assert result.interval_low <= result.estimate <= result.interval_high


def test_kinetics_are_summarized_by_session_then_animal() -> None:
    sessions = [
        _session(
            "a1",
            "control",
            session_index=1,
            count=3,
            duration=60,
            amplitudes=(1, 1, 100),
        ),
        _session(
            "a1",
            "control",
            session_index=2,
            count=1,
            duration=60,
            amplitudes=(3,),
        ),
        _session("a2", "control", count=1, duration=60, amplitudes=(2,)),
        _session("b1", "drug", count=1, duration=60, amplitudes=(5,)),
        _session("b2", "drug", count=1, duration=60, amplitudes=(7,)),
    ]
    spec = TransientAnimalInferenceSpec(
        metric="amplitude",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="independent",
        session_aggregation="median",
        bootstrap_resamples=200,
        permutation_resamples=200,
    )

    result = infer_transient_animals(sessions, spec)

    a1 = next(estimate for estimate in result.estimates if estimate.subject == "a1")
    assert a1.value == 2  # median of session medians 1 and 3, not all event values
    assert result.estimate == pytest.approx(4.0)  # mean(drug 5,7) - mean(control 2,2)


def test_independent_design_rejects_reused_animals() -> None:
    sessions = [
        _session("m1", "control", count=1, duration=60),
        _session("m1", "drug", count=2, duration=60),
        _session("m2", "control", count=1, duration=60),
        _session("m3", "drug", count=2, duration=60),
    ]
    spec = TransientAnimalInferenceSpec(
        metric="rate_per_minute",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="independent",
        bootstrap_resamples=100,
        permutation_resamples=100,
    )

    with pytest.raises(ValueError, match="cannot reuse subjects"):
        infer_transient_animals(sessions, spec)


def test_ratio_effect_rejects_zero_animal_rates() -> None:
    sessions = [
        _session("m1", "control", count=0, duration=60),
        _session("m1", "drug", count=2, duration=60),
        _session("m2", "control", count=1, duration=60),
        _session("m2", "drug", count=2, duration=60),
    ]
    spec = TransientAnimalInferenceSpec(
        metric="rate_per_minute",
        condition_a="control",
        condition_b="drug",
        channel="NAc",
        design="paired",
        effect_scale="ratio",
        bootstrap_resamples=100,
        permutation_resamples=100,
    )

    with pytest.raises(ValueError, match="positive animal estimates"):
        infer_transient_animals(sessions, spec)
