from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

from fiberphotometry import EncodingSession


def _module():
    path = Path("examples/dandi_000971_event_kernel.py")
    spec = importlib.util.spec_from_file_location("dandi_000971_event_kernel", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_public_model_shape_runs_with_complete_animal_holdout() -> None:
    module = _module()
    time = np.arange(0.0, 24.0, 0.1)
    regional = {region: [] for region in module.REGIONS}
    for animal in range(6):
        pokes = np.array([4.0, 8.0, 12.0, 16.0, 20.0])
        rewards = pokes[[0, 2, 4]]
        common = np.zeros(len(time))
        incremental = np.zeros(len(time))
        for event in pokes:
            index = round(event / 0.1)
            common[index : index + 3] += (0.1, 0.2, 0.1)
        for event in rewards:
            index = round(event / 0.1)
            incremental[index : index + 3] += (0.2, 0.4, 0.2)
        for region, scale in (("DMS", 1.0), ("DLS", 0.7)):
            regional[region].append(
                EncodingSession.from_arrays(
                    subject=f"mouse-{animal}",
                    session="RI60",
                    time=time,
                    response=scale * (common + incremental)
                    + 0.001 * np.sin(time + animal),
                    events={
                        "active_poke": pokes,
                        "reward_increment": rewards,
                    },
                )
            )

    results = module.run_models(
        {region: tuple(sessions) for region, sessions in regional.items()}
    )

    assert set(results) == {"DMS", "DLS"}
    for result in results.values():
        assert result.groups == 6
        assert len(result.cross_validation) == 6
        held_out = [
            group
            for alpha in result.cross_validation
            if alpha.alpha == result.selected_alpha
            for fold in alpha.folds
            for group in fold.held_out_groups
        ]
        assert sorted(held_out) == [f"mouse-{index}" for index in range(6)]
