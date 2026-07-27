"""Normative v0.1 API and artifact stability declarations."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

SUPPORTED_API_V0_1 = (
    "ArchiveCreator",
    "ArchiveMetadata",
    "ArchivePackage",
    "ArchiveRelatedIdentifier",
    "BundleComparison",
    "EventAnalysis",
    "EventAnalysisConfig",
    "EventAnalysisResult",
    "EventCoverageCounts",
    "EventCoverageRecord",
    "EventCoverageReport",
    "EventCoverageStratum",
    "EventSession",
    "EvidenceFile",
    "EvidenceDifference",
    "PeriEventInferenceResult",
    "PeriEventInferenceSpec",
    "Preprocessing",
    "ProjectConfig",
    "ProjectEvidenceBundle",
    "PublicationAttestation",
    "PublicationVerification",
    "ZenodoDraftReceipt",
    "TDTBlockSchema",
    "TDTProjectConfig",
    "TabularEventSchema",
    "TabularProjectConfig",
    "TabularRecordingSchema",
    "assess_event_coverage",
    "artifact_schema",
    "compare_project_evidence",
    "create_archive_package",
    "create_zenodo_draft",
    "export_project_nwb",
    "infer_peri_event_contrast",
    "load_project_config",
    "load_archive_metadata",
    "load_tabular_input",
    "load_tdt_input",
    "make_recording",
    "read_project_evidence",
    "sign_publication_manifest",
    "validate_recording",
    "verify_publication_manifest",
    "verify_archive_package",
)

EXPERIMENTAL_API_V0_1 = (
    "EncodingModelResult",
    "EncodingModelSpec",
    "EncodingSession",
    "EventKernelSpec",
    "MultiverseSpec",
    "ScalarMixedModelSpec",
    "baseline_dff",
    "export_project_multiverse_nwb",
    "fit_scalar_mixed_model",
    "fit_event_kernel_model",
    "hierarchical_bootstrap",
    "materialize_multiverse",
    "permutation_test",
    "resample_recording",
    "run_multiverse",
)

ARTIFACT_SCHEMAS_V0_1 = {
    "fiberphotometry_archive_metadata": "archive-metadata-v1.schema.json",
    "evidence_bundle_comparison": "evidence-bundle-comparison-v1.schema.json",
    "event_analysis_result": "event-analysis-result-v1.schema.json",
    "multiverse_lane_summary": "multiverse-lane-summary-v1.schema.json",
    "publication_manifest_attestation": (
        "publication-manifest-attestation-v1.schema.json"
    ),
    "zenodo_draft_receipt": "zenodo-draft-receipt-v1.schema.json",
    "event_coverage": "embedded schema_version 1",
    "peri_event_inference": "embedded schema_version 1",
}


def artifact_schema(artifact_type: str) -> dict[str, Any]:
    """Load a packaged normative JSON Schema by artifact type."""
    try:
        name = ARTIFACT_SCHEMAS_V0_1[artifact_type]
    except KeyError as error:
        raise ValueError(f"unknown stable artifact type {artifact_type!r}") from error
    if not name.endswith(".schema.json"):
        raise ValueError(f"{artifact_type!r} has no standalone JSON Schema")
    resource = files("fiberphotometry").joinpath("schemas", name)
    source = (
        resource.read_text(encoding="utf-8")
        if resource.is_file()
        else (Path(__file__).parents[2] / "schemas" / name).read_text(encoding="utf-8")
    )
    return cast(dict[str, Any], json.loads(source))
