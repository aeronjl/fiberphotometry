# FiberPhotometry

Composable, provenance-aware fiber photometry analysis in Python.

FiberPhotometry is an early-stage scientific library for moving from acquired
fluorescence signals to auditable preprocessing, event-aligned data, and valid
inference across animals. It is being designed as a library rather than another
closed analysis GUI: each scientific choice should be explicit, replaceable,
recorded, and testable.

> **Status:** pre-alpha research scaffold. The API and numerical methods are not
> yet validated for scientific use.

## Why this project?

Fiber photometry analysis remains fragmented across approachable but constrained
applications and specialised statistical implementations. Important choices—how
to fit a reference channel, define a baseline, handle artefacts, aggregate trials,
and preserve the animal as the experimental unit—can materially change results.

This project aims to provide:

- a canonical labelled representation for signals, events, subjects, and sessions;
- modular preprocessing with complete parameter and provenance records;
- acquisition adapters at the boundary, including NWB;
- event alignment that preserves the nested experimental design;
- several clearly labelled inferential approaches rather than one hidden default;
- simulation and public-data benchmarks with known or independently checkable answers.

The first benchmark protocol was frozen before aggregate analysis in
[`benchmarks/protocol-v0.1.md`](benchmarks/protocol-v0.1.md). It includes an
expected failure case where the reference channel contains biological signal.
The unedited outcomes—including a failed headline criterion—are reported in
[`benchmarks/results-v0.1.md`](benchmarks/results-v0.1.md).

A bounded remote integration test streams small slices from the 18.4 GB NWB file
in DANDI 001084 without downloading the asset. See
[`docs/dandi-001084-integration.md`](docs/dandi-001084-integration.md).
The first DANDI and IBL numerical findings are in
[`docs/validation-report-v0.1.md`](docs/validation-report-v0.1.md).
The expanded channel-QC audit and frozen seven-scenario preprocessing benchmark
are reported in [`docs/ibl-qc-cohort-v0.1.md`](docs/ibl-qc-cohort-v0.1.md) and
[`benchmarks/results-v0.2.md`](benchmarks/results-v0.2.md).
The event-aware diagnostic follow-up, including a retained failed lag detector,
is in [`benchmarks/results-v0.3.md`](benchmarks/results-v0.3.md).

The scientific scope and competing methods are documented in
[`docs/scientific-design.md`](docs/scientific-design.md). The existing-tool audit is
in [`docs/landscape.md`](docs/landscape.md), and the extraction assessment of the
author's earlier work is in [`docs/extraction-audit.md`](docs/extraction-audit.md).

## Prototype API

```python
import numpy as np

from fiberphotometry import (
    assess_recording,
    align_events,
    make_recording,
    reference_dff,
)

time = np.arange(0, 60, 0.1)
recording = make_recording(
    time=time,
    signal=np.sin(time),
    reference=0.2 * np.sin(time) + 1,
    subject="mouse-01",
    session="session-01",
)

corrected = reference_dff(recording)
qc = assess_recording(recording)
epochs = align_events(corrected, [10, 20, 30], window=(-2, 5), rate=10)
```

Event-aware QC requires the experimental event times rather than guessing them:

```python
from fiberphotometry import assess_event_confounds

event_qc = assess_event_confounds(recording, [10, 20, 30])
```

Diagnostic figures are optional: install with `uv sync --extra plots`, then use
`fiberphotometry.plotting.plot_event_diagnostics`.

The experimental inference schema keeps arbitrary observation metadata open
while explicitly declaring units, nesting, factor assignment, estimands, and
exchangeability. See
[`docs/inference-design-v0.1.md`](docs/inference-design-v0.1.md).
The first frozen inference benchmark demonstrates the pseudoreplication failure
of trial-level resampling in [`benchmarks/results-v0.4.md`](benchmarks/results-v0.4.md).

## Development

Python and dependencies are managed by `uv`:

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing scientific methods.

## Scientific position

FiberPhotometry will not market a single correction or inferential method as
universally correct. Defaults must be justified against simulations, controls,
and public datasets; outputs must expose assumptions and diagnostics. Raw data is
never silently overwritten.

## License

BSD-3-Clause.
