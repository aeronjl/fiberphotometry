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


def test_event_analysis_schema_fixes_the_complete_top_level_ledger() -> None:
    assert ARTIFACT_SCHEMAS_V0_1["event_analysis_result"].endswith(".schema.json")
    schema = fiberphotometry.artifact_schema("event_analysis_result")
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["artifact_type"]["const"] == ("event_analysis_result")
    assert schema["properties"]["schema_version"]["const"] == "1"


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
