"""Fit a leakage-safe event-kernel model to a reproducible synthetic cohort."""

from pathlib import Path

import numpy as np

from fiberphotometry.encoding import (
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    fit_event_kernel_model,
)


def simulate_cohort(seed: int = 481) -> tuple[EncodingSession, ...]:
    """Create overlapping cue/reward responses with a continuous motion effect."""
    rng = np.random.default_rng(seed)
    sessions = []
    sample_interval = 0.1
    cue_kernel = np.array([0.25, 0.80, 1.20, 0.70, 0.20])
    reward_kernel = np.array([-0.20, 0.40, 0.90, 0.45])
    for animal_index in range(8):
        for session_index in range(2):
            time = np.arange(0.0, 40.0, sample_interval)
            cues = np.arange(3.0, 36.0, 4.0) + 0.1 * (animal_index % 2)
            rewards = cues + 0.5 + 0.1 * (session_index % 2)
            motion = np.sin(0.7 * time + animal_index)
            motion += rng.normal(0.0, 0.15, len(time))
            response = 0.35 * motion + 0.05 * animal_index
            for event_time in cues:
                index = round(event_time / sample_interval)
                response[index - 1 : index + 4] += cue_kernel
            for event_time in rewards:
                index = round(event_time / sample_interval)
                response[index : index + 4] += reward_kernel
            response += rng.normal(0.0, 0.08, len(time))
            sessions.append(
                EncodingSession.from_arrays(
                    subject=f"mouse-{animal_index}",
                    session=f"day-{session_index}",
                    time=time,
                    response=response,
                    events={"cue": cues, "reward": rewards},
                    continuous_covariates={"motion": motion},
                )
            )
    return tuple(sessions)


def main(output: Path = Path("event-kernel-result.json")) -> None:
    result = fit_event_kernel_model(
        simulate_cohort(),
        EncodingModelSpec(
            event_kernels=(
                EventKernelSpec("cue", (-0.1, 0.3)),
                EventKernelSpec("reward", (0.0, 0.3)),
            ),
            continuous_covariates=("motion",),
            alpha_grid=(0.0, 0.1, 1.0, 10.0),
            group_by="animal",
            folds=4,
        ),
    )
    output.write_text(result.to_json() + "\n", encoding="utf-8")
    selected = next(
        item for item in result.cross_validation if item.alpha == result.selected_alpha
    )
    print(f"selected alpha: {result.selected_alpha:g}")
    print(f"animal-held-out mean R²: {selected.mean_r_squared:.3f}")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
