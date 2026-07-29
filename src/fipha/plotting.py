"""Optional diagnostic plots that expose raw signals and QC assumptions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import xarray as xr

from fipha.event_qc import assess_event_confounds
from fipha.events import align_events
from fipha.model import validate_recording
from fipha.preprocess import reference_dff


@dataclass(frozen=True)
class SpecificationCurveEntry:
    """One successful universe prepared for a specification-curve plot."""

    universe_id: str
    estimate: float
    confidence_interval: tuple[float, float]
    decisions: tuple[tuple[str, str], ...]
    is_reference: bool = False


def plot_specification_curve(
    entries: Sequence[SpecificationCurveEntry],
    *,
    decision_order: Sequence[str] | None = None,
    null_value: float = 0.0,
    effect_label: str = "Estimate",
) -> tuple[Any, np.ndarray]:
    """Plot ordered estimates and the decisions defining each universe.

    Entries are sorted by estimate, so this is a descriptive robustness display;
    the order is not an inferential ranking. Confidence intervals must be finite.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError("specification-curve plots require `fipha[plots]`") from error
    if not entries:
        raise ValueError("a specification curve requires at least one entry")
    _validate_specification_entries(entries)
    ordered = sorted(entries, key=lambda entry: (entry.estimate, entry.universe_id))
    known_decisions = tuple(dict(ordered[0].decisions))
    names = tuple(decision_order) if decision_order is not None else known_decisions
    if set(names) != set(known_decisions) or len(names) != len(set(names)):
        raise ValueError("decision_order must name each decision exactly once")

    alternatives = {
        name: tuple(dict.fromkeys(dict(entry.decisions)[name] for entry in ordered))
        for name in names
    }
    rows = [(name, alternative) for name in names for alternative in alternatives[name]]
    figure, axes = plt.subplots(
        2,
        1,
        figsize=(max(7.0, 0.55 * len(ordered)), 4.2 + 0.32 * len(rows)),
        sharex=True,
        gridspec_kw={"height_ratios": (2.2, max(1.0, 0.34 * len(rows)))},
        constrained_layout=True,
    )
    estimate_axis, decision_axis = axes
    x = np.arange(len(ordered))
    estimates = np.asarray([entry.estimate for entry in ordered])
    intervals = np.asarray([entry.confidence_interval for entry in ordered])
    errors = np.vstack((estimates - intervals[:, 0], intervals[:, 1] - estimates))
    colors = ["#c44e52" if entry.is_reference else "#376795" for entry in ordered]
    for index, color in enumerate(colors):
        estimate_axis.errorbar(
            x[index],
            estimates[index],
            yerr=errors[:, index].reshape(2, 1),
            fmt="none",
            ecolor=color,
            elinewidth=1.2,
            capsize=2.5,
            alpha=0.9,
        )
    estimate_axis.scatter(x, estimates, c=colors, s=32, zorder=3)
    estimate_axis.axhline(null_value, color="#555555", linestyle="--", linewidth=1)
    estimate_axis.set_ylabel(effect_label)
    estimate_axis.set_title("Specification curve")
    estimate_axis.spines[["top", "right"]].set_visible(False)

    for row, (name, alternative) in enumerate(rows):
        selected = [
            index
            for index, entry in enumerate(ordered)
            if dict(entry.decisions)[name] == alternative
        ]
        decision_axis.scatter(selected, [row] * len(selected), color="#376795", s=28)
    boundaries = np.cumsum([len(alternatives[name]) for name in names])[:-1] - 0.5
    for boundary in boundaries:
        decision_axis.axhline(boundary, color="#dddddd", linewidth=0.8)
    decision_axis.set_yticks(
        np.arange(len(rows)), [f"{name}: {alternative}" for name, alternative in rows]
    )
    decision_axis.set_xlabel("Universe (ordered by estimate)")
    decision_axis.set_xticks(x, [str(index + 1) for index in x])
    decision_axis.set_ylim(len(rows) - 0.5, -0.5)
    decision_axis.spines[["top", "right", "left"]].set_visible(False)
    decision_axis.tick_params(axis="y", length=0)
    return figure, axes


def _validate_specification_entries(
    entries: Sequence[SpecificationCurveEntry],
) -> None:
    identifiers = [entry.universe_id for entry in entries]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("universe identifiers must be unique")
    expected_names = tuple(dict(entries[0].decisions))
    for entry in entries:
        decisions = dict(entry.decisions)
        values = (entry.estimate, *entry.confidence_interval)
        if len(decisions) != len(entry.decisions) or tuple(decisions) != expected_names:
            raise ValueError("every entry must define the same unique decisions")
        if not np.all(np.isfinite(values)):
            raise ValueError("estimates and confidence intervals must be finite")
        lower, upper = entry.confidence_interval
        if lower > entry.estimate or entry.estimate > upper:
            raise ValueError("confidence intervals must contain their estimates")


def plot_event_diagnostics(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    channel: str | int = 0,
    window: tuple[float, float] = (-1.0, 2.0),
) -> tuple[Any, np.ndarray]:
    """Plot raw traces, peri-event signal/reference means, and corrected dF/F."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError("diagnostic plots require `fipha[plots]`") from error
    validate_recording(recording)
    index = (
        int(np.flatnonzero(recording.channel.values == channel)[0])
        if isinstance(channel, str)
        else channel
    )
    rate = 1 / float(np.median(np.diff(recording.time.values)))
    corrected = reference_dff(recording)
    signal = align_events(
        recording, event_times, window=window, rate=rate, variable="signal"
    )
    reference = align_events(
        recording, event_times, window=window, rate=rate, variable="reference"
    )
    dff = align_events(corrected, event_times, window=window, rate=rate, variable="dff")
    qc = assess_event_confounds(recording, event_times).channels[index]
    figure, axes = plt.subplots(3, 1, figsize=(9, 8), constrained_layout=True)
    axes[0].plot(
        recording.time, recording.signal[:, index], label="signal", linewidth=0.8
    )
    axes[0].plot(
        recording.time, recording.reference[:, index], label="reference", linewidth=0.8
    )
    axes[0].legend()
    for axis, aligned, label in (
        (axes[1], signal, "signal"),
        (axes[1], reference, "reference"),
        (axes[2], dff, "IRLS dF/F"),
    ):
        axis.plot(
            aligned.relative_time, np.nanmean(aligned[:, :, index], axis=0), label=label
        )
        axis.axvline(0, color="black", linewidth=0.8, linestyle="--")
        axis.legend()
    axes[0].set_title(
        f"{qc.channel}: {', '.join(qc.warnings) or 'no event-QC warning'}"
    )
    axes[2].set_xlabel("Time from event (s)")
    return figure, axes
