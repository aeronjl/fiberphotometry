# SDR-0056: Form interactions from animal-condition contrasts

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

A common photometry experiment compares treatment and control animals across two
repeated conditions—for example pre/post, cue A/cue B, or rewarded/unrewarded.
Testing all events in a group-by-condition model without preserving the animal
boundary can make trial yield determine apparent population precision.

The scientific estimand is also easy to obscure. A treatment-control difference in
one condition is not the same question as whether the within-animal condition
difference changes between treatment groups.

## Decision

Represent the interaction as an explicit difference in differences:

1. Materialize one estimate for every animal-condition cell.
2. Within each complete animal, subtract the declared condition denominator from
   the condition numerator.
3. Compare those within-animal differences between two disjoint animal groups.

The outer comparison reuses the independent-group population contract. It therefore
resamples animals separately within group, reports a Welch standard error, retains
pointwise group support, produces pointwise and simultaneous bands, and records
leave-one-animal-out influence.

Group membership is a separate typed assignment and must be constant within animal.
The software never infers groups from filenames, balance, or condition labels.
Animals missing either condition remain in the cell ledger and exclusion list but
do not enter the interaction estimate.

## Consequences

Every included animal has equal population weight regardless of its event count.
The interaction answers whether a within-animal condition contrast differs between
groups. It does not establish a causal treatment effect unless assignment and the
rest of the experimental design justify that interpretation.

The initial contract supports two groups and two repeated conditions. It does not
fit arbitrary factorial models, partial pooling, continuous moderators, or
generalized outcomes.

## Alternatives considered

- **Compare groups separately at each condition.** Rejected because two separate
  tests do not test the interaction.
- **Pool events in a group-by-condition regression.** Rejected as the default
  because lower-level observations would control precision unless the complete
  hierarchical model were declared and validated.
- **Infer group membership from labels.** Rejected because assignment semantics are
  scientific metadata, not a property of the outcome table.

## Revisit trigger

Add richer factorial or hierarchical models only with explicit estimands,
exchangeability rules, missing-cell policies, and simulation coverage across the
designs they claim to support.
