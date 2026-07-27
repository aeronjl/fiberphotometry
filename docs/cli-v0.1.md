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

Execute every explicitly declared robustness workflow:

```bash
uv run fiberphotometry multiverse examples/tabular_project/project.toml
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

The `multiverse` command writes `multiverse.json`, a unit-local
`robustness-summary.json`, and a self-contained `robustness.html` alongside the
shared preflight, metadata, and manifest. The
preflight materializes stable universe IDs and checks every pipeline's clock,
channel, and operation compatibility without accessing fluorescence outcomes.

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

When `[nwb]` and `[multiverse]` are both declared, the `multiverse` command also
exports one validated NWB file per session. Each file stores raw acquisition data
once and one processed time series for the explicitly selected reference universe.
It does not duplicate full signals for every workflow. Scratch datasets retain the
complete multiverse result, stable universe IDs and choices, failures and declared
incompatibilities, unit-local robustness summary and thresholds, normalized
project, metadata readiness, session preflight, and reference-workflow QC. The
NWB identifier is labelled `multiverse`, and every file is hashed in the manifest.

## Reading completed evidence

The supported Python API reads either a complete output directory or one exported
NWB file through the same normalized object:

```python
from fiberphotometry import read_project_evidence

bundle = read_project_evidence("artifacts")
print(bundle.kind, bundle.status, bundle.manifest_verified)
analysis = bundle.analysis
multiverse = bundle.multiverse
lane_summary = bundle.robustness_summary
```

Directory reads require `manifest.json`, verify every declared SHA-256 before
returning records, reject missing or modified artifacts, and prevent absolute,
parent-relative, or symlink paths from escaping the bundle. Standalone NWB reads
recover the embedded project, analysis or multiverse result, robustness summary,
metadata, preflight, and QC. Because a standalone file has no external expected
hash, `manifest_verified` is `None` rather than an unsupported claim of integrity.
See the [evidence reader contract](evidence-reader-v0.1.md).

Compare any two readable bundles from the command line:

```bash
uv run fiberphotometry compare artifacts-a artifacts-b
uv run fiberphotometry compare artifacts-a session.nwb \
  --absolute-tolerance 1e-8 --output reproducibility.json
```

Markdown is printed by default. An `.json` destination writes the versioned
machine artifact; other extensions receive Markdown. Comparison reports byte
identity, project fingerprint agreement, scientific comparability, and semantic
differences classified as configuration, specification, data, quality, outcome,
execution, or provenance. See the
[reproducibility comparison contract](reproducibility-comparison-v0.1.md).

## Signing a publication bundle

Sign only after a bundle is complete and its manifest verifies:

```bash
uv run fiberphotometry sign artifacts \
  --key ~/.ssh/id_ed25519 \
  --identity scientist@example.org
```

This creates `publication-attestation.json` and the detached
`publication-attestation.json.sig`. Existing signatures are not replaced unless
`--force` is explicit. Private keys are never copied into the bundle.

Verifiers maintain an OpenSSH `allowed_signers` file outside the evidence bundle:

```text
scientist@example.org namespaces="fiberphotometry-publication@aeronjl.github.io" ssh-ed25519 AAAA...
```

Then verify signer authorization, signature bytes, the exact manifest digest, and
the project fingerprint:

```bash
uv run fiberphotometry verify-signature artifacts \
  --allowed-signers allowed_signers
```

The identity and namespace are signed. A readable self-signature is insufficient:
the identity must match a trusted key in `allowed_signers`. See the
[publication signing contract](publication-signing-v0.1.md).

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

## Robustness configuration

An optional `[multiverse]` section declares named scientific alternatives rather
than anonymous parameter arrays. Each alternative requires a rationale, and one
alternative per decision must be selected as the reference workflow. This first
schema supports reference-correction recipes, signal-only baseline recipes, and
response windows:

```toml
[multiverse]
schema_version = "1"
intent = "exploratory"
direction = "positive"
smallest_effect = 0.01
leave_one_animal_out = true
reference_preprocessing = "filtered_irls"
reference_response_window = "half_second"

[[multiverse.preprocessing]]
name = "filtered_irls"
rationale = "Suppress high-frequency noise before robust reference correction."
method = "irls"
lowpass_hz = 3.0

[[multiverse.preprocessing]]
name = "unfiltered_ols"
rationale = "Test dependence on filtering and robust regression."
method = "ols"

[[multiverse.response_windows]]
name = "half_second"
rationale = "Match the primary event definition."
response = [0.0, 0.5]

[[multiverse.response_windows]]
name = "quarter_second"
rationale = "Test sensitivity to an early-response definition."
response = [0.0, 0.25]
```

Every declared decision must contain at least two uniquely named alternatives.
The scientific estimand, design, baseline, and inference plan remain fixed across
this first configuration surface. A structurally incompatible universe blocks
execution before outcome access and remains visible in `preflight.json`.

Signal-only alternatives use the same named-recipe structure. Operations are
materialized in scientific order: resampling, optional low-pass filtering, then
baseline estimation. Recipes can select `double_exponential`, `asls`, or
`rolling_mean`; divisive and subtractive normalizations may coexist:

```toml
[[multiverse.preprocessing]]
name = "regularized_asls"
rationale = "Test a smooth asymmetric baseline on an explicit regular clock."
kind = "signal_only"
method = "asls"
normalization = "divide"
resample_rate_hz = "median"
resample_max_gap_factor = 1.5
lowpass_hz = 3.0

[[multiverse.preprocessing]]
name = "rolling_subtract"
rationale = "Test dependence on divisive versus subtractive normalization."
kind = "signal_only"
method = "rolling_mean"
normalization = "subtract"
rolling_window_s = 60.0
```

The primary analysis must also be `signal_only`; a multiverse does not silently
change the acquisition model. Reports partition ΔF/F and acquired-fluorescence
estimates into separate evidence lanes. A single `smallest_effect` is rejected
when alternatives span units because no one threshold is meaningful in both.

Baseline parameters are method-specific and appear directly on the relevant
recipe:

```toml
[[multiverse.preprocessing]]
name = "regularized_asls"
rationale = "Test the predeclared smooth lower-envelope comparator."
kind = "signal_only"
method = "asls"
normalization = "divide"
asls_smoothness = 10000000.0
asls_asymmetry = 0.02
max_iterations = 25
asls_reference_rate_hz = 20.0
resample_rate_hz = "median"
resample_max_gap_factor = 1.5
```

`double_exponential` accepts `min_tau_s`; `asls` accepts the four AsLS fields
above; and `rolling_mean` accepts `rolling_window_s` and `rolling_gap_factor`.
Supplying a parameter from another method is an error rather than an ignored
setting. All values are range-checked before universe materialization.

Scientifically incoherent combinations can be excluded prospectively:

```toml
[[multiverse.compatibility_rules]]
reason = "The parametric fit was not validated for the shortened window."
when = [
  { node = "preprocessing", alternative = "double_exponential" },
  { node = "response_window", alternative = "quarter_second" },
]
```

Rules must name declared choices, cannot repeat a choice, and cannot exclude the
reference workflow. Matching universes remain in the result as `incompatible`
with the declared reason and never access outcomes.

Declare a complete threshold policy with one table per unit lane:

```toml
[[multiverse.effect_thresholds]]
units = "ΔF/F"
smallest_effect = 0.01
direction = "positive"

[[multiverse.effect_thresholds]]
units = "acquired fluorescence"
smallest_effect = 25.0
direction = "either"
```

If any lane threshold is declared, every lane must receive exactly one. The
legacy scalar `multiverse.smallest_effect` remains valid for single-unit projects
and is mutually exclusive with `effect_thresholds`.

## Current boundary

v0.1 handles the categorical, within-animal scalar event contrast supported by
`EventAnalysis`, with either schema-first tabular files or explicitly mapped TDT
blocks. Multiverse configuration currently varies reference preprocessing,
signal-only baseline recipes, normalization, and response windows. It does not
yet expose arbitrary designs or method-specific reference-regression parameters.
