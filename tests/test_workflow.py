import numpy as np
import pytest

from fiberphotometry import (
    EventAnalysis,
    EventSession,
    Preprocessing,
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
