"""Fit onset, duration-modulated and normalized-progress behavior kernels."""

import numpy as np

from fipha.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    EventModulationSpec,
    LinearProgressBasisSpec,
    ProgressKernelSpec,
    fit_event_kernel_model,
)
from fipha.interoperability import BehaviorAnnotations, BehaviorInterval

rng = np.random.default_rng(2027)
sessions = []
progress_weights = np.asarray([0.1, 0.7, 1.0, 0.4])
progress_centers = np.linspace(0.0, 1.0, len(progress_weights))
for animal in range(8):
    time = np.arange(0.0, 60.0, 0.1)
    starts = np.arange(3.0, 53.0, 5.0)
    durations = np.asarray([1.2, 2.0, 3.0, 1.6, 2.4] * 2)
    annotations = BehaviorAnnotations(
        subject=f"mouse-{animal}",
        session="day-0",
        point_events={},
        intervals=tuple(
            BehaviorInterval("rear", float(start), float(start + duration))
            for start, duration in zip(starts, durations, strict=True)
        ),
        source="simulated-bouts",
        clock_id="photometry",
    )
    inputs = annotations.interval_encoding_inputs(edge="onset")
    response = rng.normal(0.0, 0.04, len(time))
    for start, stop in inputs.intervals["rear"]:
        inside = (time >= start) & (time < stop)
        progress = (time[inside] - start) / (stop - start)
        response[inside] += np.interp(progress, progress_centers, progress_weights)
        onset = round(start / 0.1)
        response[onset : onset + 2] += 0.08 * (stop - start)
    sessions.append(
        EncodingSession.from_arrays(
            subject=annotations.subject,
            session=annotations.session,
            time=time,
            response=response,
            events=inputs.events,
            event_values=inputs.event_values,
            intervals=inputs.intervals,
        )
    )

spec = EncodingModelSpec(
    event_kernels=(
        EventKernelSpec("rear", (0.0, 0.1)),
        EventKernelSpec(
            "rear-by-duration",
            (0.0, 0.1),
            source_event="rear",
            modulation=EventModulationSpec("duration_s"),
        ),
    ),
    progress_kernels=(
        ProgressKernelSpec(
            "rear-progress",
            source_interval="rear",
            basis=LinearProgressBasisSpec(functions=4),
        ),
    ),
    alpha_grid=(0.0, 0.1, 1.0),
    folds=4,
)
result = fit_event_kernel_model(tuple(sessions), spec)

print("retained fraction", result.validity.retained_fraction)
print("duration kernel", np.round(result.event_kernels[1].coefficient, 3))
print("progress weights", np.round(result.progress_kernels[0].basis.coefficient, 3))
