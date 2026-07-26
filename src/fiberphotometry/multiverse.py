"""Deterministic robustness analysis across defensible typed pipelines."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
from pathlib import Path
from statistics import median
from typing import Literal, TypeAlias

import numpy as np

from fiberphotometry.design import Scalar
from fiberphotometry.pipeline import (
    EventSummarySpec,
    PipelineSpec,
    PreprocessingOperation,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    run_pipeline,
)
from fiberphotometry.planning import AnalysisPlan

DecisionValue: TypeAlias = (
    PreprocessingSpec
    | tuple[PreprocessingOperation, ...]
    | QualityGateSpec
    | EventSummarySpec
    | AnalysisPlan
)
DecisionTarget = Literal[
    "preprocessing", "quality_gate", "event_summary", "analysis_plan"
]
UniverseStatus = Literal["success", "blocked", "failed", "incompatible"]


@dataclass(frozen=True)
class DecisionAlternative:
    label: str
    rationale: str
    value: DecisionValue


@dataclass(frozen=True)
class DecisionNode:
    name: str
    target: DecisionTarget
    alternatives: tuple[DecisionAlternative, ...]


@dataclass(frozen=True)
class ChoiceRef:
    node: str
    alternative: str


@dataclass(frozen=True)
class CompatibilityRule:
    """Reject a universe when every named choice in ``when`` is selected."""

    when: tuple[ChoiceRef, ...]
    reason: str


@dataclass(frozen=True)
class MultiverseSpec:
    base_pipeline: PipelineSpec
    decision_nodes: tuple[DecisionNode, ...]
    compatibility_rules: tuple[CompatibilityRule, ...]
    reference_selection: tuple[ChoiceRef, ...]
    intent: Literal["confirmatory", "exploratory", "descriptive"]
    smallest_effect: float | None = None
    direction: Literal["positive", "negative", "either"] = "either"
    leave_one_unit_out: bool = False
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class MaterializedUniverse:
    universe_id: str
    choices: tuple[ChoiceRef, ...]
    pipeline: PipelineSpec
    incompatibility: str | None = None


@dataclass(frozen=True)
class UniverseResult:
    universe_id: str
    choices: tuple[ChoiceRef, ...]
    status: UniverseStatus
    estimate: float | None
    confidence_interval: tuple[float, float] | None
    p_value: float | None
    pipeline: PipelineSpec
    blocked_by: tuple[str, ...] = ()
    error: str | None = None
    is_reference: bool = False


@dataclass(frozen=True)
class DecisionSummary:
    node: str
    alternative: str
    successful_universes: int
    median_estimate: float | None


@dataclass(frozen=True)
class LeaveOneOutResult:
    omitted_unit: Scalar
    status: Literal["success", "blocked", "failed"]
    estimate: float | None
    error: str | None = None


@dataclass(frozen=True)
class RobustnessSummary:
    total_universes: int
    valid_universes: int
    successful_universes: int
    blocked_universes: int
    failed_universes: int
    incompatible_universes: int
    estimate_range: tuple[float, float] | None
    median_estimate: float | None
    fraction_positive: float | None
    fraction_negative: float | None
    fraction_meeting_practical_effect: float | None
    reference_estimate: float | None
    decision_summaries: tuple[DecisionSummary, ...]


@dataclass(frozen=True)
class MultiverseResult:
    spec: MultiverseSpec
    universes: tuple[UniverseResult, ...]
    summary: RobustnessSummary
    leave_one_out: tuple[LeaveOneOutResult, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_grouped_html(
        self,
        groups: Sequence[MultiverseReportGroup],
        *,
        title: str = "Fiber photometry robustness report",
    ) -> str:
        """Render unit-compatible universes in explicitly separate evidence lanes."""
        from fiberphotometry.report import render_multiverse_report

        return render_multiverse_report(self, groups, title=title)

    def write_grouped_html(
        self,
        path: str | Path,
        groups: Sequence[MultiverseReportGroup],
        *,
        title: str = "Fiber photometry robustness report",
    ) -> Path:
        """Write a self-contained grouped report and return its resolved path."""
        destination = Path(path)
        destination.write_text(
            self.to_grouped_html(groups, title=title), encoding="utf-8"
        )
        return destination.resolve()


@dataclass(frozen=True)
class MultiverseReportGroup:
    """A unit-compatible set of universes that may share a visual evidence lane."""

    name: str
    units: str
    universe_ids: tuple[str, ...]

    @classmethod
    def from_choice(
        cls,
        result: MultiverseResult,
        *,
        name: str,
        units: str,
        node: str,
        alternatives: Sequence[str],
    ) -> MultiverseReportGroup:
        """Select every compatible universe matching alternatives at one node."""
        allowed = set(alternatives)
        identifiers = tuple(
            universe.universe_id
            for universe in result.universes
            if universe.status != "incompatible"
            and any(
                choice.node == node and choice.alternative in allowed
                for choice in universe.choices
            )
        )
        if not identifiers:
            raise ValueError("multiverse report group selects no compatible universes")
        return cls(name, units, identifiers)


def materialize_multiverse(spec: MultiverseSpec) -> tuple[MaterializedUniverse, ...]:
    """Expand and validate every choice combination without executing data analysis."""
    _validate_spec(spec)
    universes = []
    for alternatives in product(*(node.alternatives for node in spec.decision_nodes)):
        choices = tuple(
            ChoiceRef(node.name, alternative.label)
            for node, alternative in zip(spec.decision_nodes, alternatives, strict=True)
        )
        pipeline = spec.base_pipeline
        for node, alternative in zip(spec.decision_nodes, alternatives, strict=True):
            pipeline = _apply_choice(pipeline, node.target, alternative.value)
        if pipeline.analysis_plan.estimand != spec.base_pipeline.analysis_plan.estimand:
            raise ValueError("every universe must retain the base scientific estimand")
        incompatibility = next(
            (
                rule.reason
                for rule in spec.compatibility_rules
                if set(rule.when) <= set(choices)
            ),
            None,
        )
        universes.append(
            MaterializedUniverse(
                _universe_id(choices, pipeline), choices, pipeline, incompatibility
            )
        )
    identifiers = [universe.universe_id for universe in universes]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("universe identifiers collided")
    return tuple(universes)


def run_multiverse(
    spec: MultiverseSpec, inputs: Sequence[RecordingInput]
) -> MultiverseResult:
    """Execute all valid universes and retain every outcome class."""
    materialized = materialize_multiverse(spec)
    reference = frozenset(spec.reference_selection)
    results = []
    for universe in materialized:
        is_reference = frozenset(universe.choices) == reference
        if universe.incompatibility is not None:
            results.append(
                UniverseResult(
                    universe.universe_id,
                    universe.choices,
                    "incompatible",
                    None,
                    None,
                    None,
                    universe.pipeline,
                    error=universe.incompatibility,
                    is_reference=is_reference,
                )
            )
            continue
        try:
            result = run_pipeline(universe.pipeline, inputs)
            if result.analysis is None:
                results.append(
                    UniverseResult(
                        universe.universe_id,
                        universe.choices,
                        "blocked",
                        None,
                        None,
                        None,
                        universe.pipeline,
                        blocked_by=result.blocked_by,
                        is_reference=is_reference,
                    )
                )
            elif not np.isfinite(result.analysis.estimate):
                results.append(
                    UniverseResult(
                        universe.universe_id,
                        universe.choices,
                        "failed",
                        None,
                        None,
                        None,
                        universe.pipeline,
                        error="analysis produced a non-finite estimate",
                        is_reference=is_reference,
                    )
                )
            else:
                results.append(
                    UniverseResult(
                        universe.universe_id,
                        universe.choices,
                        "success",
                        result.analysis.estimate,
                        result.analysis.confidence_interval,
                        result.analysis.p_value,
                        universe.pipeline,
                        is_reference=is_reference,
                    )
                )
        except Exception as error:  # retained as a scientific workflow outcome
            results.append(
                UniverseResult(
                    universe.universe_id,
                    universe.choices,
                    "failed",
                    None,
                    None,
                    None,
                    universe.pipeline,
                    error=f"{type(error).__name__}: {error}",
                    is_reference=is_reference,
                )
            )
    result_tuple = tuple(results)
    return MultiverseResult(
        spec,
        result_tuple,
        _summarize(spec, result_tuple),
        _leave_one_out(spec, materialized, inputs) if spec.leave_one_unit_out else (),
    )


def _validate_spec(spec: MultiverseSpec) -> None:
    if spec.schema_version != "1":
        raise ValueError("unsupported multiverse schema version")
    if spec.smallest_effect is not None and spec.smallest_effect < 0:
        raise ValueError("smallest_effect must be nonnegative")
    if not spec.decision_nodes:
        raise ValueError("a multiverse requires at least one decision node")
    names = [node.name for node in spec.decision_nodes]
    targets = [node.target for node in spec.decision_nodes]
    if len(names) != len(set(names)):
        raise ValueError("decision-node names must be unique")
    if len(targets) != len(set(targets)):
        raise ValueError("each pipeline component may have only one decision node")
    known = {}
    for node in spec.decision_nodes:
        labels = [alternative.label for alternative in node.alternatives]
        if len(labels) < 2 or len(labels) != len(set(labels)):
            raise ValueError("each decision node requires unique alternatives")
        known[node.name] = set(labels)
        for alternative in node.alternatives:
            _validate_value(node.target, alternative.value)
    reference = {choice.node: choice.alternative for choice in spec.reference_selection}
    if set(reference) != set(names) or len(reference) != len(spec.reference_selection):
        raise ValueError(
            "reference_selection must choose exactly one alternative per node"
        )
    for reference_node, reference_alternative in reference.items():
        if reference_alternative not in known[reference_node]:
            raise ValueError("reference_selection names an unknown alternative")
    for rule in spec.compatibility_rules:
        if not rule.when or not rule.reason:
            raise ValueError("compatibility rules require choices and a reason")
        for choice in rule.when:
            if choice.node not in known or choice.alternative not in known[choice.node]:
                raise ValueError("compatibility rule names an unknown choice")
        if set(rule.when) <= set(spec.reference_selection):
            raise ValueError("reference_selection must be scientifically compatible")


def _validate_value(target: DecisionTarget, value: DecisionValue) -> None:
    expected = {
        "quality_gate": QualityGateSpec,
        "event_summary": EventSummarySpec,
        "analysis_plan": AnalysisPlan,
    }
    if target == "preprocessing":
        if not isinstance(value, (PreprocessingSpec, tuple)):
            raise TypeError("preprocessing alternatives require a preprocessing spec")
    elif not isinstance(value, expected[target]):
        raise TypeError(f"alternative value does not match target {target!r}")


def _apply_choice(
    pipeline: PipelineSpec, target: DecisionTarget, value: DecisionValue
) -> PipelineSpec:
    if target == "preprocessing" and isinstance(value, (PreprocessingSpec, tuple)):
        return replace(pipeline, preprocessing=value)
    if target == "quality_gate" and isinstance(value, QualityGateSpec):
        return replace(pipeline, quality_gate=value)
    if target == "event_summary" and isinstance(value, EventSummarySpec):
        return replace(pipeline, event_summary=value)
    if target == "analysis_plan" and isinstance(value, AnalysisPlan):
        return replace(pipeline, analysis_plan=value)
    raise TypeError(f"alternative value does not match target {target!r}")


def _universe_id(choices: tuple[ChoiceRef, ...], pipeline: PipelineSpec) -> str:
    payload = json.dumps(
        {
            "choices": [asdict(choice) for choice in choices],
            "pipeline": asdict(pipeline),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode()).hexdigest()[:16]


def _summarize(
    spec: MultiverseSpec, results: tuple[UniverseResult, ...]
) -> RobustnessSummary:
    successful = [result for result in results if result.status == "success"]
    estimates = [
        result.estimate for result in successful if result.estimate is not None
    ]
    valid_count = sum(result.status != "incompatible" for result in results)
    reference = next((result for result in results if result.is_reference), None)
    practical = (
        [_meets_effect(value, spec) for value in estimates]
        if spec.smallest_effect is not None
        else None
    )
    decision_summaries = []
    for node in spec.decision_nodes:
        for alternative in node.alternatives:
            selected = [
                result.estimate
                for result in successful
                if ChoiceRef(node.name, alternative.label) in result.choices
                and result.estimate is not None
            ]
            decision_summaries.append(
                DecisionSummary(
                    node.name,
                    alternative.label,
                    len(selected),
                    float(median(selected)) if selected else None,
                )
            )
    return RobustnessSummary(
        total_universes=len(results),
        valid_universes=valid_count,
        successful_universes=len(successful),
        blocked_universes=sum(result.status == "blocked" for result in results),
        failed_universes=sum(result.status == "failed" for result in results),
        incompatible_universes=sum(
            result.status == "incompatible" for result in results
        ),
        estimate_range=(float(min(estimates)), float(max(estimates)))
        if estimates
        else None,
        median_estimate=float(median(estimates)) if estimates else None,
        fraction_positive=float(np.sum(np.asarray(estimates) > 0) / valid_count)
        if valid_count
        else None,
        fraction_negative=float(np.sum(np.asarray(estimates) < 0) / valid_count)
        if valid_count
        else None,
        fraction_meeting_practical_effect=float(np.sum(practical) / valid_count)
        if valid_count and practical is not None
        else None,
        reference_estimate=reference.estimate if reference is not None else None,
        decision_summaries=tuple(decision_summaries),
    )


def _meets_effect(estimate: float, spec: MultiverseSpec) -> bool:
    if spec.smallest_effect is None:
        raise ValueError("a practical-effect threshold was not declared")
    if spec.direction == "positive":
        return estimate >= spec.smallest_effect
    if spec.direction == "negative":
        return estimate <= -spec.smallest_effect
    return abs(estimate) >= spec.smallest_effect


def _leave_one_out(
    spec: MultiverseSpec,
    universes: tuple[MaterializedUniverse, ...],
    inputs: Sequence[RecordingInput],
) -> tuple[LeaveOneOutResult, ...]:
    reference = frozenset(spec.reference_selection)
    pipeline = next(
        universe.pipeline
        for universe in universes
        if frozenset(universe.choices) == reference
    )
    aggregation = pipeline.analysis_plan.estimand.aggregation_unit
    unit_column = next(
        unit.column for unit in pipeline.design.units if unit.name == aggregation
    )
    units = sorted(
        {value for item in inputs for value in item.columns[unit_column]}, key=str
    )
    output = []
    for omitted in units:
        reduced = _exclude_unit(inputs, unit_column, omitted)
        try:
            result = run_pipeline(pipeline, reduced)
            if result.analysis is None:
                output.append(LeaveOneOutResult(omitted, "blocked", None))
            elif not np.isfinite(result.analysis.estimate):
                output.append(
                    LeaveOneOutResult(omitted, "failed", None, "non-finite estimate")
                )
            else:
                output.append(
                    LeaveOneOutResult(omitted, "success", result.analysis.estimate)
                )
        except Exception as error:
            output.append(
                LeaveOneOutResult(
                    omitted, "failed", None, f"{type(error).__name__}: {error}"
                )
            )
    return tuple(output)


def _exclude_unit(
    inputs: Sequence[RecordingInput], unit_column: str, omitted: Scalar
) -> tuple[RecordingInput, ...]:
    output = []
    for item in inputs:
        keep = [value != omitted for value in item.columns[unit_column]]
        if not any(keep):
            continue
        output.append(
            RecordingInput(
                item.recording,
                [
                    value
                    for value, retain in zip(item.event_times, keep, strict=True)
                    if retain
                ],
                [
                    value
                    for value, retain in zip(item.event_ids, keep, strict=True)
                    if retain
                ],
                {
                    name: [
                        value
                        for value, retain in zip(values, keep, strict=True)
                        if retain
                    ]
                    for name, values in item.columns.items()
                },
            )
        )
    return tuple(output)
