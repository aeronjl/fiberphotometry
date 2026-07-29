# SDR-0030: Delegate behavioral learning trajectories to Behavio

- Status: **Accepted**
- Date: 2026-07-27

## Context

Longitudinal photometry studies combine signal processing with behavioral models,
multiple time coordinates, repeated sessions, and animal-level generalization.
fipha already owns the optical and event-analysis layers. Behavio (originally
released as Unspool and renamed when it also absorbed fipha's general behaviour
surface) is
a separate process-first package with explicit clocks, forward-session validation,
hierarchical smooth trajectories, model recovery, and IBL/NWB adapters.

Adding a second session-trajectory engine here would duplicate behavior, create
divergent validation rules, and blur which package owns learning-model assumptions.

The public IBL study by Pan-Vazquez, Sanchez Araujo et al. reinforces the separation:
session-evolving behavioral weights and neural event kernels occupy related but
non-equivalent analysis layers. Loewinger et al.'s functional mixed models also show
that trial-, session-, and animal-level variation must be represented explicitly.

## Decision

fipha will export validated trial-level neural summaries and explicit
subject/session/trial/session-order coordinates through a dependency-light bridge.
Behavio will own behavioral trajectory models, longitudinal clocks, and prospective
session validation.

Behavio remains an optional peer package, not a hard runtime dependency. The bridge
must retain source columns, fingerprint the handoff, and reject inferred or ambiguous
chronology. A public biological result requires a separately frozen cross-package
protocol.

## Alternatives considered

- **Add a linear mixed trajectory model to fipha:** rejected because it
  duplicates only a small and misleading subset of Behavio's longitudinal contract.
- **Make Behavio a mandatory dependency:** rejected because event-locked photometry
  users should not inherit a behavioral-modeling stack.
- **Document an ad hoc dataframe conversion:** rejected because chronology and trial
  identity need executable validation and provenance.

## Consequences

- fipha gains a clear route into sophisticated learning analyses without
  claiming those models as native photometry methods.
- Cross-package examples must pin both versions and define the handoff schema.
- Functional photometry models remain an independent planned capability rather than
  being relabeled as behavioral trajectory models.

## Evidence added later

The peer package was renamed from `unspool` to `behavio`. fipha's bridge module
followed: `fipha.unspool` is now `fipha.behavio`, `UnspoolStudyExport` is now
`BehavioStudyExport`, and `prepare_unspool_study` is now `prepare_behavio_study`.
The same rename carried fipha's general behaviour surface — the pose and ethogram adapters,
clock synchronization, and interval policies — out of this repository and into
[behavio](https://github.com/aeronjl/behavio), widening the boundary this record
established without changing its reasoning.

## Revisit trigger

Revisit if Behavio no longer supports the required longitudinal contract, if a neural
trajectory method cannot be expressed through the trial-level handoff without losing
essential provenance, or after two external laboratories exercise the integration.
