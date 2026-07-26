# Tutorial: raw public NWB to an animal-level robustness report

This is FiberPhotometry's canonical end-to-end product tutorial. It starts with
six immutable public NWB files, validates their acquisition and event structure,
runs a declared primary analysis and eight-universe preprocessing multiverse, and
writes a checksummed evidence bundle.

The tutorial reanalyzes a bounded subset of
[DANDI:000971](https://doi.org/10.48324/dandi.000971/0.260213.1851), the public data
for [Seiler et al. (2022)](https://doi.org/10.1016/j.cub.2022.01.055). It asks a
descriptive question: across these six animals, how different is the DMS response
to rewarded versus unrewarded active nose pokes, and how sensitive is that answer
to defensible preprocessing and response-window choices?

It does **not** test phenotype differences, estimate phenotype prevalence, or
independently confirm the source publication. Read the frozen
[scientific protocol](../../benchmarks/protocol-dandi-000971-tutorial-v0.1.md)
before interpreting the output.

## Install

The repository uses its locked `uv` environment. No global Python is required:

```bash
uv sync --all-extras --locked
```

## Run

```bash
uv run python examples/dandi_000971_reward_tutorial.py
```

The first run downloads 2.20 GB into
`~/Library/Caches/fiberphotometry/dandi-000971-tutorial`. Every file is checked
against its frozen byte size and SHA-256 digest. Repeated runs reuse only verified
files.

To put the cache or artifacts elsewhere:

```bash
uv run python examples/dandi_000971_reward_tutorial.py \
  --cache-dir /path/to/cache \
  --output-dir /path/to/artifacts
```

## Step 1: inspect before inference

`preflight.json` is written before any multiverse result. For every animal it
records:

- the immutable DANDI asset and verified digest;
- source and analysis sampling rates;
- all active nose pokes;
- rewarded and unrewarded boundary-complete events;
- events excluded solely because their full `[-5, 1.5]` second window was not
  acquired;
- structural failures, which are retained without replacement.

Reward labels are not inferred from fluorescence. The NWB conversion exposes
reward timestamps separately, and the adapter requires each reward to match
exactly one active nose-poke timestamp.

## Step 2: understand the primary analysis

The primary workflow applies a fourth-order 3 Hz zero-phase filter to DMS calcium
and isosbestic measurements, robustly fits the reference with IRLS, calculates
fitted-reference dF/F, and summarizes each event as its 0-1.5 second mean minus its
-5-0 second baseline mean.

Events are averaged within condition and animal before the rewarded-minus-
unrewarded contrast is inferred. Six animals—not hundreds of events—define the
population uncertainty. `primary-analysis.json` records the paired interval,
assumptions, package version, timestamp, input fingerprint, and inference engine.

## Step 3: read the multiverse as a robustness analysis

The same animals, events, labels, estimand, and inferential unit are used in all
eight universes:

| Decision | Alternatives |
|---|---|
| Reference correction | OLS or robust IRLS |
| Filtering | no additional filter or fourth-order 3 Hz zero-phase filter |
| Response window | 0-0.5 s or 0-1.5 s |

`multiverse.json` retains successes and every blocked, failed, or incompatible
workflow. `report.html` shows the reference estimate, estimate range, direction
stability, decision summaries, and leave-one-animal-out sensitivity. The number of
nominally significant universes is deliberately not the headline.

## Step 4: verify the evidence bundle

The result directory contains:

```text
dandi-000971-tutorial-artifacts/
├── preflight.json
├── primary-analysis.json
├── multiverse.json
├── report.html
└── manifest.json
```

`manifest.json` records the package version, scientific protocol, completion
status, and SHA-256 digest of every result artifact. A collaborator can rerun the
same command against the same immutable source assets and compare those machine-
readable objects. Execution timestamps may differ; scientific specifications,
input fingerprints, estimates, and deterministic inferential results should not.

## What to change for your own study

Replace only the acquisition adapter and event loader at first. Preserve the
canonical `RecordingInput` boundary, declare the experimental units and estimand,
and build a bounded multiverse before looking at aggregate outcomes. Do not copy
the six-animal cohort, windows, filter, or reference method as universal defaults:
they are defensible choices for this worked example, not rules for all indicators,
tasks, or acquisition systems.
