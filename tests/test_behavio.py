import sys

import pytest

from fipha.behavio import prepare_behavio_study
from fipha.design import ObservationTable


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


def test_prepare_behavio_study_retains_neural_and_behavioral_columns() -> None:
    export = prepare_behavio_study(
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


def test_prepare_behavio_study_rejects_ambiguous_chronology() -> None:
    table = ObservationTable.from_columns(
        {
            "animal": ["a", "a"],
            "recording": ["s1", "s1"],
            "event_index": [0, 1],
            "day": [0, 1],
        }
    )

    with pytest.raises(ValueError, match="constant within session"):
        prepare_behavio_study(
            table,
            subject="animal",
            session="recording",
            trial="event_index",
            session_order="day",
        )


def test_behavio_export_constructs_a_real_study() -> None:
    """Exercise the genuine dependency rather than a stubbed module."""

    behavio = pytest.importorskip("behavio")
    export = prepare_behavio_study(
        _table(),
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="day",
    )
    study = export.to_study()

    assert isinstance(study, behavio.Study)
    assert set(export.columns) <= set(study.columns)
    assert tuple(study["neural_response"]) == (0.1, 0.2, 0.4, 0.3)
    assert tuple(study["session_order"]) == (0, 0, 1, 1)
    assert study.subjects == ("a",)


def test_behavio_export_names_the_extra_when_behavio_is_absent(monkeypatch) -> None:
    """Without behavio installed the handoff must say which extra to install."""

    monkeypatch.setitem(sys.modules, "behavio", None)
    export = prepare_behavio_study(
        _table(),
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="day",
    )

    with pytest.raises(ValueError, match=r"fipha\[behavior\]"):
        export.to_study()
