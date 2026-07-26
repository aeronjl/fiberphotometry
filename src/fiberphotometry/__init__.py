"""Composable fiber photometry analysis."""

from fiberphotometry.event_qc import assess_event_confounds
from fiberphotometry.events import align_events, summarize_event_windows
from fiberphotometry.model import make_recording, validate_recording
from fiberphotometry.preprocess import reference_dff
from fiberphotometry.qc import assess_recording

__all__ = [
    "align_events",
    "assess_event_confounds",
    "assess_recording",
    "make_recording",
    "reference_dff",
    "summarize_event_windows",
    "validate_recording",
]
