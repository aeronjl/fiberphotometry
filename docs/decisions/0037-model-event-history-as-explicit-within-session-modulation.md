# SDR-0037: Model event history as explicit within-session modulation

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related method: [behavioral event-kernel encoding](../event-kernel-encoding.md)

## Context

Photometry responses can depend on trial outcome, choice, elapsed time, or prior
events. A single pooled event kernel cannot represent those conditional changes.
Encoding every behavioral sequence inside fipha would, however, duplicate
the longitudinal modeling owned by Unspool and make trial ordering easy to infer
incorrectly.

The design also needs one extensible mechanism for current-event amplitude or
duration and for previous-event history. All are event-wise multipliers on a
declared kernel, but their scientific meanings and coding must remain visible.

## Decision

Represent a conditional kernel as a separately named `EventKernelSpec` that points
to a `source_event` and carries an `EventModulationSpec`. The modulation names one
per-event value, declares a nonnegative lag in event occurrences, and records the
value used when that history is unavailable.

Per-event values live beside their source event in `EncodingSession.event_values`
and must be finite with exactly one value per occurrence. History is evaluated only
within a session. A lagged source event must be strictly ordered; values never carry
across recording boundaries.

Do not infer coding or standardize event values globally. Scientists must supply an
interpretable coding, such as −0.5/+0.5 for a binary previous outcome, and include
the corresponding unmodulated main-event kernel when they want the modulation to be
interpreted as a conditional difference. Model alternatives remain subject to the
common-evidence multiverse rules.

## Consequences

Current-event modulation (`lag_events=0`) and trial history (`lag_events>0`) share a
typed, serialized design boundary. Duration, amplitude, confidence, and categorical
contrasts can use the same mechanism without adding special-case model engines.

The unavailable value is an explicit assumption. Zero is suitable only when zero
has the intended meaning under the supplied coding. The package rejects mismatched,
missing, non-finite, or ambiguously ordered values rather than silently dropping
events.

This is a within-session neural encoding predictor, not a behavioral learning
trajectory. Cross-session history and evolving behavioral parameters remain in
Unspool under [SDR-0030](0030-delegate-behavioral-trajectories-to-unspool.md).

The event-kernel fit artifact advances to schema v6 and stores each fitted kernel's
source event and complete modulation specification.

## Alternatives considered

- **Create dedicated previous-reward and previous-choice fields:** rejected because
  the API would not generalize to durations, confidence, or study-specific
  contrasts.
- **Accept pre-weighted event trains only:** rejected because the lag, source value,
  and unavailable-history rule would disappear from the result artifact.
- **Infer trial order from a cross-session table:** rejected because it risks
  crossing session boundaries and duplicates Unspool's chronology contract.
- **Automatically center or standardize event values:** deferred because fold-safe
  transformations need their own typed policy and change coefficient and ridge
  interpretations.

## Revisit trigger

Add typed categorical contrast construction or fold-local event-value scaling when
a validated use case requires it. Revisit the package boundary only if a neural
history model cannot be expressed without importing longitudinal behavioral state.

## Evidence added later

None.
