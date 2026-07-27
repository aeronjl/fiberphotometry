import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from fiberphotometry.cli import main
from fiberphotometry.project import TabularProjectConfig


def _project(
    tmp_path: Path,
    *,
    acknowledge: bool = True,
    nwb: bool = False,
    mixed_model: bool = False,
) -> Path:
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
scalar_mixed_model = {str(mixed_model).lower()}
contrast_unit = "session"
acknowledged_assumptions = [
{assumptions}]

[analysis.quality]
blocking_warnings = []
"""
    )
    return project


def _declare_multiverse(project: Path, *, cutoff_hz: float = 3.0) -> None:
    project.write_text(
        project.read_text()
        + f"""

[multiverse]
schema_version = "1"
intent = "exploratory"
direction = "positive"
smallest_effect = 0.001
leave_one_animal_out = true
reference_preprocessing = "filtered_irls"
reference_response_window = "half_second"

[[multiverse.preprocessing]]
name = "filtered_irls"
rationale = "Suppress high-frequency acquisition noise before robust correction."
method = "irls"
lowpass_hz = {cutoff_hz}

[[multiverse.preprocessing]]
name = "unfiltered_ols"
rationale = "Test dependence on filtering and robust regression."
method = "ols"

[[multiverse.response_windows]]
name = "half_second"
rationale = "Match the primary event definition."
response = [0.0, 0.5]

[[multiverse.response_windows]]
name = "quarter_second"
rationale = "Test sensitivity to an early-response definition."
response = [0.0, 0.25]
"""
    )


def _declare_signal_only_multiverse(project: Path) -> None:
    project.write_text(
        project.read_text().replace(
            'kind = "reference"\nmethod = "irls"',
            'kind = "signal_only"\nmethod = "rolling_mean"',
        )
        + """

[multiverse]
schema_version = "1"
intent = "exploratory"
reference_preprocessing = "rolling_divide"
reference_response_window = "half_second"

[[multiverse.preprocessing]]
name = "rolling_divide"
rationale = "Estimate slow drift with a rolling baseline and divide."
kind = "signal_only"
method = "rolling_mean"
normalization = "divide"
rolling_window_s = 4.0

[[multiverse.preprocessing]]
name = "rolling_subtract"
rationale = "Test dependence on divisive versus subtractive normalization."
kind = "signal_only"
method = "rolling_mean"
normalization = "subtract"
rolling_window_s = 4.0

[[multiverse.preprocessing]]
name = "regularized_asls"
rationale = "Test an asymmetric smooth baseline on an explicit regular clock."
kind = "signal_only"
method = "asls"
normalization = "divide"
resample_rate_hz = "median"
resample_max_gap_factor = 1.5
lowpass_hz = 3.0

[[multiverse.preprocessing]]
name = "double_exponential"
rationale = "Test a parametric bleaching trajectory."
kind = "signal_only"
method = "double_exponential"
normalization = "divide"

[[multiverse.response_windows]]
name = "half_second"
rationale = "Match the primary event definition."
response = [0.0, 0.5]

[[multiverse.response_windows]]
name = "quarter_second"
rationale = "Test sensitivity to an early-response definition."
response = [0.0, 0.25]
"""
    )


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


def test_cli_materializes_and_runs_declared_multiverse(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    _declare_multiverse(project_path)
    preflight_path = tmp_path / "preflight.json"
    output = tmp_path / "robustness"

    assert main(["inspect", str(project_path), "--output", str(preflight_path)]) == 0
    assert main(["multiverse", str(project_path), "--output-dir", str(output)]) == 0

    preflight = json.loads(preflight_path.read_text())
    result = json.loads((output / "multiverse.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(preflight["multiverse"]["universes"]) == 4
    assert {
        item["status"] for item in preflight["multiverse"]["compatibility"]["universes"]
    } == {"compatible"}
    assert preflight["multiverse"]["compatibility"]["outcome_values_accessed"] is False
    assert result["summary"]["total_universes"] == 4
    assert result["summary"]["successful_universes"] == 4
    assert len(result["leave_one_out"]) == 4
    assert sum(item["is_reference"] for item in result["universes"]) == 1
    assert manifest["status"] == "complete"
    assert set(manifest["artifacts"]) == {
        "metadata.json",
        "multiverse.json",
        "preflight.json",
        "robustness.html",
        "robustness-summary.json",
    }
    assert "Robustness artifacts written" in capsys.readouterr().out


def test_cli_rejects_structurally_incompatible_multiverse_before_run(
    tmp_path, capsys
) -> None:
    project_path = _project(tmp_path)
    _declare_multiverse(project_path, cutoff_hz=100.0)

    assert main(["multiverse", str(project_path)]) == 2

    preflight = json.loads((tmp_path / "artifacts" / "preflight.json").read_text())
    statuses = {
        item["status"] for item in preflight["multiverse"]["compatibility"]["universes"]
    }
    assert statuses == {"compatible", "incompatible"}
    assert "before outcome access" in capsys.readouterr().err
    assert not (tmp_path / "artifacts" / "multiverse.json").exists()


def test_cli_runs_signal_only_recipes_in_unit_safe_report_lanes(tmp_path) -> None:
    project_path = _project(tmp_path)
    _declare_signal_only_multiverse(project_path)
    project_path.write_text(
        project_path.read_text()
        + """

[[multiverse.effect_thresholds]]
units = "ΔF/F"
smallest_effect = 0.001
direction = "positive"

[[multiverse.effect_thresholds]]
units = "acquired fluorescence"
smallest_effect = 0.001
direction = "either"
"""
    )
    output = tmp_path / "signal-only"

    assert main(["multiverse", str(project_path), "--output-dir", str(output)]) == 0

    result = json.loads((output / "multiverse.json").read_text())
    lane_summary = json.loads((output / "robustness-summary.json").read_text())
    html = (output / "robustness.html").read_text()
    assert result["summary"]["total_universes"] == 8
    assert result["summary"]["successful_universes"] >= 4
    assert "Divisive normalization" in html
    assert "Subtractive normalization" in html
    assert "Parallel evidence lanes preserve unit" in html
    assert {lane["units"] for lane in lane_summary["lanes"]} == {
        "ΔF/F",
        "acquired fluorescence",
    }
    assert all(
        lane["fraction_meeting_practical_effect"] is not None
        for lane in lane_summary["lanes"]
    )
    assert "practical-effect stability" in html
    for universe in result["universes"]:
        preprocessing = next(
            choice["alternative"]
            for choice in universe["choices"]
            if choice["node"] == "preprocessing"
        )
        variable = universe["pipeline"]["event_summary"]["variable"]
        assert variable == (
            "baseline_subtracted" if preprocessing == "rolling_subtract" else "dff"
        )
        if preprocessing == "regularized_asls":
            assert [
                operation["kind"] for operation in universe["pipeline"]["preprocessing"]
            ] == ["resample", "lowpass_filter", "baseline_dff"]


def test_signal_only_multiverse_rejects_implicit_gap_regularization(tmp_path) -> None:
    project_path = _project(tmp_path)
    _declare_signal_only_multiverse(project_path)
    project_path.write_text(
        project_path.read_text().replace('resample_rate_hz = "median"\n', "")
    )

    assert main(["inspect", str(project_path)]) == 2


def test_signal_only_multiverse_rejects_effect_threshold_across_units(
    tmp_path, capsys
) -> None:
    project_path = _project(tmp_path)
    _declare_signal_only_multiverse(project_path)
    project_path.write_text(
        project_path.read_text().replace(
            '[multiverse]\nschema_version = "1"\nintent = "exploratory"\n',
            '[multiverse]\nschema_version = "1"\n'
            'intent = "exploratory"\nsmallest_effect = 0.01\n',
        )
    )

    assert main(["inspect", str(project_path)]) == 2
    assert "cannot span" in capsys.readouterr().err


def test_signal_only_multiverse_requires_threshold_for_every_unit_lane(
    tmp_path, capsys
) -> None:
    project_path = _project(tmp_path)
    _declare_signal_only_multiverse(project_path)
    project_path.write_text(
        project_path.read_text()
        + """

[[multiverse.effect_thresholds]]
units = "ΔF/F"
smallest_effect = 0.001
"""
    )

    assert main(["inspect", str(project_path)]) == 2
    assert "cover every declared unit lane" in capsys.readouterr().err


def test_cli_requires_multiverse_declaration(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)

    assert main(["multiverse", str(project_path)]) == 2
    assert "does not declare" in capsys.readouterr().err


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


def test_cli_writes_opt_in_scalar_mixed_model_summary(tmp_path) -> None:
    pynwb = pytest.importorskip("pynwb")
    project_path = _project(tmp_path, nwb=True, mixed_model=True)
    output = tmp_path / "results"

    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0

    mixed = json.loads((output / "mixed-model.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert mixed["spec"]["role"] == "sensitivity_analysis"
    assert mixed["engine"] == "statsmodels.MixedLM"
    assert mixed["groups"] == 4
    assert mixed["nested_units"] is None
    assert "mixed-model.json" in manifest["artifacts"]
    assert "mixed-model.html" in manifest["artifacts"]
    assert "Secondary sensitivity estimand" in (output / "mixed-model.html").read_text()
    nwb_path = next((output / "nwb").glob("*.nwb"))
    with pynwb.NWBHDF5IO(nwb_path, "r") as io:
        assert "fiberphotometry_scalar_mixed_model" in io.read().scratch


def test_nwb_export_rejects_timezone_free_session_metadata(tmp_path) -> None:
    project_path = _project(tmp_path, nwb=True)
    project_path.write_text(project_path.read_text().replace("T12:00:00Z", "T12:00:00"))

    assert main(["inspect", str(project_path)]) == 2


def test_cli_preflight_blocks_structurally_incompatible_asls(tmp_path) -> None:
    project_path = _project(tmp_path)
    project_path.write_text(
        project_path.read_text()
        .replace('kind = "reference"', 'kind = "signal_only"')
        .replace('method = "irls"', 'method = "asls"')
    )
    recording = tmp_path / "data" / "recording-1.csv"
    recording.write_text(recording.read_text().replace("0.050,", "0.051,", 1))
    preflight_path = tmp_path / "preflight.json"

    assert main(["inspect", str(project_path), "--output", str(preflight_path)]) == 0
    assert main(["run", str(project_path)]) == 2

    preflight = json.loads(preflight_path.read_text())
    compatibility = preflight["pipeline_compatibility"]
    assert compatibility["status"] == "incompatible"
    assert {issue["code"] for issue in compatibility["issues"]} == {
        "asls_requires_regular_sampling"
    }
    manifest = json.loads((tmp_path / "artifacts" / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert "structurally incompatible" in manifest["error"]


def test_cli_explicit_regularization_makes_jittered_asls_compatible(tmp_path) -> None:
    project_path = _project(tmp_path)
    project_path.write_text(
        project_path.read_text()
        .replace('kind = "reference"', 'kind = "signal_only"')
        .replace('method = "irls"', 'method = "asls"')
        .replace(
            'normalization = "divide"',
            'normalization = "divide"\nresample_rate_hz = "median"\n'
            "resample_max_gap_factor = 1.5",
        )
    )
    recording = tmp_path / "data" / "recording-1.csv"
    recording.write_text(recording.read_text().replace("0.050,", "0.051,", 1))
    preflight_path = tmp_path / "preflight.json"

    assert main(["inspect", str(project_path), "--output", str(preflight_path)]) == 0
    compatibility = json.loads(preflight_path.read_text())["pipeline_compatibility"]
    assert compatibility["status"] == "compatible"
    assert not compatibility["outcome_values_accessed"]
    assert main(["run", str(project_path)]) == 0

    result = json.loads((tmp_path / "artifacts" / "analysis.json").read_text())
    operation = result["processing_lineage"][0]["operations"][0]
    assert operation["kind"] == "resample"
    assert operation["rate_policy"] == "median"
    assert operation["max_gap_factor"] == 1.5
