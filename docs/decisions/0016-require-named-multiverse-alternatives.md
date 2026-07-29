# SDR-0016: Require named, justified multiverse alternatives

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Configuration-first CLI v0.1](../cli.md)

## Context

The typed Python API can already materialize and execute robustness multiverses,
but scientists cannot declare them in a project file. A compact array of parameter
values would be convenient, yet it would obscure why each workflow is defensible,
make reference-workflow selection implicit, and become brittle as recipes gain
ordered operations or method-specific fields.

## Decision

Represent each project-level multiverse choice as a uniquely named alternative
with a required scientific rationale and typed value. Require an explicit reference
alternative for every decision node. Materialize stable universe identifiers and
assess structural compatibility during outcome-blind inspection before execution.

The first schema exposes complete reference-correction recipes and response-window
definitions. It holds the estimand, design, baseline, and inference plan fixed.
Incompatible pipelines block project execution before fluorescence outcomes are
accessed; executable failures remain distinct outcomes of the multiverse engine.

## Consequences

Project files are longer than parameter grids, but reports can identify choices in
scientific language and preserve their rationale. New recipe fields can be added
without reinterpreting positional arrays. The initial surface deliberately does not
cover signal-only preprocessing or arbitrary analysis-plan variation.

## Alternatives considered

- Accept lists such as `method = ["irls", "ols"]`: rejected because labels,
  rationales, and reference selection would remain implicit.
- Serialize the low-level `MultiverseSpec` directly in TOML: deferred because it
  exposes internal pipeline structure before those schemas are stable.
- Run all combinations automatically from the primary analysis: rejected because
  software defaults cannot establish scientific defensibility.

## Revisit trigger

Revisit the supported alternative types after usability sessions and when a
validated signal-only preprocessing family is promoted to the typed project
workflow. Preserve names, rationales, explicit references, and outcome-blind
materialization in any successor schema.

## Evidence added later

On 2026-07-27, signal-only recipes were added while preserving this record's
requirements for names, rationales, explicit references, and outcome-blind
materialization. Output-variable coupling and unit separation are governed by
[SDR-0017](0017-couple-preprocessing-outputs-and-separate-units.md).
