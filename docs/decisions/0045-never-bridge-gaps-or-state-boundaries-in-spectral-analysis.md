# SDR-0045: Never bridge gaps or state boundaries in spectral analysis

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

Autocorrelation, Welch PSD, and spectrogram implementations commonly assume a
regular, uninterrupted series. Photometry recordings can contain non-finite
samples, acquisition pauses, explicitly invalid regions, and externally supplied
behavioral or physiological state boundaries. Compressing time or padding across
those regions manufactures pairs and windows that were never observed.

Irregular timestamps pose a different problem: Fourier frequency bins assume a
regular sampling interval. Silently substituting a median sampling rate hides that
model mismatch. State labels add another boundary because joining separate bouts
can treat an unobserved transition as within-state continuity.

## Decision

Single-signal time/frequency methods operate on explicit continuity runs.

- Non-finite values, caller validity masks, and timestamp gaps split runs.
- Within-run interval variation above a declared tolerance is refused, with
  prospective resampling remaining a separate auditable operation.
- Autocorrelation pairs never cross a run or state-epoch boundary and retain their
  denominator at every lag.
- Welch PSDs use a common complete window within each run and aggregate run spectra
  in proportion to complete window count.
- Spectrograms emit complete windows only, without implicit edge padding, and
  retain window bounds, run identity, and distances to both run edges.
- State labels are supplied by the user. Overlap is refused in v0.1, and separate
  epochs remain separate even when labels match or bounds touch.
- State band-power inference aggregates sessions within animals and resamples or
  sign-flips animals rather than windows, epochs, or sessions.

## Alternatives considered

- **Compress away invalid timestamps.** Rejected because it creates false temporal
  adjacency and changes lags and frequencies.
- **Interpolate every gap automatically.** Rejected because allowable gap size and
  interpolation assumptions are analysis choices that can create oscillations.
- **Use a Lomb-Scargle estimate for all inputs.** Deferred because it changes the
  estimand and does not solve missingness, state boundaries, or autocorrelation.
- **Zero-pad edge and gap windows.** Rejected as a default because padding changes
  local power and disguises unequal edge support.
- **Concatenate bouts carrying the same state.** Rejected because the concatenation
  introduces artificial pairs and time-frequency transitions.

## Consequences

Short runs can contribute no spectral windows and remain visible as exclusions.
Long-lag autocorrelation support declines transparently. Spectrograms may have
fewer columns than padding-based tools. Analysts must choose an explicit resampling
operation for clocks that fail regularity rather than receiving a plausible but
mis-specified spectrum.

The default gap and regularity tolerances are product defaults, not empirically
validated universal thresholds. Window duration, overlap, detrending, and band
definitions remain declared sensitivity choices.

## Revisit trigger

Revisit after validation against two long-duration public photometry datasets with
independently documented acquisition gaps and state annotations, or when an
irregular-sampling estimator can be added with a distinct typed estimand and
cross-method validation.
