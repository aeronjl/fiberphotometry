# fipha

Auditable fiber photometry analysis in Python — dF/F, peri-event and transient
analysis, and NWB provenance from raw signals to inference across animals, with
every choice recorded.

> **Status: pre-alpha.** Never released. `0.1.0.dev0`, installable only from Git.
> The API and numerical methods are **not yet validated for scientific use**.

## Install

Not on PyPI. Install from the repository:

```bash
pip install "fipha @ git+https://github.com/aeronjl/fipha.git"
```

Format readers, plotting, and statistics are opt-in extras (`acquisition`,
`tdt`, `nwb`, `behavior`, `plots`, `stats`). See the
[install guide](https://aeronjl.github.io/fipha/getting-started/install/).

## Quick start

```python
import numpy as np
from fipha import (
    align_events,
    assess_recording,
    make_recording,
    reference_dff,
)

recording = make_recording(
    time=time,  # seconds, 1-D
    signal=signal,  # e.g. 470 nm
    reference=reference,  # e.g. 405 nm isosbestic
    channel_names=["DMS"],
    subject="mouse-01",
    session="day-01",
)

corrected = reference_dff(recording)  # fitted-reference dF/F, raw data retained
qc = assess_recording(recording)  # outcome-blind quality control
epochs = align_events(  # events remain a labelled dimension
    corrected, event_times, window=(-2.0, 6.0), rate=100.0
)
```

Runnable, self-contained versions using synthetic data:

- [Your first dF/F trace](https://aeronjl.github.io/fipha/getting-started/first-dff-trace/)
- [Your first peri-event plot](https://aeronjl.github.io/fipha/getting-started/first-peri-event-plot/)

## The product workflow

The scientist-facing API turns labelled sessions into an auditable event contrast
and a self-contained HTML evidence report:

```python
from fipha import EventAnalysis, EventSession, Preprocessing

session = EventSession.from_arrays(recording, event_times, conditions)
study = EventAnalysis(
    (session,),
    numerator="correct",
    denominator="incorrect",
    channel="DMS",
    preprocessing=Preprocessing.reference(method="irls"),
)
plan = study.plan()
result = study.run(acknowledged_assumptions=plan.required_assumptions)
result.write_html("feedback-report.html")
```

The explicit planning step is intentional: execution cannot silently accept
inferential assumptions on the scientist's behalf. See the
[workflow guide](docs/product-workflow.md) and the runnable
[`examples/event_analysis_report.py`](examples/event_analysis_report.py).

The same analysis can be driven from a TOML project file rather than Python:

```bash
fipha inspect project.toml
fipha run project.toml
```

See the [configuration-first CLI](docs/cli.md). Ordinary lab exports enter through
the [generic tabular import contract](docs/tabular-import.md), TDT blocks through
an [explicit stream and epoc mapping](docs/tdt-import.md), and Doric,
Neurophotometrics and pyPhotometry files through
[typed native readers](docs/native-acquisition-import.md). Signal, reference,
channel, timestamp, and event roles are always declared, never inferred from
column order or filenames.

## Why this project?

Fiber photometry analysis remains fragmented across approachable but constrained
applications and specialised statistical implementations. Important choices — how
to fit a reference channel, define a baseline, handle artefacts, aggregate trials,
and preserve the animal as the experimental unit — can materially change results.

This project provides:

- a canonical labelled representation for signals, events, subjects, and sessions;
- modular preprocessing with complete parameter and provenance records;
- acquisition adapters at the boundary, including NWB, TDT, and native
  acquisition-system files;
- schema-first CSV/TSV recording and event import with source fingerprints;
- typed interoperability with pose, state-discovery, ethogram, and longitudinal
  behavior packages rather than duplicate behavior-analysis implementations;
- event alignment that preserves the nested experimental design;
- several clearly labelled inferential approaches rather than one hidden default;
- [robustness multiverses](docs/multiverse-contract.md) that run one fixed
  estimand under every declared preprocessing alternative and report the whole
  ledger, failures included;
- simulation and public-data benchmarks with known or independently checkable
  answers.

**[Read the documentation](https://aeronjl.github.io/fipha/)** to choose
a workflow by scientific question, browse the
[capability matrix](https://aeronjl.github.io/fipha/methods/capability-matrix/),
and run worked public-data examples.

The prospective v0.1 compatibility boundary is documented in the
[API stability policy](docs/api-stability.md) and the
[artifact schema policy](docs/artifact-schemas.md). Importability alone is not a
stability promise during development.

## Evidence and validation

Benchmark protocols are frozen before the analysis is run, and failed criteria are
retained rather than removed. [`benchmarks/`](benchmarks/) holds those protocols
and their unedited outcomes — for example
[`protocol-v0.1.md`](benchmarks/protocol-v0.1.md) and
[`results-v0.1.md`](benchmarks/results-v0.1.md), which include an expected failure
case where the reference channel contains biological signal, and a failed headline
criterion.

Narrative write-ups of individual studies live in [`research/`](research/). They
are internal records rather than user documentation, and several report negative
or mixed results:

- [`validation-report-v0.1.md`](research/validation-report-v0.1.md) — the first
  DANDI and IBL numerical findings.
- [`dandi-000351-parity-v0.2.md`](research/dandi-000351-parity-v0.2.md) — a
  retained structural alignment failure and a failed timestamp-aligned
  reconstruction.
- [`ibl-feedback-prospective-v0.2.md`](research/ibl-feedback-prospective-v0.2.md)
  — an 18-animal expansion stopped at its frozen readiness gate because the new
  sessions lack labelled reference-channel rows.
- [`ibl-regularized-asls-results-v0.1.md`](research/ibl-regularized-asls-results-v0.1.md)
  — stable event summaries but a failed aggregate whole-trace gate.
- [`control-free-benchmark-v0.2.md`](research/control-free-benchmark-v0.2.md) —
  why signal-only bleaching correction is still not in the recommended pipeline.

A formative usability study has been **designed and frozen but not run**: zero
participant sessions have taken place, and no results exist. The protocol,
moderator guide, response sheet, and scoring key are in
[`planning/usability/`](planning/usability/README.md), and the frozen HTML stimulus
they refer to is
[`docs/usability/usability-study-stimulus.html`](docs/usability/usability-study-stimulus.html).

Project-management material — roadmap, tool landscape, scientific design notes,
and readiness audits — is in [`planning/`](planning/). Consequential project
judgments are indexed in [`docs/decisions/README.md`](docs/decisions/README.md).

## Development

Python and dependencies are managed by `uv`:

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv sync --group docs
uv run --group docs mkdocs serve
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing scientific methods.

## Scientific position

fipha will not market a single correction or inferential method as
universally correct. Defaults must be justified against simulations, controls,
and public datasets; outputs must expose assumptions and diagnostics. Raw data is
never silently overwritten.

## License

BSD-3-Clause.
