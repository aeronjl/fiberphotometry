# SDR-0048: Freeze transient thresholds and retain waveform QC

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Spontaneous-event counts can change materially when thresholds are estimated from the
same outcome recording in which events are counted. Session-specific noise, treatment
effects, bleaching, and true signal prevalence can all alter an adaptive threshold.
That makes it difficult to tell whether a condition difference reflects events or a
changed selection rule.

Candidate kinetics also become unreliable near recording boundaries, acquisition
gaps, detector rails, digitized plateaus, and neighboring events. Silently dropping
those cutouts conceals the denominator; interpolating across a gap invents a waveform.

## Decision

Control/baseline threshold calibration, outcome detection, waveform QC, and kinetic
quantification remain separate typed operations.

- Calibration consumes explicitly identified baseline or negative-control evidence,
  never outcome samples supplied to the later detection call.
- Candidate-like scores are computed separately within uninterrupted acquisition
  runs. The estimator is either a declared median-plus-MAD rule or an empirical
  quantile; the package does not select between them automatically.
- Frozen thresholds are channel-specific and bound to the exact detector spec,
  variable, ordered channels, source identity/role, preprocessing fingerprint,
  estimator, sample denominator, and source bytes.
- A frozen threshold is an additional detector-score gate. It does not replace the
  named detector family's native candidate rule.
- Every rejected local maximum retains its observed and required scores.
- Waveform cuts contain native timestamps and values only. Recording boundaries,
  missing acquisition, and large timestamp gaps truncate the cut rather than being
  bridged or interpolated.
- Every candidate retains waveform coverage, baseline, flat-step, detector-rail,
  neighboring-event, issue, and pass/warning/fail evidence.
- Quantification may prospectively require waveform QC. Refused candidates remain in
  the quantification exclusion ledger; warnings may be allowed or refused explicitly.

## Alternatives considered

- **Re-estimate a threshold in every outcome session.** Rejected as the only product
  route because the event prevalence and condition can change their own selection
  rule. It remains a named sensitivity alternative when declared prospectively.
- **Pool control and outcome recordings before calibration.** Rejected because outcome
  samples would influence the gate used to select those outcomes.
- **Replace each detector's threshold with one generic frozen number.** Rejected
  because PASTa amplitude, GuPPY amplitude, and z-prominence are different score
  contracts. The detector specification remains binding.
- **Interpolate every cutout onto a common grid.** Rejected as a default because gaps
  and irregular sampling would be hidden. Padded export preserves native relative
  times and an explicit presence mask.
- **Delete failed cutouts before returning results.** Rejected because users could no
  longer audit candidate and denominator attrition.
- **Automatically reject all compound events.** Rejected because overlap changes
  isolation, but does not by itself establish that either candidate is invalid.

## Consequences

Scientists must construct and identify calibration evidence and retain its preprocessing
identity. Threshold transfer is intentionally strict: changed detector parameters or
channel layouts require a new calibration. Some studies have no defensible independent
source, in which case session-adaptive thresholds must remain an explicit alternative
rather than being described as frozen.

Native cutouts are ragged and therefore less convenient than silently resampled matrices.
The xarray view pads them for plotting but preserves per-event relative time. QC can
reduce the quantified denominator, so both waveform statuses and quantification
exclusions must accompany event summaries.

## Revisit trigger

Revisit after manual annotations and raw optical controls across at least two sensors
and acquisition systems establish how calibration sources and waveform metrics relate
to false positives, missed events, and kinetic error. Revisit common-grid export only
with an explicit gap-safe resampling contract and numerical fidelity tests.
