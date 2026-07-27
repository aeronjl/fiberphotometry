# Worked examples

The tutorials are executable scientific narratives rather than isolated API
snippets. Each begins with a question and records the experimental unit,
preprocessing choices, event denominator, inferential target, and limitations.

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

## Public DANDI event-kernel reproduction

Fit joint active-poke and reward-increment kernels to DMS and DLS recordings from
six checksum-pinned public animals. The example foregrounds weak held-out
prediction and a boundary-selected ridge penalty rather than hiding them behind
pooled coefficient shapes.

[Open the public event-kernel reproduction](dandi-000971-event-kernel.md)

## Literature reproductions to add

The capability audit identifies the next examples needed for field coverage:

1. a trial-level functional mixed-model reproduction of Loewinger et al.;
2. a multi-site/multi-color association example;
3. a long-duration tonic/phasic and spontaneous-transient example;
4. a spectrally resolved or hemodynamic-correction example with real controls.

These are roadmap commitments, not currently supported tutorials.
