# Draft: control-free benchmark v0.2 design

Status: **archived design draft; non-normative**. The normative protocol is now
[`benchmarks/protocol-control-free-v0.2.md`](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-control-free-v0.2.md).

This note captures design reasoning before the v0.2 protocol is frozen. It may
change and must not be read as a package guarantee.

## Questions

1. Can a method recover the known slow baseline independently of high-frequency
   acquisition noise?
2. Does performance remain stable at 10, 20 and 40 Hz?
3. When bleaching affects indicator fluorescence versus additive autofluorescence,
   what quantity is preserved by division and subtraction?
4. Which diagnostics can identify a mismatch without using the hidden truth?

## Proposed changes from v0.1

- Replace the headline full-trace correlation gate with baseline-relative RMSE.
  Retain correlation as descriptive output so the change is visible rather than
  erased.
- Report residual error and event-amplitude bias separately.
- Scale the AsLS second-difference penalty with sampling rate and verify the scaling
  rather than assuming it.
- Expose division and subtraction as distinct output variables and provenance
  records; never label a subtractive result dF/F.
- Retain motion and event-locked artefact as non-identifiability demonstrations.

## Open decisions before freezing

- Exact baseline-error and across-rate stability thresholds.
- Whether early-versus-late event attenuation is the clearest normalization test.
- Whether subtraction should be normalized afterward for comparison or remain in
  acquired-fluorescence units.
- Minimum real-data control required before pipeline promotion.

## Resolution

The frozen protocol selected 1% relative baseline RMSE, 10% event-amplitude bias,
and 0.5 percentage-point across-rate stability thresholds. Subtractive output was
kept in acquired units. SDR-0002 retains the independent real-data-control
requirement; the draft did not resolve what dataset should satisfy it.
