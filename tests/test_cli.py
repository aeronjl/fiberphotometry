import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from fiberphotometry import cli
from fiberphotometry.cli import main
from fiberphotometry.comparison import compare_project_evidence
from fiberphotometry.io.nwb import series_provenance
from fiberphotometry.project import TabularProjectConfig
from fiberphotometry.publication import PUBLICATION_NAMESPACE
from fiberphotometry.results import read_project_evidence


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
rolling_gap_factor = 1.75

[[multiverse.preprocessing]]
name = "rolling_subtract"
rationale = "Test dependence on divisive versus subtractive normalization."
kind = "signal_only"
method = "rolling_mean"
normalization = "subtract"
rolling_window_s = 4.0
rolling_gap_factor = 1.75

[[multiverse.preprocessing]]
name = "regularized_asls"
rationale = "Test an asymmetric smooth baseline on an explicit regular clock."
kind = "signal_only"
method = "asls"
normalization = "divide"
resample_rate_hz = "median"
resample_max_gap_factor = 1.5
lowpass_hz = 3.0
asls_smoothness = 10000000.0
asls_asymmetry = 0.02
max_iterations = 25
asls_reference_rate_hz = 20.0

[[multiverse.preprocessing]]
name = "double_exponential"
rationale = "Test a parametric bleaching trajectory."
kind = "signal_only"
method = "double_exponential"
normalization = "divide"
min_tau_s = 3.0

[[multiverse.response_windows]]
name = "half_second"
rationale = "Match the primary event definition."
response = [0.0, 0.5]

[[multiverse.response_windows]]
name = "quarter_second"
rationale = "Test sensitivity to an early-response definition."
response = [0.0, 0.25]

[[multiverse.compatibility_rules]]
reason = "The parametric baseline is not supported for the shortened event definition."
when = [
  { node = "preprocessing", alternative = "double_exponential" },
  { node = "response_window", alternative = "quarter_second" },
]
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
    bundle = read_project_evidence(output)
    assert bundle.source_format == "directory"
    assert bundle.kind == "analysis"
    assert bundle.status == "complete"
    assert bundle.manifest_verified is True
    assert bundle.analysis == analysis
    assert bundle.metadata is not None


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
    bundle = read_project_evidence(output)
    assert bundle.kind == "multiverse"
    assert bundle.multiverse == result
    assert bundle.robustness_summary is not None
    assert all(item.verified is True for item in bundle.files)


def test_evidence_reader_rejects_manifest_tampering(tmp_path) -> None:
    project_path = _project(tmp_path)
    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0
    (output / "analysis.json").write_text("{}")

    with pytest.raises(ValueError, match="checksum mismatch"):
        read_project_evidence(output)


def test_evidence_reader_rejects_manifest_path_traversal(tmp_path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    fingerprint = hashlib.sha256(outside.read_bytes()).hexdigest()
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "project": {"name": "project.toml", "sha256": "0" * 64},
                "status": "complete",
                "artifacts": {"../outside.json": {"sha256": fingerprint}},
            }
        )
    )

    with pytest.raises(ValueError, match="unsafe manifest artifact path"):
        read_project_evidence(bundle)


def test_evidence_comparison_ignores_only_volatile_run_provenance(tmp_path) -> None:
    project_path = _project(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert main(["run", str(project_path), "--output-dir", str(first)]) == 0
    assert main(["run", str(project_path), "--output-dir", str(second)]) == 0

    comparison = compare_project_evidence(
        read_project_evidence(first), read_project_evidence(second)
    )

    assert comparison.comparable is True
    assert comparison.same_project is True
    assert comparison.scientifically_equivalent is True
    assert comparison.byte_identical is False
    assert {item.category for item in comparison.differences} <= {"provenance"}
    assert "Scientific result:** reproduced" in comparison.to_markdown()
    report = tmp_path / "comparison.md"
    assert main(["compare", str(first), str(second), "--output", str(report)]) == 0
    assert "Scientific result:** reproduced" in report.read_text()


def test_evidence_comparison_detects_changed_data_and_outcome(tmp_path) -> None:
    project_path = _project(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert main(["run", str(project_path), "--output-dir", str(first)]) == 0
    recording = tmp_path / "data" / "recording-1.csv"
    values = np.genfromtxt(recording, delimiter=",", names=True)
    response = ((values["time"] >= 6) & (values["time"] < 6.5)) | (
        (values["time"] >= 10) & (values["time"] < 10.5)
    )
    values["signal"][response] += 0.1
    np.savetxt(
        recording,
        np.column_stack((values["time"], values["signal"], values["reference"])),
        delimiter=",",
        header="time,signal,reference",
        comments="",
    )
    assert main(["run", str(project_path), "--output-dir", str(second)]) == 0

    comparison = compare_project_evidence(
        read_project_evidence(first), read_project_evidence(second)
    )

    assert comparison.same_project is True
    assert comparison.scientifically_equivalent is False
    assert {item.category for item in comparison.differences} & {
        "data",
        "outcome",
        "quality",
    }
    report = tmp_path / "comparison.json"
    assert main(["compare", str(first), str(second), "--output", str(report)]) == 0
    payload = json.loads(report.read_text())
    assert payload["artifact_type"] == "evidence_bundle_comparison"
    assert payload["scientifically_equivalent"] is False


def test_cli_signs_and_verifies_complete_publication_manifest(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0
    key = tmp_path / "publication-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )
    identity = "scientist@example.org"
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(
        f'{identity} namespaces="{PUBLICATION_NAMESPACE}" '
        f"{key.with_suffix('.pub').read_text()}"
    )

    assert (
        main(
            [
                "sign",
                str(output),
                "--key",
                str(key),
                "--identity",
                identity,
            ]
        )
        == 0
    )
    attestation = json.loads((output / "publication-attestation.json").read_text())
    assert attestation["artifact_type"] == "publication_manifest_attestation"
    assert (
        (output / "publication-attestation.json.sig")
        .read_text()
        .startswith("-----BEGIN SSH SIGNATURE-----")
    )
    capsys.readouterr()
    assert (
        main(
            [
                "verify-signature",
                str(output),
                "--allowed-signers",
                str(allowed),
            ]
        )
        == 0
    )
    verification = json.loads(capsys.readouterr().out)
    assert verification["status"] == "verified"
    assert verification["signer_identity"] == identity
    allowed.write_text(f"other@example.org {key.with_suffix('.pub').read_text()}")
    assert (
        main(
            [
                "verify-signature",
                str(output),
                "--allowed-signers",
                str(allowed),
            ]
        )
        == 2
    )
    assert "verification failed" in capsys.readouterr().err


def test_publication_verification_rejects_manifest_tampering(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0
    key = tmp_path / "publication-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )
    identity = "scientist@example.org"
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(f"{identity} {key.with_suffix('.pub').read_text()}")
    assert (
        main(
            [
                "sign",
                str(output),
                "--key",
                str(key),
                "--identity",
                identity,
            ]
        )
        == 0
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["fiberphotometry_version"] = "tampered"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    assert (
        main(
            [
                "verify-signature",
                str(output),
                "--allowed-signers",
                str(allowed),
            ]
        )
        == 2
    )
    assert "does not match manifest bytes" in capsys.readouterr().err


def _archive_metadata(path) -> None:
    path.write_text(
        json.dumps(
            {
                "artifact_type": "fiberphotometry_archive_metadata",
                "schema_version": "1",
                "title": "Reproducible reward photometry analysis",
                "description": "Analysis evidence, provenance, and results.",
                "creators": [
                    {
                        "name": "Laffere, Aeron",
                        "affiliation": "University of Example",
                        "orcid": "0000-0002-1825-0097",
                    }
                ],
                "publication_date": "2026-07-27",
                "publisher": "Zenodo",
                "license": "cc-by-4.0",
                "keywords": ["fiber photometry", "reproducibility"],
                "related_identifiers": [
                    {"identifier": "10.1234/example", "relation": "IsSupplementTo"}
                ],
                "resource_type": "Dataset",
                "language": "en",
            }
        )
    )


def test_cli_creates_reproducible_repository_archive(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0
    capsys.readouterr()
    metadata = tmp_path / "archive-metadata.json"
    _archive_metadata(metadata)
    first = tmp_path / "deposit-a.zip"
    second = tmp_path / "deposit-b.zip"
    assert (
        main(
            [
                "archive",
                str(output),
                "--metadata",
                str(metadata),
                "--output",
                str(first),
            ]
        )
        == 0
    )
    first_result = json.loads(capsys.readouterr().out)
    assert (
        main(
            [
                "archive",
                str(output),
                "--metadata",
                str(metadata),
                "--output",
                str(second),
            ]
        )
        == 0
    )
    second_result = json.loads(capsys.readouterr().out)
    assert first_result["sha256"] == second_result["sha256"]
    assert first.read_bytes() == second.read_bytes()

    import zipfile

    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        assert {
            "archive-metadata.json",
            "archive-manifest.json",
            "datacite.json",
            ".zenodo.json",
        } <= names
        assert "evidence/manifest.json" in names
        assert (
            json.loads(archive.read("datacite.json"))["data"]["attributes"][
                "publicationYear"
            ]
            == 2026
        )
        assert (
            json.loads(archive.read(".zenodo.json"))["creators"][0]["orcid"]
            == "0000-0002-1825-0097"
        )
    assert main(["verify-archive", str(first)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


def test_archive_rejects_invalid_orcid_and_tampering(tmp_path, capsys) -> None:
    project_path = _project(tmp_path)
    output = tmp_path / "results"
    assert main(["run", str(project_path), "--output-dir", str(output)]) == 0
    capsys.readouterr()
    metadata = tmp_path / "archive-metadata.json"
    _archive_metadata(metadata)
    value = json.loads(metadata.read_text())
    value["creators"][0]["orcid"] = "0000-0002-1825-0098"
    metadata.write_text(json.dumps(value))
    archive = tmp_path / "deposit.zip"
    assert (
        main(
            [
                "archive",
                str(output),
                "--metadata",
                str(metadata),
                "--output",
                str(archive),
            ]
        )
        == 2
    )
    assert "ORCID is invalid" in capsys.readouterr().err

    _archive_metadata(metadata)
    assert (
        main(
            [
                "archive",
                str(output),
                "--metadata",
                str(metadata),
                "--output",
                str(archive),
            ]
        )
        == 0
    )
    capsys.readouterr()
    import zipfile

    rewritten = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "evidence/analysis.json":
                content += b"\n"
            target.writestr(info, content)
    assert main(["verify-archive", str(rewritten)]) == 2
    assert "checksum mismatch" in capsys.readouterr().err


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
    assert result["summary"]["incompatible_universes"] == 1
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
            operations = universe["pipeline"]["preprocessing"]
            assert [operation["kind"] for operation in operations] == [
                "resample",
                "lowpass_filter",
                "baseline_dff",
            ]
            assert operations[-1]["asls_smoothness"] == 10000000.0
            assert operations[-1]["asls_asymmetry"] == 0.02
            assert operations[-1]["max_iterations"] == 25


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


def test_signal_only_multiverse_rejects_method_irrelevant_parameters(
    tmp_path, capsys
) -> None:
    project_path = _project(tmp_path)
    _declare_signal_only_multiverse(project_path)
    project_path.write_text(
        project_path.read_text().replace(
            'method = "double_exponential"\nnormalization = "divide"',
            'method = "double_exponential"\nnormalization = "divide"\n'
            "asls_asymmetry = 0.02",
        )
    )

    assert main(["inspect", str(project_path)]) == 2
    assert "invalid for double_exponential" in capsys.readouterr().err


def test_multiverse_rejects_rule_that_excludes_reference_workflow(
    tmp_path, capsys
) -> None:
    project_path = _project(tmp_path)
    _declare_multiverse(project_path)
    project_path.write_text(
        project_path.read_text()
        + """

[[multiverse.compatibility_rules]]
reason = "Invalid fixture excluding the declared reference."
when = [
  { node = "preprocessing", alternative = "filtered_irls" },
  { node = "response_window", alternative = "half_second" },
]
"""
    )

    assert main(["inspect", str(project_path)]) == 2
    assert "reference_selection" in capsys.readouterr().err


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
            "fiberphotometry_series_attributes",
            "fiberphotometry_series_channels",
            "fiberphotometry_session_preflight",
            "fiberphotometry_session_qc",
        }
        provenance = series_provenance(nwbfile, "ProcessedFiberPhotometrySignal")
        assert json.loads(provenance["fiberphotometry_operations"])
        assert provenance["source_variable"] == "dff"
    manifest = json.loads((output / "manifest.json").read_text())
    for path in paths:
        name = f"nwb/{path.name}"
        assert (
            manifest["artifacts"][name]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
    nwb_bundle = read_project_evidence(paths[0])
    assert nwb_bundle.kind == "analysis"
    assert nwb_bundle.analysis is not None
    assert (
        nwb_bundle.project_sha256
        == TabularProjectConfig.from_toml(project_path).fingerprint
    )


def test_cli_exports_multiverse_provenance_without_duplicate_signals(tmp_path) -> None:
    pynwb = pytest.importorskip("pynwb")
    project_path = _project(tmp_path, nwb=True)
    _declare_multiverse(project_path)
    output = tmp_path / "multiverse-results"

    assert main(["multiverse", str(project_path), "--output-dir", str(output)]) == 0

    paths = sorted((output / "nwb").glob("*.nwb"))
    assert len(paths) == 4
    assert not pynwb.validate(path=str(paths[0]))
    with pynwb.NWBHDF5IO(paths[0], "r") as io:
        nwbfile = io.read()
        interfaces = nwbfile.processing["fiberphotometry"].data_interfaces
        assert set(interfaces) == {"ReferenceWorkflowProcessedFiberPhotometrySignal"}
        assert set(nwbfile.scratch) == {
            "fiberphotometry_metadata_completeness",
            "fiberphotometry_multiverse_result",
            "fiberphotometry_project",
            "fiberphotometry_robustness_summary",
            "fiberphotometry_series_attributes",
            "fiberphotometry_series_channels",
            "fiberphotometry_session_preflight",
            "fiberphotometry_session_qc",
        }
        multiverse = json.loads(
            nwbfile.scratch["fiberphotometry_multiverse_result"].data
        )
        summary = json.loads(nwbfile.scratch["fiberphotometry_robustness_summary"].data)
        assert multiverse["summary"]["total_universes"] == 4
        assert summary["artifact_type"] == "multiverse_lane_summary"
        assert sum(item["is_reference"] for item in multiverse["universes"]) == 1
        assert nwbfile.identifier.endswith("-multiverse")
    manifest = json.loads((output / "manifest.json").read_text())
    for path in paths:
        name = f"nwb/{path.name}"
        assert (
            manifest["artifacts"][name]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
    nwb_bundle = read_project_evidence(paths[0])
    assert nwb_bundle.source_format == "nwb"
    assert nwb_bundle.kind == "multiverse"
    assert nwb_bundle.status == "complete"
    assert nwb_bundle.manifest_verified is None
    assert nwb_bundle.multiverse is not None
    assert nwb_bundle.robustness_summary is not None
    cross_format = compare_project_evidence(read_project_evidence(output), nwb_bundle)
    assert cross_format.byte_identical is None
    assert cross_format.same_project is True
    assert cross_format.scientifically_equivalent is True


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


def _write_table(path: Path, columns: dict[str, np.ndarray]) -> Path:
    names = list(columns)
    rows = zip(*(columns[name] for name in names), strict=True)
    path.write_text(
        ",".join(names)
        + "\n"
        + "".join(",".join(repr(float(value)) for value in row) + "\n" for row in rows)
    )
    return path


def _paired_recording(
    path: Path,
    *,
    slope: float = 3.0,
    intercept: float = 0.5,
    rate_hz: float = 20.0,
    duration_s: float = 120.0,
) -> Path:
    time = np.round(np.arange(int(duration_s * rate_hz)) / rate_hz, 6)
    reference = 1 + 0.05 * np.sin(2 * np.pi * 0.01 * time)
    return _write_table(
        path,
        {"time": time, "signal": intercept + slope * reference, "reference": reference},
    )


def _transient_recording(
    path: Path,
    *,
    amplitude: float = 0.25,
    sigma_s: float = 0.3,
    onsets: tuple[float, ...] = (20.0, 45.0, 70.0, 95.0),
) -> Path:
    time = np.round(np.arange(2400) * 0.05, 6)
    reference = 1 + 0.05 * np.sin(2 * np.pi * 0.01 * time)
    dff = np.zeros_like(time)
    for onset in onsets:
        dff += amplitude * np.exp(-0.5 * ((time - onset) / sigma_s) ** 2)
    return _write_table(
        path,
        {
            "time": time,
            "signal": (2.0 + 0.5 * reference) * (1 + dff),
            "reference": reference,
        },
    )


def _run(capsys, argv: list[str]) -> dict:
    assert main(argv) == 0
    return json.loads(capsys.readouterr().out)


def test_qc_recovers_the_analytic_rate_slope_and_correlation(tmp_path, capsys) -> None:
    source = _paired_recording(tmp_path / "recording.csv", slope=3.0, intercept=0.5)

    report = _run(capsys, ["qc", str(source), "--quiet"])

    recording = report["recording"]
    channel = report["channels"][0]
    assert recording["estimated_rate_hz"] == pytest.approx(20.0, abs=1e-9)
    assert recording["duration_s"] == pytest.approx(119.95, abs=1e-9)
    assert recording["samples"] == 2400
    assert channel["signal_reference_correlation"] == pytest.approx(1.0, abs=1e-9)
    assert channel["ols_slope"] == pytest.approx(3.0, abs=1e-9)
    assert channel["ols_intercept"] == pytest.approx(0.5, abs=1e-9)
    assert channel["irls_slope"] == pytest.approx(3.0, abs=1e-9)
    assert channel["ols_residual_rmse"] == pytest.approx(0.0, abs=1e-9)
    assert report["status"] == "ok"
    assert report["warnings"] == []


def test_dff_recovers_the_injected_transient_amplitude(tmp_path, capsys) -> None:
    source = _transient_recording(
        tmp_path / "recording.csv", amplitude=0.25, onsets=(30.0,)
    )

    result = _run(capsys, ["dff", str(source), "--quiet"])

    time = np.asarray(result["samples"]["time_s"], dtype=float)
    recovered = np.asarray(result["samples"]["channels"]["signal"], dtype=float)
    assert result["units"] == "dF/F"
    assert np.max(recovered) == pytest.approx(0.25, abs=1e-6)
    assert time[int(np.argmax(recovered))] == pytest.approx(30.0, abs=1e-9)
    assert np.max(np.abs(recovered[np.abs(time - 30.0) > 3.0])) < 1e-6
    assert result["provenance"] == [
        {
            "kind": "reference_dff",
            "max_iterations": 50,
            "method": "irls",
            "tolerance": 1e-8,
        }
    ]


def test_align_baseline_z_returns_the_analytic_z_score(tmp_path, capsys) -> None:
    time = np.round(np.arange(800) * 0.05, 6)
    signal = np.ones_like(time)
    baseline = (time >= 9.0) & (time < 10.0)
    signal[baseline] = np.where(np.arange(int(baseline.sum())) % 2 == 0, 1.2, 0.8)
    signal[(time >= 10.0) & (time < 11.0)] = 1.5
    source = _write_table(tmp_path / "recording.csv", {"time": time, "signal": signal})
    events = tmp_path / "events.csv"
    events.write_text("time,event_id\n10.0,cue-1\n")

    result = _run(
        capsys,
        [
            "align",
            str(source),
            "--events",
            str(events),
            "--event-id-column",
            "event_id",
            "--variable",
            "signal",
            "--baseline",
            "-1",
            "0",
            "--response",
            "0",
            "1",
            "--normalization",
            "baseline_z",
            "--quiet",
        ],
    )

    row = result["per_event"][0]
    assert result["units"] == "baseline SD"
    assert row["event_id"] == "cue-1"
    assert row["disposition"] == "complete"
    assert row["baseline_mean"] == pytest.approx(0.0, abs=1e-12)
    assert row["response_mean"] == pytest.approx(2.5, abs=1e-12)
    assert row["delta"] == pytest.approx(2.5, abs=1e-12)
    assert result["summary"][0]["mean_delta"] == pytest.approx(2.5, abs=1e-12)


def test_transients_recover_the_injected_count_times_and_width(
    tmp_path, capsys
) -> None:
    onsets = (20.0, 45.0, 70.0, 95.0)
    source = _transient_recording(
        tmp_path / "recording.csv", amplitude=0.25, sigma_s=0.3, onsets=onsets
    )

    result = _run(
        capsys,
        [
            "transients",
            str(source),
            "--detector",
            "absolute",
            "--threshold",
            "0.1",
            "--baseline-duration",
            "2",
            "--baseline-gap",
            "2",
            "--min-distance",
            "2",
            "--quiet",
        ],
    )

    events = result["events"]
    assert len(events) == len(onsets)
    assert [event["peak_time"] for event in events] == pytest.approx(onsets, abs=1e-9)
    for event in events:
        assert event["amplitude"] == pytest.approx(0.25, abs=1e-6)
        assert event["full_width_half_height_s"] == pytest.approx(
            2 * 0.3 * np.sqrt(2 * np.log(2)), abs=2e-3
        )
    assert result["summaries"][0]["count"] == 4
    assert result["summaries"][0]["rate_per_minute"] == pytest.approx(2.0, abs=1e-3)
    accepted = {event["peak_time"] for event in events}
    rejected = {item["peak_time"] for item in result["exclusions"]}
    assert accepted.isdisjoint(rejected)
    assert {item["reason"] for item in result["exclusions"]} <= {
        "below_threshold",
        "degenerate_noise_scale",
        "incomplete_shape",
        "insufficient_baseline",
        "insufficient_noise_samples",
        "nonpositive_amplitude",
    }


def _write_ppd(path: Path) -> Path:
    header = {
        "subject_ID": "mouse-01",
        "date_time": "2026-01-01T12:00:00",
        "mode": "2 colour pulsed",
        "sampling_rate": 20,
        "volts_per_division": [0.001, 0.001],
        "version": "1.1",
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "ADC_max_value": 32767,
    }
    encoded = json.dumps(header).encode()
    words: list[int] = []
    for index in range(200):
        words.extend(
            [
                ((3000 + index) << 1) | (1 if 40 <= index < 50 else 0),
                1000 << 1,
                (2000 + index) << 1,
                900 << 1,
            ]
        )
    path.write_bytes(
        len(encoded).to_bytes(2, "little")
        + encoded
        + np.asarray(words, dtype="<u2").tobytes()
    )
    return path


def _write_doric(path: Path):
    h5py = pytest.importorskip("h5py")
    time = np.round(np.arange(1200) * 0.05, 6)
    with h5py.File(path, "w") as file:
        root = file.create_group("DataAcquisition/FPConsole/Signals/Series0001")
        signal = root.create_group("AIN01xAOUT01-LockIn")
        signal.create_dataset("Time", data=time)
        signal.create_dataset("Values", data=2 + 0.5 * np.sin(time / 10))
        reference = root.create_group("AIN01xAOUT02-LockIn")
        reference.create_dataset("Time", data=time)
        reference.create_dataset("Values", data=1 + 0.1 * np.sin(time / 10))
        digital = root.create_group("DigitalIO/DIO01")
        digital.create_dataset("Time", data=time)
        digital.create_dataset("Values", data=(np.sin(time) > 0.99).astype(float))
    return path


def _write_neurophotometrics(path: Path) -> Path:
    rows = ["FrameCounter,SystemTimestamp,LedState,Region0G"]
    for index in range(1000):
        led = 2 if index % 2 == 0 else 1
        value = 3.0 + 0.01 * index if led == 2 else 1.0 + 0.001 * index
        rows.append(f"{index},{index * 0.025:.4f},{led},{value:.6f}")
    path.write_text("\n".join(rows) + "\n")
    return path


def test_qc_reads_pyphotometry_without_a_schema(tmp_path, capsys) -> None:
    source = _write_ppd(tmp_path / "mouse.ppd")

    report = _run(capsys, ["qc", str(source), "--quiet"])

    assert report["source"]["format"] == "pyphotometry"
    assert report["recording"]["has_reference"] is True
    assert report["recording"]["estimated_rate_hz"] == pytest.approx(20.0, abs=1e-9)
    assert report["recording"]["channel_names"] == ["analog_1"]


def test_align_reads_doric_digital_events_without_a_schema(tmp_path, capsys) -> None:
    source = _write_doric(tmp_path / "Console_Acq_0000.doric")

    result = _run(
        capsys,
        ["align", str(source), "--baseline", "-1", "0", "--response", "0", "1", "-q"],
    )

    assert result["source"]["format"] == "doric"
    assert result["events"]["count"] > 0
    assert result["events"]["origin"] == "doric source"
    assert result["units"] == "dF/F"
    assert result["per_event"][0]["disposition"] == "complete"


def test_qc_reads_neurophotometrics_without_a_schema(tmp_path, capsys) -> None:
    source = _write_neurophotometrics(tmp_path / "fpdata.csv")

    report = _run(capsys, ["qc", str(source), "--quiet"])

    assert report["source"]["format"] == "neurophotometrics"
    assert report["recording"]["channel_names"] == ["Region0G"]
    assert report["recording"]["has_reference"] is True


def test_qc_reads_a_tdt_block_without_a_schema(tmp_path, capsys, monkeypatch) -> None:
    block = tmp_path / "Subject-Block-1"
    block.mkdir()
    (block / "Subject.tsq").write_bytes(b"")
    time = np.arange(1200) / 20
    stream = SimpleNamespace(
        data=np.vstack([2 + 0.5 * np.sin(time / 10), 3 + 0.5 * np.sin(time / 10)]),
        fs=20.0,
        start_time=0.0,
    )
    reference = SimpleNamespace(
        data=np.vstack([1 + 0.1 * np.sin(time / 10), 1 + 0.1 * np.sin(time / 10)]),
        fs=20.0,
        start_time=0.0,
    )
    block_data = SimpleNamespace(
        streams=SimpleNamespace(x465A=stream, x405A=reference),
        epocs=SimpleNamespace(
            Trl_=SimpleNamespace(
                onset=np.asarray([5.0, 25.0]),
                offset=np.asarray([5.1, 25.1]),
                data=np.asarray([1.0, 2.0]),
            )
        ),
    )
    monkeypatch.setattr(cli, "_tdt_reader", lambda: lambda path, **kwargs: block_data)

    report = _run(capsys, ["qc", str(block), "--quiet"])

    assert report["source"]["format"] == "tdt"
    assert report["recording"]["channel_names"] == ["x465A_1", "x465A_2"]
    assert report["recording"]["estimated_rate_hz"] == pytest.approx(20.0, abs=1e-9)


def test_dff_round_trips_through_nwb(tmp_path, capsys) -> None:
    pytest.importorskip("pynwb")
    source = _paired_recording(tmp_path / "recording.csv")
    destination = tmp_path / "session.nwb"

    assert (
        main(
            [
                "dff",
                str(source),
                "--output",
                str(destination),
                "--session-start-time",
                "2026-01-01T12:00:00+00:00",
                "--quiet",
            ]
        )
        == 0
    )
    report = _run(capsys, ["qc", str(destination), "--quiet"])

    assert destination.is_file()
    assert report["source"]["format"] == "nwb"
    assert report["recording"]["samples"] == 2400
    assert report["recording"]["estimated_rate_hz"] == pytest.approx(20.0, abs=1e-9)


def test_dff_csv_carries_provenance_inline_and_in_a_sidecar(tmp_path, capsys) -> None:
    source = _paired_recording(tmp_path / "recording.csv")
    destination = tmp_path / "dff.csv"

    assert (
        main(
            [
                "dff",
                str(source),
                "--format",
                "csv",
                "--output",
                str(destination),
                "--quiet",
            ]
        )
        == 0
    )

    lines = destination.read_text().splitlines()
    inline = json.loads(lines[0].removeprefix("# "))
    sidecar = json.loads((tmp_path / "dff.csv.provenance.json").read_text())
    assert inline["variable"] == "dff"
    assert inline["operations"][0]["kind"] == "reference_dff"
    assert lines[1] == "time_s,signal"
    assert len(lines) == 2402
    assert sidecar["provenance"] == inline["operations"]
    assert "samples" not in sidecar
    assert capsys.readouterr().out == ""


def test_quiet_suppresses_the_human_summary(tmp_path, capsys) -> None:
    source = _paired_recording(tmp_path / "recording.csv")

    assert main(["qc", str(source)]) == 0
    assert "status: ok" in capsys.readouterr().err
    assert main(["qc", str(source), "--quiet"]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["qc", "absent.csv"], "acquisition_source_unreadable"),
        (["qc", "notes.md"], "unrecognized_acquisition_format"),
        (["qc", "recording.csv", "--channel", "absent"], "channel_not_found"),
        (
            ["dff", "signal-only.csv", "--method", "reference"],
            "reference_channel_missing",
        ),
        (["align", "recording.csv"], "event_times_missing"),
        (
            [
                "dff",
                "jittered.csv",
                "--method",
                "baseline",
                "--baseline-method",
                "asls",
            ],
            "asls_requires_regular_sampling",
        ),
        (
            ["dff", "recording.csv", "--output", "out.nwb"],
            "nwb_session_start_time_missing",
        ),
    ],
)
def test_analysis_failures_use_stable_codes_and_name_a_next_step(
    tmp_path, capsys, monkeypatch, argv, code
) -> None:
    monkeypatch.chdir(tmp_path)
    _paired_recording(tmp_path / "recording.csv")
    (tmp_path / "notes.md").write_text("not a recording\n")
    time = np.round(np.arange(400) * 0.05, 6)
    _write_table(tmp_path / "signal-only.csv", {"time": time, "signal": 1 + time / 100})
    jittered = time + np.concatenate([[0.0], np.tile([0.004, -0.004], 199), [0.0]])
    _write_table(
        tmp_path / "jittered.csv", {"time": jittered, "signal": 1 + jittered / 100}
    )

    assert main(argv) == 2

    captured = capsys.readouterr()
    assert captured.err.startswith(f"error: {code}: ")
    assert "hint: " in captured.err
    assert captured.out == ""
