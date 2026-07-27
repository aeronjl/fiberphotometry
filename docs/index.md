# FiberPhotometry

**Auditable fiber-photometry analysis from acquired signals to inference across
animals.**

FiberPhotometry is a Python library and command-line workflow for scientists who
need to understand how preprocessing choices affect their result—not simply obtain
one corrected trace. It preserves subjects, sessions, events, channels, exclusions,
parameters, and uncertainty throughout the analysis.

!!! warning "Development status"

    This is a pre-release research tool. The documentation distinguishes
    **supported**, **experimental**, **planned**, and **out-of-scope** methods.
    Experimental availability is not a claim of scientific validation.

## Find your question

| I want to… | Start with |
|---|---|
| Run an event-aligned comparison across animals | [First event analysis](product-workflow-v0.1.md) |
| Analyze CSV/TSV exports without rewriting code | [Configuration-first CLI](cli-v0.1.md) |
| Import a TDT block | [TDT import](tdt-import-v0.1.md) |
| Work from public NWB data | [DANDI tutorial](tutorials/dandi-000971-reward-multiverse.md) |
| Compare reasonable preprocessing choices | [Robustness multiverses](multiverse-contract-v0.1.md) |
| Choose an inferential method | [Methods catalog](methods/index.md) |
| See what the package cannot yet do | [Capability matrix](methods/capability-matrix.md) |
| Produce verifiable publication evidence | [Publication workflow](publication-signing-v0.1.md) |

## The evidence path

```text
raw / tabular / TDT / NWB
        ↓
schema and metadata preflight
        ↓
QC → resampling → filtering → correction
        ↓
event coverage and animal-aware analysis
        ↓
declared robustness multiverse
        ↓
JSON / HTML / NWB evidence bundle
        ↓
comparison → signature → archival deposit
```

The project does not claim that one preprocessing or statistical method is always
correct. It makes the choice, its assumptions, and its sensitivity visible.
