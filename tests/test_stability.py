import fiberphotometry
from fiberphotometry.stability import (
    ARTIFACT_SCHEMAS_V0_1,
    EXPERIMENTAL_API_V0_1,
    SUPPORTED_API_V0_1,
)


def test_declared_supported_and_experimental_names_are_exported() -> None:
    supported = set(SUPPORTED_API_V0_1)
    experimental = set(EXPERIMENTAL_API_V0_1)
    assert supported.isdisjoint(experimental)
    assert supported <= set(fiberphotometry.__all__)
    assert experimental <= set(fiberphotometry.__all__)
    assert all(hasattr(fiberphotometry, name) for name in supported | experimental)


def test_every_public_export_is_classified_supported_or_experimental() -> None:
    exported = set(fiberphotometry.__all__)
    classified = set(SUPPORTED_API_V0_1) | set(EXPERIMENTAL_API_V0_1)

    assert not exported - classified, (
        "every name in fiberphotometry.__all__ must be declared in "
        "SUPPORTED_API_V0_1 or EXPERIMENTAL_API_V0_1; unclassified: "
        f"{sorted(exported - classified)}"
    )
    assert not classified - exported, (
        "stability declarations must not name unexported symbols; stale: "
        f"{sorted(classified - exported)}"
    )


def test_declared_names_are_unique_within_each_stability_tier() -> None:
    assert len(SUPPORTED_API_V0_1) == len(set(SUPPORTED_API_V0_1))
    assert len(EXPERIMENTAL_API_V0_1) == len(set(EXPERIMENTAL_API_V0_1))
    assert len(fiberphotometry.__all__) == len(set(fiberphotometry.__all__))


def test_the_scientific_core_path_is_supported_not_unclassified() -> None:
    core = {
        "make_recording",
        "reference_dff",
        "baseline_dff",
        "lowpass_filter",
        "resample_recording",
        "assess_recording",
        "align_events",
        "summarize_event_windows",
        "run_pipeline",
    }

    assert core <= set(SUPPORTED_API_V0_1)


def test_event_analysis_schema_fixes_the_complete_top_level_ledger() -> None:
    assert ARTIFACT_SCHEMAS_V0_1["event_analysis_result"].endswith(".schema.json")
    schema = fiberphotometry.artifact_schema("event_analysis_result")
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["artifact_type"]["const"] == ("event_analysis_result")
    assert schema["properties"]["schema_version"]["const"] == "1"


def test_multiverse_lane_summary_has_a_normative_schema() -> None:
    schema = fiberphotometry.artifact_schema("multiverse_lane_summary")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["artifact_type"]["const"] == ("multiverse_lane_summary")


def test_evidence_bundle_comparison_has_a_normative_schema() -> None:
    schema = fiberphotometry.artifact_schema("evidence_bundle_comparison")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["artifact_type"]["const"] == (
        "evidence_bundle_comparison"
    )


def test_publication_attestation_has_a_normative_schema() -> None:
    schema = fiberphotometry.artifact_schema("publication_manifest_attestation")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["signature_method"]["const"] == "openssh"


def test_archive_metadata_has_a_normative_schema() -> None:
    schema = fiberphotometry.artifact_schema("fiberphotometry_archive_metadata")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["artifact_type"]["const"] == (
        "fiberphotometry_archive_metadata"
    )


def test_zenodo_draft_receipt_has_a_normative_schema() -> None:
    schema = fiberphotometry.artifact_schema("zenodo_draft_receipt")

    assert schema["additionalProperties"] is False
    assert schema["properties"]["submitted"]["const"] is False
    assert schema["properties"]["state"]["const"] == "unsubmitted"


def test_unknown_or_embedded_schema_is_not_guessed() -> None:
    for artifact_type in ("missing", "event_coverage"):
        try:
            fiberphotometry.artifact_schema(artifact_type)
        except ValueError:
            pass
        else:
            raise AssertionError("artifact_schema must reject unavailable schemas")


def test_package_exposes_installed_version() -> None:
    assert fiberphotometry.__version__
    assert fiberphotometry.__version__ != "0+unknown"
