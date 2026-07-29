# fipha

**A Python library for fiber photometry: from raw signals to dF/F to inference
across animals — with every choice recorded.**

```python
import numpy as np
from fipha import align_events, make_recording, reference_dff

recording = make_recording(
    time=time,  # seconds, 1-D
    signal=signal,  # e.g. 470 nm
    reference=reference,  # e.g. 405 nm isosbestic
    channel_names=["DMS"],
    subject="mouse-01",
    session="day-01",
)

corrected = reference_dff(recording)  # fitted-reference dF/F
epochs = align_events(  # events stay a dimension
    corrected, event_times, window=(-2.0, 6.0), rate=100.0
)
```

That is the whole first mile.
[Your first dF/F trace](getting-started/first-dff-trace.md) runs it end to end on
synthetic data in about fifteen lines — no data files, no repository checkout.

!!! warning "Development status"

    Pre-alpha. Never released; installable only
    [from Git](getting-started/install.md). The API and numerical methods are not
    yet validated for scientific use. The
    [capability matrix](methods/capability-matrix.md) states exactly what
    *supported* and *experimental* mean here — neither is a claim of scientific
    validation.

## Start here

1. [**Install**](getting-started/install.md) — not on PyPI; the working command
   and what each extra is for.
2. [**Your first dF/F trace**](getting-started/first-dff-trace.md) — build a
   recording, correct it against the reference channel, read the QC.
3. [**Your first peri-event plot**](getting-started/first-peri-event-plot.md) —
   the standard event-aligned figure, and why its error band is not an
   animal-level claim.
4. [**First event analysis**](product-workflow.md) — the real workflow: named
   conditions, several animals, an auditable contrast, an HTML evidence report.

## Why this rather than a script

Fiber photometry results move when preprocessing moves. How the reference channel
is fitted, where the baseline sits, which artefacts are excluded, how trials are
aggregated, and whether the animal or the trial is treated as the experimental
unit can each change the answer.

fipha keeps those choices explicit and attached to the result:

- one canonical labelled representation for signals, events, subjects, sessions,
  and channels, so nothing downstream has to guess what a column meant;
- preprocessing that records its parameters and never overwrites raw data;
- typed import boundaries where channel roles and event semantics are declared
  rather than inferred from column order or filenames;
- inference that keeps the animal as the experimental unit instead of treating
  trials as independent replicates;
- robustness multiverses that run one fixed estimand under every declared
  preprocessing alternative and report the whole ledger, failures included.

## Find your question

| I want to… | Start with |
|---|---|
| Get a dF/F trace out of my data | [Your first dF/F trace](getting-started/first-dff-trace.md) |
| Draw an event-aligned figure | [Your first peri-event plot](getting-started/first-peri-event-plot.md) |
| Run an event-aligned comparison across animals | [First event analysis](product-workflow.md) |
| Analyze CSV/TSV exports without rewriting code | [Configuration-first CLI](cli.md) |
| Import a TDT block | [TDT import](tdt-import.md) |
| Work from public NWB data | [DANDI tutorial](tutorials/dandi-000971-reward-multiverse.md) |
| Combine DeepLabCut, SLEAP, MoSeq or BORIS with photometry | [Behavioral ecosystem tutorial](tutorials/behavior-tool-interoperability.md) |
| Detect spontaneous transients | [Spontaneous transients](spontaneous-transients.md) |
| Separate calibrated optical contributions | [Wavelength-aware optical unmixing](optical-unmixing.md) |
| Test or invert a declared sensor response | [Sensor-kinetic modeling](sensor-kinetic-modeling.md) |
| Analyze a coordinate-mapped multi-fiber array | [Coordinate-aware dense arrays](spatial-network.md) |
| Model neural summaries across learning | [Unspool interoperability](unspool-interoperability.md) |
| Describe a long recording at several time scales | [Multiscale long-duration summaries](multiscale-long-duration.md) |
| Compare reasonable preprocessing choices | [Robustness multiverses](multiverse-contract.md) |
| Understand a refusal or error code | [Compatibility and error codes](pipeline-compatibility.md) |
| Choose an inferential method | [Methods catalog](methods/index.md) |
| See what the package cannot yet do | [Capability matrix](methods/capability-matrix.md) |
| Produce verifiable publication evidence | [Publication workflow](publication-signing.md) |

## The evidence path

<figure class="doc-figure doc-figure--wide">
  <img src="assets/evidence-path.svg" alt="Five linked stages carry acquired photometry signals through explicit preprocessing, animal-level evidence, robustness analysis, and a verifiable publication object.">
  <figcaption><strong>The evidence path.</strong> Signal identity, clocks, events, processing choices, exclusions, uncertainty, and provenance remain attached to the final scientific claim.</figcaption>
</figure>

The project does not claim that one preprocessing or statistical method is always
correct. It makes the choice, its assumptions, and its sensitivity visible.
