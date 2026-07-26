import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from fiberphotometry.cli import main
from fiberphotometry.project import TabularProjectConfig


def _project(tmp_path: Path, *, acknowledge: bool = True, nwb: bool = False) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    sessions = []
    for animal_index in range(4):
        recording = data / f"recording-{animal_index + 1}.csv"
        events = data / f"events-{animal_index + 1}.csv"
        time = np.arange(0, 14, 0.05)
        reference = 1 + 0.04 * np.sin(time / 3)
        signal = 2 + 0.5 * reference
        event_times = [4.0, 6.0, 8.0, 10.0]
        conditions = ["control", "drug", "control", "drug"]
        for event_time, condition in zip(event_times, conditions, strict=True):
            if condition == "drug":
                signal[(time >= event_time) & (time < event_time + 0.5)] += (
                    0.06 + animal_index * 0.005
                )
        recording.write_text(
            "time,signal,reference\n"
            + "".join(
                f"{sample_time:.3f},{sample:.8f},{control:.8f}\n"
                for sample_time, sample, control in zip(
                    time, signal, reference, strict=True
                )
            )
        )
        events.write_text(
            "time,event_id,condition\n"
            + "".join(
                f"{event_time},e-{animal_index + 1}-{index + 1},{condition}\n"
                for index, (event_time, condition) in enumerate(
                    zip(event_times, conditions, strict=True)
                )
            )
        )
        sessions.append(
            f"""[[sessions]]
subject = "mouse-{animal_index + 1:02d}"
session = "session-{animal_index + 1:02d}"
recording = "data/{recording.name}"
events = "data/{events.name}"
{f"session_start_time = 2026-01-{animal_index + 1:02d}T12:00:00Z" if nwb else ""}

"""
        )
    assumptions = (
        '  "approximately_gaussian_unit_differences",\n'
        '  "complete_pairs",\n'
        '  "estimand_matches_question",\n'
        '  "independent_aggregation_units",\n'
        if acknowledge
        else ""
    )
    project = tmp_path / "project.toml"
    project.write_text(
        """schema_version = "1"
output_directory = "artifacts"

"""
        + "".join(sessions)
        + (
            """[nwb]
session_description = "Synthetic CLI photometry session"
identifier_prefix = "cli-fixture"

"""
            if nwb
            else ""
        )
        + f"""[recording]
time_column = "time"
time_unit = "seconds"

[[recording.channels]]
name = "DMS"
signal_column = "signal"
reference_column = "reference"

[events]
time_column = "time"
event_id_column = "event_id"
time_unit = "seconds"

[[events.columns]]
source = "condition"

[analysis]
schema_version = "1"
title = "CLI feedback response"

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
{assumptions}]

[analysis.quality]
blocking_warnings = []
"""
    )
    return project


def test_cli_inspects_and_runs_complete_tabular_project(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    preflight_path = tmp_path / "preflight-only.json"
    output = tmp_path / "results"

    assert main(["inspect", str(project_path), "--output", str(preflight_path)]) == 0
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0

    project = TabularProjectConfig.from_toml(project_path)
    preflight = json.loads(preflight_path.read_text())
    analysis = json.loads((output / "analysis.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert preflight["project_sha256"] == project.fingerprint
    assert len(preflight["sessions"]) == 4
    readiness = {
        item["target"]: item for item in preflight["metadata_completeness"]["readiness"]
    }
    assert readiness["analysis"]["status"] == "ready"
    assert readiness["nwb"]["status"] == "incomplete"
    assert readiness["publication"]["status"] == "incomplete"
    assert analysis["analysis"] is not None
    assert analysis["configuration_sha256"] == project.fingerprint
    assert analysis["data_summary"] == {"animals": 4, "events": 16, "sessions": 4}
    assert manifest["status"] == "complete"
    for name in ("metadata.json", "preflight.json", "analysis.json", "report.html"):
        assert (
            manifest["artifacts"][name]["sha256"]
            == hashlib.sha256((output / name).read_bytes()).hexdigest()
        )
    assert (output / "manifest.json").is_file()
    assert "Analysis artifacts written" in capsys.readouterr().out


def test_cli_inspect_does_not_bypass_run_assumption_gate(tmp_path, capsys) -> None:
    project_path = _project(tmp_path, acknowledge=False)

    assert main(["inspect", str(project_path)]) == 0
    assert main(["run", str(project_path)]) == 2

    captured = capsys.readouterr()
    assert '"sessions"' in captured.out
    assert "unacknowledged analysis assumptions" in captured.err
    manifest = json.loads((tmp_path / "artifacts" / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert "unacknowledged" in manifest["error"]
    assert (tmp_path / "artifacts" / "preflight.json").is_file()
    assert not (tmp_path / "artifacts" / "analysis.json").exists()


def test_project_config_rejects_unknown_input_keys(tmp_path) -> None:
    project_path = _project(tmp_path)
    project_path.write_text(
        project_path.read_text().replace(
            'output_directory = "artifacts"',
            'output_directory = "artifacts"\nmagic = true',
        )
    )

    assert main(["inspect", str(project_path)]) == 2


def test_cli_exports_valid_provenance_complete_nwb(tmp_path) -> None:
    pynwb = pytest.importorskip("pynwb")
    project_path = _project(tmp_path, nwb=True)
    output = tmp_path / "results"

    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0

    paths = sorted((output / "nwb").glob("*.nwb"))
    assert len(paths) == 4
    assert not pynwb.validate(path=str(paths[0]))
    with pynwb.NWBHDF5IO(paths[0], "r") as io:
        nwbfile = io.read()
        assert nwbfile.subject.subject_id == "mouse-01"
        assert set(nwbfile.acquisition) == {
            "RawFiberPhotometryReference",
            "RawFiberPhotometrySignal",
        }
        assert (
            "ProcessedFiberPhotometrySignal"
            in nwbfile.processing["fiberphotometry"].data_interfaces
        )
        assert len(nwbfile.trials) == 4
        assert set(nwbfile.trials.colnames) >= {"event_id", "condition"}
        assert set(nwbfile.scratch) == {
            "fiberphotometry_analysis",
            "fiberphotometry_metadata_completeness",
            "fiberphotometry_project",
            "fiberphotometry_session_preflight",
            "fiberphotometry_session_qc",
        }
        comments = (
            nwbfile.processing["fiberphotometry"]
            .data_interfaces["ProcessedFiberPhotometrySignal"]
            .comments
        )
        assert "fiberphotometry_operations" in comments
    manifest = json.loads((output / "manifest.json").read_text())
    for path in paths:
        name = f"nwb/{path.name}"
        assert (
            manifest["artifacts"][name]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )


def test_complete_metadata_profile_is_publication_ready(tmp_path) -> None:
    project_path = _project(tmp_path, nwb=True)
    project_path.write_text(
        project_path.read_text().replace(
            'output_directory = "artifacts"',
            '''output_directory = "artifacts"

[metadata]
experimenters = ["A. Scientist"]
institution = "Example University"
lab = "Example Lab"
experiment_description = "Within-animal photometry contrast"
protocol = "https://example.org/protocol"
species = "Mus musculus"
indicator = "GCaMP"
brain_regions = ["DMS"]
acquisition_system = "Example lock-in system"
data_license = "CC-BY-4.0"
implant_batch = "2026-07-A"''',
        )
    )

    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0

    report = json.loads((output / "metadata.json").read_text())
    readiness = {item["target"]: item for item in report["readiness"]}
    assert report["unrecognized_fields"] == ["implant_batch"]
    assert {target: item["status"] for target, item in readiness.items()} == {
        "analysis": "ready",
        "nwb": "ready",
        "publication": "ready",
    }


def test_nwb_export_rejects_timezone_free_session_metadata(tmp_path) -> None:
    project_path = _project(tmp_path, nwb=True)
    project_path.write_text(project_path.read_text().replace("T12:00:00Z", "T12:00:00"))

    assert main(["inspect", str(project_path)]) == 2
