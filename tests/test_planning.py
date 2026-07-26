from test_t_inference import paired_table

from fiberphotometry import create_analysis_plan, welch_power_sensitivity


def test_analysis_plan_requires_acknowledgements() -> None:
    table, design, estimand = paired_table()
    draft = create_analysis_plan(table, design, estimand, randomized=True)
    ready = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=True,
        acknowledged_assumptions=draft.required_assumptions,
    )

    assert not draft.executable
    assert ready.executable
    assert '"schema_version": "1"' in ready.to_json()


def test_power_sensitivity_exposes_pilot_uncertainty() -> None:
    result = welch_power_sensitivity(
        animals_per_condition=20,
        effect_range=(0.5, 0.8),
        animal_sd_range=(0.8, 1.2),
    )

    assert 0 < result.minimum_power < result.maximum_power < 1
