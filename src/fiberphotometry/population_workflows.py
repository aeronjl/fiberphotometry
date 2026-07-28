"""Domain materializers for the common animal-level population boundary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal, TypeAlias

import numpy as np

from fiberphotometry.association_inference import (
    AssociationAnimalEstimate,
    AssociationSessionEstimate,
)
from fiberphotometry.population import (
    PopulationContrastResult,
    PopulationContrastSpec,
    PopulationGroupAssignment,
    PopulationInteractionResult,
    PopulationInteractionSpec,
    PopulationUnitEstimate,
    infer_population_contrast,
    infer_population_interaction,
)
from fiberphotometry.spectral import (
    StateBandPowerEstimate,
    StatePSDSession,
    _band_power,
)
from fiberphotometry.transient_inference import (
    TransientAnimalEstimate,
    TransientMetric,
    TransientStudySession,
    _aggregate,
    _session_evidence,
    _validate_sessions,
)

Aggregation: TypeAlias = Literal["mean", "median"]


@dataclass(frozen=True)
class TransientPopulationMaterialization:
    """Transient animal-condition cells ready for common population inference."""

    metric: TransientMetric
    channel: str
    levels: tuple[str, ...]
    session_aggregation: Aggregation
    animal_estimates: tuple[TransientAnimalEstimate, ...]
    population_estimates: tuple[PopulationUnitEstimate, ...]
    schema_version: str = "1"

    def contrast(self, spec: PopulationContrastSpec) -> PopulationContrastResult:
        """Apply the common population contrast to materialized animal cells."""
        return infer_population_contrast(self.population_estimates, spec)

    def interaction(
        self,
        assignments: tuple[PopulationGroupAssignment, ...]
        | list[PopulationGroupAssignment],
        spec: PopulationInteractionSpec,
    ) -> PopulationInteractionResult:
        """Compare within-animal transient contrasts across disjoint groups."""
        return infer_population_interaction(
            self.population_estimates, tuple(assignments), spec
        )

    def to_json(self) -> str:
        """Serialize domain denominators and common population cells."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class StateBandPowerPopulationMaterialization:
    """Animal-state band-power cells ready for common population inference."""

    frequency_band_hz: tuple[float, float]
    states: tuple[str, ...]
    animal_estimates: tuple[StateBandPowerEstimate, ...]
    population_estimates: tuple[PopulationUnitEstimate, ...]
    schema_version: str = "1"

    def contrast(self, spec: PopulationContrastSpec) -> PopulationContrastResult:
        """Apply the common population contrast to animal-state band power."""
        return infer_population_contrast(self.population_estimates, spec)

    def interaction(
        self,
        assignments: tuple[PopulationGroupAssignment, ...]
        | list[PopulationGroupAssignment],
        spec: PopulationInteractionSpec,
    ) -> PopulationInteractionResult:
        """Compare within-animal state contrasts across disjoint groups."""
        return infer_population_interaction(
            self.population_estimates, tuple(assignments), spec
        )

    def to_json(self) -> str:
        """Serialize state-band cells and their source-session support."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class AssociationPopulationMaterialization:
    """Animal-condition association cells ready for common population inference."""

    metric: str
    pair_id: str
    levels: tuple[str, ...]
    session_aggregation: Aggregation
    animal_estimates: tuple[AssociationAnimalEstimate, ...]
    population_estimates: tuple[PopulationUnitEstimate, ...]
    schema_version: str = "1"

    def contrast(self, spec: PopulationContrastSpec) -> PopulationContrastResult:
        """Apply the common population contrast to association cells."""
        return infer_population_contrast(self.population_estimates, spec)

    def interaction(
        self,
        assignments: tuple[PopulationGroupAssignment, ...]
        | list[PopulationGroupAssignment],
        spec: PopulationInteractionSpec,
    ) -> PopulationInteractionResult:
        """Compare within-animal association contrasts across disjoint groups."""
        return infer_population_interaction(
            self.population_estimates, tuple(assignments), spec
        )

    def to_json(self) -> str:
        """Serialize association cells and their actual lower-level support."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def materialize_transient_population(
    sessions: tuple[TransientStudySession, ...] | list[TransientStudySession],
    *,
    metric: TransientMetric,
    channel: str,
    levels: tuple[str, ...],
    session_aggregation: Aggregation = "median",
) -> TransientPopulationMaterialization:
    """Pool transient evidence into one scalar per animal and condition.

    Rates pool event counts over analyzed exposure. Kinetic metrics first summarize
    each session and then aggregate sessions equally within an animal-condition.
    """
    selected_levels = _validate_materialization_inputs(
        levels, channel, session_aggregation, "transient"
    )
    if not sessions:
        raise ValueError("transient population materialization requires sessions")
    _validate_sessions(sessions)
    grouped: dict[tuple[str, str], list[TransientStudySession]] = {}
    for session in sessions:
        if session.condition in selected_levels:
            grouped.setdefault((session.subject, session.condition), []).append(session)

    animal_output: list[TransientAnimalEstimate] = []
    population_output: list[PopulationUnitEstimate] = []
    for (subject, level), subject_sessions in sorted(grouped.items()):
        evidence = [
            (session, *_session_evidence(session, metric, channel))
            for session in subject_sessions
        ]
        usable = [item for item in evidence if item[1] is not None]
        if not usable:
            continue
        session_values = [float(item[1]) for item in usable if item[1] is not None]
        event_count = sum(item[2] for item in usable)
        duration = float(sum(item[3] for item in usable))
        if metric == "rate_per_minute":
            value = 60 * event_count / duration if duration > 0 else float("nan")
        else:
            value = _aggregate(session_values, session_aggregation)
        if not np.isfinite(value):
            continue
        sources = tuple(sorted(item[0].session for item in usable))
        animal_output.append(
            TransientAnimalEstimate(
                subject,
                level,
                metric,
                float(value),
                len(usable),
                event_count,
                duration,
            )
        )
        population_output.append(
            PopulationUnitEstimate(
                unit_id=subject,
                level=level,
                estimate=(float(value),),
                support=(len(usable),),
                source_units=sources,
                observation_count=event_count,
            )
        )
    if not population_output:
        raise ValueError("no transient evidence matches the requested materialization")
    return TransientPopulationMaterialization(
        metric,
        channel,
        selected_levels,
        session_aggregation,
        tuple(animal_output),
        tuple(population_output),
    )


def materialize_state_band_power_population(
    sessions: tuple[StatePSDSession, ...] | list[StatePSDSession],
    *,
    states: tuple[str, ...],
    frequency_band_hz: tuple[float, float],
) -> StateBandPowerPopulationMaterialization:
    """Integrate session spectra, then average sessions within animal-state cells."""
    selected_states = _validate_levels(states, "state")
    low, high = frequency_band_hz
    if low < 0 or low >= high:
        raise ValueError("frequency_band_hz must be increasing and non-negative")
    if not sessions:
        raise ValueError(
            "state band-power population materialization requires sessions"
        )
    identities = [(item.subject, item.session) for item in sessions]
    if any(
        not subject.strip() or not session.strip() for subject, session in identities
    ):
        raise ValueError("state PSD sessions require subject and session identity")
    if len(set(identities)) != len(identities):
        raise ValueError("state PSD subject-session identities must be unique")

    grouped: dict[tuple[str, str], list[tuple[str, float, int]]] = {}
    for session in sessions:
        by_state = {item.state: item for item in session.result.states}
        for state in selected_states:
            if state not in by_state:
                continue
            state_result = by_state[state].result
            grouped.setdefault((session.subject, state), []).append(
                (
                    session.session,
                    _band_power(state_result, frequency_band_hz),
                    state_result.total_window_count,
                )
            )

    animal_output: list[StateBandPowerEstimate] = []
    population_output: list[PopulationUnitEstimate] = []
    for (subject, state), items in sorted(grouped.items()):
        value = float(np.mean([item[1] for item in items]))
        sources = tuple(sorted(item[0] for item in items))
        window_count = sum(item[2] for item in items)
        animal_output.append(StateBandPowerEstimate(subject, state, value, len(items)))
        population_output.append(
            PopulationUnitEstimate(
                unit_id=subject,
                level=state,
                estimate=(value,),
                support=(len(items),),
                source_units=sources,
                observation_count=window_count,
            )
        )
    if not population_output:
        raise ValueError("no state spectra match the requested materialization")
    return StateBandPowerPopulationMaterialization(
        frequency_band_hz,
        selected_states,
        tuple(animal_output),
        tuple(population_output),
    )


def materialize_association_population(
    sessions: tuple[AssociationSessionEstimate, ...] | list[AssociationSessionEstimate],
    *,
    metric: str,
    pair_id: str,
    levels: tuple[str, ...],
    session_aggregation: Aggregation = "mean",
) -> AssociationPopulationMaterialization:
    """Average session association summaries within animal-condition cells."""
    selected_levels = _validate_materialization_inputs(
        levels, pair_id, session_aggregation, "association"
    )
    if not metric.strip():
        raise ValueError("association metric cannot be empty")
    selected = tuple(
        item
        for item in sessions
        if item.metric == metric
        and item.pair_id == pair_id
        and item.condition in selected_levels
    )
    if not selected:
        raise ValueError("no session estimates match the association materialization")
    identities = [(item.subject, item.session, item.condition) for item in selected]
    if len(set(identities)) != len(identities):
        raise ValueError(
            "association subject-session-condition identities must be unique"
        )

    grouped: dict[tuple[str, str], list[AssociationSessionEstimate]] = {}
    for item in selected:
        grouped.setdefault((item.subject, item.condition), []).append(item)
    animal_output: list[AssociationAnimalEstimate] = []
    population_output: list[PopulationUnitEstimate] = []
    for (subject, level), items in sorted(grouped.items()):
        values = np.asarray([item.value for item in items])
        value = float(
            np.mean(values) if session_aggregation == "mean" else np.median(values)
        )
        support = sum(item.support for item in items)
        sources = tuple(sorted(item.session for item in items))
        animal_output.append(
            AssociationAnimalEstimate(
                subject, level, metric, value, len(items), support
            )
        )
        population_output.append(
            PopulationUnitEstimate(
                unit_id=subject,
                level=level,
                estimate=(value,),
                support=(len(items),),
                source_units=sources,
                observation_count=support,
            )
        )
    return AssociationPopulationMaterialization(
        metric,
        pair_id,
        selected_levels,
        session_aggregation,
        tuple(animal_output),
        tuple(population_output),
    )


def _validate_materialization_inputs(
    levels: tuple[str, ...],
    identity: str,
    aggregation: Aggregation,
    domain: str,
) -> tuple[str, ...]:
    selected = _validate_levels(levels, "level")
    if not identity.strip():
        raise ValueError(f"{domain} identity cannot be empty")
    if aggregation not in {"mean", "median"}:
        raise ValueError("session_aggregation must be 'mean' or 'median'")
    return selected


def _validate_levels(levels: tuple[str, ...], label: str) -> tuple[str, ...]:
    if len(levels) < 2:
        raise ValueError(f"population materialization requires at least two {label}s")
    if any(not item.strip() for item in levels):
        raise ValueError(f"population {label} labels cannot be empty")
    if len(set(levels)) != len(levels):
        raise ValueError(f"population {label} labels must be unique")
    return levels
