import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from fiberphotometry.design import Factor, ObservationTable, StudyDesign, Unit
from fiberphotometry.inference import Contrast, Estimand
from fiberphotometry.mixed import ScalarMixedModelSpec, fit_scalar_mixed_model


def _unbalanced_nested_fixture():
    rng = np.random.default_rng(20260726)
    rows = []
    event = 0
    for animal_index in range(24):
        animal = f"a{animal_index:02d}"
        animal_intercept = rng.normal(0, 0.8)
        animal_effect = rng.normal(0.35, 0.15)
        for session_index in range(1 + animal_index % 3):
            session = f"{animal}-s{session_index}"
            session_intercept = rng.normal(0, 0.25)
            for condition, count in (
                ("control", 5 + (animal_index + session_index) % 7),
                ("drug", 4 + (2 * animal_index + session_index) % 9),
            ):
                for _ in range(count):
                    outcome = (
                        animal_intercept
                        + session_intercept
                        + (animal_effect if condition == "drug" else 0)
                        + rng.normal(0, 0.2)
                    )
                    rows.append((f"e{event}", animal, session, condition, outcome))
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
    return frame, table, design, estimand


def test_scalar_mixed_model_matches_independent_statsmodels_interval() -> None:
    frame, table, design, estimand = _unbalanced_nested_fixture()

    ours = fit_scalar_mixed_model(table, design, estimand)
    direct_frame = frame.assign(condition=(frame["condition"] == "drug").astype(float))
    direct = smf.mixedlm(
        "outcome ~ condition",
        direct_frame,
        groups=direct_frame["animal"],
        re_formula="1 + condition",
        vc_formula={"nested": "0 + C(session)"},
    ).fit(reml=True, method="lbfgs", disp=False)
    interval = direct.conf_int().loc["condition"]

    assert ours.converged
    assert ours.estimate == pytest.approx(direct.fe_params["condition"], abs=1e-12)
    assert ours.standard_error == pytest.approx(direct.bse_fe["condition"], abs=1e-12)
    assert ours.confidence_interval == pytest.approx(interval.tolist(), abs=1e-12)
    assert ours.groups == 24
    assert ours.nested_units == frame["session"].nunique()
    assert ours.engine == "statsmodels.MixedLM"
    assert ours.spec.role == "sensitivity_analysis"


def test_scalar_mixed_model_reports_unestimable_nested_level() -> None:
    frame, table, design, estimand = _unbalanced_nested_fixture()
    first_session = frame.groupby("animal")["session"].transform("first")
    one_session = frame[frame["session"] == first_session]
    table = ObservationTable.from_columns(
        {
            "event_id": one_session["event_id"].tolist(),
            "animal": one_session["animal"].tolist(),
            "session": one_session["session"].tolist(),
            "condition": one_session["condition"].tolist(),
            "outcome": one_session["outcome"].tolist(),
        }
    )

    result = fit_scalar_mixed_model(
        table,
        design,
        estimand,
        ScalarMixedModelSpec(nested_random_intercept_unit="session"),
    )

    assert result.nested_units is None
    assert (
        "nested_random_intercept_not_estimable_one_nested_unit_per_group"
        in result.warnings
    )


def test_frozen_mixed_model_parity_fixture_passes() -> None:
    payload = json.loads(Path("benchmarks/mixed-model-parity-v0.2.json").read_text())
    expected = payload.pop("result_sha256")

    assert (
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == expected
    )
    assert payload["passed"]
    assert {item["name"] for item in payload["scenarios"]} == {
        "unbalanced_events",
        "unbalanced_nested_sessions",
    }
