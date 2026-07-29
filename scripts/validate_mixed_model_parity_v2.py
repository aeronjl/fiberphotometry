"""Validate scalar mixed-model point and interval plumbing against direct MixedLM."""

from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from fipha import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
)
from fipha.mixed import ScalarMixedModelSpec, fit_scalar_mixed_model


def main() -> None:
    output = Path("benchmarks/mixed-model-parity-v0.2.json")
    scenarios = [_run_scenario(nested=False), _run_scenario(nested=True)]
    body = {
        "schema_version": "mixed-model-parity-v0.2",
        "statsmodels_version": version("statsmodels"),
        "tolerance": 1e-10,
        "scope": (
            "numerical wrapper parity for fixed-effect estimates, standard errors, "
            "and normal-theory intervals; not interval coverage validation"
        ),
        "scenarios": scenarios,
        "passed": all(item["passed"] for item in scenarios),
    }
    result_sha256 = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {**body, "result_sha256": result_sha256}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _run_scenario(*, nested: bool) -> dict[str, object]:
    rng = np.random.default_rng(100 if nested else 99)
    rows = []
    event = 0
    for animal_index in range(24):
        animal = f"a{animal_index:02d}"
        intercept = rng.normal(0, 0.8)
        effect = rng.normal(0.4, 0.18)
        session_count = 1 + animal_index % 3 if nested else 1
        for session_index in range(session_count):
            session = f"{animal}-s{session_index}"
            session_effect = rng.normal(0, 0.25) if nested else 0
            for label, count in (
                ("control", 7 + (animal_index + session_index) % 5),
                ("drug", 5 + (2 * animal_index + session_index) % 8),
            ):
                for _ in range(count):
                    outcome = (
                        intercept
                        + session_effect
                        + (effect if label == "drug" else 0)
                        + rng.normal(0, 0.2)
                    )
                    rows.append((f"e{event}", animal, session, label, outcome))
                    event += 1
    frame = pd.DataFrame(
        rows, columns=["event_id", "animal", "session", "condition", "outcome"]
    )
    table = ObservationTable.from_columns(
        {column: frame[column].tolist() for column in frame.columns}
    )
    design = StudyDesign(
        "event_id",
        (
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        (Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")
    spec = ScalarMixedModelSpec(
        nested_random_intercept_unit="session" if nested else None
    )
    ours = fit_scalar_mixed_model(table, design, estimand, spec)
    direct_frame = frame.assign(condition=(frame["condition"] == "drug").astype(float))
    direct = smf.mixedlm(
        "outcome ~ condition",
        direct_frame,
        groups=direct_frame["animal"],
        re_formula="1 + condition",
        vc_formula={"session": "0 + C(session)"} if nested else None,
    ).fit(reml=True, method="lbfgs", disp=False)
    direct_interval = direct.conf_int().loc["condition"].to_numpy(dtype=float)
    ours_interval = np.asarray(ours.confidence_interval)
    differences = {
        "estimate": abs(ours.estimate - float(direct.fe_params["condition"])),
        "standard_error": abs(ours.standard_error - float(direct.bse_fe["condition"])),
        "interval": float(np.max(np.abs(ours_interval - direct_interval))),
    }
    return {
        "name": "unbalanced_nested_sessions" if nested else "unbalanced_events",
        "animals": 24,
        "sessions": int(frame["session"].nunique()),
        "observations": len(frame),
        "converged": ours.converged and bool(direct.converged),
        "fipha": {
            "estimate": ours.estimate,
            "standard_error": ours.standard_error,
            "confidence_interval": ours.confidence_interval,
        },
        "direct_statsmodels": {
            "estimate": float(direct.fe_params["condition"]),
            "standard_error": float(direct.bse_fe["condition"]),
            "confidence_interval": direct_interval.tolist(),
        },
        "absolute_differences": differences,
        "passed": ours.converged
        and bool(direct.converged)
        and max(differences.values()) < 1e-10,
    }


if __name__ == "__main__":
    main()
