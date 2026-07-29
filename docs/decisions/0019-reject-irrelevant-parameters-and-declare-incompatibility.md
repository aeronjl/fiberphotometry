# SDR-0019: Reject irrelevant parameters and declare incompatibility prospectively

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Multiverse scientific contract v0.1](../multiverse-contract.md)

## Context

Signal-only methods expose different scientific assumptions and parameters. A
permissive project schema could silently accept an AsLS parameter on a rolling or
exponential recipe, creating false provenance. Some individually defensible
choices may also form combinations that were never validated together.

## Decision

Validate baseline parameters against the selected method before materialization.
Expose `min_tau_s` for double-exponential fitting; smoothness, asymmetry,
iterations, and reference rate for AsLS; and window and gap factor for rolling
means. Reject irrelevant fields and invalid numeric ranges.

Allow project files to declare prospective incompatibility rules as conjunctions
of named node/alternative choices with a required reason. Require every choice to
exist, reject repeated choices, and preserve the invariant that the reference
workflow is compatible. Retain matched universes and their reasons without
execution or outcome access.

## Consequences

Materialized pipeline provenance contains the actual numerical method policy.
Configuration mistakes fail loudly. Scientists can distinguish “not a defensible
workflow” from execution failure, but they must justify each excluded combination
before viewing its result.

## Alternatives considered

- Accept all baseline fields for every method: rejected because ignored values
  make the configuration misleading.
- Drop incompatible combinations during expansion: rejected because their absence
  would hide the declared boundary and change denominators silently.
- Infer incompatibilities from observed estimates: rejected as outcome-dependent
  specification search.

## Revisit trigger

Add typed compatibility predicates only when a recurring rule cannot be expressed
as named-choice conjunctions. Such predicates must remain outcome-blind and
serialize an explanatory reason.

## Evidence added later

None yet.
