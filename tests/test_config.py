import json
from pathlib import Path

import pytest
from test_workflow import _sessions

from fiberphotometry import EventAnalysisConfig


def test_toml_config_builds_and_runs_reproducibly() -> None:
    config = EventAnalysisConfig.from_toml(Path("examples/feedback-analysis.toml"))

    first = config.run(_sessions())
    second = config.run(_sessions())

    assert first.pipeline.analysis is not None
    assert first.pipeline.analysis.estimate == second.pipeline.analysis.estimate
    assert first.configuration_fingerprint == config.fingerprint
    assert config.fingerprint in first.to_html()
    assert config.fingerprint in config.to_json()
    artifact = json.loads(first.to_json())
    assert artifact["data_summary"] == {"animals": 4, "sessions": 4, "events": 20}
    assert len(artifact["quality_reports"]) == 4
    assert artifact["processing_lineage"][0]["operations"][0]["kind"] == "reference_dff"
    assert artifact["timecourse"]["draws"] == 500
    assert first.timecourse is not None
    assert first.timecourse.animal_count == 4


def test_toml_config_rejects_unknown_keys_and_invalid_methods() -> None:
    unknown = (
        Path("examples/feedback-analysis.toml")
        .read_text()
        .replace(
            'title = "IBL feedback-aligned DMS response"',
            'title = "test"\nmagic = true',
        )
    )
    invalid = (
        Path("examples/feedback-analysis.toml")
        .read_text()
        .replace('method = "irls"', 'method = "guess"')
    )

    with pytest.raises(ValueError, match="unknown root"):
        EventAnalysisConfig.from_toml(unknown)
    with pytest.raises(ValueError, match="reference preprocessing method"):
        EventAnalysisConfig.from_toml(invalid)


def test_toml_config_requires_recorded_assumptions_to_execute() -> None:
    raw = Path("examples/feedback-analysis.toml").read_text()
    start = raw.index("acknowledged_assumptions = [")
    end = raw.index("\n]", start) + 2
    unacknowledged = raw[:start] + "acknowledged_assumptions = []" + raw[end:]
    config = EventAnalysisConfig.from_toml(unacknowledged)

    with pytest.raises(ValueError, match="unacknowledged"):
        config.run(_sessions())


def test_signal_only_config_selects_units_explicitly() -> None:
    raw = Path("examples/feedback-analysis.toml").read_text()
    raw = raw.replace('kind = "reference"', 'kind = "signal_only"')
    raw = raw.replace('method = "irls"', 'method = "rolling_mean"')
    raw = raw.replace('normalization = "divide"', 'normalization = "subtract"')
    config = EventAnalysisConfig.from_toml(raw)

    study = config.build(_sessions(reference=False))

    assert study.preprocessing.output_variable == "baseline_subtracted"
    assert study.preprocessing.units == "acquired fluorescence"


def test_signal_only_config_declares_regularization_before_asls() -> None:
    raw = Path("examples/feedback-analysis.toml").read_text()
    raw = raw.replace('kind = "reference"', 'kind = "signal_only"')
    raw = raw.replace('method = "irls"', 'method = "asls"')
    raw = raw.replace(
        'normalization = "divide"',
        'normalization = "divide"\nresample_rate_hz = "median"\n'
        "resample_max_gap_factor = 1.5",
    )

    config = EventAnalysisConfig.from_toml(raw)
    study = config.build(_sessions(reference=False))

    assert config.resample_rate_hz == "median"
    assert config.resample_max_gap_factor == 1.5
    assert study.preprocessing.operations[0].kind == "resample"
    assert study.preprocessing.operations[1].kind == "baseline_dff"


def test_config_declares_independent_population_design() -> None:
    raw = Path("examples/feedback-analysis.toml").read_text()
    raw = raw.replace(
        'factor = "feedback"', 'factor = "feedback"\nassignment_unit = "animal"'
    )
    raw = raw.replace("[timecourse]\n", '[timecourse]\ndesign = "independent"\n')

    config = EventAnalysisConfig.from_toml(raw)

    assert config.factor_assignment_unit == "animal"
    assert config.timecourse is not None
    assert config.timecourse.design == "independent"
