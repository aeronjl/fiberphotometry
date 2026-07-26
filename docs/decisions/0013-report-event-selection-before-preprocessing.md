# SDR-0013: Report event selection before and after preprocessing

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

The outcome-blind IBL event-coverage audit found that the prospective
regularization policy retained every frozen event, but the older rolling-validity
gate had already removed 1,612 otherwise boundary-eligible events. Aggregate
retention was 99.29%, while one session retained 88.1% and a different session
had an 8.44-percentage-point condition-retention difference. Reporting only the
final denominator would conceal where selection occurred.

## Decision

Event-analysis workflows report at least three denominators when applicable:
candidate events with nominal recording-boundary coverage, events retained by
eligibility/QC gates, and events complete after preprocessing. Counts and
retention fractions are stratified by condition, session, and animal. Upstream
selection and incremental preprocessing attrition remain separate; a later stage
cannot receive credit for events removed earlier.

These diagnostics are structural and should be available before fluorescence
outcomes or effect estimates are accessed. Aggregate balance never substitutes
for session- and animal-level reporting.

## Consequences

Reports become slightly larger, but scientists can identify differential
selection, distinguish acquisition/QC limitations from algorithmic loss, and
reproduce the exact analysis population. Product APIs need a first-class coverage
audit rather than a lone warning or final event count.

## Revisit trigger

Revisit the required strata or default warning thresholds after moderated
usability studies and external datasets reveal whether the report is too noisy or
misses consequential selection patterns.
