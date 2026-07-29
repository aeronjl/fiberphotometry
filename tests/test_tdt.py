import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from fiberphotometry import (
    TDTBlockSchema,
    TDTEpocEvents,
    TDTEpocValue,
    TDTStreamChannel,
    load_tdt_input,
)
from fiberphotometry.cli import run_project
from fiberphotometry.io.tabular import inspect_loaded_tabular_input
from fiberphotometry.project import TDTProjectConfig, load_project_config


def _schema() -> TDTBlockSchema:
    return TDTBlockSchema(
        channels=(
            TDTStreamChannel("DMS", "x465A", 1, "x405A", 1),
            TDTStreamChannel("NAc", "x465A", 2, "x405A", 2),
        ),
        events=TDTEpocEvents(
            "Trl_",
            "condition",
            (TDTEpocValue(1, "control"), TDTEpocValue(2, "drug")),
        ),
    )


def _block(*, reference_fs: float = 20, event_values=(1.0, 2.0)):
    return SimpleNamespace(
        streams=SimpleNamespace(
            x465A=SimpleNamespace(
                data=np.asarray([[10, 11, 12, 13, 14, 15], [20, 21, 22, 23, 24, 25]]),
                fs=20,
                start_time=0.25,
            ),
            x405A=SimpleNamespace(
                data=np.asarray(
                    [[1, 1.1, 1.2, 1.3, 1.4, 1.5], [2, 2.1, 2.2, 2.3, 2.4, 2.5]]
                ),
                fs=reference_fs,
                start_time=0.25,
            ),
        ),
        epocs=SimpleNamespace(
            Trl_=SimpleNamespace(
                onset=np.asarray([0.3, 0.45]),
                offset=np.asarray([0.31, 0.46]),
                data=np.asarray(event_values),
            )
        ),
    )


def test_tdt_adapter_maps_sdk_streams_epocs_and_provenance(tmp_path) -> None:
    block_path = tmp_path / "Subject-Block-1"
    block_path.mkdir()
    calls = []

    def reader(path, **kwargs):
        calls.append((path, kwargs))
        return _block()

    first = load_tdt_input(
        block_path,
        _schema(),
        subject="mouse-01",
        session="session-01",
        reader=reader,
    )
    second = load_tdt_input(
        block_path,
        _schema(),
        subject="mouse-01",
        session="session-01",
        reader=reader,
    )

    assert calls[0][1] == {
        "evtype": ["streams", "epocs"],
        "store": ["Trl_", "x405A", "x465A"],
        "verbose": 0,
    }
    assert first.recording.channel.values.tolist() == ["DMS", "NAc"]
    assert np.allclose(first.recording.time.values, [0.25, 0.3, 0.35, 0.4, 0.45, 0.5])
    assert first.recording.signal.values[:, 1].tolist() == [20, 21, 22, 23, 24, 25]
    assert first.recording.reference.values[:, 0].tolist() == [
        1,
        1.1,
        1.2,
        1.3,
        1.4,
        1.5,
    ]
    assert first.event_times == (0.3, 0.45)
    assert first.event_ids == ("session-01:Trl_:1", "session-01:Trl_:2")
    assert first.columns == {
        "condition": ("control", "drug"),
        "tdt_epoc_value": (1.0, 2.0),
        "tdt_epoc_offset": (0.31, 0.46),
    }
    assert first.recording.attrs["source_format"] == "TDT_block"
    assert first.recording.attrs["source_fingerprint_scope"] == (
        "declared_stream_channels_and_epoc_content"
    )
    assert (
        first.recording.attrs["source_sha256"]
        == second.recording.attrs["source_sha256"]
    )
    changed_block = _block()
    changed_block.streams.x465A.data[0, 0] += 1
    changed = load_tdt_input(
        block_path,
        _schema(),
        subject="mouse-01",
        session="session-01",
        reader=lambda *args, **kwargs: changed_block,
    )
    assert (
        first.recording.attrs["source_sha256"]
        != changed.recording.attrs["source_sha256"]
    )
    inspection = inspect_loaded_tabular_input(first)
    assert inspection.recording.estimated_rate_hz == pytest.approx(20)
    assert inspection.events.metadata_columns == (
        "condition",
        "tdt_epoc_value",
        "tdt_epoc_offset",
    )


def test_tdt_adapter_rejects_unaligned_streams(tmp_path) -> None:
    block_path = tmp_path / "block"
    block_path.mkdir()

    with pytest.raises(ValueError, match="different sampling rates"):
        load_tdt_input(
            block_path,
            _schema(),
            subject="mouse",
            session="session",
            reader=lambda *args, **kwargs: _block(reference_fs=10),
        )


def test_tdt_adapter_rejects_unmapped_epoc_values(tmp_path) -> None:
    block_path = tmp_path / "block"
    block_path.mkdir()

    with pytest.raises(ValueError, match=r"unmapped values: \[3.0\]"):
        load_tdt_input(
            block_path,
            _schema(),
            subject="mouse",
            session="session",
            reader=lambda *args, **kwargs: _block(event_values=(1, 3)),
        )


def test_tdt_schema_rejects_partial_reference_mapping(tmp_path) -> None:
    block_path = tmp_path / "block"
    block_path.mkdir()
    schema = TDTBlockSchema(
        channels=(
            TDTStreamChannel("DMS", "x465A", 1, "x405A", 1),
            TDTStreamChannel("NAc", "x465A", 2),
        ),
        events=_schema().events,
    )

    with pytest.raises(ValueError, match="every channel or none"):
        load_tdt_input(
            block_path,
            schema,
            subject="mouse",
            session="session",
            reader=lambda *args, **kwargs: _block(),
        )


def test_tdt_project_runs_through_shared_artifact_boundary(tmp_path: Path) -> None:
    sessions = []
    for index in range(4):
        block = tmp_path / f"block-{index + 1}"
        block.mkdir()
        sessions.append(
            f'''[[sessions]]
subject = "mouse-{index + 1:02d}"
session = "session-{index + 1:02d}"
block = "{block.name}"

'''
        )
    project_path = tmp_path / "tdt-project.toml"
    project_path.write_text(
        """schema_version = "1"
input_format = "tdt"
output_directory = "artifacts"

"""
        + "".join(sessions)
        + """[tdt]

[[tdt.channels]]
name = "DMS"
signal_store = "x465A"
signal_channel = 1
reference_store = "x405A"
reference_channel = 1

[tdt.events]
store = "Trl_"
factor_name = "condition"

[[tdt.events.values]]
value = 1
label = "control"

[[tdt.events.values]]
value = 2
label = "drug"

[analysis]
schema_version = "1"
title = "TDT CLI fixture"

[analysis.contrast]
factor = "condition"
numerator = "drug"
denominator = "control"

[analysis.channel]
name = "DMS"

[analysis.preprocessing]
kind = "reference"
method = "irls"
normalization = "divide"

[analysis.event_windows]
baseline = [-0.5, 0.0]
response = [0.0, 0.5]

[analysis.inference]
intent = "exploratory"
randomized = false
acknowledged_assumptions = [
  "approximately_gaussian_unit_differences",
  "complete_pairs",
  "estimand_matches_question",
  "independent_aggregation_units",
]

[analysis.quality]
blocking_warnings = []
"""
    )

    def reader(path, **kwargs):
        animal_index = int(Path(path).name.rsplit("-", 1)[1]) - 1
        time = np.arange(0, 14, 0.05)
        reference = 1 + 0.04 * np.sin(time / 3)
        signal = 2 + 0.5 * reference
        event_times = np.asarray([4.0, 6.0, 8.0, 10.0])
        values = np.asarray([1.0, 2.0, 1.0, 2.0])
        for event_time, value in zip(event_times, values, strict=True):
            if value == 2:
                signal[(time >= event_time) & (time < event_time + 0.5)] += (
                    0.06 + animal_index * 0.005
                )
        return SimpleNamespace(
            streams=SimpleNamespace(
                x465A=SimpleNamespace(data=signal, fs=20, start_time=0),
                x405A=SimpleNamespace(data=reference, fs=20, start_time=0),
            ),
            epocs=SimpleNamespace(
                Trl_=SimpleNamespace(
                    onset=event_times,
                    offset=event_times + 0.1,
                    data=values,
                )
            ),
        )

    project = load_project_config(project_path)
    assert isinstance(project, TDTProjectConfig)
    loaded = project.load(reader=reader)
    output = run_project(project, loaded, tmp_path / "results")

    analysis = json.loads((output / "analysis.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    preflight = json.loads((output / "preflight.json").read_text())
    assert analysis["data_summary"] == {"animals": 4, "events": 16, "sessions": 4}
    assert manifest["status"] == "complete"
    assert (
        preflight["sessions"][0]["inspection"]["recording"]["source_fingerprint_scope"]
        == "declared_stream_channels_and_epoc_content"
    )
