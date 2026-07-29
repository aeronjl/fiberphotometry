"""Normative v0.1 API and artifact stability declarations.

Every name in ``fipha.__all__`` appears in exactly one of
``SUPPORTED_API_V0_1`` or ``EXPERIMENTAL_API_V0_1``. There is no third state, and
``tests/test_stability.py`` fails if a root export is unclassified, classified
twice, or declared without being exported. Names reachable only from their own
module, such as ``fipha.spectral.welch_psd``, are outside the declared
surface entirely and carry no compatibility promise.
"""

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
    "BaselineDFFOperation",
    "BundleComparison",
    "EventAnalysis",
    "EventAnalysisConfig",
    "EventAnalysisResult",
    "EventCoverageCounts",
    "EventCoverageRecord",
    "EventCoverageReport",
    "EventCoverageStratum",
    "EventSession",
    "EventSummarySpec",
    "EvidenceDifference",
    "EvidenceFile",
    "LowpassFilterOperation",
    "PeriEventInferenceResult",
    "PeriEventInferenceSpec",
    "PipelineResult",
    "PipelineSpec",
    "Preprocessing",
    "PreprocessingSpec",
    "ProjectConfig",
    "ProjectEvidenceBundle",
    "PublicationAttestation",
    "PublicationVerification",
    "QualityGateSpec",
    "RecordingInput",
    "ReferenceDFFOperation",
    "ResampleOperation",
    "TDTBlockSchema",
    "TDTEpocEvents",
    "TDTEpocValue",
    "TDTProjectConfig",
    "TDTStreamChannel",
    "TabularChannel",
    "TabularEventColumn",
    "TabularEventSchema",
    "TabularProjectConfig",
    "TabularRecordingSchema",
    "ZenodoDraftReceipt",
    "__version__",
    "align_events",
    "artifact_schema",
    "assess_event_confounds",
    "assess_event_coverage",
    "assess_recording",
    "assess_signal_recording",
    "baseline_dff",
    "compare_project_evidence",
    "create_archive_package",
    "create_zenodo_draft",
    "detect_acquisition_format",
    "export_project_nwb",
    "infer_peri_event_contrast",
    "inspect_tabular_input",
    "inspect_tabular_recording",
    "load_archive_metadata",
    "load_project_config",
    "load_tabular_events",
    "load_tabular_input",
    "load_tabular_recording",
    "load_tdt_input",
    "lowpass_filter",
    "make_recording",
    "read_project_evidence",
    "reference_dff",
    "resample_recording",
    "run_pipeline",
    "sign_publication_manifest",
    "summarize_event_windows",
    "validate_acquisition_input",
    "validate_recording",
    "verify_archive_package",
    "verify_publication_manifest",
)

EXPERIMENTAL_API_V0_1 = (
    "Contrast",
    "DoricChannel",
    "DoricDigitalEvents",
    "DoricSchema",
    "DoricSeries",
    "Estimand",
    "Factor",
    "NWBAcquisitionMetadata",
    "NWBChannelMetadata",
    "NWBDeviceMetadata",
    "NWBIndicatorMetadata",
    "NeurophotometricsChannel",
    "NeurophotometricsDigitalEvents",
    "NeurophotometricsSchema",
    "ObservationTable",
    "PyPhotometryChannel",
    "PyPhotometryDigitalEvents",
    "PyPhotometrySchema",
    "SpecificationCurveEntry",
    "TransientDetectionResult",
    "TransientDetectionSpec",
    "StudyDesign",
    "TIntervalResult",
    "Unit",
    "add_recording_to_nwb",
    "detect_transients",
    "export_project_multiverse_nwb",
    "from_ibl_tables",
    "from_nwb_series",
    "hierarchical_bootstrap",
    "inspect_doric",
    "inspect_neurophotometrics",
    "inspect_pyphotometry",
    "load_doric_input",
    "load_neurophotometrics_input",
    "load_pyphotometry_input",
    "permutation_test",
    "plot_event_diagnostics",
    "plot_specification_curve",
    "resolve_dandi_download_url",
    "unit_t_interval",
    "validate_design",
    "validate_remote_nwb_asset",
)

ARTIFACT_SCHEMAS_V0_1 = {
    "fipha_archive_metadata": "archive-metadata-v1.schema.json",
    "evidence_bundle_comparison": "evidence-bundle-comparison-v1.schema.json",
    "event_analysis_result": "event-analysis-result-v1.schema.json",
    "multiverse_lane_summary": "multiverse-lane-summary-v1.schema.json",
    "publication_manifest_attestation": (
        "publication-manifest-attestation-v1.schema.json"
    ),
    "zenodo_draft_receipt": "zenodo-draft-receipt-v1.schema.json",
    "event_coverage": "embedded schema_version 1",
    "peri_event_inference": "embedded schema_version 2",
    "peri_event_interaction": "embedded schema_version 1",
    "transient_population_materialization": "embedded schema_version 1",
    "state_band_power_population_materialization": "embedded schema_version 1",
    "association_population_materialization": "embedded schema_version 1",
    "curve_population_materialization": "embedded schema_version 1",
}


def artifact_schema(artifact_type: str) -> dict[str, Any]:
    """Load a packaged normative JSON Schema by artifact type."""
    try:
        name = ARTIFACT_SCHEMAS_V0_1[artifact_type]
    except KeyError as error:
        raise ValueError(f"unknown stable artifact type {artifact_type!r}") from error
    if not name.endswith(".schema.json"):
        raise ValueError(f"{artifact_type!r} has no standalone JSON Schema")
    resource = files("fipha").joinpath("schemas", name)
    source = (
        resource.read_text(encoding="utf-8")
        if resource.is_file()
        else (Path(__file__).parents[2] / "schemas" / name).read_text(encoding="utf-8")
    )
    return cast(dict[str, Any], json.loads(source))
