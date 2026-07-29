"""Typed event-selection and preprocessing-coverage diagnostics."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EventCoverageRecord:
    """One candidate event's path through eligibility and preprocessing."""

    event_id: str
    condition: str
    animal: str
    session: str
    eligible: bool
    complete: bool
    disposition: str


@dataclass(frozen=True)
class EventCoverageCounts:
    """Candidate, gated, and complete event counts with explicit denominators."""

    candidate: int
    gated: int
    complete: int
    gate_retention: float
    completion_retention: float


@dataclass(frozen=True)
class EventCoverageStratum:
    """Coverage totals and condition-specific counts for one named stratum."""

    name: str
    total: EventCoverageCounts
    conditions: tuple[tuple[str, EventCoverageCounts], ...]
    condition_gate_retention_difference: float
    condition_completion_retention_difference: float


@dataclass(frozen=True)
class EventCoverageReport:
    """Auditable event denominators at study, animal, and session levels."""

    total: EventCoverageCounts
    conditions: tuple[tuple[str, EventCoverageCounts], ...]
    animals: tuple[EventCoverageStratum, ...]
    sessions: tuple[EventCoverageStratum, ...]
    gate_dispositions: tuple[tuple[str, int], ...]
    preprocessing_dispositions: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize the complete coverage audit."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_event_coverage(
    records: tuple[EventCoverageRecord, ...],
) -> EventCoverageReport:
    """Summarize candidate-to-gated-to-complete coverage without outcomes."""
    if not records:
        raise ValueError("event coverage requires at least one candidate event")
    identifiers = [record.event_id for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("event coverage requires unique event IDs")
    for record in records:
        if record.complete and not record.eligible:
            raise ValueError("an ineligible event cannot be preprocessing-complete")
        if not record.disposition.strip():
            raise ValueError("every event requires a disposition")

    conditions = _group_counts(records, "condition")
    animals = _strata(records, "animal")
    sessions = _strata(records, "session")
    total = _counts(records)
    warnings = []
    if _retention_difference(conditions, "gate_retention") > 0:
        warnings.append("condition_dependent_gate_retention")
    if _retention_difference(conditions, "completion_retention") > 0:
        warnings.append("condition_dependent_completion_retention")
    if any(item.condition_gate_retention_difference > 0 for item in animals):
        warnings.append("animal_level_condition_dependent_gate_retention")
    if any(item.condition_completion_retention_difference > 0 for item in animals):
        warnings.append("animal_level_condition_dependent_completion_retention")
    if any(item.condition_gate_retention_difference > 0 for item in sessions):
        warnings.append("session_level_condition_dependent_gate_retention")
    if any(item.condition_completion_retention_difference > 0 for item in sessions):
        warnings.append("session_level_condition_dependent_completion_retention")
    gate_dispositions = Counter(
        record.disposition for record in records if not record.eligible
    )
    preprocessing_dispositions = Counter(
        record.disposition
        for record in records
        if record.eligible and not record.complete
    )
    return EventCoverageReport(
        total,
        tuple(sorted(conditions.items())),
        animals,
        sessions,
        tuple(sorted(gate_dispositions.items())),
        tuple(sorted(preprocessing_dispositions.items())),
        tuple(warnings),
    )


def _strata(
    records: tuple[EventCoverageRecord, ...], field: str
) -> tuple[EventCoverageStratum, ...]:
    grouped: dict[str, list[EventCoverageRecord]] = defaultdict(list)
    for record in records:
        grouped[str(getattr(record, field))].append(record)
    output = []
    for name, selected in sorted(grouped.items()):
        selected_tuple = tuple(selected)
        conditions = _group_counts(selected_tuple, "condition")
        output.append(
            EventCoverageStratum(
                name,
                _counts(selected_tuple),
                tuple(sorted(conditions.items())),
                _retention_difference(conditions, "gate_retention"),
                _retention_difference(conditions, "completion_retention"),
            )
        )
    return tuple(output)


def _group_counts(
    records: tuple[EventCoverageRecord, ...], field: str
) -> dict[str, EventCoverageCounts]:
    grouped: dict[str, list[EventCoverageRecord]] = defaultdict(list)
    for record in records:
        grouped[str(getattr(record, field))].append(record)
    return {name: _counts(tuple(selected)) for name, selected in grouped.items()}


def _counts(records: tuple[EventCoverageRecord, ...]) -> EventCoverageCounts:
    candidate = len(records)
    gated = sum(record.eligible for record in records)
    complete = sum(record.complete for record in records)
    return EventCoverageCounts(
        candidate,
        gated,
        complete,
        gated / candidate if candidate else 0.0,
        complete / gated if gated else 0.0,
    )


def _retention_difference(counts: dict[str, EventCoverageCounts], field: str) -> float:
    values = [float(getattr(item, field)) for item in counts.values()]
    return max(values) - min(values) if len(values) > 1 else 0.0
