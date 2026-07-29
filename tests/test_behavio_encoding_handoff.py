"""The behaviour-to-photometry handoff, exercised against the real behavio.

The reader and interval semantics themselves are behavio's tests. What fipha
owns, and what this file protects, is the boundary: annotations discovered by a
behaviour tool must land in ``fipha.encoding`` with their edges, duration
values, physical interval bounds and validity masks intact.
"""

from __future__ import annotations

import numpy as np
import pytest

from fipha.encoding import EncodingSession

ethograms = pytest.importorskip(
    "behavio.ethograms", reason="requires the 'behavior' optional dependency"
)


def test_moseq_interval_encoding_inputs_feed_an_encoding_session() -> None:
    annotations = ethograms.annotations_from_moseq(
        [2, 2, 2, 5, 5, 2],
        subject="mouse-1",
        session="day-1",
        fps=2.0,
        labels={2: "rear", 5: "groom"},
    )
    inputs = annotations.interval_encoding_inputs()

    session = EncodingSession.from_arrays(
        subject="mouse-1",
        session="day-1",
        time=np.arange(0.0, 3.0, 0.5),
        response=np.zeros(6),
        events=inputs.events,
        event_values=inputs.event_values,
        intervals=inputs.intervals,
    )

    assert session.events["rear"] == (0.0, 2.5)
    assert session.event_values["groom"]["duration_s"] == (1.0,)
    assert session.intervals["groom"] == ((1.5, 2.5),)


def test_normalized_progress_covariate_keeps_its_validity_mask() -> None:
    annotations = ethograms.annotations_from_boris(
        {
            "Behavior": ["cue", "approach"],
            "Type": ["POINT", "STATE"],
            "Start": [0.5, 1.0],
            "Stop": [np.nan, 3.0],
        },
        subject="mouse-1",
        session="day-1",
        behavior_column="Behavior",
        type_column="Type",
        start_column="Start",
        stop_column="Stop",
    )
    progress = annotations.normalized_progress(
        [0.0, 1.0, 2.0, 3.0, 4.0], label="approach"
    )

    session = EncodingSession.from_arrays(
        subject="mouse-1",
        session="day-1",
        time=[0.0, 1.0, 2.0, 3.0, 4.0],
        response=[0.0, 0.1, 0.2, 0.3, 0.4],
        events=annotations.event_times(),
        continuous_covariates={"approach_progress": progress.values},
        continuous_covariate_validity={"approach_progress": progress.valid},
    )

    assert session.events["approach"] == (1.0,)
    assert session.events["cue"] == (0.5,)
    assert progress.values[1:4].tolist() == [0.0, 0.5, 1.0]
    assert progress.valid.tolist() == [False, True, True, True, False]
