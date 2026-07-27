# SDR-0040: Keep simultaneous kernel bands opt-in after failed calibration

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related evidence: [event-kernel interval calibration v0.1](../event-kernel-interval-calibration-v0.1.md)

## Context

Pointwise grouped-jackknife intervals do not control error across a complete event
or progress curve. A Gaussian-multiplier maximum over jackknife pseudo-curves can
retain cross-lag dependence and form one whole-model critical value, but its
finite-group behavior is not guaranteed for photometry designs.

The prespecified v0.1 benchmark ran 80 studies in each of six scenarios. All 480
fits succeeded. Marginal pointwise coverage ranged from 93.8% to 96.0%. Candidate
whole-family simultaneous coverage exceeded the frozen 85% minimum in five
scenarios but reached only 82.5% for six-animal normalized-progress kernels.

## Decision

Do not make simultaneous event-kernel bands the default and do not mark the
roadmap calibration milestone complete. Preserve `KernelUncertaintySpec` as the
default pointwise-only policy.

Retain the complete failed benchmark and expose the candidate only through the
distinct `MultiplierSimultaneousBandSpec` opt-in type. When explicitly requested,
store nullable simultaneous bounds together with method, family size, multiplier
draws, seed, critical value, group identities, and selected ridge penalty. Define
the family as every evaluated position from every event and progress kernel in the
model. Never silently narrow it to one selected curve.

Continue to label both pointwise and candidate simultaneous outputs as conditional
sensitivity summaries. They do not account for selective model construction or
establish causal, representational, or zero-exclusion claims.

## Consequences

Scientists receive no stronger default guarantee after a failed gate. Method
developers can reproduce and improve the candidate without maintaining an
untracked fork. Serialized default results use `null` for simultaneous metadata
and bounds, while explicit candidate results are self-describing and seeded.

The event-kernel result schema advances to v8 because interval records and grouped
uncertainty now distinguish unavailable from explicitly requested simultaneous
output.

## Alternatives considered

- **Lower the frozen gate to 80%:** rejected as outcome-dependent thresholding.
- **Promote because five of six scenarios passed:** rejected because the protocol
  required every declared scenario and progress kernels are a first-class feature.
- **Delete the candidate implementation:** rejected because a typed opt-in supports
  exact reproduction and method development while preserving the failed status.
- **Always serialize candidate bands with a warning:** rejected because default
  availability would still imply a promotion that the benchmark did not earn.
- **Exclude progress points from the family:** rejected because that changes the
  scientific claim after observing the failing scenario.

## Revisit trigger

Freeze a v0.2 protocol before new aggregate execution. It must target the
normalized-progress failure, add heterogeneous progress curves, retain a
whole-model family, and use independent seeds. Promotion still requires every
prespecified scenario to pass.

## Evidence added later

None.
