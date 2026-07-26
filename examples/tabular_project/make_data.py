"""Generate the small deterministic CSV fixture used by the CLI walkthrough."""

import csv
import math
from pathlib import Path


def main() -> None:
    destination = Path(__file__).parent / "data"
    destination.mkdir(exist_ok=True)
    for animal_index in range(4):
        times = [index * 0.05 for index in range(280)]
        reference = [1 + 0.04 * math.sin(value / 3) for value in times]
        signal = [2 + 0.5 * value for value in reference]
        event_times = [4.0, 6.0, 8.0, 10.0]
        conditions = ["control", "drug", "control", "drug"]
        for event_time, condition in zip(event_times, conditions, strict=True):
            if condition == "drug":
                for index, sample_time in enumerate(times):
                    if event_time <= sample_time < event_time + 0.5:
                        signal[index] += 0.06 + animal_index * 0.005
        with (destination / f"recording-{animal_index + 1}.csv").open(
            "w", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(("time", "signal", "reference"))
            writer.writerows(zip(times, signal, reference, strict=True))
        with (destination / f"events-{animal_index + 1}.csv").open(
            "w", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(("time", "event_id", "condition"))
            writer.writerows(
                (
                    event_time,
                    f"event-{animal_index + 1}-{event_index + 1}",
                    condition,
                )
                for event_index, (event_time, condition) in enumerate(
                    zip(event_times, conditions, strict=True)
                )
            )
    print(f"Wrote four synthetic sessions to {destination}")


if __name__ == "__main__":
    main()
