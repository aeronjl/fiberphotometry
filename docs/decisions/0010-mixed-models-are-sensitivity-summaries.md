# SDR-0010: Scalar mixed models are sensitivity summaries

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

An event-level mixed model and an equally weighted animal/session contrast need
not estimate the same quantity. Mixed models also require random-effects choices,
optimizer convergence, and normal-theory interval assumptions. Treating them as a
universally superior replacement would hide rather than resolve those differences.

## Decision

The initial scalar mixed model is opt-in and labelled
`role = "sensitivity_analysis"`. It fits the declared two-level event contrast
using animal random intercepts and condition slopes, with a nested session random
intercept when multiple sessions per animal make it estimable.

The artifact reports convergence, optimizer, fixed-effect interval, random-effect
variances, warnings, engine version, and input fingerprint. It remains separate
from the primary design-aware result.

## Consequences

Scientists can inspect agreement without allowing the mixed model to silently
change the primary estimand. Nonconvergence remains visible. Current intervals are
statsmodels normal-theory fixed-effect intervals, not simultaneous waveform bands
or validated small-sample coverage guarantees.

## Revisit trigger

Revisit after coverage calibration, alternative degrees-of-freedom methods, or
functional mixed-model parity provides evidence for a different default role.
