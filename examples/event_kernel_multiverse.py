"""Compare named event-kernel designs without silently selecting a winner."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from fiberphotometry import (
    EncodingModelAlternative,
    EncodingModelSpec,
    EncodingMultiverseSpec,
    EncodingSession,
    EventKernelSpec,
    run_encoding_multiverse,
)


def simulated_sessions() -> tuple[EncodingSession, ...]:
    rng = np.random.default_rng(481)
    sessions = []
    dt = 0.1
    for animal in range(8):
        time = np.arange(0.0, 30.0, dt)
        cue = np.arange(3.0, 27.0, 4.0)
        reward = cue + 0.7
        motion = np.sin(time * 0.6 + animal)
        response = 0.25 * motion + rng.normal(0.0, 0.07, len(time))
        for event_time in cue:
            index = round(event_time / dt)
            response[index : index + 3] += (0.2, 0.45, 0.2)
        for event_time in reward:
            index = round(event_time / dt)
            response[index : index + 3] += (0.5, 0.9, 0.4)
        sessions.append(
            EncodingSession.from_arrays(
                subject=f"mouse-{animal}",
                session="day-0",
                time=time,
                response=response,
                events={"cue": cue, "reward": reward},
                continuous_covariates={"motion": motion},
            )
        )
    return tuple(sessions)


def model(
    *events: EventKernelSpec,
    covariates: tuple[str, ...] = (),
) -> EncodingModelSpec:
    return EncodingModelSpec(
        event_kernels=events,
        continuous_covariates=covariates,
        alpha_grid=(0.0, 0.1, 1.0, 10.0),
        group_by="animal",
        folds=4,
        minimum_session_coverage=0.9,
    )


def run() -> None:
    cue = EventKernelSpec("cue", (0.0, 0.2))
    reward = EventKernelSpec("reward", (0.0, 0.2))
    spec = EncodingMultiverseSpec(
        alternatives=(
            EncodingModelAlternative(
                "cue-only",
                "Minimal task-event reference model.",
                model(cue),
            ),
            EncodingModelAlternative(
                "cue-and-reward",
                "Separate the delayed reward response from the cue.",
                model(cue, reward),
            ),
            EncodingModelAlternative(
                "cue-reward-motion",
                "Test whether measured motion adds held-out predictive value.",
                model(cue, reward, covariates=("motion",)),
            ),
        ),
        reference="cue-only",
        intent="exploratory",
    )
    result = run_encoding_multiverse(simulated_sessions(), spec)
    Path("event-kernel-multiverse-result.json").write_text(result.to_json())
    for comparison in result.comparisons:
        print(
            comparison.name,
            comparison.status,
            comparison.alternative_mean_r_squared,
            comparison.delta_mean_r_squared,
        )


if __name__ == "__main__":
    run()
