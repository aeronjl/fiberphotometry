# Command line

The `fipha` command has two layers.

**Analysis commands** take one recording file and produce a number. They need no
project file, no schema, and no declared study design: `qc`, `dff`, `align`, and
`transients`. Use them to find out whether a recording is usable and what it
contains.

**Project commands** run a declared, reproducible study and emit publishable
evidence: `inspect`, `run`, `multiverse`, `compare`, and the deposition commands.
They require a TOML project because a claim about an experiment needs the
experiment written down.

Everything below runs as written after
[installing the package](getting-started/install.md). Neither layer contains a
second analysis implementation; both call the same typed library functions.

## Analyse one recording

### Make an example recording

Every example on this page uses two files in the current directory. Create them:

```bash
python - <<'PY'
import numpy as np

rate_hz = 20.0
time = np.round(np.arange(int(120 * rate_hz)) / rate_hz, 6)
reference = 1 + 0.05 * np.sin(2 * np.pi * 0.01 * time)
onsets = (20.0, 45.0, 70.0, 95.0)
dff = sum(0.25 * np.exp(-0.5 * ((time - onset) / 0.3) ** 2) for onset in onsets)
signal = (2.0 + 0.5 * reference) * (1 + dff)

with open("recording.csv", "w") as stream:
    stream.write("time,signal,reference\n")
    for row in zip(time, signal, reference):
        stream.write(",".join(repr(float(value)) for value in row) + "\n")

with open("events.csv", "w") as stream:
    stream.write("time,event_id\n")
    for index, onset in enumerate(onsets, start=1):
        stream.write(f"{onset},cue-{index}\n")
PY
```

`recording.csv` is a 120-second, 20 Hz recording of one channel with an
isosbestic reference and four injected 0.25 ΔF/F transients. Any of the
[supported acquisition formats](#formats-read-without-configuration) works in its
place; nothing below is specific to CSV.

### `qc` — is this recording usable?

```bash
fipha qc recording.csv
```

The human summary goes to stderr and the machine-readable report to stdout:

```text
recording.csv (tabular): 1 channel(s), 2400 samples, 119.950 s at 20 Hz
  signal: correlation=0.1830 flat_steps=0.0000 denominator_ratio=0.9880 warnings=none
status: ok
```

The JSON reports the estimated sampling rate, the interval coefficient of
variation, the large-gap count, and for every channel the finite-paired fraction,
the longest valid segment, the signal/reference correlation, the repeated-extreme
and flat-step fractions, the OLS and IRLS intercepts, slopes and residual RMSEs,
the relative slope difference between them, and the minimum-to-median ratio of
the fitted ΔF/F denominator. `status` is `review` when any channel raises a
warning and `ok` otherwise.

The warning codes are `low_valid_fraction`,
`weak_signal_reference_correlation`, `repeated_extreme_values`, `flat_steps`,
`fit_method_sensitive`, and `unstable_dff_denominator`. None of them removes a
sample: `qc` never silently excludes data, so a warning is a prompt to look, not
an automatic exclusion.

Recordings without a reference channel receive the signal-only report, which
omits the correlation and regression fields rather than inventing them.

Write a per-channel table instead:

```bash
fipha qc recording.csv --format csv --output qc.csv
```

### `dff` — compute ΔF/F with its provenance

```bash
fipha dff recording.csv --output dff.csv --format csv
```

`--method auto` (the default) fits the reference channel when one exists and
falls back to a signal-only baseline when it does not. Choose explicitly with
`--method reference` or `--method baseline`.

| Flag | Applies to | Values |
|---|---|---|
| `--fit` | `--method reference` | `irls` (default), `ols` |
| `--baseline-method` | `--method baseline` | `double_exponential` (default), `asls`, `rolling_mean` |
| `--normalization` | `--method baseline` | `divide` (default), `subtract`, `both` |

The preprocessing decisions travel with the numbers. The CSV carries them on a
`#` comment line, and `--output` also writes a `dff.csv.provenance.json` sidecar:

```bash
head -2 dff.csv
```

```text
# {"operations": [{"kind": "reference_dff", "max_iterations": 50, "method": "irls", "tolerance": 1e-08}], "variable": "dff"}
time_s,signal
```

The default JSON output carries the same `provenance` list, per-channel summary
statistics, and the samples themselves:

```bash
fipha dff recording.csv --quiet | python -c "
import json, sys
result = json.load(sys.stdin)
print(result['units'], result['provenance'])
print(max(value for value in result['samples']['channels']['signal']))
"
```

```text
dF/F [{'kind': 'reference_dff', 'max_iterations': 50, 'method': 'irls', 'tolerance': 1e-08}]
0.24999999995929273
```

The injected 0.25 ΔF/F transient comes back at 0.25.

Writing NWB instead of CSV requires the session start time, because a valid NWB
file records when the session began and this library does not invent metadata:

```bash
fipha dff recording.csv \
  --output session.nwb \
  --session-start-time 2026-01-01T12:00:00+00:00
```

The file holds the raw signal, the raw reference, the processed series in a
`fipha` processing module, and the operation list in a scratch
dataset. It can be read straight back:

```bash
fipha qc session.nwb
```

### `align` — peri-event windows

```bash
fipha align recording.csv \
  --events events.csv \
  --event-id-column event_id \
  --baseline -2 0 \
  --response 0 1
```

Event times are read from a column of the `--events` file. Name the column with
`--event-column` when it is not called `time`; `--event-id-column` supplies
stable identifiers. Formats that carry their own event times — pyPhotometry
digital inputs, Doric digital series, TDT epocs, NWB trials — need no `--events`
at all.

`--normalization` rescales each event by the statistics of *its own* baseline
window: `none` (default) keeps ΔF/F, `baseline_z` divides the mean-centred trace
by the baseline standard deviation, and `robust_z` divides the median-centred
trace by `1.4826 × MAD`. An event whose baseline scale is zero becomes NaN rather
than an arbitrarily large number and is counted in
`events.degenerate_baseline_count`.

```bash
fipha align recording.csv \
  --events events.csv --event-id-column event_id \
  --baseline -2 0 --response 0 1 \
  --normalization baseline_z \
  --format csv
```

```text
event_id,event_time_s,channel,baseline_mean,response_mean,delta,baseline_finite_fraction,response_finite_fraction,disposition
cue-1,20.0,signal,0.0,0.7517564789919531,0.7517564789919531,1.0,1.0,complete
```

Events stay individual observations; nothing is averaged away. The JSON adds a
per-channel `summary` (complete-event count, mean baseline, mean response, mean
delta, SD and SEM) and an `aligned_mean` trace on the common peri-event grid,
sampled at `--rate` (default: the recorded median rate). `disposition` records
whether a window intersected a gap, so exclusions stay visible rather than
implicit.

`--variable signal` aligns the acquired fluorescence directly and skips
preprocessing entirely.

### `transients` — spontaneous events

```bash
fipha transients recording.csv \
  --detector absolute --threshold 0.1 \
  --baseline-duration 2 --baseline-gap 2 --min-distance 2
```

```text
4 transient(s), 1 rejected candidate(s)
  signal: n=4 rate=2.001/min median_amplitude=0.25 analyzed=120 s
```

`--detector` selects the threshold family: `rolling_mad` (default) compares each
candidate to a robust-sigma estimate from the 15-second window around it,
`global_mad` uses one robust sigma per finite run, and `absolute` takes
`--threshold` in the units of the analysed variable. Both MAD families read
`--threshold` as a multiple of `1.4826 * MAD`, so `3` is three Gaussian standard
deviations. Where that estimate degenerates the candidate is rejected rather
than compared against a floor: a flat or quantization-locked window records
`degenerate_noise_scale`, and a window with fewer than three samples records
`insufficient_noise_samples`. `--baseline-duration`,
`--baseline-gap`, `--baseline-statistic`, and `--min-distance` control the
pre-peak baseline and the peak separation. `--bin-width` adds descriptive
long-window count and rate bins, which are a summary of the detections and not a
claim about a tonic component.

The output carries three ledgers: `events` (peak time and value, local baseline,
amplitude, the threshold it had to clear, half-height crossings, rise, fall and
full width at half height, AUC above baseline, and the preceding interval),
`exclusions` (every considered local maximum that was rejected, with the reason),
and `summaries` (per channel: analysed duration, count, rate per minute, and
median amplitude, width, AUC and interval). Every considered local maximum
appears in exactly one of the first two, so they can be counted without
double-counting.

This detector is experimental and deliberately exposes choices that differ across
the literature; see [spontaneous transients](spontaneous-transients.md).

### Options every analysis command shares

| Flag | Meaning |
|---|---|
| `--channel NAME` | restrict to one named channel; repeatable |
| `--output PATH` | write to a file instead of stdout |
| `--format json\|csv` | machine-readable shape (default `json`) |
| `-q`, `--quiet` | suppress the stderr summary |
| `--subject`, `--session` | identifiers recorded in the output provenance |
| `--time-column`, `--signal-column`, `--reference-column` | override column discovery in a delimited table or a Neurophotometrics export |
| `--series` | choose a series by name inside an NWB file |

`--signal-column` and `--reference-column` are repeatable and are paired in the
order given. Writes to `--output` are atomic: a failed write never leaves a
partially updated artifact under its final name.

### Formats read without configuration

Format detection is the same conservative routine the project loader uses. It
never guesses biological identity, only mechanical structure.

| Source | Detected from | Discovery |
|---|---|---|
| Neurophotometrics / Bonsai `.csv` or `.parquet` | a `Timestamp`/`SystemTimestamp` column, a `LedState`/`Flags` column, and `Region*` columns | one channel per ROI column; 470 nm signal with a 415 nm reference where both are present, otherwise 560 nm or signal-only |
| TDT block directory | `.tsq`/`.tev`/`.tnt`/`.tbk` files inside | stream stores named for 465/470/560 nm are signal, 405/415 nm are reference; the first epoc store supplies events |
| Doric `.doric` | extension | HDF5 groups holding both `Values` and `Time`; groups named `AOUT02`, `405` or `415` become references; `DigitalIO` groups become events |
| pyPhotometry `.ppd` | extension | analog 1 is signal, analog 2 the reference; every digital input becomes an event train |
| NWB `.nwb` | extension | the acquired fiber-photometry series, or `--series`; `trials.start_time` supplies events |
| Delimited `.csv`, `.tsv`, `.txt` | extension | a time-like numeric column, then numeric columns named `reference`, `control`, `isosbestic`, `405` or `415` as references and the rest as signal |

When discovery is wrong or ambiguous, name the columns explicitly rather than
letting a heuristic decide — or declare the mapping once in a project TOML and
use `run`, which never guesses at all.

### Error codes

Failures print `error: <code>: <message>` and `hint: <next step>` to stderr and
exit with status 2. The codes marked *shared* are the same stable identifiers the
[pipeline compatibility report](pipeline-compatibility.md) uses.

| Code | Cause |
|---|---|
| `acquisition_source_unreadable` | the path does not exist, or the file cannot be parsed as its detected format |
| `unrecognized_acquisition_format` | the file matches no supported acquisition format |
| `channel_not_found` | `--channel` names a channel the recording does not contain |
| `reference_channel_missing` *(shared)* | `--method reference` on a recording with no reference channel |
| `baseline_variable_missing` *(shared)* | the analysed variable or a usable signal column is absent |
| `event_summary_variable_missing` *(shared)* | the peri-event windows cannot be summarized as declared |
| `event_times_missing` | no `--events` file and no event times in the source |
| `invalid_time_axis` *(shared)* | the timestamps are not finite and strictly increasing |
| `invalid_event_window` | a `--baseline` or `--response` pair does not start before it stops |
| `asls_requires_regular_sampling` *(shared)* | AsLS on a jittered clock; resample first, or choose another baseline |
| `nwb_session_start_time_missing` | NWB output without a timezone-aware `--session-start-time` |

Each hint names the flag or file to change. For example:

```bash
fipha dff recording.csv --channel absent
```

```text
error: channel_not_found: recording.csv has no channel named absent
hint: available channels: signal
```

## Reproducible projects

The project commands run the declared analysis that produces publishable
evidence. They do not accept inferential assumptions silently.

### Walkthrough

The example project lives in the repository, so start from a checkout:

```bash
git clone https://github.com/aeronjl/fipha.git
cd fipha
uv sync --all-extras
uv run python examples/tabular_project/make_data.py
```

Inspect schemas, file fingerprints, missingness, sampling, and event-clock
coverage without fitting an analysis:

```bash
uv run fipha inspect examples/tabular_project/project.toml
```

Execute the declared workflow:

```bash
uv run fipha run examples/tabular_project/project.toml
```

Execute every explicitly declared robustness workflow:

```bash
uv run fipha multiverse examples/tabular_project/project.toml
```

Install the `nwb` optional dependencies when the project declares NWB output
(the package is not on PyPI; see [Install](getting-started/install.md)):

```bash
pip install "fipha[nwb] @ git+https://github.com/aeronjl/fipha.git"
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

### Project file

[`examples/tabular_project/project.toml`](https://github.com/aeronjl/fipha/blob/main/examples/tabular_project/project.toml)
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
[`examples/feedback-analysis.toml`](https://github.com/aeronjl/fipha/blob/main/examples/feedback-analysis.toml) and the
[peri-event inference contract](peri-event-inference.md).

NWB export is opt-in because valid files require metadata the library must not
invent. Each session declares a timezone-aware `session_start_time`; `[nwb]`
declares `session_description` and an identifier prefix. Each file contains raw
signal/reference series, the analysed processed series, event trials, subject and
session identity, operation provenance, session QC and preflight JSON, and the
complete project and population-analysis records. Every NWB file is validated
before its atomic publication and included in `manifest.json` by SHA-256.
Signals are written as community `ndx-fiber-photometry` response series. A project
file declares no optical hardware, so the CLI writes them without a
`FiberPhotometryTable` region rather than inventing wavelengths, indicators or
devices; supply `acquisition_metadata` to `export_project_nwb()` from Python to
populate the table. See the [NWB data model](nwb-data-model.md).

When `[nwb]` and `[multiverse]` are both declared, the `multiverse` command also
exports one validated NWB file per session. Each file stores raw acquisition data
once and one processed time series for the explicitly selected reference universe.
It does not duplicate full signals for every workflow. Scratch datasets retain the
complete multiverse result, stable universe IDs and choices, failures and declared
incompatibilities, unit-local robustness summary and thresholds, normalized
project, metadata readiness, session preflight, and reference-workflow QC. The
NWB identifier is labelled `multiverse`, and every file is hashed in the manifest.

### Reading completed evidence

The supported Python API reads either a complete output directory or one exported
NWB file through the same normalized object:

```python
from fipha.results import read_project_evidence

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
See the [evidence reader contract](evidence-reader.md).

Compare any two readable bundles from the command line:

```bash
uv run fipha compare artifacts-a artifacts-b
uv run fipha compare artifacts-a session.nwb \
  --absolute-tolerance 1e-8 --output reproducibility.json
```

Markdown is printed by default. An `.json` destination writes the versioned
machine artifact; other extensions receive Markdown. Comparison reports byte
identity, project fingerprint agreement, scientific comparability, and semantic
differences classified as configuration, specification, data, quality, outcome,
execution, or provenance. See the
[reproducibility comparison contract](reproducibility-comparison.md).

### Robustness configuration

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

### Analysis contract

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

## Publishing evidence

These commands operate on a completed artifact directory, not on raw recordings.

### Signing a publication bundle

Sign only after a bundle is complete and its manifest verifies:

```bash
uv run fipha sign artifacts \
  --key ~/.ssh/id_ed25519 \
  --identity scientist@example.org
```

This creates `publication-attestation.json` and the detached
`publication-attestation.json.sig`. Existing signatures are not replaced unless
`--force` is explicit. Private keys are never copied into the bundle.

Verifiers maintain an OpenSSH `allowed_signers` file outside the evidence bundle:

```text
scientist@example.org namespaces="fipha-publication@aeronjl.github.io" ssh-ed25519 AAAA...
```

Then verify signer authorization, signature bytes, the exact manifest digest, and
the project fingerprint:

```bash
uv run fipha verify-signature artifacts \
  --allowed-signers allowed_signers
```

The identity and namespace are signed. A readable self-signature is insufficient:
the identity must match a trusted key in `allowed_signers`. See the
[publication signing contract](publication-signing.md).

### Creating a DOI/repository deposit

Create one strict metadata record (all fields are required; optional values use
empty arrays or `null`):

```json
{
  "artifact_type": "fipha_archive_metadata",
  "schema_version": "1",
  "title": "Reward photometry analysis evidence",
  "description": "Analysis, provenance, QC, and robustness results.",
  "creators": [
    {
      "name": "Laffere, Aeron",
      "affiliation": "Example University",
      "orcid": "0000-0002-1825-0097"
    }
  ],
  "publication_date": "2026-07-27",
  "publisher": "Zenodo",
  "license": "cc-by-4.0",
  "keywords": ["fiber photometry", "reproducibility"],
  "related_identifiers": [],
  "resource_type": "Dataset",
  "language": "en"
}
```

Then create and independently verify a deterministic deposit:

```bash
uv run fipha archive artifacts \
  --metadata archive-metadata.json \
  --output reward-analysis-deposit.zip
uv run fipha verify-archive reward-analysis-deposit.zip
```

The archive contains verified evidence, a checksum inventory, the neutral source
metadata, and generated DataCite and Zenodo metadata. It is not uploaded or
published automatically. See the
[archival deposition contract](archive-deposition.md).

Upload the verified package as an unpublished sandbox draft:

```bash
export ZENODO_SANDBOX_TOKEN="..."
uv run fipha zenodo-draft reward-analysis-deposit.zip
```

The JSON receipt records the environment, draft ID and URL, archive and project
fingerprints, filename, byte size, and `submitted = false`; it contains no token.
Production draft creation requires `--production`. fipha exposes no DOI
publication action.

## Current boundary

The analysis commands read one file at a time and make no inferential claim: they
report diagnostics, ΔF/F, per-event windows, and transient ledgers. Group
comparisons, uncertainty, and robustness live in the project commands, whose v0.1
surface handles the categorical, within-animal scalar event contrast supported by
`EventAnalysis`, with either schema-first tabular files or explicitly mapped TDT
blocks. Multiverse configuration currently varies reference preprocessing,
signal-only baseline recipes, normalization, and response windows. It does not
yet expose arbitrary designs or method-specific reference-regression parameters.
