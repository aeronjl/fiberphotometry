from test_t_inference import paired_table

from fiberphotometry import recommend_inference


def test_router_requires_randomization_claim_for_exact_test() -> None:
    table, design, estimand = paired_table()

    unknown = recommend_inference(table, design, estimand, randomized=None)
    randomized = recommend_inference(table, design, estimand, randomized=True)

    assert unknown.primary == "paired_t"
    assert unknown.warnings == ("randomization_status_unspecified",)
    assert randomized.primary == "exact_sign_flip"


def test_router_recommends_welch_for_observational_between_unit_factor() -> None:
    table, design, estimand = paired_table(between=True)

    result = recommend_inference(table, design, estimand, randomized=False)

    assert result.primary == "welch_t"
