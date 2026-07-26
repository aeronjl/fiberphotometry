import json
from dataclasses import replace

import numpy as np

from fiberphotometry import (
    BaselineDFFOperation,
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    LowpassFilterOperation,
    ObservationTable,
    PipelineSpec,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    ReferenceDFFOperation,
    ResampleOperation,
    StudyDesign,
    Unit,
    create_analysis_plan,
    make_recording,
    run_pipeline,
)


def _inputs(*, missing: bool = False) -> tuple[RecordingInput, ...]:
    inputs = []
    for index in range(4):
        time = np.arange(0, 12, 0.05)
        reference = 1 + 0.05 * np.sin(time)
        signal = 2 + reference + 0.02 * np.sin(3 * time)
        for event_time in (5.0, 9.0):
            signal[(time >= event_time) & (time < event_time + 0.5)] += (
                0.08 + 0.01 * index
            )
        if missing:
            signal[:80] = np.nan
            reference[:80] = np.nan
        recording = make_recording(
            time=time,
            signal=signal,
            reference=reference,
            channel_names=["DMS"],
            subject=f"a{index}",
            session=f"s{index}",
        )
        inputs.append(
            RecordingInput(
                recording,
                [3.0, 5.0, 7.0, 9.0],
                [f"e{index}-{event}" for event in range(4)],
                {
                    "animal": [f"a{index}"] * 4,
                    "session": [f"s{index}"] * 4,
                    "condition": ["control", "drug", "control", "drug"],
                },
            )
        )
    return tuple(inputs)


def _spec(*, block: bool = False) -> PipelineSpec:
    inputs = _inputs()
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("dms_delta", Contrast("condition", "drug", "control"), "animal")
    # Build the plan from the same event metadata shape; outcome values do not
    # affect routing, and execution fingerprints the actual pipeline table.
    table_columns = {
        "event_id": [event for item in inputs for event in item.event_ids],
        "animal": [value for item in inputs for value in item.columns["animal"]],
        "session": [value for item in inputs for value in item.columns["session"]],
        "condition": [value for item in inputs for value in item.columns["condition"]],
        "dms_delta": [0.0] * 16,
    }
    table = ObservationTable.from_columns(table_columns)
    draft = create_analysis_plan(
        table, design, estimand, randomized=False, intent="descriptive"
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=False,
        intent="descriptive",
        acknowledged_assumptions=draft.required_assumptions,
    )
    return PipelineSpec(
        PreprocessingSpec(method="ols"),
        QualityGateSpec(("low_valid_fraction",) if block else ()),
        EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
        design,
        plan,
    )


def test_pipeline_composes_processing_events_and_inference() -> None:
    result = run_pipeline(_spec(), _inputs())

    assert result.inference_executed
    assert result.analysis is not None
    assert result.analysis.plan.estimand.aggregation_unit == "animal"
    assert result.analysis.estimate > 0.01
    assert len(result.observation_table) == 16
    assert len(result.processed_recordings) == 4
    assert '"schema_version": "1"' in _spec().to_json()


def test_qc_gate_blocks_inference_without_dropping_observations() -> None:
    result = run_pipeline(_spec(block=True), _inputs(missing=True))

    assert not result.inference_executed
    assert len(result.observation_table) == 16
    assert len(result.blocked_by) == 4
    assert all("low_valid_fraction" in reason for reason in result.blocked_by)


def test_schema_v2_executes_tagged_preprocessing_sequence() -> None:
    spec = replace(
        _spec(),
        preprocessing=(
            ResampleOperation(rate_hz=20, max_gap_s=0.2),
            LowpassFilterOperation(cutoff_hz=5),
            ReferenceDFFOperation(method="ols"),
        ),
        schema_version="2",
    )

    result = run_pipeline(spec, _inputs())

    assert result.inference_executed
    operations = result.processed_recordings[0].attrs["fiberphotometry_operations"]
    assert [item["kind"] for item in json.loads(operations)] == [
        "resample",
        "lowpass_filter",
        "reference_dff",
    ]
    assert "source_signal" in result.processed_recordings[0]
    assert "prefilter_signal" in result.processed_recordings[0]


def test_schema_v2_executes_signal_only_rolling_comparator() -> None:
    spec = replace(
        _spec(),
        preprocessing=(
            BaselineDFFOperation(
                method="rolling_mean", normalization="divide", rolling_window_s=4
            ),
        ),
        schema_version="2",
    )

    result = run_pipeline(spec, _inputs())

    assert result.inference_executed
    operation = json.loads(
        result.processed_recordings[0].attrs["fiberphotometry_baseline_dff"]
    )
    assert operation["method"] == "rolling_mean"
    assert operation["window_s"] == 4
    assert operation["published_comparator"] == "Pan-Vazquez et al. 2024"
