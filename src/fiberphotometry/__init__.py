"""Composable fiber photometry analysis."""

from fiberphotometry.events import align_events, summarize_event_windows
from fiberphotometry.model import make_recording, validate_recording
from fiberphotometry.preprocess import reference_dff

__all__ = [
    "align_events",
    "make_recording",
    "reference_dff",
    "summarize_event_windows",
    "validate_recording",
]
