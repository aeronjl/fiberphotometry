# SDR-0004: Require explicit alignment for externally derived data

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report:
  [DANDI:000351 v0.1](../dandi-000351-parity-v0.1.md),
  [DANDI:000351 v0.2](../dandi-000351-parity-v0.2.md)

## Context

Four DANDI:000351 assets stored raw 405/470-nm fluorescence beside archived dF/F,
but none supported direct sample alignment. Two had clock drift despite equal
lengths; two stored different raw and derived sampling rates. Explicit timestamp
interpolation enabled comparison but simple OLS and IRLS reconstructions both
failed frozen exact-parity gates.

## Decision

Treat externally archived processed series as derived data with their own timebase
and provenance. Require an explicit, recorded alignment policy before comparison
with raw or newly processed data. Never infer index alignment solely from equal
lengths, silently interpolate, or describe approximate agreement as reproduction.
An archived output is an interoperability target, not scientific ground truth.

## Consequences

Adapters may reject apparently convenient datasets until callers choose an
alignment policy. Benchmark protocols must state interpolation, extrapolation,
finite-sample, and clock-tolerance rules. This adds work but makes cross-tool
comparisons auditable and prevents timing assumptions from being hidden.

## Alternatives considered

- Assume equal indices correspond when lengths match: rejected because recorded
  clocks drifted within sessions.
- Always interpolate automatically: rejected because interpolation is a scientific
  and numerical choice that can alter event-scale signals.
- Ignore archived series after parity failure: rejected because they remain useful
  as explicitly labelled external comparators and robustness inputs.

## Revisit trigger

Reconsider default alignment only after stable NWB conventions encode transformation
provenance and clock relationships sufficiently to make the policy unambiguous.

## Evidence added later

None.
