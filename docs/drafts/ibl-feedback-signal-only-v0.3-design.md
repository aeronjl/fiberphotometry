# Draft: IBL feedback signal-only analysis v0.3

Status: **superseded by the frozen protocol; not executed** (26 July 2026)

The normative successor is the
[frozen v0.3 protocol](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-ibl-feedback-signal-only-v0.3.md).

This document proposes a prospective use of the 18 held-out IBL animals that
failed the paired-reference v0.2 readiness gate. It does not amend v0.2 and must
not be described as its held-out replication. The acquisition was signal-only;
the design therefore changes the preprocessing assumptions while preserving the
scientific contrast and animal-level inferential unit.

## Scope and estimand

- Population: held-out DMS recordings from animals other than `fip_13`–`fip_16`.
- Signal: explicitly labelled 470-nm GCaMP samples only; wavelength-0 no-LED rows
  are ignored rather than interpolated as a reference.
- Event: feedback time, with the same pre-event and response windows as the frozen
  feedback protocol.
- Contrast: within-animal correct-minus-incorrect event response, summarized
  across animals. Trials and sessions are not treated as independent animals.
- Interpretation: robustness of a signal-only fluorescence contrast, not proof
  that motion, haemodynamics, or other shared artefacts were removed.

## Outcome-blind eligibility lock

Before reading condition-labelled fluorescence outcomes, regenerate and commit a
complete manifest requiring:

1. DMS ROI metadata and an explicitly labelled 470-nm signal;
2. valid timestamps and sufficient samples for the declared event windows;
3. at least 20 correct and 20 incorrect eligible events per session;
4. non-destructive QC annotations and explicit exclusion reasons;
5. at least 12 eligible animals after all schema and count gates.

The manifest must include all queried sessions, package/query versions, an input
fingerprint, and the exact development-animal exclusion. The prior v0.2 manifest
cannot be reused as the eligibility definition has changed.

## Preprocessing multiverse

No single signal-only baseline has yet earned confirmatory status in this package.
The analysis should therefore be labelled exploratory and retain every declared
universe, including failures.

Two normalization families should be reported separately because their units and
estimands differ:

| Family | Baseline estimators | Output | Interpretation |
| --- | --- | --- | --- |
| Divisive | double exponential; rate-aware AsLS | `(F - F0) / F0` | relative fluorescence |
| Subtractive | double exponential; rate-aware AsLS | `F - F0` | acquired fluorescence units |

Each estimator is crossed with the three already-declared response windows,
yielding six divisive and six subtractive universes. Results may be compared for
sign, interval overlap, and influence, but must not be pooled across unit families.
The paper's ±30 s rolling-baseline dF/F is implemented as a faithful published
workflow comparator, producing three additional divisive universes. Inspection of
the released analysis code established the exact regular-data semantics: rounded
frame rate, a 60-second sample-count window, centred alignment, and full-window
boundary NaNs. The package additionally splits timestamp gaps and records that
safety extension in provenance. It is a comparator, not automatically the package
default.

Every universe must record baseline parameters, edge handling, effective sampling
rate, missingness, retained events, and failures. The 20-Hz minority must not
inherit sample-count parameters calibrated at 50 Hz.

## Inference and robustness

- Use the existing animal-level hierarchical bootstrap and animal-level interval
  comparators; retain leave-one-animal-out diagnostics.
- Present a specification curve grouped by normalization family and baseline
  estimator.
- Define robustness descriptively: fraction of valid universes sharing the same
  direction, interval ranges, and whether any single animal changes the direction.
- Do not select a preferred workflow from the held-out effect size or p-value.
- Do not collapse failed universes or incompatible units into a consensus number.
- Treat disagreement as information about preprocessing dependence, not as an
  inconvenience to be averaged away.

## Completed prerequisites for freezing

All four prerequisites were completed before computing any
correct-minus-incorrect fluorescence contrast. See the normative successor above.

## Stop rules

Stop without outcome analysis if fewer than 12 animals pass, if acquisition-rate
metadata cannot be made explicit, or if the published rolling comparator cannot be
reproduced unambiguously. Record a readiness failure rather than relaxing gates
after seeing results.

## Relationship to existing evidence

The package's independent-control pilots found mixed performance for control-free
baselines, so this protocol does not promote either double-exponential or AsLS to
a trusted universal default. See
[SDR-0002](../decisions/0002-control-free-methods-remain-experimental.md) and the
[channel-provenance audit](../ibl-new-cohort-channel-provenance-v0.1.md).
