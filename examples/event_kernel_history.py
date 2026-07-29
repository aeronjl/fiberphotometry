"""Recover a previous-outcome modulation of a cue response."""

import numpy as np

from fipha.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    EventModulationSpec,
    fit_event_kernel_model,
)

rng = np.random.default_rng(914)
sessions = []
for animal in range(8):
    time = np.arange(0.0, 50.0, 0.1)
    cue = np.arange(2.0, 48.0, 2.0)
    outcome = np.where((np.arange(len(cue)) + animal) % 3 == 0, 0.5, -0.5)
    response = rng.normal(0.0, 0.04, len(time))
    for index, event_time in enumerate(cue):
        previous_outcome = 0.0 if index == 0 else outcome[index - 1]
        start = round(event_time / 0.1)
        response[start : start + 3] += np.asarray([0.3, 0.8, 0.4])
        response[start : start + 3] += previous_outcome * np.asarray([-0.2, 0.5, 0.25])
    sessions.append(
        EncodingSession.from_arrays(
            subject=f"mouse-{animal}",
            session="day-0",
            time=time,
            response=response,
            events={"cue": cue},
            event_values={"cue": {"outcome_code": outcome}},
        )
    )

model = EncodingModelSpec(
    event_kernels=(
        EventKernelSpec("cue", (0.0, 0.2)),
        EventKernelSpec(
            "cue-by-previous-outcome",
            (0.0, 0.2),
            source_event="cue",
            modulation=EventModulationSpec("outcome_code", lag_events=1),
        ),
    ),
    alpha_grid=(0.0, 0.1),
    folds=4,
)
result = fit_event_kernel_model(tuple(sessions), model)

for kernel in result.event_kernels:
    print(kernel.name, np.round(kernel.coefficient, 3))
