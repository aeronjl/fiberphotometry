# fipha interface system

## Direction and intent

Design for a practicing neuroscientist who has just run or received an analysis and
must decide whether the apparent result is trustworthy. Interfaces should feel
like a calibrated laboratory instrument paired with a candid methods section:
quiet, exact, evidence-led, and unwilling to hide disagreement.

The focal point is always the scientific estimand or robustness conclusion. Sample
counts, QC, assumptions, and provenance support it without competing for attention.
Avoid generic dashboard metaphors, celebratory KPI styling, decorative charts, and
any visual treatment that implies certainty the analysis did not earn.

Domain vocabulary: fluorescence traces, acquisition sessions, event windows,
animals, QC gates, preprocessing lineage, estimands, intervals, universes,
robustness, and failed workflows.

Signature pattern: every conclusion is followed by an **evidence trace** connecting
the result to its population unit, preprocessing lineage, QC state, and assumptions.
For multiverses, use **parallel evidence lanes**: incompatible unit families occupy
separate panels and never share a pooled summary.

## Color tokens

Colors come from the physical and analytical world of photometry:

```css
:root {
  --paper: #f6f7f3;                 /* report canvas */
  --sheet: #ffffff;                 /* evidence surface */
  --ink: #18211d;                   /* microscope charcoal */
  --secondary: #4f5e57;             /* instrument steel */
  --muted: #7b8982;                 /* metadata */
  --line: rgba(24, 33, 29, 0.13);   /* structural edge */
  --soft: rgba(24, 33, 29, 0.055);  /* row separation */
  --gcamp: #167a50;                 /* trusted/selected evidence */
  --gcamp-soft: #e4f1e9;            /* trusted status surface */
  --amber: #9a6416;                 /* warning, limitation */
  --amber-soft: #f7eddc;             /* warning status surface */
}
```

Color is semantic and scarce. GCaMP green marks selected evidence, completed
analysis, and effect points. Amber marks retained warnings and limitations. Do not
introduce colors merely to distinguish categories; use position, labels, marker
shape, and value first.

## Depth and surfaces

- Strategy: borders only. Do not combine with decorative shadows.
- Canvas: `--paper`; primary sections: `--sheet` with a 1px `--line` border.
- Provenance/code inset: `--ink` with pale neutral text.
- Section radius: 10px. Inset/operation radius: 6–7px. Status/chip radius: 5–6px.
- A selected evidence section may use a 3px GCaMP-green top or left edge.
- Borders should disappear during a squint test; hierarchy must remain through
  spacing, type, and tonal contrast.

## Spacing and density

Base unit: 4px.

- Micro gaps: 4–8px.
- Chip/control padding: 5px 8px.
- Operation rows: 12px.
- Standard section gap: 16px.
- Evidence-section padding: 24px desktop, 18px narrow view.
- Section-header internal gap: 32px.
- Major report separation: 32–48px.
- Report width: maximum 960px with 16px minimum viewport gutter.

Density is “working scientific report,” not brochure-airy and not terminal-dense.
Tables may be compact; conclusions require more whitespace.

## Typography and hierarchy

- Scientific findings and headings: `Charter, "Iowan Old Style", Georgia, serif`.
- Explanatory text: `"Avenir Next", "Segoe UI", sans-serif`.
- IDs, parameters, provenance, labels: `ui-monospace, SFMono-Regular, monospace`.
- Display estimate: 52px/600 desktop, 42px narrow; negative tracking; tabular nums.
- Page title: 42px desktop, 34px narrow; 1.08 line height; balanced wrapping.
- Section heading: 22px/600 serif.
- Body: 13–16px with ~1.5 line height.
- Eyebrow: 11px/600 monospace, 0.1em tracking, uppercase, muted.
- Metadata and table labels: 10–11px monospace, muted.

Use size, weight, and color together. Dynamic numbers always use tabular numerals.

## Reusable patterns

### Report header

Two-column desktop layout: title/dek on the left, compact semantic status on the
right. Collapse to one column below 680px. The status is supportive, never the
headline.

### Finding panel

White section with a 3px GCaMP-green top edge. The estimate is the dominant element;
interval and p-value sit immediately beneath it. Animal/session/event counts form a
secondary definition list separated by quiet vertical rules.

### Evidence trace

White section with a 3px GCaMP-green left edge. Show preprocessing, event windows,
inferential method, QC chips, and—when present—configuration fingerprint. This is
the product’s core provenance signature.

### Animal evidence plot

Inline SVG, zero rule dashed and quiet, one labelled row per animal, thin neutral
stem, GCaMP-green point, monospace exact value at right. Never substitute event
counts for visible animals.

### Parallel evidence lanes

One lane per unit-compatible robustness family. Each lane owns its units, estimate
range, success/failure counts, and specification curve. Lanes may align vertically
for comparison but must not share a pooled median, direction fraction, or axis label
that implies commensurate units.

### QC chips and table

No-warning state uses GCaMP green on `--gcamp-soft`; retained warnings use amber on
`--amber-soft`. Tables use quiet horizontal separators, no zebra striping, and
monospace identifiers/numeric alignment where helpful. Empty and blocked states are
plain-language evidence, not blank space.

### Provenance operations

Numbered rows on `--paper`; kind and method visible at rest; exact parameters inside
native `<details>`/`<summary>`. Preserve keyboard and print accessibility without
JavaScript.

## States and accessibility

- Complete: GCaMP-green status.
- Warning or blocked: amber status with the blocking evidence listed explicitly.
- Failed universe: retain it with reason text; never silently omit it.
- Empty: centered quiet panel explaining what evidence is unavailable and why.
- Use native semantic HTML, real tables, definition lists, and `<details>`.
- SVG plots require `role="img"` and a meaningful `aria-label`.
- Minimum interactive target: 44px when controls are introduced.
- Reports must remain useful without JavaScript, external assets, or telemetry.
- Respect print: white canvas, avoid breaking evidence sections, retain semantic
  status borders.
- Narrow layout breakpoint: 680px; stack headers, findings, traces, and assumptions.

## Anti-patterns

- Generic dashboard sidebar or equal-weight card grid.
- Green used as decoration rather than evidence/status.
- Pooled summaries across incompatible units.
- Event/trial counts presented as independent population replication.
- Harsh borders, gradients, dramatic shadows, excessive rounding, or multiple
  accents.
- Hidden QC exclusions, failed workflows, assumptions, or provenance.
