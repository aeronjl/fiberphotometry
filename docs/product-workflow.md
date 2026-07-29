# First event analysis

*Applies to v0.1.*

This is the main workflow: take labelled sessions to a dF/F event contrast
between two named conditions, with the animal as the experimental unit.

Scientists supply sessions, event times and categorical conditions.
fipha runs the reference-channel correction to dF/F, constructs the
animal/session/event hierarchy, exposes the required inferential assumptions
before execution, and produces a self-contained HTML evidence report.

If you have not produced a dF/F trace yet, start with
[your first dF/F trace](getting-started/first-dff-trace.md) — this page assumes
you already have `recording` objects and event times.

```python
from fipha import EventAnalysis, EventSession, Preprocessing

session = EventSession.from_arrays(
    recording,
    event_times=trials.feedback_times,
    conditions=trials.outcome,
)
study = EventAnalysis(
    (session,),
    numerator="correct",
    denominator="incorrect",
    channel="DMS",
    preprocessing=Preprocessing.reference(method="irls"),
)

plan = study.plan()
print(plan.required_assumptions)
result = study.run(acknowledged_assumptions=plan.required_assumptions)
result.write_html("feedback-report.html")
```

## Event coverage is a first-class result

`EventSession` can retain candidate events that an eligibility rule excludes.
Supply an `eligible` mask and a reason for every excluded event; only eligible
events enter preprocessing and inference, while all candidates remain in the
coverage audit:

```python
session = EventSession.from_arrays(
    recording,
    event_times,
    conditions,
    eligible=passes_declared_gate,
    exclusion_reasons=gate_reasons,
)
result = study.run(acknowledged_assumptions=plan.required_assumptions)
print(result.coverage.total)
```

The typed `EventCoverageReport` separates candidate, eligibility-gated, and
complete-after-preprocessing counts. It reports retention by condition and within
every animal and session, preserves gate and preprocessing dispositions, and
warns about any differential retention. The same complete structure appears under
`event_coverage` in JSON. The HTML report presents the three-stage denominator and
keeps animal/session detail expandable.

For lower-level or non-workflow integrations, construct `EventCoverageRecord`
objects and call `assess_event_coverage` directly. This audit requires only event
routing and missingness metadata; it does not calculate or inspect effect sizes.

## Optional time-resolved evidence

Add `timecourse=PeriEventInferenceSpec(...)` to `EventAnalysis` to estimate the
condition contrast across a declared peri-event window. Events are reduced to
equal-weighted session means and then animal contrast curves before bootstrap
inference. The report shows both local pointwise intervals and a wider simultaneous
band for the whole window; they are never presented as interchangeable.

See [animal-level peri-event inference](peri-event-inference.md) for the full
aggregation, uncertainty, missing-support, and interpretation contract.

`Preprocessing.signal_only(...)` provides the same surface for explicitly declared
control-free workflows. Signal-only recordings receive only the QC metrics that
can actually be identified from one channel; the report never invents reference
correlation or reference-fit diagnostics.

The report leads with the contrast and interval, then shows individual-animal
effects, per-session QC, ordered preprocessing provenance, and acknowledged
assumptions. It is offline, printable, and contains no external JavaScript,
stylesheets, fonts, or telemetry.

Run the complete synthetic example with:

```bash
uv run python examples/event_analysis_report.py
```

This is intentionally a narrow first workflow. It currently covers a categorical
within-animal event contrast; it does not yet replace the lower-level APIs for
continuous predictors, between-group designs, full multiverses, or functional
time-series inference.

## Configuration-first reruns

`EventAnalysisConfig.from_toml(...)` validates a versioned analysis contract and
binds its SHA-256 to the JSON and HTML artifacts. The file records preprocessing,
windows, contrast, intent, randomization status, quality gates, and acknowledged
assumptions. See [`feedback-analysis.toml`](https://github.com/aeronjl/fipha/blob/main/examples/feedback-analysis.toml).

The complete public-data path is documented in the
[IBL import-to-report tutorial](tutorials/ibl-feedback-report.md).

Robustness results use a separate
[grouped multiverse report](grouped-multiverse-report.md). Its parallel
evidence lanes make unit boundaries executable and visually explicit.
