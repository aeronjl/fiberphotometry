# Scientist-facing workflow v0.1

The first product surface wraps the typed pipeline in a focused event-contrast
workflow. Scientists supply sessions, event times and categorical conditions;
FiberPhotometry constructs the animal/session/event hierarchy, exposes the
required inferential assumptions before execution, and produces a self-contained
HTML evidence report.

```python
from fiberphotometry import EventAnalysis, EventSession, Preprocessing

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
assumptions. See [`feedback-analysis.toml`](../examples/feedback-analysis.toml).

The complete public-data path is documented in the
[IBL import-to-report tutorial](tutorials/ibl-feedback-report.md).

Robustness results use a separate
[grouped multiverse report](grouped-multiverse-report-v0.1.md). Its parallel
evidence lanes make unit boundaries executable and visually explicit.
