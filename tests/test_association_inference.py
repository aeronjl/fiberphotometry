import numpy as np
import pytest

from fipha.association_inference import (
    AssociationAnimalInferenceSpec,
    AssociationSessionEstimate,
    infer_association_animals,
)


def test_association_inference_aggregates_sessions_before_animals() -> None:
    rng = np.random.default_rng(5)
    sessions = []
    for animal_index in range(8):
        animal_offset = rng.normal(0, 0.03)
        for condition, effect in (("rest", 0.1), ("explore", 0.55)):
            for session_index in range(2):
                sessions.append(
                    AssociationSessionEstimate(
                        f"animal-{animal_index}",
                        f"session-{session_index}",
                        condition,
                        "green__red",
                        "mean_coherence_1_4Hz",
                        effect + animal_offset + rng.normal(0, 0.02),
                        20,
                        "test_fixture",
                    )
                )

    result = infer_association_animals(
        sessions,
        AssociationAnimalInferenceSpec(
            "mean_coherence_1_4Hz",
            "green__red",
            "explore",
            "rest",
            bootstrap_resamples=500,
            permutation_resamples=500,
            seed=11,
        ),
    )

    assert result.estimate == pytest.approx(0.45, abs=0.03)
    assert result.interval_low > 0.4
    assert result.permutation_pvalue < 0.02
    assert len(result.animals_a) == 8
    assert len(result.animal_estimates) == 16
    assert {item.session_count for item in result.animal_estimates} == {2}
    assert {item.total_support for item in result.animal_estimates} == {40}


def test_association_inference_refuses_session_pseudoreplication() -> None:
    duplicate = AssociationSessionEstimate(
        "mouse",
        "session",
        "a",
        "pair",
        "metric",
        0.2,
        10,
        "fixture",
    )
    with pytest.raises(ValueError, match="identities must be unique"):
        infer_association_animals(
            [duplicate, duplicate],
            AssociationAnimalInferenceSpec(
                "metric",
                "pair",
                "a",
                "b",
                bootstrap_resamples=100,
                permutation_resamples=100,
            ),
        )
