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
    PermutationPlan,
    ResamplingPlan,
    exact_sign_flip_test,
    hierarchical_bootstrap,
    permutation_test,
)
from fiberphotometry.model import make_recording, validate_recording
from fiberphotometry.preprocess import reference_dff
from fiberphotometry.qc import assess_recording

__all__ = [
    "Contrast",
    "Estimand",
    "Factor",
    "ObservationTable",
    "PermutationPlan",
    "ResamplingPlan",
    "StudyDesign",
    "Unit",
    "align_events",
    "assess_event_confounds",
    "assess_recording",
    "exact_sign_flip_test",
    "hierarchical_bootstrap",
    "make_recording",
    "permutation_test",
    "reference_dff",
    "summarize_event_windows",
    "validate_design",
    "validate_recording",
]
