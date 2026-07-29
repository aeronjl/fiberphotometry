# Tutorial: public IBL data to an evidence report

This tutorial exercises the first scientist-facing product workflow on four fixed
public International Brain Laboratory sessions. It produces both a machine-readable
JSON artifact and a self-contained HTML report from a versioned TOML analysis file.

The example is deliberately a previously studied development cohort, not new
confirmatory evidence. Its purpose is to demonstrate an honest import-to-report
workflow with real acquisition irregularities and QC warnings.

## Install

```bash
uv sync --extra plots --group ibl-validation
```

## Inspect the scientific contract

[`examples/feedback-analysis.toml`](https://github.com/aeronjl/fipha/blob/main/examples/feedback-analysis.toml) declares:

- DMS as the selected region;
- correct minus incorrect feedback;
- IRLS reference correction;
- -0.5–0 s baseline and 0–0.5 s response windows;
- descriptive intent and non-randomized interpretation;
- every assumption required by the animal-level paired interval.

Unknown settings are errors. Changing any normalized choice changes the SHA-256
embedded in the output artifacts.

## Run

```bash
uv run --group ibl-validation python examples/ibl_feedback_report.py \
  --output ibl-feedback-report.html
```

The first run downloads the fixed public assets into
`~/Library/Caches/fipha/ibl-tutorial`. It writes:

- `ibl-feedback-report.html`, an offline report for inspection and sharing;
- `ibl-feedback-report.json`, containing the configuration/specification, analysis
  result, input fingerprint, QC reports, processing lineage, and data counts.

The report shows the aggregate estimate only after exposing the population unit.
Its animal panel makes the four independent animals visible; the 2,507 events are
not presented as 2,507 independent replicates. Session QC warnings remain in the
report and do not silently delete observations.

## Adapt to another dataset

Keep the TOML contract and replace only `load_sessions` with an NWB, IBL, or tabular
loader that produces `EventSession` objects. Acquisition-specific parsing stays at
the boundary; the scientific workflow, assumptions, artifacts, and report remain
the same.

This tutorial is descriptive and intentionally small. It is not evidence that IRLS
is universally preferable, and it does not replace the separately frozen held-out
signal-only protocol.
