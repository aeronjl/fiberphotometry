# Figure provenance

Figures in this site are scientific communication objects. This register separates
conceptual explanations from empirical and benchmark evidence so readers do not mistake a
schematic for a result.

All generated figures follow the [publication-quality figure standard](figure-style.md).
Worked examples separately declare their relationship to exact
[source-paper figures](../tutorials/paper-figure-roadmap.md).

## Generated conceptual figures

The following SVGs are generated deterministically by
[`scripts/plot_documentation_figures.py`](https://github.com/aeronjl/fiberphotometry/blob/main/scripts/plot_documentation_figures.py):

| Figure | Purpose |
|---|---|
| `evidence-path.svg` | Trace scientific identity from acquisition to archival evidence |
| `preprocessing-sequence.svg` | Separate acquired channels, fitted reference, and corrected output |
| `qc-gating.svg` | Show why QC blocks inference without deleting observations |
| `peri-event-inference.svg` | Distinguish animal curves, pointwise intervals, and simultaneous bands |
| `population-inference-boundary.svg` | Materialize session and animal estimates before paired or independent population inference |
| `population-interaction-boundary.svg` | Form repeated-condition contrasts within animals before comparing disjoint groups |
| `multiverse-robustness.svg` | Explain fixed-estimand robustness with a complete execution ledger |
| `method-question-map.svg` | Route scientific questions to distinct method contracts |
| `event-kernel-validation.svg` | Connect overlapping-event estimation to held-out-group validation |
| `predictor-family-contributions.svg` | Distinguish literal family drops, paired held-out groups, and predictive sensitivity |
| `variable-duration-kernels.svg` | Separate physical bout duration, normalized progress, and full-denominator design support |
| `publication-provenance.svg` | Separate verification, comparison, signing, and deposition |

These figures use synthetic or schematic values selected for explanation. They are not
estimates from an experiment. Rebuild them with:

```bash
uv run --group docs python scripts/plot_documentation_figures.py
```

The following hand-authored SVGs are deterministic conceptual schematics committed
directly with their method pages:

| Figure | Purpose |
|---|---|
| `gap-aware-spectral-contract.svg` | Show that gaps and state boundaries partition valid spectral evidence |
| `multiscale-long-duration-contract.svg` | Show named physical-time scales, acceptance evidence, and window-to-animal aggregation without biological labels |
| `multisignal-evidence-contract.svg` | Separate paired-signal identity, optical review, association, and animal inference |
| `spatial-network-contract.svg` | Separate declared array geometry, gap-aware edge evidence, within-session spatial summaries, and edge-to-session-to-mouse inference |
| `sensor-kinetic-modeling-contract.svg` | Separate descriptive kinetics from executable models, forward prediction from gated inversion, and numerical reconstruction from biological validity |
| `optical-unmixing-contract.svg` | Separate independent matrix identification, pre-outcome gates, pattern-specific application, and reconstruction diagnostics |
| `optical-validity-contract.svg` | Separate prospective pulse masks, observed artifact diagnostics, and versioned sensor-validity gates |
| `transient-product-evidence.svg` | Separate threshold calibration, outcome detection, native cutouts, waveform QC, and quantification |

## Public-data evidence figures

| Figure | Source and claim boundary |
|---|---|
| `dandi-000971-reward-multiverse-v0.1.svg` | Frozen eight-universe animal-level robustness result generated from the committed DANDI 000971 result JSON |
| `dandi-000971-source-figure-bounded-v0.1.svg` | Six-animal, single-session partial reproduction of Seiler et al. Figures 3E–F and 4E–F, regenerated from checksum-pinned NWB assets |
| `ibl-unspool-longitudinal-v0.1.svg` | Frozen 18-animal cohort-forward IBL result; animal scores and bootstrap interval generated from the committed cross-package result JSON |
| `dandi-000971-event-kernels-v0.2.png` | Checksum-pinned public DANDI 000971 benchmark; pooled DMS/DLS kernels and grouped-jackknife sensitivity intervals |
| `dandi-000251-transient-robustness-v0.1.png` | Checksum-pinned DANDI 000251 result artifact; all eight frozen detector universes and retained cross-universe disagreement |
| `event-kernel-interval-coverage-v0.1.svg` | Frozen 480-study event/progress simulation; pointwise and candidate simultaneous whole-family coverage against a prospective gate |
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
