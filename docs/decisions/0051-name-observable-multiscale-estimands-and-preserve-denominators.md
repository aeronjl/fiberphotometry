# SDR-0051: Name observable multiscale estimands and preserve denominators

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Long photometry recordings are commonly described using terms such as tonic,
phasic, baseline, drift, state, and transient. Windowing a processed signal at a
longer duration does not identify any of those biological processes. Yet
scientists still need to describe location, spread, magnitude, and trend over
several physical-time scales, tolerate irregular observations, retain gaps, and
compare declared summaries across animals.

Naive rolling functions hide several consequential choices: sample versus time
weighting, incomplete edge windows, minimum coverage, acquisition gaps, state
boundaries, overlap, and the experimental unit used for uncertainty.

## Decision

FiberPhotometry provides typed, observable multiscale summaries with a complete
acceptance ledger.

- Every scale has a name, physical duration, physical step, minimum temporal
  coverage, and minimum sample count.
- A recording is split at caller-invalid or non-finite samples, declared timestamp
  gaps, and each user-supplied state epoch boundary.
- Candidate windows have a fixed requested duration. Their observed duration,
  coverage, sample count, acceptance, and exclusion reason remain in the result.
- Metric names declare sample weighting or physical-time trapezoidal weighting.
  Time integration interpolates only between adjacent observations inside one
  continuity run.
- Results retain state and epoch identity but never infer a state or biological
  tonic/phasic label.
- Condition inference aggregates windows within sessions and sessions within
  animals. Resampling and randomization operate on animals; overlap never creates
  extra experimental units.
- The effect direction is explicit: condition B minus A, or B divided by A.
- Inputs, validity, epochs, units, and the full specification are bound by a
  deterministic evidence fingerprint.

## Alternatives considered

- **Call long windows tonic and short windows phasic.** Rejected because window
  duration does not identify a biological generator.
- **Expose a generic rolling dataframe.** Rejected because missingness, boundaries,
  units, and acceptance evidence would become caller conventions.
- **Require regular resampling first.** Rejected for location and spread summaries:
  physical-time trapezoidal integration has a clear irregular-clock estimand and
  avoids an unnecessary interpolation step. Fourier analyses retain their separate
  regular-clock requirement.
- **Shorten edge windows and divide by their shorter duration.** Rejected as a
  default because nominally equal rows would then represent different scales.
- **Pool all windows for inference.** Rejected because autocorrelation and overlap
  do not turn windows into independent animals.
- **Choose one universal set of durations.** Rejected because sensor kinetics,
  behavior, acquisition length, and the scientific question differ across studies.

## Consequences

Scientists must name scales and weighting choices instead of receiving implicit
defaults. Some edge windows and short state bouts will be rejected, but their lost
support is visible. Time- and sample-weighted estimates can legitimately disagree
under irregular sampling. Overlapping windows can improve descriptive resolution
without increasing animal-level degrees of freedom.

These summaries remain sensitive to preprocessing and optical validity. The
contract enables multiverse comparison of reasonable scales, but it does not
validate a scale as a neural mechanism.

## Revisit trigger

Revisit after raw-signal validation across at least two sensors and acquisition
systems with external long-duration annotations, or when a sensor-specific forward
model supports a separately named latent-state or kinetic estimand.
