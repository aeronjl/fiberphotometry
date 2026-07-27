# SDR-0003: Represent subtraction and division as different transformations

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report:
  [protocol v0.2](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-control-free-v0.2.md),
  [report v0.2](../control-free-benchmark-v0.2.md)

## Context

Bleaching can affect indicator fluorescence, additive autofluorescence, or both.
Division assumes the estimated baseline scales physiological amplitude and yields a
fractional dF/F quantity. Subtraction assumes an additive baseline and retains
acquired-fluorescence units. Calling both outputs dF/F would conceal incompatible
generative assumptions.

The frozen v0.2 simulation found that division preserved early-to-late response
amplitude under indicator bleaching (-0.2% change), while subtraction attenuated it
by 25.9%. Under additive autofluorescence bleaching, subtraction was stable (-0.4%)
while division inflated late responses by 34.4%.

## Decision

Require callers to choose `divide` or `subtract`. Divisive output is named `dff`;
subtractive output is named `baseline_subtracted` and remains in acquired
fluorescence units. Store the choice and formula in provenance. Do not silently
normalize a subtractive result afterward or present either choice as universally
correct.

## Consequences

Downstream pipelines must acknowledge the transformation and cannot accidentally
pool unlike units. Users need biological or acquisition evidence to choose. Some
existing tools use “dF/F” more loosely, so interoperability documentation must make
the semantic difference explicit.

## Alternatives considered

- Always divide: rejected because additive autofluorescence creates time-varying
  fractional scaling.
- Always subtract: rejected because indicator bleaching attenuates physiological
  amplitude in acquired units.
- Return both under generic names: rejected because it encourages opportunistic
  selection and unit confusion.

## Revisit trigger

Revisit if an independently validated generative model can estimate indicator and
autofluorescence components jointly, or if acquisition metadata provides those
components directly.

## Evidence added later

None.
