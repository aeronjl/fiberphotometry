# Frozen multiverse-engine benchmark protocol v0.9

**Frozen:** 2026-07-26 before aggregate benchmark execution.

## Engine criteria

- Cartesian expansion produces every valid combination exactly once.
- Stable universe identifiers repeat across executions.
- A declared incompatible combination is retained with its reason and not run.
- A deliberately invalid operation is retained as a failed universe.
- QC-blocked universes remain distinct from execution failures.
- The reference universe is identified explicitly.
- Decision summaries use effect estimates rather than significance counts.

## Scientific scenarios

Run the same small preprocessing multiverse on simulated multi-animal data under:

1. a stable positive event effect;
2. a true null;
3. an event-correlated reference contaminant that makes at least one reference
   correction family fragile;
4. one influential animal.

The benchmark records estimate ranges, directional and practical-effect
fractions, failures, exclusions, and reference leave-one-animal-out estimates.
It tests whether fragility is exposed, not whether one method wins. All criteria
and scenario outcomes are retained whether they pass or fail.
