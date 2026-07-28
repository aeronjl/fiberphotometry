"""Parity checks for the bounded Seiler source-panel reproduction."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


def _figure_module():
    path = Path("scripts/plot_dandi_000971_source_figure.py")
    spec = importlib.util.spec_from_file_location("source_figure", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent.resolve()))
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_source_peak_score_matches_published_definition() -> None:
    module = _figure_module()
    time = np.asarray([-1.0, 0.0, 0.5, 1.5, 2.0])
    rewarded = np.asarray([50.0, 0.2, 1.4, 0.9, 80.0])
    unrewarded = np.asarray([-50.0, -0.1, -0.6, 0.3, -90.0])

    score = module.source_peak_score(rewarded, unrewarded, time)

    assert score == pytest.approx(2.0)


def test_source_peak_score_requires_published_window() -> None:
    module = _figure_module()

    with pytest.raises(ValueError, match=r"0-1\.5 s"):
        module.source_peak_score(
            np.asarray([1.0]), np.asarray([0.0]), np.asarray([-1.0])
        )
