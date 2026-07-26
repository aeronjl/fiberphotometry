# Control-free bleaching benchmark protocol v0.1

Status: **frozen before aggregate execution** (26 July 2026)

## Purpose

Evaluate initial signal-only baseline estimators for fluorescence bleaching. This
benchmark does not claim that control-free detrending removes motion or other
shared artefacts. A method that estimates slow baseline well may still be invalid
for a particular biological contrast.

## Candidate methods fixed in advance

1. Robust double-exponential baseline: non-negative offset and amplitudes,
   time constants constrained to 5 s–10 recording durations, robust `soft_l1`
   residual loss.
2. Asymmetric least-squares (AsLS) baseline: second-difference penalty
   `lambda=1e8`, asymmetry `p=0.01`, 20 iterations.

Both calculate `(signal - fitted_baseline) / fitted_baseline`, retain the acquired
signal, process finite runs independently, and record complete parameters in
provenance. No reference variable is used.

## Frozen simulations

Each scenario uses 20 seeds, 300 s at 20 Hz and known event-related dF/F:

- `single_exponential`: single exponential bleaching plus Gaussian noise;
- `double_exponential`: fast and slow bleaching components;
- `large_transients`: double exponential bleaching with fivefold transients;
- `slow_drift`: double exponential bleaching plus a slow sinusoidal baseline;
- `motion_without_control`: double exponential bleaching plus an event-independent
  oscillatory multiplicative artefact;
- `event_locked_artifact`: double exponential bleaching plus an event-locked
  fluorescence artefact indistinguishable from neural signal using this channel.

## Metrics and acceptance fixed in advance

Metrics are calculated only where ground truth and estimates are finite:

- Pearson correlation with true neural dF/F;
- RMSE from true neural dF/F;
- median event-amplitude relative bias using 0–1 s response minus -1–0 s baseline.

A method passes a recoverable scenario when the median across seeds has correlation
at least 0.90, RMSE at most 0.015 dF/F, and absolute event-amplitude bias at most
20%. The benchmark as a whole requires at least one candidate to pass each of
`single_exponential`, `double_exponential`, `large_transients`, and `slow_drift`.

`motion_without_control` and `event_locked_artifact` are retained limitation cases,
not acceptance gates. Event-locked artefact is deliberately non-identifiable from
one fluorescence channel; apparent recovery must not be interpreted as validation.

## Reporting rules

- Report all seeds, failures, warnings and aggregate metrics.
- Do not tune parameters after aggregate results are inspected in v0.1.
- Do not select methods by significance tests.
- A future parameter change or new method requires a new protocol version.
- Passing simulations licenses further validation, not automatic use on real data.
