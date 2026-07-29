# Group-by-condition animal interactions v0.1

Use this workflow when two independent groups of animals each contribute repeated
measurements in two conditions. The estimand is a difference in differences, not a
pair of unrelated group comparisons.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/population-interaction-boundary.svg" alt="Treatment and control animals each form a within-animal condition A minus condition B contrast before those animal contrasts are compared between disjoint groups.">
  <figcaption><strong>The condition difference is formed inside each animal before groups are compared.</strong> Events and sessions determine each animal-condition estimate but never become population replicates.</figcaption>
</figure>

## Estimand

For group $g$, condition $c$, and animal $i$, let
$\widehat{\mu}_{igc}(t)$ be the materialized animal estimate. The interaction is

\[
\widehat{\Delta}_{\mathrm{interaction}}(t)
=
\operatorname{mean}_{i \in G_1}
\left[\widehat{\mu}_{iG_1C_1}(t)-\widehat{\mu}_{iG_1C_0}(t)\right]
-
\operatorname{mean}_{i \in G_0}
\left[\widehat{\mu}_{iG_0C_1}(t)-\widehat{\mu}_{iG_0C_0}(t)\right].
\]

The order is fixed by `group_numerator`, `group_denominator`,
`condition_numerator`, and `condition_denominator`. Reversing either contrast
changes the sign and therefore creates a different estimand.

## Typed population API

`PopulationUnitEstimate.level` names the repeated condition. Group membership is a
separate `PopulationGroupAssignment`, which prevents condition and assignment
semantics from being compressed into one label.

```python
from fiberphotometry.population import (
    PopulationGroupAssignment,
    PopulationInteractionSpec,
    infer_population_interaction,
)

spec = PopulationInteractionSpec(
    group_numerator="drug",
    group_denominator="control",
    condition_numerator="post",
    condition_denominator="pre",
    group_factor="treatment",
    condition_factor="phase",
    draws=2_000,
    seed=7,
)

result = infer_population_interaction(animal_condition_estimates, groups, spec)
```

The result retains:

- the complete supplied animal-condition cell ledger;
- explicit animal-to-group assignments;
- one within-animal condition contrast for every complete animal;
- animals excluded because either condition is absent; and
- the complete independent-group population result, including standardized effect,
  group support, simultaneous bands, and leave-one-animal-out influence.

## Peri-event curves

`infer_peri_event_interaction()` accepts event-by-time values plus animal, session,
group, and condition labels. It first stores session-condition curves, averages
sessions equally within animal-condition, forms each animal's condition contrast,
and only then compares groups.

Duplicating events changes recorded event counts but cannot narrow the population
standard error or confidence bands. An animal whose group label changes across
events is rejected rather than silently split between groups.

## Interpretation boundary

- This tests an interaction. A significant comparison in one group and a
  nonsignificant comparison in another is not a substitute.
- The population sample size is the number of complete animals in each group.
- Pointwise intervals describe individual outcome points; simultaneous bands cover
  the declared full vector or time window.
- Hedges *g* standardizes the between-group difference of animal condition
  contrasts. The primary effect remains in the original measurement units.
- Causal language additionally requires justified treatment assignment, timing,
  exclusions, and interference assumptions.

## Current boundary

Version 0.1 supports exactly two disjoint groups and two repeated conditions.
Factorial designs with more levels, continuous moderators, incomplete-cell models,
crossed effects, and functional mixed models remain gaps. Missing cells are visible
but are not imputed.
