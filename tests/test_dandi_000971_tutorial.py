from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

from fiberphotometry import RecordingInput, make_recording, run_multiverse


def _tutorial_module():
    path = Path("examples/dandi_000971_reward_tutorial.py")
    spec = importlib.util.spec_from_file_location("dandi_000971_reward_tutorial", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assets():
    return [
        {"asset_id": f"asset-{index}", "subject": f"mouse-{index}"}
        for index in range(6)
    ]


def _inputs() -> tuple[RecordingInput, ...]:
    result = []
    for animal in range(6):
        time = np.arange(0, 40, 0.05)
        reference = 1.0 + 0.015 * np.sin(time / 4 + animal)
        signal = 2.0 * reference + 0.005 * np.sin(3 * time)
        events = np.asarray([8, 12, 16, 20, 24, 28, 32], dtype=float)
        conditions = (
            "rewarded",
            "unrewarded",
            "rewarded",
            "unrewarded",
            "rewarded",
            "unrewarded",
            "rewarded",
        )
        for event, condition in zip(events, conditions, strict=True):
            if condition == "rewarded":
                signal[(time >= event) & (time < event + 0.5)] += 0.04 + animal * 0.002
        recording = make_recording(
            time=time,
            signal=np.column_stack((signal, signal * 0.9)),
            reference=np.column_stack((reference, reference * 0.95)),
            channel_names=("DMS", "DLS"),
            subject=f"mouse-{animal}",
            session=f"session-{animal}",
        )
        result.append(
            RecordingInput(
                recording,
                events,
                [f"event-{animal}-{index}" for index in range(len(events))],
                {
                    "animal": [f"mouse-{animal}"] * len(events),
                    "session": [f"session-{animal}"] * len(events),
                    "condition": conditions,
                },
            )
        )
    return tuple(result)


def test_frozen_tutorial_materializes_and_executes_complete_multiverse():
    module = _tutorial_module()
    spec = module.build_spec(_assets())

    result = run_multiverse(spec, _inputs())

    assert len(result.universes) == 8
    assert {universe.status for universe in result.universes} == {"success"}
    assert sum(universe.is_reference for universe in result.universes) == 1
    assert result.summary.successful_universes == 8
    assert len(result.leave_one_out) == 6
    assert {item.status for item in result.leave_one_out} == {"success"}
