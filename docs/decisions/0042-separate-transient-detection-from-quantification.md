# SDR-0042: Separate transient detection from quantification

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

Spontaneous-event methods disagree at both stages of analysis. GuPPY applies a
two-threshold MAD detector to z-scored data; PASTa tests local-maximum amplitude
against a pre-peak baseline; the Wallace prominence workflow uses normalized
data to locate peaks but returns to non-z-scored dF/F for kinetic measurement.

A combined function makes detector scale leak into amplitude, width, and AUC.
This is especially consequential when comparing conditions because whole-session
z-scoring can change the apparent event amplitude distribution.

## Decision

Candidate detection and event quantification are separate public operations.
A candidate retains a stable identifier, detector family, time/sample location,
threshold, baseline where relevant, and detector score. Quantification consumes
those candidates and an explicitly named variable, normally non-z-scored dF/F.

Detector families use separate dataclass specifications. Parameters irrelevant
to one family do not appear in its type. All stages split at missing acquisition
and timestamp gaps.

Named compatibility means reproducing the defining algorithmic choices, not
claiming exact parity with every upstream preprocessing or software release.
Compound-event metadata is descriptive; it does not merge events or assign a
biological mechanism.

## Alternatives considered

- **Add a detector name to the existing combined specification.** Rejected
  because it preserves scale leakage and creates many irrelevant parameters.
- **Always quantify the detector input.** Rejected because prominence detection
  intentionally uses normalization only for localization.
- **Choose one default detector for the field.** Rejected because available
  public validation shows material detector disagreement.

## Consequences

Workflows are one call longer but make the scientific scales explicit. Detector
multiverses can reuse one quantification contract, and quantification alternatives
can reuse frozen candidates. Legacy `detect_transients()` remains available while
the separated API is experimental.

## Revisit trigger

Revisit after raw-signal/manual-annotation validation across at least two sensors
and acquisition systems, or if upstream method changes invalidate the documented
compatibility definitions.
