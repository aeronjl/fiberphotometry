import pytest
from test_t_inference import paired_table

from fipha.planning import (
    AnalysisPlan,
    create_analysis_plan,
    execute_analysis_plan,
    welch_power_sensitivity,
)


def test_analysis_plan_requires_acknowledgements() -> None:
    table, design, estimand = paired_table()
    draft = create_analysis_plan(
        table, design, estimand, randomized=True, intent="confirmatory"
    )
    ready = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=True,
        intent="confirmatory",
        acknowledged_assumptions=draft.required_assumptions,
    )

    assert not draft.executable
    assert ready.executable
    assert '"schema_version": "1"' in ready.to_json()
    assert type(ready).from_json(ready.to_json()) == ready
    assert execute_analysis_plan(ready, table, design).engine == "exact"
    result = execute_analysis_plan(ready, table, design)
    assert len(result.input_fingerprint) == 64
    assert result.package_version


def test_power_sensitivity_exposes_pilot_uncertainty() -> None:
    result = welch_power_sensitivity(
        animals_per_condition=20,
        effect_range=(0.5, 0.8),
        animal_sd_range=(0.8, 1.2),
    )

    assert 0 < result.minimum_power < result.maximum_power < 1


def test_monte_carlo_plan_records_and_reuses_seed() -> None:
    table, design, estimand = paired_table()
    assumptions = (
        "independent_aggregation_units",
        "estimand_matches_question",
        "exchangeability_under_null",
        "randomization_mechanism_correct",
    )
    plan = AnalysisPlan(
        estimand,
        "monte_carlo_sign_flip",
        assumptions,
        assumptions,
        True,
        "confirmatory",
        seed=8675309,
    )

    first = execute_analysis_plan(plan, table, design)
    second = execute_analysis_plan(plan, table, design)

    assert first.random_seed == 8675309
    assert first.estimate == second.estimate
    assert first.p_value == second.p_value


def test_monte_carlo_plan_rejects_missing_seed() -> None:
    table, design, estimand = paired_table()
    plan = AnalysisPlan(
        estimand,
        "monte_carlo_sign_flip",
        (),
        (),
        True,
        "exploratory",
    )

    with pytest.raises(ValueError, match="recorded seed"):
        execute_analysis_plan(plan, table, design)


def test_assignment_unit_permutation_plan_executes() -> None:
    table, design, estimand = paired_table(between=True)
    draft = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=True,
        intent="confirmatory",
        seed=42,
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=True,
        intent="confirmatory",
        acknowledged_assumptions=draft.required_assumptions,
        seed=42,
    )

    result = execute_analysis_plan(plan, table, design)

    assert plan.method == "assignment_unit_permutation"
    assert result.engine == "numpy-monte-carlo"
    assert result.random_seed == 42
