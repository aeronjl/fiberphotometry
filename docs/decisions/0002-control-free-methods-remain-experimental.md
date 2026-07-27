# SDR-0002: Keep initial control-free methods experimental

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report:
  [protocol v0.1](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-control-free-v0.1.md),
  [report v0.1](../control-free-benchmark-v0.1.md)

## Context

Robust double-exponential and asymmetric least-squares baselines were implemented
under a frozen 240-run simulation benchmark. Both preserved event amplitudes under
ordinary bleaching and passed the large-transient scenario. Neither passed the
frozen samplewise-correlation gate for small transients. Both failed under motion
without a control, while event-locked artefact produced deceptively high
correlation and roughly 133% event-amplitude inflation.

The correlation failure partly reflects residual acquisition noise rather than
baseline error, revealing a weakness in the v0.1 metric. That does not negate the
artefact failures or justify changing the frozen threshold after execution.

## Decision

Expose both methods as experimental, provenance-recorded APIs. Do not add them to
the recommended typed pipeline or public-data multiverse. Do not describe either
as motion correction. Preserve the failed v0.1 acceptance result unchanged.

Design v0.2 to separate baseline fidelity, residual noise and event-amplitude
recovery; treat subtraction and division as different scientific transformations;
and test sampling-rate dependence.

## Consequences

Advanced users can inspect and test the implementations, while ordinary pipeline
users are not given an unjustified default. Promotion is slower but tied to
explicit evidence. Documentation must clearly label experimental outputs.

## Alternatives considered

- Promote double exponential because it had lower RMSE: rejected because RMSE did
  not detect event-locked non-identifiability and normalization assumptions remain.
- Remove both APIs: rejected because transparent experimental access supports
  validation and comparison.
- Relax the v0.1 correlation criterion retrospectively: rejected because it would
  compromise the frozen benchmark; metric revision belongs in v0.2.

## Revisit trigger

Reconsider promotion after v0.2 passes its frozen baseline, normalization and
sampling-rate criteria and after at least one real dataset with an independent
control supports the simulation conclusions.

## Evidence added later

The frozen v0.2 benchmark passed all baseline-fidelity, sampling-rate and matched
normalization gates. Double exponential passed exponential scenarios; AsLS also
passed slow drift after rate-aware penalty scaling. SDR-0002 still requires
real-data validation with an independent control before typed-pipeline promotion.
See the [v0.2 report](../control-free-benchmark-v0.2.md).

The subsequently frozen DANDI:000971 independent-control pilot passed all
engineering gates and the median relative-RMSE gate for both methods, but failed
the slow-trend-correlation gate (double exponential 0.259; AsLS 0.713, against a
0.90 threshold). Four animals and eight region-level cases are an assumption audit,
not population validation; the isosbestic comparator is not ground truth. The
mixed result therefore satisfies the real-data revisit trigger but does not justify
promotion. See the [pilot report](../dandi-000971-control-v0.1.md).

The later 24-session held-out IBL comparison executed regularized AsLS everywhere
and retained all selected event windows, but failed its prospective whole-trace
fidelity and coverage gate. AsLS-versus-comparator event deltas were very similar
while fitted baselines differed materially, demonstrating estimand-specific
agreement rather than baseline identifiability. This reinforces the experimental,
non-default status. See the
[held-out regularization report](../ibl-regularized-asls-results-v0.1.md).
