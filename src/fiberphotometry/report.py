"""Self-contained HTML evidence reports for scientist-facing workflows."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from fiberphotometry.design import Scalar
from fiberphotometry.qc import RecordingQC, SignalChannelQC, SignalRecordingQC

if TYPE_CHECKING:
    from fiberphotometry.multiverse import (
        MultiverseReportGroup,
        MultiverseResult,
        UniverseResult,
    )
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
    config_trace = (
        f" · configuration <code>{escape(result.configuration_fingerprint)}</code>"
        if result.configuration_fingerprint is not None
        else ""
    )
    coverage_section = _event_coverage_section(result)
    timecourse_section = _timecourse_section(result)
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

  {timecourse_section}

  {coverage_section}

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
  <code>{escape(analysis.input_fingerprint if analysis else "not executed")}</code>
  {config_trace}</footer>
</main>
</body>
</html>"""


def _timecourse_section(result: EventAnalysisResult) -> str:
    inference = result.timecourse
    if inference is None:
        return ""
    time = np.asarray(inference.relative_time, dtype=float)
    estimate = np.asarray(inference.estimate, dtype=float)
    pointwise_lower = np.asarray(inference.pointwise_lower, dtype=float)
    pointwise_upper = np.asarray(inference.pointwise_upper, dtype=float)
    simultaneous_lower = np.asarray(inference.simultaneous_lower, dtype=float)
    simultaneous_upper = np.asarray(inference.simultaneous_upper, dtype=float)
    finite_bounds = np.concatenate(
        (
            estimate[np.isfinite(estimate)],
            simultaneous_lower[np.isfinite(simultaneous_lower)],
            simultaneous_upper[np.isfinite(simultaneous_upper)],
        )
    )
    low, high = float(np.min(finite_bounds)), float(np.max(finite_bounds))
    padding = max((high - low) * 0.12, 1e-6)
    low -= padding
    high += padding
    width, height = 760, 280
    left, right, top, bottom = 54, 18, 14, 36

    def x(value: float) -> float:
        return float(
            left + (value - time[0]) / (time[-1] - time[0]) * (width - left - right)
        )

    def y(value: float) -> float:
        return top + (high - value) / (high - low) * (height - top - bottom)

    simultaneous = _band_paths(time, simultaneous_lower, simultaneous_upper, x, y)
    pointwise = _band_paths(time, pointwise_lower, pointwise_upper, x, y)
    line = _line_paths(time, estimate, x, y)
    zero = (
        f'<line x1="{left}" y1="{y(0):.2f}" x2="{width - right}" '
        f'y2="{y(0):.2f}" class="zero-line"/>'
        if low <= 0 <= high
        else ""
    )
    event = (
        f'<line x1="{x(0):.2f}" y1="{top}" x2="{x(0):.2f}" '
        f'y2="{height - bottom}" class="event-line"/>'
        if time[0] <= 0 <= time[-1]
        else ""
    )
    warning_markup = (
        "".join(
            f'<span class="warning-chip">{escape(item)}</span>'
            for item in inference.warnings
        )
        if inference.warnings
        else '<span class="quiet-chip">Stable animal support</span>'
    )
    confidence = f"{inference.confidence:.0%}"
    return f"""<section>
    <div class="section-head"><div><p class="eyebrow">TIME-COURSE INFERENCE</p>
    <h2>Animal-level peri-event contrast</h2></div>
    <p>{escape(confidence)} pointwise intervals describe individual times; the
    simultaneous band covers the whole declared window.</p></div>
    <div class="timecourse-legend"><span class="legend-estimate">Estimate</span>
    <span class="legend-pointwise">Pointwise</span>
    <span class="legend-simultaneous">Simultaneous</span></div>
    <div class="timecourse-plot"><svg viewBox="0 0 {width} {height}" role="img"
    aria-label="Animal-level contrast with pointwise and simultaneous confidence bands">
    {zero}{event}<g class="simultaneous-band">{simultaneous}</g>
    <g class="pointwise-band">{pointwise}</g><g class="timecourse-estimate">{line}</g>
    <text x="{left}" y="{height - 8}" class="axis-label">{time[0]:g} s</text>
    <text x="{width - right}" y="{height - 8}" text-anchor="end"
    class="axis-label">{time[-1]:g} s</text></svg></div>
    <div class="chips coverage-warnings">{warning_markup}</div>
    <p class="coverage-dispositions">Equal session-condition means were formed
    within each animal before {inference.animal_count} animal curves were resampled
    {inference.draws:,} times (seed {inference.seed}). The pointwise band is not a
    whole-window significance test.</p></section>"""


def _line_paths(
    time: np.ndarray,
    values: np.ndarray,
    x: Callable[[float], float],
    y: Callable[[float], float],
) -> str:
    finite = np.isfinite(values)
    changes = np.diff(np.concatenate(([False], finite, [False])).astype(int))
    paths = []
    for start, stop in zip(
        np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True
    ):
        points = " ".join(
            f"{x(time[index]):.2f},{y(values[index]):.2f}"
            for index in range(start, stop)
        )
        paths.append(f'<polyline points="{points}"/>')
    return "".join(paths)


def _band_paths(
    time: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    x: Callable[[float], float],
    y: Callable[[float], float],
) -> str:
    finite = np.isfinite(lower) & np.isfinite(upper)
    changes = np.diff(np.concatenate(([False], finite, [False])).astype(int))
    paths = []
    for start, stop in zip(
        np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True
    ):
        forward = [
            f"{x(time[index]):.2f},{y(upper[index]):.2f}"
            for index in range(start, stop)
        ]
        backward = [
            f"{x(time[index]):.2f},{y(lower[index]):.2f}"
            for index in range(stop - 1, start - 1, -1)
        ]
        paths.append(f'<polygon points="{" ".join((*forward, *backward))}"/>')
    return "".join(paths)


def _event_coverage_section(result: EventAnalysisResult) -> str:
    coverage = result.coverage
    total = coverage.total
    condition_rows = "".join(
        f"<tr><td>{escape(condition)}</td><td>{counts.candidate}</td>"
        f"<td>{counts.gated}</td><td>{counts.complete}</td>"
        f"<td>{counts.gate_retention:.1%}</td>"
        f"<td>{counts.completion_retention:.1%}</td></tr>"
        for condition, counts in coverage.conditions
    )
    stratum_rows = "".join(
        f"<tr><td>{kind}</td><td>{escape(item.name)}</td>"
        f"<td>{item.total.candidate}</td><td>{item.total.gated}</td>"
        f"<td>{item.total.complete}</td>"
        f"<td>{item.condition_gate_retention_difference:.1%}</td>"
        f"<td>{item.condition_completion_retention_difference:.1%}</td></tr>"
        for kind, strata in (
            ("Animal", coverage.animals),
            ("Session", coverage.sessions),
        )
        for item in strata
    )
    warning_markup = (
        "".join(
            f'<span class="warning-chip">{escape(warning)}</span>'
            for warning in coverage.warnings
        )
        if coverage.warnings
        else '<span class="quiet-chip">No differential retention</span>'
    )
    gate_dispositions = (
        ", ".join(f"{name}: {count}" for name, count in coverage.gate_dispositions)
        or "none"
    )
    preprocessing_dispositions = (
        ", ".join(
            f"{name}: {count}" for name, count in coverage.preprocessing_dispositions
        )
        or "none"
    )
    return f"""<section>
    <div class="section-head"><div><p class="eyebrow">EVENT COVERAGE</p>
    <h2>Which events reached the estimate?</h2></div>
    <p>Candidate, eligibility-gated, and complete denominators remain separate.</p></div>
    <div class="coverage-chain">
      <div><span>Candidate</span><strong>{total.candidate}</strong></div>
      <div><span>Gated</span><strong>{total.gated}</strong>
      <small>{total.gate_retention:.1%} of candidates</small></div>
      <div><span>Complete</span><strong>{total.complete}</strong>
      <small>{total.completion_retention:.1%} of gated</small></div>
    </div>
    <div class="chips coverage-warnings">{warning_markup}</div>
    <p class="coverage-dispositions"><strong>Gate exclusions:</strong>
    {escape(gate_dispositions)} · <strong>Incomplete after preprocessing:</strong>
    {escape(preprocessing_dispositions)}</p>
    <h3>By condition</h3>
    <div class="table-wrap"><table><thead><tr><th>Condition</th><th>Candidate</th>
    <th>Gated</th><th>Complete</th><th>Gate retention</th>
    <th>Completion retention</th></tr></thead><tbody>{condition_rows}</tbody></table></div>
    <details class="coverage-detail"><summary>Animal and session detail</summary>
    <div class="table-wrap"><table><thead><tr><th>Level</th><th>Name</th>
    <th>Candidate</th><th>Gated</th><th>Complete</th><th>Condition gate Δ</th>
    <th>Condition completion Δ</th></tr></thead><tbody>{stratum_rows}</tbody></table></div>
    </details></section>"""


def render_multiverse_report(
    result: MultiverseResult,
    groups: Sequence[MultiverseReportGroup],
    *,
    title: str,
) -> str:
    """Render separate evidence lanes and reject incomplete or overlapping groups."""
    grouped = _validate_multiverse_groups(result, groups)
    compatible = [item for item in result.universes if item.status != "incompatible"]
    incompatible = [item for item in result.universes if item.status == "incompatible"]
    lanes = "".join(_multiverse_lane(group, grouped[group.name]) for group in groups)
    failed_count = sum(item.status == "failed" for item in compatible)
    blocked_count = sum(item.status == "blocked" for item in compatible)
    success_count = sum(item.status == "success" for item in compatible)
    status_class = "status-ok" if failed_count == blocked_count == 0 else "status-warn"
    status = (
        "All declared workflows completed"
        if status_class == "status-ok"
        else "Workflow disagreement retained"
    )
    rows = "".join(
        _universe_row(item, _group_for(item.universe_id, groups)) for item in compatible
    )
    incompatible_rows = "".join(
        f"<li><code>{escape(item.universe_id)}</code> — "
        f"{escape(item.error or 'declared incompatible')}</li>"
        for item in incompatible
    )
    incompatible_section = (
        f"""<section><div class="section-head"><div>
        <p class="eyebrow">DECLARED BOUNDARY</p><h2>Incompatible workflows</h2></div>
        <p>These combinations remain visible but never enter an estimate lane.</p></div>
        <ul class="evidence-list">{incompatible_rows}</ul></section>"""
        if incompatible
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>{_CSS}</style></head><body><main>
  <header class="report-head"><div>
  <p class="eyebrow">FIBER PHOTOMETRY · ROBUSTNESS REPORT</p>
  <h1>{escape(title)}</h1><p class="dek">Parallel evidence lanes preserve unit
  boundaries. No estimate, median, or direction fraction is pooled across lanes.</p>
  </div><span class="status {status_class}">{status}</span></header>

  <section class="finding robustness-summary"><div>
  <p class="eyebrow">DECLARED UNIVERSES</p>
  <div class="estimate">{len(compatible)}<span>compatible workflows</span></div>
  <p class="interval">{escape(result.spec.intent)} intent · {len(groups)}
  unit-compatible evidence lanes</p></div><dl class="study-counts">
  <div><dt>Successful</dt><dd>{success_count}</dd></div>
  <div><dt>Failed</dt><dd>{failed_count}</dd></div>
  <div><dt>Blocked</dt><dd>{blocked_count}</dd></div></dl></section>

  <div class="lane-stack">{lanes}</div>

  <section><div class="section-head"><div><p class="eyebrow">COMPLETE LEDGER</p>
  <h2>Every compatible workflow</h2></div>
  <p>Failure and blocking reasons remain first-class results.</p></div>
  <div class="table-wrap"><table><thead><tr><th>Lane</th><th>Universe</th>
  <th>Choices</th><th>Status</th><th>Estimate</th><th>Interval or reason</th>
  </tr></thead><tbody>{rows}</tbody></table></div></section>
{incompatible_section}
  <footer>Generated by FiberPhotometry · grouped summaries are unit-local by
  contract.</footer>
</main></body></html>"""


def _validate_multiverse_groups(
    result: MultiverseResult, groups: Sequence[MultiverseReportGroup]
) -> dict[str, list[UniverseResult]]:
    if not groups:
        raise ValueError("grouped multiverse report requires at least one group")
    names = [group.name for group in groups]
    if len(names) != len(set(names)):
        raise ValueError("multiverse report group names must be unique")
    assignments: dict[str, str] = {}
    known = {
        item.universe_id for item in result.universes if item.status != "incompatible"
    }
    grouped: dict[str, list[UniverseResult]] = {group.name: [] for group in groups}
    by_id = {item.universe_id: item for item in result.universes}
    for group in groups:
        if not group.name.strip() or not group.units.strip():
            raise ValueError("multiverse report groups require names and units")
        for identifier in group.universe_ids:
            if identifier not in known:
                raise ValueError(
                    "report group names an unknown or incompatible universe"
                )
            if identifier in assignments:
                raise ValueError(
                    "compatible universes cannot appear in multiple groups"
                )
            assignments[identifier] = group.name
            grouped[group.name].append(by_id[identifier])
    if known - assignments.keys():
        raise ValueError("every compatible universe must belong to exactly one group")
    return grouped


def _multiverse_lane(
    group: MultiverseReportGroup, universes: list[UniverseResult]
) -> str:
    successful = [item for item in universes if item.status == "success"]
    estimates = [
        float(item.estimate) for item in successful if item.estimate is not None
    ]
    estimate_range = (
        f"{_number(min(estimates))} to {_number(max(estimates))}"
        if estimates
        else "No finite estimates"
    )
    failed = sum(item.status == "failed" for item in universes)
    blocked = sum(item.status == "blocked" for item in universes)
    lane_class = "evidence-lane lane-warning" if not successful else "evidence-lane"
    return f"""<section class="{lane_class}"><div class="lane-head"><div>
    <p class="eyebrow">UNIT-COMPATIBLE EVIDENCE LANE</p>
    <h2>{escape(group.name)}</h2><p>{escape(group.units)} · estimate range
    {escape(estimate_range)}</p></div><dl class="lane-counts">
    <div><dt>Success</dt><dd>{len(successful)}</dd></div>
    <div><dt>Failed</dt><dd>{failed}</dd></div>
    <div><dt>Blocked</dt><dd>{blocked}</dd></div></dl></div>
    {_universe_plot(successful, group.units)}</section>"""


def _universe_plot(universes: list[UniverseResult], units: str) -> str:
    if not universes:
        return '<div class="empty">No successful workflows in this evidence lane.</div>'
    estimates = [
        float(item.estimate) for item in universes if item.estimate is not None
    ]
    interval_values = [
        value
        for item in universes
        if item.confidence_interval is not None
        for value in item.confidence_interval
    ]
    bounds = [0.0, *estimates, *interval_values]
    low, high = min(bounds), max(bounds)
    padding = max((high - low) * 0.12, 1e-6)
    low -= padding
    high += padding
    width, left, right, row_height = 760, 132, 24, 30
    plot_width = width - left - right

    def x(value: float) -> float:
        return float(left + (value - low) / (high - low) * plot_width)

    height = 30 + row_height * len(universes)
    rows = []
    ordered = sorted(universes, key=lambda item: float(item.estimate or 0.0))
    for index, item in enumerate(ordered):
        y = 22 + index * row_height
        interval_line = ""
        if item.confidence_interval is not None:
            lower, upper = item.confidence_interval
            interval_line = (
                f'<line x1="{x(lower):.2f}" y1="{y}" x2="{x(upper):.2f}" '
                f'y2="{y}" class="interval-stem"/>'
            )
        estimate = float(item.estimate or 0.0)
        rows.append(
            f'<text x="0" y="{y + 4}" class="animal-label">'
            f"{escape(item.universe_id[:10])}</text>{interval_line}"
            f'<circle cx="{x(estimate):.2f}" cy="{y}" r="4.5" '
            f'class="effect-dot"/><text x="{width - 1}" y="{y + 4}" '
            f'text-anchor="end" class="effect-value">{_number(estimate)}</text>'
        )
    return (
        f'<div class="effect-plot"><svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Specification estimates in {escape(units)} for '
        f'{len(universes)} workflows"><line x1="{x(0):.2f}" y1="4" '
        f'x2="{x(0):.2f}" y2="{height - 10}" class="zero-line"/>'
        f"{''.join(rows)}</svg></div>"
    )


def _universe_row(item: UniverseResult, group_name: str) -> str:
    choices = " · ".join(
        f"{choice.node}: {choice.alternative}" for choice in item.choices
    )
    estimate = _number(float(item.estimate)) if item.estimate is not None else "—"
    detail = (
        _interval(item.confidence_interval)
        if item.confidence_interval is not None
        else item.error or ", ".join(item.blocked_by) or "not available"
    )
    return (
        f"<tr><td>{escape(group_name)}</td>"
        f"<td><code>{escape(item.universe_id)}</code></td>"
        f"<td>{escape(choices)}</td><td>{escape(item.status)}</td>"
        f"<td>{estimate}</td><td>{escape(detail)}</td></tr>"
    )


def _group_for(identifier: str, groups: Sequence[MultiverseReportGroup]) -> str:
    return next(group.name for group in groups if identifier in group.universe_ids)


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
main{width:calc(100vw - 32px);max-width:960px;min-width:0;margin:48px auto 80px}.report-head{display:flex;
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
margin-bottom:0}.effect-plot{max-width:100%;overflow-x:auto}.effect-plot svg{display:block;width:100%;min-width:560px}
.zero-line{stroke:var(--line);stroke-width:1.5;stroke-dasharray:3 3}.effect-stem{stroke:#9aaba2;
stroke-width:2}.effect-dot{fill:var(--gcamp)}.animal-label,.effect-value{fill:var(--secondary);
font:11px ui-monospace,SFMono-Regular,monospace}.effect-value{font-variant-numeric:tabular-nums}
.lane-stack{display:grid;min-width:0;gap:16px;margin-top:16px}.evidence-lane{min-width:0;margin-top:0;
border-left:3px solid var(--gcamp);padding-left:21px}.lane-head{display:flex;
justify-content:space-between;gap:32px;align-items:end;margin-bottom:16px}.evidence-lane.lane-warning{
border-left-color:var(--amber)}.lane-head p{
color:var(--secondary);margin-bottom:0}.lane-counts{display:flex;margin:0}.lane-counts div{
padding:0 14px;border-left:1px solid var(--line)}.lane-counts dd{font-size:18px}
.interval-stem{stroke:#9aaba2;stroke-width:2}.robustness-summary .estimate{font-size:46px}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;
color:var(--muted);font:600 10px/1.2 ui-monospace,monospace;letter-spacing:.08em;
text-transform:uppercase;padding:9px 10px;border-bottom:1px solid var(--line)}td{padding:10px;
border-bottom:1px solid var(--soft);font-variant-numeric:tabular-nums}tr:last-child td{border:0}
.coverage-chain{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
.coverage-chain>div{display:grid;gap:3px;background:var(--paper);border-radius:7px;padding:14px}
.coverage-chain span,.coverage-chain small{color:var(--muted);font-size:11px}.coverage-chain strong{
font:600 28px/1 Charter,Georgia,serif;font-variant-numeric:tabular-nums}.coverage-warnings{
justify-content:flex-start;margin-bottom:12px}.coverage-dispositions{color:var(--secondary);font-size:12px;
margin-bottom:20px}.coverage-detail{margin-top:14px}.coverage-detail summary{
color:var(--secondary);font-size:12px;font-weight:600;padding-top:6px}
.timecourse-plot{max-width:100%;overflow-x:auto}.timecourse-plot svg{display:block;width:100%;
min-width:560px}.simultaneous-band polygon{fill:rgba(22,122,80,.10)}.pointwise-band polygon{
fill:rgba(22,122,80,.20)}.timecourse-estimate polyline{fill:none;stroke:var(--gcamp);
stroke-width:2}.event-line{stroke:var(--secondary);stroke-width:1;stroke-dasharray:5 4}
.axis-label{fill:var(--muted);font:11px ui-monospace,SFMono-Regular,monospace}
.timecourse-legend{display:flex;gap:16px;margin-bottom:8px;color:var(--secondary);font-size:11px}
.timecourse-legend span:before{content:"";display:inline-block;width:18px;height:8px;margin-right:6px;
border-radius:2px}.legend-estimate:before{background:var(--gcamp);height:2px!important;
vertical-align:middle}.legend-pointwise:before{background:rgba(22,122,80,.20)}
.legend-simultaneous:before{background:rgba(22,122,80,.10)}
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
margin-top:16px}.assumptions{grid-template-columns:1fr}.coverage-chain{grid-template-columns:1fr}
h1{font-size:34px}section{padding:18px}}
@media(max-width:680px){.lane-head{display:block}.lane-counts{margin-top:16px}
.lane-counts div:first-child{border-left:0;padding-left:0}}
@media print{body{background:#fff}main{width:100%;margin:0}section{break-inside:avoid}.status{border:1px solid currentColor}}
"""
