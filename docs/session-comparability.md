# Across-session comparability

*Applies to v0.1.*

Longitudinal modeling is only meaningful when a declared neural series still
refers to the same measurement across sessions. fipha now performs an
outcome-blind preflight before the trial table crosses into Unspool.

This is an operational QC contract, not a test that two sessions are biologically
identical. It answers a narrower question: are signal identity, units, processing,
coverage, and basic acquisition diagnostics sufficiently consistent for the
planned longitudinal analysis to proceed transparently?

## Declare one record per session and logical series

```python
from fipha.comparability import (
    SessionComparabilityRecord,
    assess_session_comparability,
)

records = [
    SessionComparabilityRecord(
        subject="mouse-07",
        session="day-01",
        series_id="dms-dlight",
        sensor="dLight1.3b",
        site="DMS",
        output_variable="dff",
        unit="fraction",
        preprocessing_fingerprint="sha256:recipe-a",
        finite_fraction=0.992,
        event_coverage_fraction=0.91,
        baseline_median=1842.0,
        reference_correlation=0.74,
        sampling_rate_hz=20.0,
        acquisition_system="Neurophotometrics",
    ),
    SessionComparabilityRecord(
        subject="mouse-07",
        session="day-02",
        series_id="dms-dlight",
        sensor="dLight1.3b",
        site="DMS",
        output_variable="dff",
        unit="fraction",
        preprocessing_fingerprint="sha256:recipe-a",
        finite_fraction=0.987,
        event_coverage_fraction=0.88,
        baseline_median=1710.0,
        reference_correlation=0.70,
        sampling_rate_hz=20.0,
        acquisition_system="Neurophotometrics",
    ),
]

comparability = assess_session_comparability(records)
comparability.require_ready()
```

`series_id` is the analyst's stable logical identity. It lets vendor channel names
change without pretending that a different sensor or implant site is the same
measurement. Duplicate subject/session/series records are rejected.

## What warns and what refuses

Identity changes are refusal states by default:

- sensor;
- site;
- output variable;
- unit; and
- preprocessing fingerprint.

Changing acquisition system is a warning because a legitimate hardware migration
is possible, but it needs review. Per-session finite fraction and event coverage
are checked against prospective thresholds. Across sessions, the preflight reports
the raw-baseline fold change, reference-correlation range, and sampling-rate ratio.

The v0.1 defaults are deliberately visible configuration, not claims of universal
scientific cutoffs:

| Diagnostic | Warning | Refusal |
|---|---:|---:|
| finite fraction | below 0.95 | below 0.80 |
| event coverage | below 0.80 | below 0.50 |
| raw-baseline maximum/minimum | above 2× | above 4× |
| reference-correlation range | above 0.30 | above 0.60 |
| sampling-rate maximum/minimum | above 1.20× | above 2× |

Missing optional diagnostics warn. A prospective `SessionComparabilitySpec` can
make any missing event-coverage, baseline, reference, or sampling-rate metric a
refusal. Thresholds belong in the analysis configuration before longitudinal
outcomes are inspected.

## Bind the evidence into the Unspool handoff

```python
handoff = prepare_unspool_study(
    trial_table,
    subject="animal",
    session="recording",
    trial="event_index",
    session_order="training_day",
    comparability=comparability,
    require_comparability=True,
)
```

The handoff refuses a failed report and verifies that every exported
subject/session pair is covered. By default warnings may proceed and remain visible;
set `allow_comparability_warnings=False` to require a clean pass. The report
fingerprint and status are included in the Unspool export fingerprint, so replacing
the preflight changes the handoff identity.

## Result structure

`SessionComparabilityReport` retains:

- every declared session record;
- the prospective threshold specification;
- one computed summary per subject and logical series;
- warning/error codes with affected sessions;
- overall `pass`, `warning`, or `fail` status; and
- a deterministic input fingerprint.

`to_json()` emits a self-contained evidence artifact. It contains no neural
outcomes and does not select sessions based on downstream longitudinal results.

## Boundaries

This preflight does not establish that fluorescence amplitude is an absolute
measure of expression, correct biological drift, or certify a sensor model. It
does not replace visual trace review, histology, sensor/isobestic validity checks,
or an explicit model for measurement error. Those remain separate product work.

It also does not fit trajectories. fipha owns the measurement and its
comparability evidence; Unspool owns longitudinal clocks, validation folds, and
behavioral or cognitive model families.
