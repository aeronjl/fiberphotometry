import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fiberphotometry.cli import main
from fiberphotometry.comparison import compare_project_evidence
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
