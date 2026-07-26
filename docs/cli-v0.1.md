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

The configured output directory receives:

- `preflight.json`: acquisition and event diagnostics for every session;
- `analysis.json`: typed pipeline, inference, QC, and processing lineage;
- `report.html`: self-contained scientist-facing evidence report;
- `manifest.json`: project identity, package version, status, and SHA-256 for every
  artifact.

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

`inspect` validates data without bypassing the analysis contract. `run` still
fails when required assumptions are not recorded, contrast levels are absent,
input roles are ambiguous, reference data are unavailable, or a schema is invalid.

## Current boundary

v0.1 handles the categorical, within-animal scalar event contrast supported by
`EventAnalysis`. It does not yet expose multiverse execution, arbitrary designs,
TDT import, or NWB export through the command line. Those features should extend
the typed library contracts rather than accumulate command-specific behavior.
