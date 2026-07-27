from __future__ import annotations

from dataclasses import replace

import pytest

from fiberphotometry import (
    ObservationTable,
    SessionComparabilityRecord,
    SessionComparabilitySpec,
    assess_session_comparability,
    prepare_unspool_study,
)


def _records() -> tuple[SessionComparabilityRecord, ...]:
    common = {
        "subject": "mouse-1",
        "series_id": "dms-dlight",
        "sensor": "dLight1.3b",
        "site": "DMS",
        "output_variable": "dff",
        "unit": "fraction",
        "preprocessing_fingerprint": "pipeline-a",
        "finite_fraction": 0.99,
        "event_coverage_fraction": 0.92,
        "reference_correlation": 0.71,
        "sampling_rate_hz": 20.0,
        "acquisition_system": "neurophotometrics",
    }
    return (
        SessionComparabilityRecord(
            session="day-1",
            baseline_median=100.0,
            **common,
        ),
        SessionComparabilityRecord(
            session="day-2",
            baseline_median=110.0,
            reference_correlation=0.73,
            **{
                key: value
                for key, value in common.items()
                if key != "reference_correlation"
            },
        ),
    )


def _table(second_session: str = "day-2") -> ObservationTable:
    return ObservationTable.from_columns(
        {
            "animal": ["mouse-1", "mouse-1"],
            "recording": ["day-1", second_session],
            "event_index": [0, 0],
            "day": [0, 1],
            "neural_response": [0.1, 0.2],
        }
    )


def test_comparability_passes_stable_series_and_is_order_invariant() -> None:
    records = _records()
    report = assess_session_comparability(records)
    reversed_report = assess_session_comparability(tuple(reversed(records)))

    assert report.status == "pass"
    assert report.issues == ()
    assert report.groups[0].baseline_fold_change == pytest.approx(1.1)
    assert report.groups[0].reference_correlation_range == pytest.approx(0.02)
    assert report.groups[0].sampling_rate_ratio == pytest.approx(1.0)
    assert report.input_fingerprint == reversed_report.input_fingerprint
    assert '"artifact_type":"session_comparability"' in report.to_json()


def test_comparability_warns_without_silently_failing_handoff() -> None:
    first, second = _records()
    second = replace(
        second,
        baseline_median=250.0,
        acquisition_system="doric",
    )
    report = assess_session_comparability((first, second))

    assert report.status == "warning"
    assert {issue.code for issue in report.issues} == {
        "acquisition_system_changed",
        "baseline_fold_change",
    }
    report.require_ready()
    with pytest.raises(ValueError, match="has warnings"):
        report.require_ready(allow_warnings=False)


def test_comparability_refuses_identity_preprocessing_and_qc_failures() -> None:
    first, second = _records()
    second = replace(
        second,
        sensor="GCaMP8m",
        preprocessing_fingerprint="pipeline-b",
        finite_fraction=0.5,
    )
    report = assess_session_comparability((first, second))

    assert report.status == "fail"
    codes = {issue.code for issue in report.issues if issue.severity == "error"}
    assert codes == {
        "low_finite_fraction",
        "preprocessing_changed",
        "sensor_changed",
    }
    with pytest.raises(ValueError, match="session comparability failed"):
        report.require_ready()


def test_comparability_missing_metrics_follow_prospective_spec() -> None:
    records = tuple(
        replace(
            record,
            event_coverage_fraction=None,
            baseline_median=None,
            reference_correlation=None,
            sampling_rate_hz=None,
        )
        for record in _records()
    )
    warning_report = assess_session_comparability(records)
    strict_report = assess_session_comparability(
        records,
        SessionComparabilitySpec(
            require_event_coverage=True,
            require_baseline_metric=True,
            require_reference_metric=True,
            require_sampling_rate=True,
        ),
    )

    assert warning_report.status == "warning"
    assert strict_report.status == "fail"
    assert {issue.code for issue in strict_report.issues} == {
        "baseline_metric_missing",
        "event_coverage_missing",
        "reference_metric_missing",
        "sampling_rate_missing",
    }


def test_unspool_handoff_carries_and_enforces_comparability() -> None:
    report = assess_session_comparability(_records())
    export = prepare_unspool_study(
        _table(),
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="day",
        comparability=report,
        require_comparability=True,
    )

    assert export.comparability_status == "pass"
    assert export.comparability_fingerprint == report.input_fingerprint
    assert export.schema_version == "2"

    with pytest.raises(ValueError, match="requires a session comparability"):
        prepare_unspool_study(
            _table(),
            subject="animal",
            session="recording",
            trial="event_index",
            session_order="day",
            require_comparability=True,
        )


def test_unspool_handoff_rejects_failed_or_incomplete_preflight() -> None:
    first, second = _records()
    failed = assess_session_comparability((first, replace(second, unit="z-score")))
    with pytest.raises(ValueError, match="session comparability failed"):
        prepare_unspool_study(
            _table(),
            subject="animal",
            session="recording",
            trial="event_index",
            session_order="day",
            comparability=failed,
        )

    passed = assess_session_comparability(_records())
    with pytest.raises(ValueError, match="does not cover Unspool sessions"):
        prepare_unspool_study(
            _table("day-3"),
            subject="animal",
            session="recording",
            trial="event_index",
            session_order="day",
            comparability=passed,
        )


def test_comparability_validates_threshold_nesting_and_record_keys() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        SessionComparabilitySpec(
            minimum_finite_fraction_error=0.95,
            minimum_finite_fraction_warning=0.8,
        )
    with pytest.raises(ValueError, match="must be unique"):
        assess_session_comparability((_records()[0], _records()[0]))
