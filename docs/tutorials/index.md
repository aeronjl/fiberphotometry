# Worked examples

## Spontaneous events and long recordings

The [spontaneous-transient sensitivity tutorial](spontaneous-transients.md) starts
with known synthetic events, introduces an acquisition gap, and compares named
threshold and local-baseline alternatives without claiming a tonic signal.

The tutorials are executable scientific narratives rather than isolated API
snippets. Each begins with a question and records the experimental unit,
preprocessing choices, event denominator, inferential target, and limitations.

Start with the [public-data evidence atlas](../methods/public-evidence-atlas.md)
if you want to compare the scientific outputs and evidence boundaries before
choosing a tutorial.

## Public IBL feedback analysis

Import public IBL tables, inspect event coverage, and produce fingerprinted JSON
and HTML evidence. This is the shortest complete example.

[Open the IBL tutorial](ibl-feedback-report.md)

## Raw DANDI NWB to robustness report

Run a six-animal reward analysis across eight declared preprocessing universes.
This example demonstrates NWB ingestion, animal-level inference, explicit
incompatibility, failure retention, and report verification.

[Open the DANDI tutorial](dandi-000971-reward-multiverse.md)

## Event-kernel encoding simulation

Recover overlapping cue and reward kernels while controlling a continuous motion
covariate and holding out complete animals. This is the ground-truth
implementation-validation companion to the public-data example below.

[Open the event-kernel simulation](event-kernel-simulation.md)

## Event-kernel model multiverse

Compare named cue, reward and motion design specifications under one fixed
animal-held-out validation policy. Score deltas are only reported when models use
the exact same retained timestamps, and failed designs remain in the ledger.

[Open the model-multiverse method](../event-kernel-multiverse-v0.1.md)

## Previous-outcome event kernels

Fit an average cue kernel together with an explicitly coded previous-outcome
modulation. The simulation demonstrates recovery, session-boundary resets, and the
separation between within-session neural encoding and Unspool's longitudinal
behavior models.

[Open the event-history tutorial](event-kernel-history.md)

## Public DANDI event-kernel reproduction

Fit joint active-poke and reward-increment kernels to DMS and DLS recordings from
six checksum-pinned public animals. The example foregrounds weak held-out
prediction and a boundary-selected ridge penalty rather than hiding them behind
pooled coefficient shapes.

[Open the public event-kernel reproduction](dandi-000971-event-kernel.md)

## Public IBL longitudinal neural–behavioral forecast

Compose FiberPhotometry's checksum-verified session neural summaries with
Unspool's cohort-forward behavioral validation. The retained result shows that the
previous session's coarse DMS feedback contrast does not improve prediction in the
declared future session.

[Open the cross-package longitudinal tutorial](ibl-unspool-longitudinal.md)

## Pose and behavior-tool interoperability

Compose DeepLabCut or SLEAP pose confidence, Keypoint-MoSeq bouts, and BORIS
point/state annotations with photometry covariates and events. The tutorial then
passes declared neural summaries to Unspool without duplicating longitudinal
behavior models.

[Open the ecosystem interoperability tutorial](behavior-tool-interoperability.md)

## Literature reproductions to add

The capability audit identifies the next examples needed for field coverage:

1. a trial-level functional mixed-model reproduction of Loewinger et al.;
2. a multi-site/multi-color association example;
3. a long-duration tonic/phasic and spontaneous-transient example;
4. a spectrally resolved or hemodynamic-correction example with real controls.

These are roadmap commitments, not currently supported tutorials.
