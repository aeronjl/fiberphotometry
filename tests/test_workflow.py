import json

import numpy as np
import pytest

from fiberphotometry import (
    EventAnalysis,
    EventSession,
    PeriEventInferenceSpec,
    Preprocessing,
    artifact_schema,
    make_recording,
)


def _sessions(*, reference: bool = True) -> tuple[EventSession, ...]:
    sessions = []
    for animal_index in range(4):
        time = np.arange(0, 80, 0.05)
        control = 1 + 0.05 * np.sin(time / 8)
        signal = 2 + 0.6 * control
        event_times = [20.0, 30.0, 40.0, 50.0, 60.0]
        conditions = ["incorrect", "correct", "incorrect", "correct", "correct"]
        for event_time, condition in zip(event_times, conditions, strict=True):
            if condition == "correct":
                selected = (time >= event_time) & (time < event_time + 0.5)
                signal[selected] += 0.08 + animal_index * 0.005
        recording = make_recording(
            time=time,
            signal=signal,
            reference=control if reference else None,
            channel_names=["DMS"],
            subject=f"animal-{animal_index + 1}",
            session=f"session-{animal_index + 1}",
        )
        sessions.append(EventSession.from_arrays(recording, event_times, conditions))
    return tuple(sessions)


def test_scientist_workflow_plans_runs_and_renders_report(tmp_path) -> None:
    study = EventAnalysis(
        _sessions(),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.reference(),
        title="Feedback response",
    )
    plan = study.plan()

    with pytest.raises(ValueError, match="unacknowledged"):
        study.run(acknowledged_assumptions=())

    result = study.run(acknowledged_assumptions=plan.required_assumptions)
    report_path = result.write_html(tmp_path / "report.html")

    assert result.pipeline.analysis is not None
    assert result.pipeline.analysis.estimate > 0
    assert report_path.exists()
    html = report_path.read_text()
    assert "Feedback response" in html
    assert "Does the effect survive the animal boundary?" in html
    assert "animal-1" in html
    assert "IRLS reference correction" in html
    assert "input fingerprint" in html
    artifact = json.loads(result.to_json())
    schema = artifact_schema("event_analysis_result")
    assert set(artifact) == set(schema["properties"])
    assert artifact["artifact_type"] == "event_analysis_result"
    assert artifact["schema_version"] == "1"
    assert artifact["event_coverage"]["schema_version"] == "1"


def test_scientist_workflow_supports_signal_only_qc() -> None:
    study = EventAnalysis(
        _sessions(reference=False),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.signal_only(
            method="rolling_mean", rolling_window_s=10
        ),
    )
    plan = study.plan()

    result = study.run(acknowledged_assumptions=plan.required_assumptions)

    assert result.pipeline.analysis is not None
    assert "reference" not in result.pipeline.processed_recordings[0]
    quality_json = result.pipeline.quality_reports[0].to_json()
    assert "signal_reference_correlation" not in quality_json


def test_scientist_workflow_reports_candidate_gate_and_complete_events() -> None:
    sessions = []
    for session in _sessions():
        sessions.append(
            EventSession.from_arrays(
                session.recording,
                session.event_times,
                session.conditions,
                event_ids=session.event_ids,
                eligible=[False, True, True, True, True],
                exclusion_reasons=["recording_edge"] * 5,
            )
        )
    study = EventAnalysis(
        tuple(sessions),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.reference(),
    )
    plan = study.plan()

    result = study.run(acknowledged_assumptions=plan.required_assumptions)

    assert result.coverage.total.candidate == 20
    assert result.coverage.total.gated == 16
    assert result.coverage.total.complete == 16
    assert dict(result.coverage.gate_dispositions) == {"recording_edge": 4}
    assert "condition_dependent_gate_retention" in result.coverage.warnings
    payload = json.loads(result.to_json())
    assert payload["event_coverage"]["total"]["candidate"] == 20
    html = result.to_html()
    assert "Which events reached the estimate?" in html
    assert "recording_edge: 4" in html
    assert "Condition gate Δ" in html


def test_scientist_workflow_reports_incomplete_preprocessing_windows() -> None:
    sessions = list(_sessions())
    first = sessions[0]
    recording = first.recording.copy(deep=True)
    response = (recording.time.values >= 50.0) & (recording.time.values < 50.5)
    recording["signal"].values[response, 0] = np.nan
    sessions[0] = EventSession.from_arrays(
        recording,
        first.event_times,
        first.conditions,
        event_ids=first.event_ids,
    )
    study = EventAnalysis(
        tuple(sessions),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.reference(),
    )
    plan = study.plan()

    result = study.run(acknowledged_assumptions=plan.required_assumptions)

    assert result.coverage.total.gated == 20
    assert result.coverage.total.complete == 19
    assert dict(result.coverage.preprocessing_dispositions) == {"event_inside_gap": 1}
    assert "condition_dependent_completion_retention" in result.coverage.warnings


def test_scientist_workflow_can_add_animal_level_timecourse() -> None:
    study = EventAnalysis(
        _sessions(),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.reference(),
        timecourse=PeriEventInferenceSpec(draws=100, seed=4),
    )
    plan = study.plan()

    result = study.run(acknowledged_assumptions=plan.required_assumptions)

    assert result.timecourse is not None
    assert result.timecourse.animal_count == 4
    assert len(result.timecourse.relative_time) == 61
    assert json.loads(result.to_json())["timecourse"]["seed"] == 4
    html = result.to_html()
    assert "Animal-level peri-event contrast" in html
    assert "simultaneous band covers the whole declared window" in html
    assert "whole-window significance test" in html
