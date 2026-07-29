import json

import numpy as np
import pytest

from fipha.multiscale import (
    MultiscaleAnimalInferenceSpec,
    MultiscaleContinuitySpec,
    MultiscaleStudySession,
    MultiscaleSummarySpec,
    MultiscaleWindowSpec,
    infer_multiscale_animals,
    summarize_multiscale,
)
from fipha.spectral import StateEpoch


def test_multiscale_summary_keeps_sample_and_time_weighting_distinct() -> None:
    time = np.asarray([0.0, 1.0, 9.0, 10.0])
    values = np.asarray([0.0, 0.0, 10.0, 10.0])
    result = summarize_multiscale(
        time,
        values,
        MultiscaleSummarySpec(
            windows=(MultiscaleWindowSpec("ten_seconds", 10.0),),
            metrics=("sample_mean", "time_weighted_mean"),
            continuity=MultiscaleContinuitySpec(maximum_gap_s=20.0),
        ),
        value_unit="dF/F",
    )

    estimates = {item.metric: item for item in result.estimates}
    assert estimates["sample_mean"].value == pytest.approx(10 / 3)
    assert estimates["time_weighted_mean"].value == pytest.approx(5)
    assert {item.unit for item in estimates.values()} == {"dF/F"}
    assert result.windows[0].coverage_fraction == pytest.approx(1)
    assert result.runs[0].interval_cv > 0
    assert json.loads(result.to_json())["schema_version"] == "1"


def test_multiscale_windows_never_bridge_acquisition_gaps() -> None:
    time = np.concatenate((np.arange(0.0, 10.0), np.arange(20.0, 30.0)))
    values = np.sin(time)
    result = summarize_multiscale(
        time,
        values,
        MultiscaleSummarySpec(
            windows=(MultiscaleWindowSpec("eight_seconds", 8.0, minimum_coverage=0.9),),
            metrics=("time_weighted_mean",),
        ),
    )

    accepted = [window for window in result.windows if window.accepted]
    rejected = [window for window in result.windows if not window.accepted]
    assert len(result.runs) == 2
    assert result.gap_count == 1
    assert len(accepted) == 2
    assert len(rejected) == 2
    assert all(window.stop_s <= 10 or window.start_s >= 20 for window in accepted)
    assert all(
        window.exclusion_reason is not None
        and "below_minimum_coverage" in window.exclusion_reason
        for window in rejected
    )


def test_state_epochs_are_separate_runs_even_when_labels_match() -> None:
    time = np.arange(0.0, 20.0, 0.5)
    values = np.where(time < 10, 1.0, 2.0)
    epochs = (
        StateEpoch("rest", 0.0, 8.0, "rest-1"),
        StateEpoch("rest", 10.0, 18.0, "rest-2"),
    )
    result = summarize_multiscale(
        time,
        values,
        MultiscaleSummarySpec(
            windows=(MultiscaleWindowSpec("four_seconds", 4.0, minimum_coverage=0.85),),
            metrics=("sample_mean",),
        ),
        epochs=epochs,
    )

    assert len(result.runs) == 2
    assert {run.epoch_id for run in result.runs} == {"rest-1", "rest-2"}
    assert {run.state for run in result.runs} == {"rest"}
    assert result.unassigned_valid_sample_count == 8
    by_epoch = {
        item.epoch_id: item.value
        for item in result.estimates
        if item.metric == "sample_mean"
    }
    assert by_epoch == {"rest-1": 1.0, "rest-2": 2.0}


def test_invalid_samples_split_runs_and_leave_rejected_windows_visible() -> None:
    time = np.arange(0.0, 12.0, 0.5)
    values = np.ones_like(time)
    valid = np.ones_like(time, dtype=bool)
    valid[10:14] = False
    valid[12] = True
    result = summarize_multiscale(
        time,
        values,
        MultiscaleSummarySpec(
            windows=(MultiscaleWindowSpec("four_seconds", 4.0),),
            metrics=("sample_mean",),
        ),
        valid=valid,
    )

    assert len(result.runs) == 2
    assert result.invalid_sample_count == 3
    assert len(result.run_exclusions) == 1
    assert result.run_exclusions[0].reason == "fewer_than_two_samples"
    assert any(not window.accepted for window in result.windows)
    assert all(
        not (window.start_s < 7 and window.stop_s > 5)
        for window in result.windows
        if window.accepted
    )


def test_paired_inference_aggregates_windows_then_sessions_then_animals() -> None:
    sessions = []
    summary_spec = MultiscaleSummarySpec(
        windows=(MultiscaleWindowSpec("five_seconds", 5.0),),
        metrics=("time_weighted_mean",),
    )
    time = np.arange(0.0, 20.0, 0.1)
    for animal in range(5):
        for condition, shift in (("baseline", 0.0), ("treatment", 2.0)):
            for session in range(2):
                values = np.full_like(time, animal + 1 + shift + 0.1 * session)
                summary = summarize_multiscale(time, values, summary_spec)
                sessions.append(
                    MultiscaleStudySession(
                        subject=f"mouse-{animal}",
                        session=f"{condition}-{session}",
                        condition=condition,
                        result=summary,
                    )
                )

    result = infer_multiscale_animals(
        sessions,
        MultiscaleAnimalInferenceSpec(
            scale="five_seconds",
            metric="time_weighted_mean",
            condition_a="baseline",
            condition_b="treatment",
            design="paired",
            bootstrap_resamples=250,
            permutation_resamples=250,
            seed=12,
        ),
    )

    assert result.estimate == pytest.approx(2)
    assert result.interval_low == pytest.approx(2)
    assert result.interval_high == pytest.approx(2)
    assert len(result.estimates) == 10
    assert {item.session_count for item in result.estimates} == {2}
    assert {item.window_count for item in result.estimates} == {8}
    assert result.animals_a == result.animals_b
    assert result.permutation_pvalue < 0.1
    assert result.effect_direction == "condition_b relative to condition_a"


def test_independent_ratio_inference_keeps_subjects_disjoint() -> None:
    time = np.arange(0.0, 12.0, 0.1)
    summary_spec = MultiscaleSummarySpec(
        windows=(MultiscaleWindowSpec("six_seconds", 6.0),),
        metrics=("sample_mean",),
    )
    sessions = []
    for condition, subjects, level in (
        ("control", ("c1", "c2", "c3"), 2.0),
        ("stimulus", ("s1", "s2", "s3"), 4.0),
    ):
        for subject in subjects:
            sessions.append(
                MultiscaleStudySession(
                    subject,
                    f"{subject}-session",
                    condition,
                    summarize_multiscale(time, np.full_like(time, level), summary_spec),
                )
            )

    result = infer_multiscale_animals(
        sessions,
        MultiscaleAnimalInferenceSpec(
            scale="six_seconds",
            metric="sample_mean",
            condition_a="control",
            condition_b="stimulus",
            design="independent",
            effect_scale="ratio",
            bootstrap_resamples=200,
            permutation_resamples=200,
        ),
    )

    assert result.estimate == pytest.approx(2)
    assert set(result.animals_a).isdisjoint(result.animals_b)
    assert result.interval_low == pytest.approx(2)
    assert result.interval_high == pytest.approx(2)


def test_multiscale_contract_refuses_ambiguous_or_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="unique"):
        MultiscaleSummarySpec(
            windows=(
                MultiscaleWindowSpec("same", 1),
                MultiscaleWindowSpec("same", 2),
            )
        )
    with pytest.raises(ValueError, match="overlap_policy"):
        summarize_multiscale(
            np.arange(20.0),
            np.ones(20),
            MultiscaleSummarySpec(
                windows=(MultiscaleWindowSpec("five", 5),),
                metrics=("sample_mean",),
            ),
            epochs=(StateEpoch("a", 0, 12), StateEpoch("b", 10, 20)),
        )
