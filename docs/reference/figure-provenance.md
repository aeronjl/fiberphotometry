# Figure provenance

Figures in this site are scientific communication objects. This register separates
conceptual explanations from empirical and benchmark evidence so readers do not mistake a
schematic for a result.

## Generated conceptual figures

The following SVGs are generated deterministically by
[`scripts/plot_documentation_figures.py`](https://github.com/aeronjl/fiberphotometry/blob/main/scripts/plot_documentation_figures.py):

| Figure | Purpose |
|---|---|
| `evidence-path.svg` | Trace scientific identity from acquisition to archival evidence |
| `preprocessing-sequence.svg` | Separate acquired channels, fitted reference, and corrected output |
| `qc-gating.svg` | Show why QC blocks inference without deleting observations |
| `peri-event-inference.svg` | Distinguish animal curves, pointwise intervals, and simultaneous bands |
| `multiverse-robustness.svg` | Explain fixed-estimand robustness with a complete execution ledger |
| `method-question-map.svg` | Route scientific questions to distinct method contracts |
| `event-kernel-validation.svg` | Connect overlapping-event estimation to held-out-group validation |
| `publication-provenance.svg` | Separate verification, comparison, signing, and deposition |

These figures use synthetic or schematic values selected for explanation. They are not
estimates from an experiment. Rebuild them with:

```bash
uv run --group docs python scripts/plot_documentation_figures.py
```

## Public-data evidence figures

| Figure | Source and claim boundary |
|---|---|
| `dandi-000971-reward-multiverse-v0.1.svg` | Frozen eight-universe animal-level robustness result generated from the committed DANDI 000971 result JSON |
| `dandi-000971-event-kernels-v0.2.png` | Checksum-pinned public DANDI 000971 benchmark; pooled DMS/DLS kernels and grouped-jackknife sensitivity intervals |
| `ibl-feedback-signal-only-subtract-v0.3.2.svg` | Frozen IBL signal-only multiverse result for subtraction workflows |
| `ibl-feedback-signal-only-divide-v0.3.2.svg` | Frozen IBL signal-only multiverse result for division workflows |
| `ibl-feedback-specification-curve-v0.1.svg` | Frozen nine-universe IBL feedback specification curve |

The surrounding result pages define the cohort, denominator, experimental unit, frozen
protocol, and limitations. Versioned empirical figures should be regenerated only from
their corresponding benchmark script and pinned inputs.

The DANDI reward-multiverse figure can be regenerated without downloading source
data or rerunning the scientific analysis:

```bash
uv run --group docs python scripts/plot_public_evidence_figures.py
```

## Review checklist

For every new or changed figure, verify that its page:

1. labels the display as conceptual, simulated, benchmark, or public-data evidence;
2. supplies alternative text that communicates the conclusion without colour;
3. names the experimental unit and uncertainty denominator for empirical displays;
4. links the generating script or frozen result; and
5. states a claim no stronger than the source evidence supports.
