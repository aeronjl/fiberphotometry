# Publication-quality figure standard

Every generated figure in this site uses one shared pipeline. The purpose is not
cosmetic uniformity: it makes the visual estimand, denominator, uncertainty, and
provenance as reviewable as the code.

## Non-negotiable defaults

| Element | Project standard |
|---|---|
| Typeface | DejaVu Sans throughout, including mathematical text; no serif fallback |
| Master format | SVG for diagrams and ordinary plots; PDF is acceptable for manuscripts |
| Raster output | 300 dpi PNG only when dense rendering or a downstream format requires it |
| Text | 9 pt base at final size; panel labels and headings use weight, not a second typeface |
| Lines | at least 0.8 pt; primary traces 1.5 pt or heavier |
| Color | restrained, color-vision-aware categorical palette with redundant line style or marker coding |
| Background | white; no gradients, drop shadows, or decorative chart furniture |
| Axes | units always shown; top and right spines removed unless they encode information |
| Uncertainty | interval type and independent unit stated in the caption or adjacent prose |
| Export | deterministic metadata, embedded TrueType text in PDF, editable text in SVG |

Apply the standard in a plotting script with:

```python
from figure_style import apply_publication_style, save_figure

apply_publication_style(hashsalt="stable-figure-identifier")
# construct the Matplotlib figure
save_figure(figure, output_path)
```

The implementation lives in
[`scripts/figure_style.py`](https://github.com/aeronjl/fiberphotometry/blob/main/scripts/figure_style.py).
It fixes sans-serif mathematical text, PDF font embedding, SVG text preservation,
300 dpi raster output, deterministic SVG hashing, and whitespace normalization.

## Scientific display rules

1. Show animals or other independent units whenever the panel geometry permits.
2. Do not use trial or sample count to imply population precision.
3. Pair repeated observations visually when the analysis is paired.
4. Label missing, excluded, and failed workflows rather than removing them.
5. Use a zero or null reference line when the estimand has a meaningful null.
6. Keep preprocessing diagnostics separate from biological outcomes.
7. Do not convert a non-significant result into evidence of equivalence.
8. Write alternative text that communicates the conclusion without relying on
   color or the image itself.

## Reproducing a paper figure

“Reproduction” is a scientific claim. A worked example receives one of four
labels:

| Label | Meaning |
|---|---|
| **Source-panel reproduction** | same public observations, preprocessing target, estimand, denominator, and panel semantics |
| **Partial source-panel reproduction** | an exact source panel is targeted, but a bounded cohort or declared unavailable input prevents full parity |
| **Adapted reanalysis** | source data or visual grammar is reused for a different estimand or method |
| **Method illustration** | synthetic or schematic values explain an API; no empirical source-panel claim |

A source-aligned page must name the paper, figure and panel; link the data and
generating code; enumerate every known departure; and distinguish qualitative
agreement from numerical parity. We redraw from data under this project style—we
do not copy a published image.

## Caption template

> **Figure X — [claim-sized title].** [What is plotted.] Lines/points represent
> [unit]; shading/error bars are [interval] across [independent denominator].
> [Preprocessing or model needed to interpret the axes.] Reproduction status:
> [label], targeting [citation, figure/panel]. [Material departures and limits.]

## Pre-merge checks

- generate the figure twice and confirm that the committed artifact is stable;
- inspect it at documentation width and manuscript-column width;
- check light and dark site themes;
- verify labels, units, legends, and panel order without consulting the prose;
- verify the source-panel correspondence in the
  [worked-example register](../tutorials/paper-figure-roadmap.md); and
- run the documentation build and local-asset audit.
