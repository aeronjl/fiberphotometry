# Choose a workflow

Start with the scientific question, not the file format.

If you have not run anything yet, do that first: [Install](install.md), then
[your first dF/F trace](first-dff-trace.md) and
[your first peri-event plot](first-peri-event-plot.md). This page is for choosing
which of the larger workflows below fits your experiment.

<figure class="doc-figure">
  <img src="../assets/method-question-map.svg" alt="A central scientific question branches to event contrasts, preprocessing sensitivity, overlapping event kernels, and population effects, each with a distinct method and evidence boundary.">
  <figcaption><strong>Choose by estimand.</strong> File format determines an adapter; the scientific question determines the analysis and validation contract.</figcaption>
</figure>

## Event-locked group comparison

Use the main workflow when you have named events, conditions, repeated trials,
and multiple animals. It supports explicit baseline and response windows,
animal-level contrasts, event-coverage accounting, peri-event uncertainty, and
preprocessing robustness.

[Run the first event analysis](../product-workflow.md)

## Configuration-first batch analysis

Use the CLI when analyses must be rerun consistently across sessions without
editing Python. A TOML project declares inputs, channel roles, preprocessing,
conditions, windows, inferential assumptions, and output location.

[Follow the CLI walkthrough](../cli.md)

## Public or archived NWB analysis

Use the DANDI tutorial for the complete path from raw public NWB through a declared
eight-universe robustness analysis and verified evidence report.

[Run the DANDI example](../tutorials/dandi-000971-reward-multiverse.md)

## A different scientific question

Check the [methods catalog](../methods/index.md) before adapting the package. It
states which workflows are supported, experimental, planned, or outside the
package's intended scope.
