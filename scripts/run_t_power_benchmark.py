"""Execute the frozen finite-sample t and power protocol v0.7."""

from __future__ import annotations

import json

import numpy as np
from scipy.stats import nct, t


def main() -> None:
    results = {}
    for animals in (6, 8, 10, 12, 16, 20, 30):
        rng = np.random.default_rng(animals)
        control = rng.normal(size=(10_000, animals))
        noise = rng.normal(size=(10_000, animals))
        null = _rejections(control, noise, 0.0)
        power = _rejections(control, noise, 0.8)
        degrees = 2 * animals - 2
        critical = t.ppf(0.975, degrees)
        noncentrality = 0.8 / np.sqrt(2 / animals)
        theoretical = float(
            nct.cdf(-critical, degrees, noncentrality)
            + nct.sf(critical, degrees, noncentrality)
        )
        results[str(animals)] = {
            "coverage": 1 - null,
            "power": power,
            "theoretical_power": theoretical,
        }
    acceptance = {
        "coverage": all(0.94 <= row["coverage"] <= 0.96 for row in results.values()),
        "power_parity": all(
            abs(row["power"] - row["theoretical_power"]) <= 0.03
            for row in results.values()
        ),
    }
    reaching = [int(size) for size, row in results.items() if row["power"] >= 0.8]
    print(
        json.dumps(
            {
                "protocol": "v0.7",
                "results": results,
                "minimum_animals_per_condition_for_80_percent_power": min(reaching)
                if reaching
                else None,
                "acceptance": acceptance,
                "all_acceptance_met": all(acceptance.values()),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _rejections(
    control: np.ndarray, treatment_noise: np.ndarray, effect: float
) -> float:
    treatment = treatment_noise + effect
    difference = treatment.mean(axis=1) - control.mean(axis=1)
    variance = (
        treatment.var(axis=1, ddof=1) / treatment.shape[1]
        + control.var(axis=1, ddof=1) / control.shape[1]
    )
    statistic = difference / np.sqrt(variance)
    numerator = variance**2
    denominator = (treatment.var(axis=1, ddof=1) / treatment.shape[1]) ** 2 / (
        treatment.shape[1] - 1
    ) + (control.var(axis=1, ddof=1) / control.shape[1]) ** 2 / (control.shape[1] - 1)
    degrees = numerator / denominator
    return float(np.mean(np.abs(statistic) > t.ppf(0.975, degrees)))


if __name__ == "__main__":
    main()
