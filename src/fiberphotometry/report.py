"""Self-contained HTML evidence reports for scientist-facing workflows."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from html import escape
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from fiberphotometry.design import Scalar
from fiberphotometry.qc import RecordingQC, SignalChannelQC, SignalRecordingQC

if TYPE_CHECKING:
    from fiberphotometry.workflow import EventAnalysisResult


def render_event_analysis_report(result: EventAnalysisResult) -> str:
    """Render one pipeline result as an offline, printable HTML document."""
    pipeline = result.pipeline
    analysis = pipeline.analysis
    plan = result.spec.analysis_plan
    contrast = plan.estimand.contrast
    unit_column = next(
        unit.column
        for unit in result.spec.design.units
        if unit.name == plan.estimand.aggregation_unit
    )
    units = sorted(
        set(pipeline.observation_table.values(unit_column).tolist()), key=str
    )
    sessions = set(pipeline.observation_table.values("session").tolist())
    observations = len(pipeline.observation_table)
    warnings = sorted(
        {
            warning
            for report in pipeline.quality_reports
            for channel in report.channels
            for warning in channel.warnings
        }
    )
    status = "Blocked by quality gate" if analysis is None else "Analysis complete"
    status_class = "status-warn" if analysis is None else "status-ok"
    estimate = _number(analysis.estimate) if analysis is not None else "—"
    interval = (
        _interval(analysis.confidence_interval)
        if analysis is not None and analysis.confidence_interval is not None
        else "Not available"
    )
    p_value = _p_value(analysis.p_value) if analysis is not None else "—"
    animal_effects = _unit_effects(
        pipeline.observation_table.columns,
        unit_column,
        contrast.factor,
        plan.estimand.outcome,
        contrast.numerator,
        contrast.denominator,
    )
    evidence_plot = _effect_plot(
        animal_effects, analysis.confidence_interval if analysis else None
    )
    qc_rows = "".join(_quality_row(report) for report in pipeline.quality_reports)
    warning_markup = (
        "".join(
            f'<span class="warning-chip">{escape(item)}</span>' for item in warnings
        )
        if warnings
        else '<span class="quiet-chip">No channel warnings</span>'
    )
    operations = _operation_cards(pipeline.processed_recordings)
    assumptions = "".join(
        f"<li>{escape(assumption)}</li>" for assumption in plan.acknowledged_assumptions
    )
    blocked = "".join(f"<li>{escape(reason)}</li>" for reason in pipeline.blocked_by)
    blocked_section = (
        f'<section><h2>Blocking evidence</h2><ul class="evidence-list">{blocked}</ul></section>'
        if pipeline.blocked_by
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(result.title)}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
  <header class="report-head">
    <div>
      <p class="eyebrow">FIBER PHOTOMETRY · EVIDENCE REPORT</p>
      <h1>{escape(result.title)}</h1>
      <p class="dek">{escape(contrast.numerator)} minus {escape(contrast.denominator)},
      aggregated at the {escape(plan.estimand.aggregation_unit)} level.</p>
    </div>
    <span class="status {status_class}">{status}</span>
  </header>

  <section class="finding" aria-labelledby="finding-title">
    <div class="finding-main">
      <p class="eyebrow" id="finding-title">ESTIMATED CONTRAST</p>
      <div class="estimate">{estimate}<span>{escape(result.preprocessing.units)}</span></div>
      <p class="interval">{interval} · p {p_value}</p>
    </div>
    <dl class="study-counts">
      <div><dt>Animals</dt><dd>{len(units)}</dd></div>
      <div><dt>Sessions</dt><dd>{len(sessions)}</dd></div>
      <div><dt>Events</dt><dd>{observations}</dd></div>
    </dl>
  </section>

  <section class="evidence-trace">
    <div>
      <p class="eyebrow">EVIDENCE TRACE</p>
      <h2>{escape(result.preprocessing.label)}</h2>
      <p>{escape(str(result.spec.event_summary.baseline))} baseline ·
      {escape(str(result.spec.event_summary.response))} response ·
      {escape(plan.method.replace("_", " "))} inference</p>
    </div>
    <div class="chips">{warning_markup}</div>
  </section>

  <section>
    <div class="section-head"><div><p class="eyebrow">UNIT-LEVEL EVIDENCE</p>
    <h2>Does the effect survive the animal boundary?</h2></div>
    <p>Dots are within-animal contrasts. The vertical rule is zero.</p></div>
    {evidence_plot}
  </section>

  <section>
    <div class="section-head"><div><p class="eyebrow">QUALITY CONTROL</p>
    <h2>Acquisition integrity by session</h2></div>
    <p>Warnings remain visible; they never silently delete data.</p></div>
    <div class="table-wrap"><table><thead><tr><th>Session</th><th>Channel</th>
    <th>Rate</th><th>Finite</th><th>Gaps</th><th>Warnings</th></tr></thead>
    <tbody>{qc_rows}</tbody></table></div>
  </section>

  <section>
    <div class="section-head"><div><p class="eyebrow">PROVENANCE</p>
    <h2>What happened to the fluorescence?</h2></div>
    <p>Ordered operations are read directly from processed recording metadata.</p></div>
    <div class="operation-grid">{operations}</div>
  </section>

  <section class="assumptions">
    <div><p class="eyebrow">INTERPRETATION CONTRACT</p><h2>Acknowledged assumptions</h2></div>
    <ul class="evidence-list">{assumptions}</ul>
  </section>
  {blocked_section}

  <footer>Generated by FiberPhotometry · input fingerprint
  <code>{escape(analysis.input_fingerprint if analysis else "not executed")}</code></footer>
</main>
</body>
</html>"""


def _unit_effects(
    columns: Mapping[str, tuple[Scalar, ...]],
    unit_column: str,
    factor_column: str,
    outcome_column: str,
    numerator: str,
    denominator: str,
) -> list[tuple[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for unit, factor, outcome in zip(
        columns[unit_column],
        columns[factor_column],
        columns[outcome_column],
        strict=True,
    ):
        value = float(outcome) if outcome is not None else float("nan")
        if np.isfinite(value):
            grouped[str(unit)][str(factor)].append(value)
    effects = []
    for unit, levels in sorted(grouped.items()):
        if levels[numerator] and levels[denominator]:
            effects.append(
                (unit, float(np.mean(levels[numerator]) - np.mean(levels[denominator])))
            )
    return effects


def _effect_plot(
    effects: list[tuple[str, float]], interval: tuple[float, float] | None
) -> str:
    if not effects:
        return '<div class="empty">No finite animal-level contrasts available.</div>'
    values = [value for _, value in effects]
    bounds: list[float] = [0.0, *values, *(interval or ())]
    low, high = min(bounds), max(bounds)
    padding = max((high - low) * 0.12, 1e-6)
    low -= padding
    high += padding
    width, left, right, row_height = 760, 116, 24, 30
    plot_width = width - left - right

    def x(value: float) -> float:
        return float(left + (value - low) / (high - low) * plot_width)

    height = 30 + row_height * len(effects)
    rows = []
    for index, (unit, value) in enumerate(effects):
        y = 22 + index * row_height
        rows.append(
            f'<text x="0" y="{y + 4}" class="animal-label">{escape(unit)}</text>'
            f'<line x1="{x(0):.2f}" y1="{y}" x2="{x(value):.2f}" y2="{y}" '
            'class="effect-stem"/>'
            f'<circle cx="{x(value):.2f}" cy="{y}" r="4.5" class="effect-dot"/>'
            f'<text x="{width - 1}" y="{y + 4}" text-anchor="end" '
            f'class="effect-value">{_number(value)}</text>'
        )
    return (
        f'<div class="effect-plot"><svg viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Animal-level contrasts for {len(effects)} animals">'
        f'<line x1="{x(0):.2f}" y1="4" x2="{x(0):.2f}" y2="{height - 10}" '
        f'class="zero-line"/>{"".join(rows)}</svg></div>'
    )


def _quality_row(report: RecordingQC | SignalRecordingQC) -> str:
    rows = []
    for channel in report.channels:
        finite = (
            channel.finite_fraction
            if isinstance(channel, SignalChannelQC)
            else channel.finite_paired_fraction
        )
        warnings = ", ".join(channel.warnings) or "none"
        rows.append(
            f"<tr><td>{escape(str(report.session))}</td>"
            f"<td>{escape(str(channel.channel))}</td>"
            f"<td>{report.estimated_rate_hz:.1f} Hz</td>"
            f"<td>{float(finite):.1%}</td>"
            f"<td>{report.large_gap_count}</td>"
            f"<td>{escape(warnings)}</td></tr>"
        )
    return "".join(rows)


def _operation_cards(recordings: tuple[xr.Dataset, ...]) -> str:
    unique: dict[str, dict[str, object]] = {}
    for recording in recordings:
        raw = recording.attrs.get("fiberphotometry_operations", "[]")
        for operation in json.loads(str(raw)):
            key = json.dumps(operation, sort_keys=True)
            unique[key] = operation
    cards = []
    for index, operation in enumerate(unique.values(), start=1):
        kind = str(operation.get("kind", "operation")).replace("_", " ")
        method = str(operation.get("method", "declared parameters"))
        cards.append(
            f'<article class="operation"><span>{index:02d}</span><div><h3>{escape(kind)}</h3>'
            f"<p>{escape(method)}</p></div><details><summary>Parameters</summary>"
            f"<pre>{escape(json.dumps(operation, indent=2, sort_keys=True))}</pre>"
            "</details></article>"
        )
    return (
        "".join(cards) or '<div class="empty">No processing operations recorded.</div>'
    )


def _number(value: float) -> str:
    return f"{value:.4g}"


def _interval(value: tuple[float, float]) -> str:
    return f"95% CI {_number(value[0])} to {_number(value[1])}"


def _p_value(value: float) -> str:
    return "< 0.001" if value < 0.001 else f"= {value:.3f}"


_CSS = r"""
:root{--paper:#f6f7f3;--sheet:#fff;--ink:#18211d;--secondary:#4f5e57;
--muted:#7b8982;--line:rgba(24,33,29,.13);--soft:rgba(24,33,29,.055);
--gcamp:#167a50;--gcamp-soft:#e4f1e9;--amber:#9a6416;--amber-soft:#f7eddc}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Avenir Next","Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
main{width:min(960px,calc(100% - 32px));margin:48px auto 80px}.report-head{display:flex;
justify-content:space-between;gap:32px;align-items:flex-start;padding-bottom:32px}
h1,h2,h3,p{margin-top:0}h1{font-family:Charter,"Iowan Old Style",Georgia,serif;
font-size:42px;line-height:1.08;letter-spacing:-.025em;margin-bottom:12px;text-wrap:balance}
h2{font:600 22px/1.25 Charter,"Iowan Old Style",Georgia,serif;letter-spacing:-.01em;
margin-bottom:8px}h3{font-size:14px;margin:0 0 4px}.dek,.section-head>p{color:var(--secondary);
line-height:1.55;max-width:620px}.eyebrow{font:600 11px/1.2 ui-monospace,SFMono-Regular,monospace;
letter-spacing:.1em;color:var(--muted);margin-bottom:10px}.status{font-size:12px;font-weight:650;
padding:7px 10px;border-radius:6px;white-space:nowrap}.status-ok{color:var(--gcamp);
background:var(--gcamp-soft)}.status-warn{color:var(--amber);background:var(--amber-soft)}
section{background:var(--sheet);border:1px solid var(--line);border-radius:10px;padding:24px;
margin-top:16px}.finding{display:grid;grid-template-columns:1fr auto;align-items:end;
border-top:3px solid var(--gcamp);padding-top:21px}.estimate{font:600 52px/1 Charter,
"Iowan Old Style",Georgia,serif;letter-spacing:-.035em;font-variant-numeric:tabular-nums}
.estimate span{font:500 13px/1.2 "Avenir Next","Segoe UI",sans-serif;color:var(--muted);
letter-spacing:0;margin-left:10px}.interval{color:var(--secondary);margin:10px 0 0;
font-variant-numeric:tabular-nums}.study-counts{display:flex;margin:0}.study-counts div{padding:0 20px;
border-left:1px solid var(--line)}dt{color:var(--muted);font-size:11px;text-transform:uppercase;
letter-spacing:.08em}dd{margin:5px 0 0;font:600 24px/1 Charter,Georgia,serif;
font-variant-numeric:tabular-nums}.evidence-trace{display:flex;justify-content:space-between;
align-items:center;border-left:3px solid var(--gcamp);padding-left:21px}.evidence-trace p:last-child{
color:var(--secondary);margin-bottom:0}.chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.warning-chip,.quiet-chip{padding:5px 8px;border-radius:5px;font:600 11px/1.2 ui-monospace,
monospace}.warning-chip{background:var(--amber-soft);color:var(--amber)}.quiet-chip{background:
var(--gcamp-soft);color:var(--gcamp)}.section-head{display:flex;justify-content:space-between;
gap:32px;align-items:end;margin-bottom:20px}.section-head>p{font-size:12px;max-width:300px;
margin-bottom:0}.effect-plot{overflow-x:auto}.effect-plot svg{display:block;width:100%;min-width:560px}
.zero-line{stroke:var(--line);stroke-width:1.5;stroke-dasharray:3 3}.effect-stem{stroke:#9aaba2;
stroke-width:2}.effect-dot{fill:var(--gcamp)}.animal-label,.effect-value{fill:var(--secondary);
font:11px ui-monospace,SFMono-Regular,monospace}.effect-value{font-variant-numeric:tabular-nums}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;
color:var(--muted);font:600 10px/1.2 ui-monospace,monospace;letter-spacing:.08em;
text-transform:uppercase;padding:9px 10px;border-bottom:1px solid var(--line)}td{padding:10px;
border-bottom:1px solid var(--soft);font-variant-numeric:tabular-nums}tr:last-child td{border:0}
.operation-grid{display:grid;gap:8px}.operation{display:grid;grid-template-columns:32px 1fr auto;
align-items:start;background:var(--paper);border-radius:7px;padding:12px}.operation>span{font:600 11px
ui-monospace,monospace;color:var(--gcamp)}.operation p{font-size:12px;color:var(--secondary);
margin:0}.operation details{font-size:11px;color:var(--muted)}summary{cursor:pointer;min-height:28px}
pre{white-space:pre-wrap;max-width:540px;background:var(--ink);color:#e8eee9;padding:12px;
border-radius:6px;overflow:auto}.assumptions{display:grid;grid-template-columns:1fr 1.4fr;gap:32px}
.evidence-list{margin:0;padding-left:18px;color:var(--secondary);font-size:13px;line-height:1.6}
.empty{padding:32px;text-align:center;background:var(--paper);color:var(--muted);border-radius:7px}
footer{color:var(--muted);font-size:11px;margin-top:24px;display:flex;justify-content:space-between;
gap:16px}code{font-family:ui-monospace,SFMono-Regular,monospace;overflow-wrap:anywhere}
@media(max-width:680px){main{margin-top:24px}.report-head,.section-head,.evidence-trace{display:block}
.status{display:inline-block;margin-top:12px}.finding{grid-template-columns:1fr}.study-counts{margin-top:24px}
.study-counts div:first-child{border-left:0;padding-left:0}.estimate{font-size:42px}.chips{justify-content:flex-start;
margin-top:16px}.assumptions{grid-template-columns:1fr}h1{font-size:34px}section{padding:18px}}
@media print{body{background:#fff}main{width:100%;margin:0}section{break-inside:avoid}.status{border:1px solid currentColor}}
"""
