import sys
from types import ModuleType

import pytest

from fiberphotometry.design import ObservationTable
from fiberphotometry.unspool import prepare_unspool_study


def _table() -> ObservationTable:
    return ObservationTable.from_columns(
        {
            "animal": ["a", "a", "a", "a"],
            "recording": ["s1", "s1", "s2", "s2"],
            "event_index": [0, 1, 0, 1],
            "day": [0, 0, 1, 1],
            "neural_response": [0.1, 0.2, 0.4, 0.3],
            "choice": [0, 1, 1, 1],
        }
    )


def test_prepare_unspool_study_retains_neural_and_behavioral_columns() -> None:
    export = prepare_unspool_study(
        _table(),
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="day",
    )

    assert export.columns["subject"] == ("a", "a", "a", "a")
    assert export.columns["session_order"] == (0, 0, 1, 1)
    assert export.columns["neural_response"] == (0.1, 0.2, 0.4, 0.3)
    assert export.columns["choice"] == (0, 1, 1, 1)
    assert export.source_columns["subject"] == "animal"
    assert len(export.input_fingerprint) == 64


def test_prepare_unspool_study_rejects_ambiguous_chronology() -> None:
    table = ObservationTable.from_columns(
        {
            "animal": ["a", "a"],
            "recording": ["s1", "s1"],
            "event_index": [0, 1],
            "day": [0, 1],
        }
    )

    with pytest.raises(ValueError, match="constant within session"):
        prepare_unspool_study(
            table,
            subject="animal",
            session="recording",
            trial="event_index",
            session_order="day",
        )


def test_unspool_export_constructs_optional_study(monkeypatch) -> None:
    class FakeStudy:
        @classmethod
        def from_columns(cls, columns):
            return columns

    module = ModuleType("unspool")
    module.Study = FakeStudy  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "unspool", module)
    export = prepare_unspool_study(
        _table(),
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="day",
    )

    assert export.to_study()["neural_response"] == (0.1, 0.2, 0.4, 0.3)
