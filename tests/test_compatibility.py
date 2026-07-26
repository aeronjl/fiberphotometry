import numpy as np

from fiberphotometry import (
    BaselineDFFOperation,
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    ObservationTable,
    PipelineSpec,
    QualityGateSpec,
    RecordingInput,
    StudyDesign,
    Unit,
    assess_pipeline_compatibility,
    create_analysis_plan,
    make_recording,
)


def _spec(table, design, estimand, operations):
    draft = create_analysis_plan(
        table, design, estimand, randomized=False, intent="exploratory"
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=False,
        intent="exploratory",
        acknowledged_assumptions=draft.required_assumptions,
    )
    return PipelineSpec(
        operations,
        QualityGateSpec(()),
        EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="outcome"),
        design,
        plan,
        schema_version="2",
    )


def test_compatibility_detects_asls_irregularity_without_reading_values() -> None:
    time = np.arange(200, dtype=float) / 20
    time[1::2] += 0.0001
    first = make_recording(
        time=time,
        signal=np.linspace(1, 2, len(time)),
        channel_names=["DMS"],
        subject="mouse",
        session="session",
    )
    second = first.copy(deep=True)
    second["signal"][:] = np.linspace(1000, -1000, len(time))[:, None]
    table = ObservationTable.from_columns(
        {
            "event_id": ["e1", "e2"],
            "animal": ["mouse", "mouse"],
            "condition": ["a", "b"],
            "outcome": [0.0, 0.0],
        }
    )
    design = StudyDesign(
        "event_id",
        (Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        (Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "a", "b"), "animal")
    spec = _spec(
        table, design, estimand, (BaselineDFFOperation("asls", normalization="both"),)
    )

    def inputs(recording):
        return (
            RecordingInput(recording, [2, 4], ["e1", "e2"], {"condition": ["a", "b"]}),
        )

    one = assess_pipeline_compatibility(spec, inputs(first))
    two = assess_pipeline_compatibility(spec, inputs(second))

    assert one == two
    assert one.status == "incompatible"
    assert one.issues[0].code == "asls_requires_regular_sampling"
    assert not one.outcome_values_accessed
