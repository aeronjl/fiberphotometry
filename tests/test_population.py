import json

import numpy as np
import pytest

from fiberphotometry.population import (
    PopulationContrastSpec,
    PopulationGroupAssignment,
    PopulationInteractionSpec,
    PopulationUnitEstimate,
    infer_population_contrast,
    infer_population_interaction,
)


def _unit(
    unit_id: str, level: str, values: tuple[float, ...]
) -> PopulationUnitEstimate:
    return PopulationUnitEstimate(
        unit_id=unit_id,
        level=level,
        estimate=values,
        support=(2,) * len(values),
        source_units=(f"{unit_id}:s1", f"{unit_id}:s2"),
        observation_count=12,
    )


def test_paired_population_contrast_retains_units_and_influence() -> None:
    estimates = tuple(
        item
        for index, difference in enumerate((0.2, 0.3, 0.4, 0.9))
        for item in (
            _unit(f"a{index}", "control", (0.0, 0.1)),
            _unit(f"a{index}", "stimulus", (difference, difference + 0.1)),
        )
    )

    result = infer_population_contrast(
        estimates,
        PopulationContrastSpec(
            numerator="stimulus",
            denominator="control",
            design="paired",
            draws=200,
            seed=7,
        ),
    )

    assert result.estimate == pytest.approx((0.45, 0.45))
    assert result.included_units == ("a0", "a1", "a2", "a3")
    assert result.excluded_units == ()
    assert len(result.unit_estimates) == 8
    assert len(result.influence) == 4
    assert (
        max(result.influence, key=lambda item: item.maximum_absolute_change).unit_id
        == "a3"
    )
    assert np.all(np.asarray(result.standardized_effect) > 0)
    payload = json.loads(result.to_json())
    assert payload["effect_size_method"] == "hedges_gz_paired"
    assert payload["spec"]["schema_version"] == "1"


def test_paired_population_contrast_reports_incomplete_units() -> None:
    estimates = (
        _unit("a", "control", (0.0,)),
        _unit("a", "stimulus", (0.2,)),
        _unit("b", "control", (0.0,)),
        _unit("b", "stimulus", (0.4,)),
        _unit("c", "stimulus", (0.8,)),
    )

    result = infer_population_contrast(
        estimates,
        PopulationContrastSpec(
            numerator="stimulus",
            denominator="control",
            design="paired",
            draws=100,
        ),
    )

    assert result.included_units == ("a", "b")
    assert result.excluded_units == ("c",)
    assert "incomplete_paired_units_excluded" in result.warnings


def test_independent_population_contrast_resamples_disjoint_groups() -> None:
    estimates = tuple(
        [
            _unit("control-1", "control", (0.0, 0.1)),
            _unit("control-2", "control", (0.1, 0.0)),
            _unit("control-3", "control", (-0.1, 0.1)),
            _unit("drug-1", "drug", (0.8, 0.9)),
            _unit("drug-2", "drug", (0.9, 0.8)),
            _unit("drug-3", "drug", (0.7, 0.9)),
        ]
    )

    result = infer_population_contrast(
        estimates,
        PopulationContrastSpec(
            numerator="drug",
            denominator="control",
            design="independent",
            draws=200,
            seed=3,
        ),
    )

    assert result.design == "independent"
    assert result.estimate == pytest.approx((0.8, 0.8))
    assert result.numerator_units_per_point == (3, 3)
    assert result.denominator_units_per_point == (3, 3)
    assert len(result.influence) == 6
    assert result.effect_size_method == "hedges_g_independent_pooled_sd"


def test_independent_population_contrast_rejects_overlapping_units() -> None:
    estimates = (
        _unit("a", "control", (0.0,)),
        _unit("a", "drug", (0.4,)),
        _unit("b", "control", (0.1,)),
        _unit("c", "drug", (0.5,)),
    )

    with pytest.raises(ValueError, match="cannot share units"):
        infer_population_contrast(
            estimates,
            PopulationContrastSpec(
                numerator="drug",
                denominator="control",
                design="independent",
                draws=100,
            ),
        )


def test_population_unit_estimate_validates_its_audit_shape() -> None:
    with pytest.raises(ValueError, match="share a shape"):
        PopulationUnitEstimate(
            unit_id="animal",
            level="condition",
            estimate=(0.2, 0.3),
            support=(1,),
            source_units=("session",),
            observation_count=2,
        )


def test_population_interaction_contrasts_within_unit_differences_between_groups() -> (
    None
):
    estimates = []
    assignments = []
    for group, differences in (("control", (0.1, 0.2, 0.3)), ("drug", (0.7, 0.8, 0.9))):
        for index, difference in enumerate(differences):
            animal = f"{group}-{index}"
            assignments.append(PopulationGroupAssignment(animal, group))
            estimates.extend(
                (
                    _unit(animal, "pre", (0.2, 0.3)),
                    _unit(animal, "post", (0.2 + difference, 0.3 + difference)),
                )
            )
    spec = PopulationInteractionSpec(
        group_numerator="drug",
        group_denominator="control",
        condition_numerator="post",
        condition_denominator="pre",
        draws=200,
        seed=4,
    )

    result = infer_population_interaction(tuple(estimates), tuple(assignments), spec)

    assert result.population.estimate == pytest.approx((0.6, 0.6))
    assert len(result.within_unit_contrasts) == 6
    assert result.excluded_units == ()
    assert result.population.spec.design == "independent"
    assert result.population.effect_size_method == "hedges_g_independent_pooled_sd"
    assert json.loads(result.to_json())["spec"]["condition_factor"] == "condition"


def test_population_interaction_retains_incomplete_condition_units() -> None:
    estimates = (
        _unit("control-a", "pre", (0.0,)),
        _unit("control-a", "post", (0.1,)),
        _unit("control-b", "pre", (0.0,)),
        _unit("control-b", "post", (0.2,)),
        _unit("drug-a", "pre", (0.0,)),
        _unit("drug-a", "post", (0.7,)),
        _unit("drug-b", "pre", (0.0,)),
        _unit("drug-b", "post", (0.8,)),
        _unit("drug-incomplete", "post", (0.9,)),
    )
    assignments = tuple(
        PopulationGroupAssignment(
            item,
            "control" if item.startswith("control") else "drug",
        )
        for item in ("control-a", "control-b", "drug-a", "drug-b", "drug-incomplete")
    )

    result = infer_population_interaction(
        estimates,
        assignments,
        PopulationInteractionSpec("drug", "control", "post", "pre", draws=100),
    )

    assert result.excluded_units == ("drug-incomplete",)
    assert "incomplete_condition_units_excluded" in result.warnings
    assert "drug-incomplete" not in result.population.included_units


def test_population_interaction_requires_explicit_unique_group_assignments() -> None:
    estimates = (_unit("a", "pre", (0.0,)), _unit("a", "post", (0.2,)))
    spec = PopulationInteractionSpec("drug", "control", "post", "pre", draws=100)

    with pytest.raises(ValueError, match="unique units"):
        infer_population_interaction(
            estimates,
            (
                PopulationGroupAssignment("a", "drug"),
                PopulationGroupAssignment("a", "control"),
            ),
            spec,
        )
    with pytest.raises(ValueError, match="missing group assignments"):
        infer_population_interaction(estimates, (), spec)


@pytest.mark.parametrize("design", ["paired", "independent"])
def test_scalar_population_band_has_gaussian_small_sample_coverage(
    design: str,
) -> None:
    rng = np.random.default_rng(42)
    true_effect = 0.4
    covered = 0
    scenario_count = 80
    for scenario in range(scenario_count):
        estimates = []
        if design == "paired":
            for index in range(10):
                baseline = rng.normal(0, 0.5)
                difference = rng.normal(true_effect, 0.35)
                estimates.extend(
                    (
                        _unit(f"a{index}", "control", (baseline,)),
                        _unit(f"a{index}", "drug", (baseline + difference,)),
                    )
                )
        else:
            for index in range(10):
                estimates.append(
                    _unit(f"control-{index}", "control", (rng.normal(0, 0.35),))
                )
                estimates.append(
                    _unit(
                        f"drug-{index}",
                        "drug",
                        (rng.normal(true_effect, 0.35),),
                    )
                )
        result = infer_population_contrast(
            tuple(estimates),
            PopulationContrastSpec(
                numerator="drug",
                denominator="control",
                design=design,  # type: ignore[arg-type]
                draws=200,
                seed=scenario,
            ),
        )
        covered += (
            result.simultaneous_lower[0] <= true_effect <= result.simultaneous_upper[0]
        )

    assert covered / scenario_count >= 0.88


def test_population_interaction_band_has_gaussian_small_sample_coverage() -> None:
    rng = np.random.default_rng(731)
    true_interaction = 0.4
    covered = 0
    scenario_count = 60
    for scenario in range(scenario_count):
        estimates = []
        assignments = []
        for group, group_effect in (("control", 0.1), ("drug", 0.5)):
            for index in range(9):
                animal = f"{group}-{index}"
                baseline = rng.normal(0, 0.45)
                difference = rng.normal(group_effect, 0.3)
                assignments.append(PopulationGroupAssignment(animal, group))
                estimates.extend(
                    (
                        _unit(animal, "pre", (baseline,)),
                        _unit(animal, "post", (baseline + difference,)),
                    )
                )
        result = infer_population_interaction(
            tuple(estimates),
            tuple(assignments),
            PopulationInteractionSpec(
                "drug",
                "control",
                "post",
                "pre",
                draws=200,
                seed=scenario,
            ),
        )
        covered += (
            result.population.simultaneous_lower[0]
            <= true_interaction
            <= result.population.simultaneous_upper[0]
        )

    assert covered / scenario_count >= 0.88
