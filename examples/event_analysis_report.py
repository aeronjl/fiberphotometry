"""Create a complete event-contrast report from small synthetic recordings."""

from pathlib import Path

import numpy as np

from fipha import EventAnalysis, EventSession, Preprocessing, make_recording


def main() -> None:
    sessions = []
    for animal_index in range(6):
        time = np.arange(0, 90, 0.05)
        reference = 1 + 0.08 * np.sin(time / 9)
        signal = 2 + 0.7 * reference
        event_times = [20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
        conditions = ["incorrect", "correct"] * 3
        for event_time, condition in zip(event_times, conditions, strict=True):
            if condition == "correct":
                signal[(time >= event_time) & (time < event_time + 0.5)] += (
                    0.07 + 0.004 * animal_index
                )
        recording = make_recording(
            time=time,
            signal=signal,
            reference=reference,
            channel_names=["DMS"],
            subject=f"mouse-{animal_index + 1:02d}",
            session=f"session-{animal_index + 1:02d}",
        )
        sessions.append(EventSession.from_arrays(recording, event_times, conditions))

    study = EventAnalysis(
        tuple(sessions),
        numerator="correct",
        denominator="incorrect",
        channel="DMS",
        preprocessing=Preprocessing.reference(method="irls"),
        title="Feedback-aligned DMS response",
        intent="exploratory",
    )
    plan = study.plan()
    print("Acknowledging:", *plan.required_assumptions, sep="\n- ")
    result = study.run(acknowledged_assumptions=plan.required_assumptions)
    destination = result.write_html(Path("event-analysis-report.html"))
    print(f"Report written to {destination}")


if __name__ == "__main__":
    main()
