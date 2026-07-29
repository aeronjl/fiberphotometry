import json

import numpy as np
import pytest

from fipha import (
    TabularChannel,
    TabularEventColumn,
    TabularEventSchema,
    TabularRecordingSchema,
    inspect_tabular_input,
    inspect_tabular_recording,
    load_tabular_events,
    load_tabular_input,
    load_tabular_recording,
)
from fipha.io.tabular import inspect_loaded_tabular_input


def _write_sources(tmp_path):
    recording = tmp_path / "recording.csv"
    recording.write_text(
        "time_ms,dms_470,dms_405,nac_470,nac_405\n"
        "0,10,1,20,2\n"
        "50,11,1.1,21,2.1\n"
        "100,,1.2,22,2.2\n"
        "151,13,1.3,23,2.3\n"
    )
    events = tmp_path / "events.tsv"
    events.write_text(
        "onset_ms\tevent\tcondition\trewarded\ttrial\n"
        "50\te-1\tcontrol\tno\t1\n"
        "100\te-2\tdrug\tyes\t2\n"
    )
    return recording, events


def _recording_schema() -> TabularRecordingSchema:
    return TabularRecordingSchema(
        "time_ms",
        (
            TabularChannel("DMS", "dms_470", "dms_405"),
            TabularChannel("NAc", "nac_470", "nac_405"),
        ),
        time_unit="milliseconds",
    )


def _event_schema() -> TabularEventSchema:
    return TabularEventSchema(
        "onset_ms",
        "event",
        (
            TabularEventColumn("condition"),
            TabularEventColumn("rewarded", kind="bool"),
            TabularEventColumn("trial", kind="int"),
        ),
        time_unit="milliseconds",
    )


def test_load_tabular_input_preserves_identity_types_and_provenance(tmp_path) -> None:
    recording_path, event_path = _write_sources(tmp_path)

    item = load_tabular_input(
        recording_path,
        _recording_schema(),
        event_path,
        _event_schema(),
        subject="mouse-01",
        session="session-01",
    )

    assert item.recording.channel.values.tolist() == ["DMS", "NAc"]
    assert np.allclose(item.recording.time.values, [0, 0.05, 0.1, 0.151])
    assert np.isnan(item.recording.signal.values[2, 0])
    assert item.event_times == (0.05, 0.1)
    assert item.columns == {
        "condition": ("control", "drug"),
        "rewarded": (False, True),
        "trial": (1, 2),
    }
    assert item.recording.attrs["source_name"] == "recording.csv"
    assert len(item.recording.attrs["source_sha256"]) == 64
    assert "/" not in item.recording.attrs["source_name"]
    schema = json.loads(item.recording.attrs["tabular_schema"])
    assert schema["channels"][0]["reference_column"] == "dms_405"
    assert len(item.recording.attrs["event_source_sha256"]) == 64


def test_inspection_reports_sampling_and_missingness(tmp_path) -> None:
    recording_path, _ = _write_sources(tmp_path)

    report = inspect_tabular_recording(
        recording_path,
        _recording_schema(),
        subject="mouse-01",
        session="session-01",
    )

    assert report.row_count == 4
    assert report.estimated_rate_hz == pytest.approx(20)
    assert report.channels[0].signal_finite_fraction == 0.75
    assert report.warnings == ("irregular_sampling", "missing_signal_values")
    assert json.loads(report.to_json())["channels"][0]["channel"] == "DMS"


def test_input_inspection_reports_event_clock_coverage(tmp_path) -> None:
    recording_path, event_path = _write_sources(tmp_path)
    event_path.write_text(
        "onset_ms\tevent\tcondition\trewarded\ttrial\n"
        "-10\te-1\tcontrol\tno\t1\n"
        "200\te-2\tdrug\tyes\t2\n"
    )

    report = inspect_tabular_input(
        recording_path,
        _recording_schema(),
        event_path,
        _event_schema(),
        subject="mouse-01",
        session="session-01",
    )

    assert report.events.row_count == 2
    assert report.events.metadata_columns == ("condition", "rewarded", "trial")
    assert report.warnings == (
        "irregular_sampling",
        "missing_signal_values",
        "events_before_recording",
        "events_after_recording",
    )
    assert json.loads(report.to_json())["events"]["source_name"] == "events.tsv"

    loaded = load_tabular_input(
        recording_path,
        _recording_schema(),
        event_path,
        _event_schema(),
        subject="mouse-01",
        session="session-01",
    )
    assert inspect_loaded_tabular_input(loaded) == report


def test_tabular_mapping_rejects_partial_reference_identity(tmp_path) -> None:
    recording_path, _ = _write_sources(tmp_path)
    schema = TabularRecordingSchema(
        "time_ms",
        (
            TabularChannel("DMS", "dms_470", "dms_405"),
            TabularChannel("NAc", "nac_470"),
        ),
        time_unit="milliseconds",
    )

    with pytest.raises(ValueError, match="every channel or none"):
        load_tabular_recording(
            recording_path, schema, subject="mouse-01", session="session-01"
        )


def test_tabular_mapping_rejects_missing_columns_and_duplicate_events(tmp_path) -> None:
    recording_path, event_path = _write_sources(tmp_path)
    missing = TabularRecordingSchema(
        "time_ms", (TabularChannel("DMS", "unknown"),), time_unit="milliseconds"
    )
    with pytest.raises(ValueError, match="missing columns: unknown"):
        load_tabular_recording(
            recording_path, missing, subject="mouse-01", session="session-01"
        )

    event_path.write_text(
        "onset_ms\tevent\tcondition\trewarded\ttrial\n"
        "50\te-1\tcontrol\tno\t1\n"
        "100\te-1\tdrug\tyes\t2\n"
    )
    with pytest.raises(ValueError, match="must be unique"):
        load_tabular_events(event_path, _event_schema())


def test_tabular_mapping_rejects_overlapping_scientific_roles(tmp_path) -> None:
    recording_path, _ = _write_sources(tmp_path)
    schema = TabularRecordingSchema(
        "time_ms",
        (TabularChannel("DMS", "dms_470", "dms_470"),),
        time_unit="milliseconds",
    )

    with pytest.raises(ValueError, match="must not overlap"):
        load_tabular_recording(
            recording_path, schema, subject="mouse-01", session="session-01"
        )


def test_single_event_is_valid(tmp_path) -> None:
    _, event_path = _write_sources(tmp_path)
    event_path.write_text(
        "onset_ms\tevent\tcondition\trewarded\ttrial\n50\te-1\tcontrol\tno\t1\n"
    )

    events = load_tabular_events(event_path, _event_schema())

    assert events.event_ids == ("e-1",)
    assert json.loads(_event_schema().to_json())["columns"][1]["kind"] == "bool"
