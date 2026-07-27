"""Normative v0.1 API and artifact stability declarations."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

SUPPORTED_API_V0_1 = (
    "EventAnalysis",
    "EventAnalysisConfig",
    "EventAnalysisResult",
    "EventCoverageCounts",
    "EventCoverageRecord",
    "EventCoverageReport",
    "EventCoverageStratum",
    "EventSession",
    "PeriEventInferenceResult",
    "PeriEventInferenceSpec",
    "Preprocessing",
    "ProjectConfig",
    "TDTBlockSchema",
    "TDTProjectConfig",
    "TabularEventSchema",
    "TabularProjectConfig",
    "TabularRecordingSchema",
    "assess_event_coverage",
    "artifact_schema",
    "export_project_nwb",
    "infer_peri_event_contrast",
    "load_project_config",
    "load_tabular_input",
    "load_tdt_input",
    "make_recording",
    "validate_recording",
)

EXPERIMENTAL_API_V0_1 = (
    "MultiverseSpec",
    "ScalarMixedModelSpec",
    "baseline_dff",
    "fit_scalar_mixed_model",
    "hierarchical_bootstrap",
    "materialize_multiverse",
    "permutation_test",
    "resample_recording",
    "run_multiverse",
)

ARTIFACT_SCHEMAS_V0_1 = {
    "event_analysis_result": "event-analysis-result-v1.schema.json",
    "multiverse_lane_summary": "multiverse-lane-summary-v1.schema.json",
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
