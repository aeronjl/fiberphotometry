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
Consequential project judgments are indexed in
[`docs/decisions/README.md`](docs/decisions/README.md), with non-normative work in
progress kept separately under [`docs/drafts/`](docs/drafts/).

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

Multiverse results can be displayed with
`fiberphotometry.plotting.plot_specification_curve`; the frozen IBL example is
rebuilt directly from its JSON artifact with
`uv run python scripts/plot_ibl_feedback_multiverse.py`.

Experimental control-free bleaching correction is available through
`fiberphotometry.baseline_dff`. Its limitations and frozen simulation results are
reported in [`docs/control-free-benchmark-v0.1.md`](docs/control-free-benchmark-v0.1.md);
it is not yet part of the recommended typed pipeline.
The first frozen independent-control pilot on published DANDI:000971 data produced
a mixed, non-promotional result; see
[`docs/dandi-000971-control-v0.1.md`](docs/dandi-000971-control-v0.1.md).
The DANDI:000351 raw-to-archived audit retained both a structural alignment failure
and a failed timestamp-aligned reconstruction; see
[`docs/dandi-000351-parity-v0.2.md`](docs/dandi-000351-parity-v0.2.md).
The prospective 18-animal IBL expansion stopped at its frozen readiness gate because
the new sessions lack labelled reference-channel rows; see
[`docs/ibl-feedback-prospective-v0.2.md`](docs/ibl-feedback-prospective-v0.2.md).
The follow-up
[`channel-provenance audit`](docs/ibl-new-cohort-channel-provenance-v0.1.md)
establishes that the held-out recordings are signal-only; the proposed v0.3
workflow remains an explicitly non-normative
[`design draft`](docs/drafts/ibl-feedback-signal-only-v0.3-design.md).
That design has now been superseded by the outcome-blind
[`frozen v0.3 protocol`](benchmarks/protocol-ibl-feedback-signal-only-v0.3.md),
whose readiness gate retained 383 sessions from 18 held-out animals; fluorescence
contrasts have not yet been calculated.
The follow-up baseline-fidelity and normalization study is in
[`docs/control-free-benchmark-v0.2.md`](docs/control-free-benchmark-v0.2.md).

The experimental inference schema keeps arbitrary observation metadata open
while explicitly declaring units, nesting, factor assignment, estimands, and
exchangeability. See
[`docs/inference-design-v0.1.md`](docs/inference-design-v0.1.md).
The first frozen inference benchmark demonstrates the pseudoreplication failure
of trial-level resampling in [`benchmarks/results-v0.4.md`](benchmarks/results-v0.4.md).
Broader scalar interval calibration and independent MixedLM point-estimate parity
are reported in [`benchmarks/results-v0.5.md`](benchmarks/results-v0.5.md).
The larger adversarial calibration, which retains failed coverage and power
criteria, is in [`benchmarks/results-v0.6.md`](benchmarks/results-v0.6.md).
Finite-sample Welch coverage and conditional power guidance are in
[`benchmarks/results-v0.7.md`](benchmarks/results-v0.7.md).
The first executable public-data analysis is reported, with its post-hoc and
four-animal limitations, in
[`docs/ibl-feedback-analysis-v0.1.md`](docs/ibl-feedback-analysis-v0.1.md).
The typed end-to-end composition and its explicit QC-gating behavior are
documented in [`docs/pipeline-v0.1.md`](docs/pipeline-v0.1.md).
The first resampling/filtering implementation benchmark, including explicit gap
and edge behavior, is in
[`benchmarks/results-v0.8.md`](benchmarks/results-v0.8.md).
The typed multiverse contract and its first adversarial engine benchmark are in
[`docs/multiverse-contract-v0.1.md`](docs/multiverse-contract-v0.1.md) and
[`benchmarks/results-v0.9.md`](benchmarks/results-v0.9.md).
The first public-data multiverse is reported, with its post-hoc limitations, in
[`docs/ibl-feedback-multiverse-v0.1.md`](docs/ibl-feedback-multiverse-v0.1.md).

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
