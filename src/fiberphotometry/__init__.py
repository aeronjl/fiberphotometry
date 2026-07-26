"""Composable fiber photometry analysis."""

from fiberphotometry.design import (
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    validate_design,
)
from fiberphotometry.event_qc import assess_event_confounds
from fiberphotometry.events import align_events, summarize_event_windows
from fiberphotometry.inference import (
    Contrast,
    Estimand,
    InferenceRecommendation,
    PermutationPlan,
    ResamplingPlan,
    TIntervalResult,
    exact_sign_flip_test,
    hierarchical_bootstrap,
    permutation_test,
    recommend_inference,
    unit_t_interval,
)
from fiberphotometry.model import make_recording, validate_recording
from fiberphotometry.pipeline import (
    EventSummarySpec,
    PipelineResult,
    PipelineSpec,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    run_pipeline,
)
from fiberphotometry.planning import (
    AnalysisPlan,
    AnalysisResult,
    PowerSensitivity,
    create_analysis_plan,
    execute_analysis_plan,
    welch_power_sensitivity,
)
from fiberphotometry.preprocess import reference_dff
from fiberphotometry.qc import assess_recording

__all__ = [
    "AnalysisPlan",
    "AnalysisResult",
    "Contrast",
    "Estimand",
    "EventSummarySpec",
    "Factor",
    "InferenceRecommendation",
    "ObservationTable",
    "PermutationPlan",
    "PipelineResult",
    "PipelineSpec",
    "PowerSensitivity",
    "PreprocessingSpec",
    "QualityGateSpec",
    "RecordingInput",
    "ResamplingPlan",
    "StudyDesign",
    "TIntervalResult",
    "Unit",
    "align_events",
    "assess_event_confounds",
    "assess_recording",
    "create_analysis_plan",
    "exact_sign_flip_test",
    "execute_analysis_plan",
    "hierarchical_bootstrap",
    "make_recording",
    "permutation_test",
    "recommend_inference",
    "reference_dff",
    "run_pipeline",
    "summarize_event_windows",
    "unit_t_interval",
    "validate_design",
    "validate_recording",
    "welch_power_sensitivity",
]
