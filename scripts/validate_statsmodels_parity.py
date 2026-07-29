"""Opt-in scalar-estimate parity check against statsmodels MixedLM."""

from __future__ import annotations

import json

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
    hierarchical_bootstrap,
)
from fipha.inference import ResamplingPlan


def main() -> None:
    rng = np.random.default_rng(42)
    animal = np.repeat([f"a{i}" for i in range(16)], 80)
    condition = np.tile(np.repeat(["control", "drug"], 40), 16)
    outcome = (
        np.repeat(rng.normal(0, 0.8, 16), 80)
        + (condition == "drug") * 0.4
        + rng.normal(0, 0.25, len(animal))
    )
    frame = pd.DataFrame({"animal": animal, "condition": condition, "outcome": outcome})
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{i}" for i in range(len(frame))],
            **{column: frame[column].tolist() for column in frame.columns},
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")
    ours = hierarchical_bootstrap(
        table,
        design,
        estimand,
        ResamplingPlan(("animal", "event")),
        interval_method="percentile",
        draws=50,
    ).estimate
    model = smf.mixedlm("outcome ~ C(condition)", frame, groups=frame["animal"]).fit()
    external = float(model.params["C(condition)[T.drug]"])
    print(
        json.dumps(
            {
                "fipha": ours,
                "statsmodels": external,
                "absolute_difference": abs(ours - external),
                "pass": abs(ours - external) < 1e-10,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
