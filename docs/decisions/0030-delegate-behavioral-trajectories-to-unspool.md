# SDR-0030: Delegate behavioral learning trajectories to Unspool

- Status: **Accepted**
- Date: 2026-07-27

## Context

Longitudinal photometry studies combine signal processing with behavioral models,
multiple time coordinates, repeated sessions, and animal-level generalization.
FiberPhotometry already owns the optical and event-analysis layers. Unspool is a
separate process-first package with explicit clocks, forward-session validation,
hierarchical smooth trajectories, model recovery, and IBL/NWB adapters.

Adding a second session-trajectory engine here would duplicate behavior, create
divergent validation rules, and blur which package owns learning-model assumptions.

The public IBL study by Pan-Vazquez, Sanchez Araujo et al. reinforces the separation:
session-evolving behavioral weights and neural event kernels occupy related but
non-equivalent analysis layers. Loewinger et al.'s functional mixed models also show
that trial-, session-, and animal-level variation must be represented explicitly.

## Decision

FiberPhotometry will export validated trial-level neural summaries and explicit
subject/session/trial/session-order coordinates through a dependency-light bridge.
Unspool will own behavioral trajectory models, longitudinal clocks, and prospective
session validation.

Unspool remains an optional peer package, not a hard runtime dependency. The bridge
must retain source columns, fingerprint the handoff, and reject inferred or ambiguous
chronology. A public biological result requires a separately frozen cross-package
protocol.

## Alternatives considered

- **Add a linear mixed trajectory model to FiberPhotometry:** rejected because it
  duplicates only a small and misleading subset of Unspool's longitudinal contract.
- **Make Unspool a mandatory dependency:** rejected because event-locked photometry
  users should not inherit a behavioral-modeling stack.
- **Document an ad hoc dataframe conversion:** rejected because chronology and trial
  identity need executable validation and provenance.

## Consequences

- FiberPhotometry gains a clear route into sophisticated learning analyses without
  claiming those models as native photometry methods.
- Cross-package examples must pin both versions and define the handoff schema.
- Functional photometry models remain an independent planned capability rather than
  being relabeled as behavioral trajectory models.

## Revisit trigger

Revisit if Unspool no longer supports the required longitudinal contract, if a neural
trajectory method cannot be expressed through the trial-level handoff without losing
essential provenance, or after two external laboratories exercise the integration.
