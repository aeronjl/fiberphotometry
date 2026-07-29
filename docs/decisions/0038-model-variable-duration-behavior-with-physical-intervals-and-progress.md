# SDR-0038: Model variable-duration behavior with physical intervals and progress

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related method: [behavioral event-kernel encoding](../event-kernel-encoding.md)

## Context

A behavioral bout has a physical onset, offset, and duration. Converting every bout
to a point event discards its state trajectory, while treating normalized progress
as a complete-case continuous covariate excludes every sample outside the behavior.
Warping raw photometry onto a common bout length can also hide physical timing and
change the noise structure.

The external-behavior boundary already preserves intervals from Keypoint-MoSeq and
BORIS. The encoding model needs to consume that structure without becoming a
behavior-discovery package or claiming that normalized progress is physical time.

## Decision

Add a first-class `ProgressKernelSpec` backed by a typed
`LinearProgressBasisSpec`. Each interval maps its acquired samples to progress in
`[0, 1)`, evaluates a piecewise-linear partition-of-unity basis, and contributes
those predictors only while the bout is active. Samples outside all bouts receive
zeros and remain in the fitting and validation denominator.

Retain the original interval bounds and count. Report the reconstructed trajectory
on an explicit `[0, 1]` evaluation grid together with basis weights and sampled
basis functions. Reconstruct delete-one-group jackknife summaries on that same
grid. Reject missing, out-of-recording, unordered, overlapping, or unsupported
interval families.

Add `BehaviorAnnotations.interval_encoding_inputs()` to produce an internally
aligned bundle of interval-edge events, duration values, and physical bounds. It
does not synchronize clocks; annotations must already use the photometry clock.
Onset and offset remain explicit event choices. Duration enters through the existing typed
event-modulation mechanism (`lag_events=0`); it does not replace the main edge
kernel. Arbitrary per-event amplitude remains caller-supplied and explicitly named.

## Consequences

Scientists can jointly estimate onset/offset transients, duration-dependent edge
responses, and within-bout progress while retaining the complete continuous
recording. A progress coefficient is indexed by dimensionless normalized position,
not seconds. Duration-conditioned and progress models should be named multiverse
alternatives rather than selected after viewing curves.

The linear basis is transparent and low-dimensional but does not assert a preferred
smoothness. Different function counts imply different shape assumptions and ridge
geometry. Physical-time peri-event kernels remain necessary when latency in seconds
is the estimand.

The event-kernel fit artifact advances to schema v7 and stores progress basis,
physical source interval, interval count, reconstructed curve, and grouped
uncertainty.

## Alternatives considered

- **Use the existing progress covariate with an outside-bout missing mask:** rejected
  because complete-case fitting changes the denominator to bout-only time.
- **Fill a continuous progress covariate with zero outside bouts:** rejected because
  zero would ambiguously mean both bout onset and absence of the behavior.
- **Warp and average every bout before modeling:** rejected as a default because it
  discards the continuous-recording prediction target and physical timing.
- **Represent duration only through offset events:** rejected because offset timing
  and duration-dependent amplitude are distinct hypotheses.
- **Allow overlapping intervals of one modeled family:** rejected until an explicit
  additive or priority policy defines their meaning.

## Revisit trigger

Add spline or raised-cosine progress bases after recovery comparisons justify them.
Add explicit overlap policies with interval merge/split/filter rules. Revisit
hierarchical bout-varying trajectories when independent-group validation and an
identifiable estimand are specified.

## Evidence added later

`BehaviorAnnotations` and its `interval_encoding_inputs()` helper moved out of
fipha with the rest of the general behaviour surface and are now
[`behavio.ethograms`](https://aeronjl.github.io/behavio/ethograms/). The bundle
contract described above is unchanged; fipha's encoding models consume it, and
`pip install 'fipha[behavior]'` supplies the package that produces it.
