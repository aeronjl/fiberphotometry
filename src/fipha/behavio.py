"""A dependency-light bridge from photometry observations to Behavio studies."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from fipha.comparability import SessionComparabilityReport
from fipha.design import ObservationTable, Scalar


@dataclass(frozen=True)
class BehavioStudyExport:
    """Validated trial columns ready for ``behavio.Study.from_columns``."""

    columns: Mapping[str, tuple[Scalar, ...]]
    source_columns: Mapping[str, str]
    input_fingerprint: str
    comparability_fingerprint: str | None = None
    comparability_status: str | None = None
    schema_version: str = "2"

    def to_study(self) -> Any:
        """Construct a Behavio Study when the behaviour package is installed."""
        try:
            from behavio import Study
        except ImportError as error:
            raise ValueError(
                "constructing a Study requires behavio; install the 'behavior' "
                "optional dependency (pip install 'fipha[behavior]')"
            ) from error
        return Study.from_columns(self.columns)


def prepare_behavio_study(
    table: ObservationTable,
    *,
    subject: str,
    session: str,
    trial: str,
    session_order: str,
    comparability: SessionComparabilityReport | None = None,
    require_comparability: bool = False,
    allow_comparability_warnings: bool = True,
) -> BehavioStudyExport:
    """Map explicit photometry columns onto Behavio's longitudinal contract.

    Chronology is never inferred from row order or identifiers. All source columns
    are retained, while the four required Behavio columns are added under canonical
    names. fipha owns the neural values; behavio owns downstream behavioural
    clocks, models, and forward-session validation.
    """
    mapping = {
        "subject": subject,
        "session": session,
        "trial": trial,
        "session_order": session_order,
    }
    missing = sorted(set(mapping.values()) - set(table.columns))
    if missing:
        raise ValueError(f"Behavio export is missing source columns: {missing}")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Behavio source columns must be distinct")
    for target, source in mapping.items():
        if target in table.columns and target != source:
            raise ValueError(
                f"cannot replace existing canonical column {target!r} from {source!r}"
            )

    columns = {name: tuple(values) for name, values in table.columns.items()}
    for target, source in mapping.items():
        columns[target] = tuple(table.columns[source])
    _validate_longitudinal_keys(columns)
    if comparability is None and require_comparability:
        raise ValueError("Behavio export requires a session comparability report")
    if comparability is not None:
        comparability.require_ready(allow_warnings=allow_comparability_warnings)
        export_sessions = frozenset(
            (str(subject_value), str(session_value))
            for subject_value, session_value in zip(
                columns["subject"], columns["session"], strict=True
            )
        )
        missing_sessions = sorted(export_sessions - comparability.session_keys)
        if missing_sessions:
            raise ValueError(
                "session comparability does not cover Behavio sessions: "
                f"{missing_sessions}"
            )
    payload = {
        "columns": columns,
        "source_columns": mapping,
        "comparability_fingerprint": (
            comparability.input_fingerprint if comparability is not None else None
        ),
        "comparability_status": (
            comparability.status if comparability is not None else None
        ),
        "schema_version": "2",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return BehavioStudyExport(
        columns=columns,
        source_columns=mapping,
        input_fingerprint=fingerprint,
        comparability_fingerprint=(
            comparability.input_fingerprint if comparability is not None else None
        ),
        comparability_status=(
            comparability.status if comparability is not None else None
        ),
    )


def _validate_longitudinal_keys(columns: Mapping[str, tuple[Scalar, ...]]) -> None:
    sessions: dict[tuple[object, object], int] = {}
    orders: dict[tuple[object, int], object] = {}
    trials: set[tuple[object, object, int]] = set()
    for row, (subject, session, trial, order) in enumerate(
        zip(
            columns["subject"],
            columns["session"],
            columns["trial"],
            columns["session_order"],
            strict=True,
        )
    ):
        if subject is None or session is None:
            raise ValueError(
                f"Behavio subject and session must be present at row {row}"
            )
        if isinstance(trial, (bool, np.bool_)) or not isinstance(
            trial, (int, np.integer)
        ):
            raise ValueError(f"Behavio trial must be an integer at row {row}")
        if isinstance(order, (bool, np.bool_)) or not isinstance(
            order, (int, np.integer)
        ):
            raise ValueError(f"Behavio session_order must be an integer at row {row}")
        trial_value, order_value = int(trial), int(order)
        if trial_value < 0 or order_value < 0:
            raise ValueError("Behavio trial and session_order must be non-negative")
        session_key = (subject, session)
        known_order = sessions.setdefault(session_key, order_value)
        if known_order != order_value:
            raise ValueError("Behavio session_order must be constant within session")
        order_key = (subject, order_value)
        known_session = orders.setdefault(order_key, session)
        if known_session != session:
            raise ValueError(
                "Behavio session_order must identify one session per subject"
            )
        trial_key = (subject, session, trial_value)
        if trial_key in trials:
            raise ValueError("Behavio subject/session/trial keys must be unique")
        trials.add(trial_key)
