# SDR-0031: Treat spontaneous-transient detection as a method family

- Status: **Accepted (experimental API)**
- Date: 2026-07-27

## Context

Published photometry workflows do not converge on one event definition. GuPPy uses
a moving window, excludes large events from its baseline estimate, and applies a
MAD threshold. PASTa separates peak detection from an adaptive pre-peak baseline
and exposes mean, minimum, and local-minimum alternatives. Other studies use
z-score thresholds or fixed prominence after smoothing. These alternatives can
change event counts, amplitudes, and durations.

Long recordings add another ambiguity. Slowly varying fluorescence can reflect
biology, bleaching, motion, sensor kinetics, or preprocessing. Calling every slow
component “tonic” would turn an operational filter choice into a biological claim.

## Decision

The package will expose an experimental detector family rather than a canonical
detector. Each result records:

- an absolute, global-MAD, or rolling-MAD threshold;
- the pre-peak baseline duration, gap, and statistic;
- minimum peak distance and acquisition-gap boundary;
- accepted events and every rejected candidate with a reason;
- local-baseline amplitude, half-height timing, AUC, and finite-duration rate;
- optional long-window descriptive bins.

Detection never bridges non-finite samples or large timestamp gaps. A candidate
without a complete local baseline or, by default, both half-height crossings is
reported but excluded. Time-bin denominators use acquired finite duration.

The first API will not label a slow fluorescence component as tonic. It will use
the neutral term **time-binned transient summary**. Any later multiscale signal
decomposition must name its cutoff and validate its interpretation separately.

## Consequences

- Scientists can run named alternatives as a robustness multiverse.
- Rejected events and missing exposure remain auditable.
- A single default remains a convenience, not a field-wide recommendation.
- Compound-event classification, deconvolution, and biological tonic/phasic
  interpretation remain future validation tasks.

## Revisit trigger

Revisit after validation against manually annotated and synthetic events across at
least two sensors and acquisition systems, or when a community benchmark provides
a consensus event definition.
