# SDR-0043: Infer transient contrasts at the animal level

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

One recording can contain hundreds of detected transients, but those events do
not constitute independent biological replicates. Treating them as independent
would make confidence depend largely on recording duration and event rate while
understating between-animal variation.

Rates also require an exposure denominator that excludes acquisition gaps.
Kinetic measurements may contain several sessions and many events per animal.

## Decision

Transient inference first produces one estimate per animal and condition.

- Event rate pools count over finite acquired duration within animal-condition.
- Amplitude, width, and AUC are summarized within session and then across
  sessions within animal.
- Paired contrasts require complete animals and resample or swap whole animal
  pairs.
- Independent contrasts require disjoint subjects and resample or shuffle whole
  animal estimates.

The complete animal ledger, session/event counts, exposure, incomplete paired
subjects, seed, and resample counts remain in the result. Difference and ratio
effects are distinct declared scales; ratios require positive animal estimates.

## Alternatives considered

- **Resample detected events.** Rejected because it is pseudoreplication.
- **Average every session equally for rate.** Rejected because sessions have
  different finite exposure; count/exposure pooling preserves the rate estimand.
- **Pool all kinetic events across a condition.** Rejected because animals with
  more sessions or events would dominate the contrast.

## Consequences

The effective sample size is the number of animals, so intervals may be wide.
That accurately represents the design. Session-level kinetic summaries prevent
one high-event session from silently becoming the replication unit.

The API is experimental pending broader calibration and does not replace a
pre-declared generalized count model when that model is scientifically required.

## Revisit trigger

Revisit after validation against pre-declared Poisson/negative-binomial
mixed-effects models across unequal exposure and repeated-session designs.
