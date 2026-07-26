# Configuration-first CLI v0.1

The CLI runs the same typed library workflow as the Python API. It does not contain
a second analysis implementation or silently accept inferential assumptions.

## Complete walkthrough

From the repository root, generate the deterministic example inputs:

```bash
uv run python examples/tabular_project/make_data.py
```

Inspect schemas, file fingerprints, missingness, sampling, and event-clock coverage
without fitting an analysis:

```bash
uv run fiberphotometry inspect examples/tabular_project/project.toml
```

Execute the declared workflow:

```bash
uv run fiberphotometry run examples/tabular_project/project.toml
```

Install the `nwb` optional dependencies when the project declares NWB output:

```bash
pip install "fiberphotometry[nwb]"
```

The configured output directory receives:

- `preflight.json`: acquisition and event diagnostics for every session;
- `metadata.json`: actionable analysis, NWB, and publication/reuse readiness;
- `mixed-model.json`: optional event-level scalar mixed-model sensitivity summary;
- `analysis.json`: typed pipeline, inference, QC, and processing lineage;
- `report.html`: self-contained scientist-facing evidence report;
- `manifest.json`: project identity, package version, status, and SHA-256 for every
  artifact.
- `nwb/*.nwb`: one validated file per session when an `[nwb]` table is declared.

Use `--output` to save an inspection or `--output-dir` to override the configured
run destination. Writes are atomic: a failed write does not leave a partially
updated artifact under its final name. If analysis validation fails after input
loading, the preflight and a failure manifest are retained while analysis and HTML
artifacts are not fabricated.

## Project file

[`examples/tabular_project/project.toml`](../examples/tabular_project/project.toml)
contains four explicit layers:

1. subject/session source files;
2. recording signal/reference/channel mappings;
3. event time, identifier, and typed metadata mappings;
4. the existing event-analysis configuration.

Relative paths resolve against the project file, not the caller's current working
directory. The exact TOML bytes receive a project SHA-256. Recording and event
files retain separate hashes, ensuring a configuration edit and a data edit remain
distinguishable provenance events.

An optional `[timecourse]` table enables the same animal-level peri-event lane as
the Python API. It declares `window`, `rate_hz`, `confidence`, `draws`, and `seed`;
the resulting JSON and HTML keep pointwise and simultaneous bands distinct. See
[`examples/feedback-analysis.toml`](../examples/feedback-analysis.toml) and the
[peri-event inference contract](peri-event-inference-v0.1.md).

NWB export is opt-in because valid files require metadata the library must not
invent. Each session declares a timezone-aware `session_start_time`; `[nwb]`
declares `session_description` and an identifier prefix. Each file contains raw
signal/reference series, the analysed processed series, event trials, subject and
session identity, operation provenance, session QC and preflight JSON, and the
complete project and population-analysis records. Every NWB file is validated
before its atomic publication and included in `manifest.json` by SHA-256.
The current writer uses valid core-NWB `TimeSeries` objects and deliberately does
not invent unavailable `ndx-fiber-photometry` hardware metadata; see
[SDR-0006](decisions/0006-require-explicit-nwb-session-metadata.md).

`inspect` validates data without bypassing the analysis contract. `run` still
fails when required assumptions are not recorded, contrast levels are absent,
input roles are ambiguous, reference data are unavailable, or a schema is invalid.

For repeated sessions within animal, `analysis.inference.contrast_unit = "session"`
calculates each within-session contrast first and weights complete sessions equally
within animal. Omitting it retains observation-pooled weighting for backward
compatibility; the choice is serialized in the estimand.

For jittered signal-only recordings, regularization must be explicit and ordered
before methods such as AsLS:

```toml
[analysis.preprocessing]
kind = "signal_only"
method = "asls"
normalization = "divide"
resample_rate_hz = "median"
resample_max_gap_factor = 1.5
```

The source arrays and timestamp diagnostics remain in the processing lineage.

## Current boundary

v0.1 handles the categorical, within-animal scalar event contrast supported by
`EventAnalysis`, with either schema-first tabular files or explicitly mapped TDT
blocks. It does not yet expose multiverse execution or arbitrary designs. Those
features should extend the typed library contracts rather than accumulate
command-specific behavior.
