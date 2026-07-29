# SDR-0011: Regularize irregular clocks prospectively

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

AsLS is defined over equally spaced samples, while real IBL photometry timestamps
contain small acquisition jitter. The v0.3.2 analysis correctly retained those
universes as structurally incompatible because no regularization policy had been
declared before outcome access. Silently treating row order as a regular clock or
adding interpolation after seeing effects would obscure a consequential choice.

## Decision

Irregular-clock workflows may explicitly declare linear regularization before a
regular-sampling operation. The prospective default candidate is:

- target rate: reciprocal of the session's median source interval;
- gap boundary: do not interpolate across an interval greater than 1.5 times the
  median source interval;
- original timestamps and values retained on `source_time`;
- Boolean acquisition masks transferred by nearest neighbour and forced false
  inside protected gaps;
- interpolation distance, source jitter, resolved rate, and gap-masked fraction
  recorded in provenance.

Compatibility preflight uses timestamps and the declared operations only. Signal
fidelity benchmarks are a separate outcome-based validation lane.

## Consequences

Adding regularization makes an AsLS pipeline mechanically executable, but does not
make it scientifically validated. Results must identify the interpolation policy,
and robustness reports must distinguish raw-compatible and regularized workflows.
The completed v0.3.2 result is not amended or rerun under this policy.

## Revisit trigger

Revisit before promotion if target-rate inflation is requested, protected gaps
remove material event coverage, interpolation distance approaches the event
timescale, or validation on sharp transients and held-out recordings fails.

## Evidence added later

The checksum-frozen 24-session held-out IBL comparison made AsLS mechanically
executable and retained all 5,920 event windows. Raw-versus-regularized event
deltas were highly stable, but the aggregate protocol failed its strict
whole-trace normalized-RMSE, interpolation-distance, and finite-coverage gates.
Maximum source distance reached 0.525 median samples, and AsLS baseline magnitude
remained materially comparator-dependent despite near-identical short-window event
deltas. Regularization therefore remains explicit and experimental rather than a
silent or recommended default. See the
[held-out report](https://github.com/aeronjl/fiberphotometry/blob/main/research/ibl-regularized-asls-results-v0.1.md).
