"""Generate deterministic conceptual figures for the scientist documentation."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from figure_style import apply_publication_style, save_figure
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "docs" / "assets"
PURPLE = "#563d7c"
TEAL = "#23877c"
AMBER = "#c47a2c"
INK = "#26212e"
MUTED = "#7b7484"
LIGHT = "#ece9f1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _style()
    _evidence_path(args.output_dir / "evidence-path.svg")
    _preprocessing(args.output_dir / "preprocessing-sequence.svg")
    _qc_gate(args.output_dir / "qc-gating.svg")
    _peri_event(args.output_dir / "peri-event-inference.svg")
    _population_boundary(args.output_dir / "population-inference-boundary.svg")
    _population_interaction(args.output_dir / "population-interaction-boundary.svg")
    _multiverse(args.output_dir / "multiverse-robustness.svg")
    _method_map(args.output_dir / "method-question-map.svg")
    _event_kernel(args.output_dir / "event-kernel-validation.svg")
    _predictor_contributions(args.output_dir / "predictor-family-contributions.svg")
    _variable_duration(args.output_dir / "variable-duration-kernels.svg")
    _publication(args.output_dir / "publication-provenance.svg")
    print(args.output_dir)


def _style() -> None:
    apply_publication_style(hashsalt="fiberphotometry-docs-v1")


def _box(
    axis: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    note: str,
    color: str = PURPLE,
) -> None:
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.025,rounding_size=0.05",
            facecolor="white",
            edgecolor=color,
            linewidth=1.25,
        )
    )
    axis.text(
        x + w / 2,
        y + h * 0.62,
        title,
        ha="center",
        va="center",
        weight="bold",
        color=color,
    )
    axis.text(
        x + w / 2, y + h * 0.28, note, ha="center", va="center", fontsize=7, color=MUTED
    )


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str = MUTED,
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=10, color=color, linewidth=1.1
        )
    )


def _canvas(
    figsize: tuple[float, float], xlim: tuple[float, float], ylim: tuple[float, float]
) -> tuple[plt.Figure, plt.Axes]:
    figure, axis = plt.subplots(figsize=figsize)
    axis.set(xlim=xlim, ylim=ylim)
    axis.axis("off")
    return figure, axis


def _save(figure: plt.Figure, path: Path) -> None:
    save_figure(figure, path)


def _evidence_path(path: Path) -> None:
    figure, axis = _canvas((11.5, 3.0), (0, 11.5), (0, 3))
    items = (
        ("Acquired signals", "channels · clocks · events"),
        ("Explicit processing", "QC · gaps · correction"),
        ("Animal-level evidence", "coverage · contrasts · bands"),
        ("Robustness", "named universes · failures"),
        ("Publication object", "JSON · NWB · signature · DOI"),
    )
    for index, (title, note) in enumerate(items):
        x = 0.2 + index * 2.3
        color = AMBER if index == 3 else TEAL if index == 2 else PURPLE
        _box(axis, x, 0.85, 1.85, 1.1, title, note, color)
        if index < len(items) - 1:
            _arrow(axis, (x + 1.88, 1.4), (x + 2.25, 1.4))
    axis.text(
        5.75,
        2.55,
        "Every claim remains attached to its acquisition and analysis choices",
        ha="center",
        weight="bold",
    )
    _save(figure, path)


def _preprocessing(path: Path) -> None:
    time = np.linspace(0, 40, 1000)
    rng = np.random.default_rng(741)
    reference = (
        0.18 * np.sin(time / 2.8) + 0.012 * time + rng.normal(0, 0.025, len(time))
    )
    neural = sum(np.exp(-(((time - event) / 0.35) ** 2)) for event in (8, 17, 29, 35))
    signal = 1.7 * reference + 0.32 * neural + rng.normal(0, 0.025, len(time))
    fitted = np.polyval(np.polyfit(reference, signal, 1), reference)
    corrected = signal - fitted
    figure, axes = plt.subplots(3, 1, figsize=(10.5, 5.8), sharex=True)
    axes[0].plot(time, signal, color=PURPLE, label="signal")
    axes[0].plot(time, reference, color=TEAL, alpha=0.8, label="reference")
    axes[0].set_title("1 · Preserve acquired channels and clock", loc="left")
    axes[1].plot(time, fitted, color=AMBER, label="fitted reference")
    axes[1].plot(time, signal, color=PURPLE, alpha=0.35)
    axes[1].set_title(
        "2 · Fit the declared correction without erasing provenance", loc="left"
    )
    axes[2].plot(time, corrected, color=TEAL)
    axes[2].axhline(0, color=LIGHT)
    axes[2].set_title(
        "3 · Carry corrected signal and operation ledger forward", loc="left"
    )
    axes[2].set_xlabel("Acquisition time (s)")
    for axis in axes:
        axis.grid(color="#f0edf3")
        axis.legend(frameon=False, fontsize=7, loc="upper right") if axis is not axes[
            2
        ] else None
    _save(figure, path)


def _qc_gate(path: Path) -> None:
    figure, axis = _canvas((10.5, 4.2), (0, 10.5), (0, 4.2))
    _box(
        axis, 0.2, 1.45, 2.0, 1.25, "Recording QC", "dropout · flats · extremes", PURPLE
    )
    _arrow(axis, (2.25, 2.08), (3.05, 2.08))
    _box(
        axis,
        3.1,
        1.45,
        2.0,
        1.25,
        "Complete outputs",
        "traces · events · warnings",
        TEAL,
    )
    _arrow(axis, (5.15, 2.08), (6.0, 2.9), AMBER)
    _arrow(axis, (5.15, 2.08), (6.0, 1.25), TEAL)
    _box(axis, 6.05, 2.35, 2.0, 1.0, "Blocking warning", "analysis = None", AMBER)
    _box(axis, 6.05, 0.7, 2.0, 1.0, "Gate passed", "animal-aware inference", TEAL)
    _arrow(axis, (8.1, 2.85), (9.0, 2.85), AMBER)
    _arrow(axis, (8.1, 1.2), (9.0, 1.2), TEAL)
    axis.text(
        9.65,
        2.85,
        "Visible failure",
        ha="center",
        va="center",
        weight="bold",
        color=AMBER,
    )
    axis.text(
        9.65, 1.2, "Bounded result", ha="center", va="center", weight="bold", color=TEAL
    )
    axis.text(
        5.25,
        3.85,
        "QC gates inference; it never silently deletes evidence",
        ha="center",
        weight="bold",
    )
    _save(figure, path)


def _peri_event(path: Path) -> None:
    rng = np.random.default_rng(812)
    time = np.linspace(-1, 2, 90)
    animals = np.vstack(
        [
            0.28 * np.exp(-(((time - 0.45) / 0.34) ** 2))
            + rng.normal(0, 0.045, len(time))
            for _ in range(8)
        ]
    )
    mean = animals.mean(axis=0)
    se = animals.std(axis=0, ddof=1) / np.sqrt(len(animals))
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.1))
    for curve in animals:
        axes[0].plot(time, curve, color=PURPLE, alpha=0.2)
    axes[0].plot(time, mean, color=PURPLE, linewidth=2.3)
    axes[0].axvline(0, color=AMBER, linestyle="--")
    axes[0].set_title("Animal contrast curves—not pooled events")
    axes[1].fill_between(
        time,
        mean - 2.5 * se,
        mean + 2.5 * se,
        color=TEAL,
        alpha=0.16,
        label="simultaneous",
    )
    axes[1].fill_between(
        time,
        mean - 1.96 * se,
        mean + 1.96 * se,
        color=PURPLE,
        alpha=0.28,
        label="pointwise",
    )
    axes[1].plot(time, mean, color=PURPLE, linewidth=2.3)
    axes[1].axvline(0, color=AMBER, linestyle="--")
    axes[1].set_title("Two uncertainty statements")
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.set(xlabel="Time from event (s)", ylabel="Condition contrast")
        axis.grid(color="#f0edf3")
    _save(figure, path)


def _population_boundary(path: Path) -> None:
    figure, axis = _canvas((11.5, 4.2), (0, 11.5), (0, 4.2))
    items = (
        ("Events / windows", "many observations", PURPLE),
        ("Session estimates", "counts + finite support", PURPLE),
        ("Animal estimates", "equal animal weight", TEAL),
        ("Population", "contrast + uncertainty", AMBER),
    )
    positions = (0.2, 3.05, 5.9, 8.75)
    for index, ((title, note, color), x_position) in enumerate(
        zip(items, positions, strict=True)
    ):
        _box(axis, x_position, 1.65, 2.25, 1.15, title, note, color)
        if index < len(items) - 1:
            _arrow(axis, (x_position + 2.3, 2.23), (x_position + 2.8, 2.23))
    axis.text(
        5.75,
        3.65,
        "The replication boundary is materialized before inference",
        ha="center",
        weight="bold",
    )
    axis.text(
        9.7,
        0.85,
        "paired · complete animals",
        ha="center",
        color=TEAL,
        weight="bold",
        fontsize=8,
    )
    axis.text(
        9.7,
        0.42,
        "independent · disjoint groups",
        ha="center",
        color=PURPLE,
        weight="bold",
        fontsize=8,
    )
    axis.text(
        4.15,
        0.62,
        "The ledger keeps sessions, observation counts, support, exclusions,\n"
        "and every leave-one-animal-out population estimate.",
        ha="center",
        va="center",
        color=MUTED,
    )
    _save(figure, path)


def _population_interaction(path: Path) -> None:
    figure, axis = _canvas((11.5, 5.1), (0, 11.5), (0, 5.1))
    axis.text(
        5.75,
        4.72,
        "Difference within animal, then difference between groups",
        ha="center",
        weight="bold",
    )
    rows = (("Treatment animals", 3.05, TEAL), ("Control animals", 1.2, PURPLE))
    for label, y_position, color in rows:
        axis.text(
            0.15,
            y_position + 0.55,
            label,
            ha="left",
            va="center",
            weight="bold",
            color=color,
            fontsize=8,
        )
        _box(
            axis,
            1.65,
            y_position,
            1.55,
            1.05,
            "Condition 0",
            "animal estimate",
            color,
        )
        _box(
            axis,
            3.65,
            y_position,
            1.55,
            1.05,
            "Condition 1",
            "animal estimate",
            color,
        )
        _arrow(axis, (3.25, y_position + 0.52), (3.6, y_position + 0.52))
        _box(
            axis,
            5.7,
            y_position,
            1.7,
            1.05,
            "Within animal Δ",
            "condition 1 - 0",
            color,
        )
        _arrow(axis, (5.25, y_position + 0.52), (5.65, y_position + 0.52))
        _arrow(axis, (7.45, y_position + 0.52), (8.45, 2.58), color)
    _box(
        axis,
        8.5,
        2.02,
        2.35,
        1.15,
        "Interaction",
        "treatment Δ - control Δ",
        AMBER,
    )
    axis.text(
        5.75,
        0.43,
        "Only complete animal contrasts cross the population boundary; "
        "missing cells stay in the ledger.",
        ha="center",
        color=MUTED,
        fontsize=8,
    )
    _save(figure, path)


def _multiverse(path: Path) -> None:
    figure, axis = _canvas((11, 4.5), (0, 11), (0, 4.5))
    _box(
        axis,
        0.2,
        1.55,
        1.7,
        1.2,
        "Fixed estimand",
        "same animals · contrast · unit",
        PURPLE,
    )
    choices = (
        ("Correction", "OLS · robust", 3.2),
        ("Normalization", "subtract · divide", 2.2),
        ("Window", "early · late", 1.2),
    )
    for title, note, y in choices:
        _box(axis, 2.6, y, 1.8, 0.75, title, note, TEAL)
        _arrow(axis, (1.95, 2.15), (2.55, y + 0.38))
        _arrow(axis, (4.45, y + 0.38), (5.15, 2.15))
    _box(
        axis,
        5.2,
        1.45,
        1.9,
        1.4,
        "Complete ledger",
        "success · blocked · incompatible · failed",
        AMBER,
    )
    _arrow(axis, (7.15, 2.15), (7.85, 2.15))
    _box(
        axis,
        7.9,
        1.45,
        2.4,
        1.4,
        "Robustness summary",
        "range · direction · practical effect · LOO",
        PURPLE,
    )
    axis.text(
        5.5,
        4.15,
        "Reasonable alternatives become an auditable sensitivity analysis",
        ha="center",
        weight="bold",
    )
    _save(figure, path)


def _method_map(path: Path) -> None:
    figure, axis = _canvas((10.8, 5.2), (0, 10.8), (0, 5.2))
    _box(
        axis,
        4.1,
        2.0,
        2.6,
        1.2,
        "Scientific question",
        "choose method by estimand",
        PURPLE,
    )
    destinations = (
        (0.2, 3.8, "Event contrast", "peri-event bands"),
        (0.2, 0.4, "Preprocessing sensitivity", "multiverse"),
        (8.1, 3.8, "Overlapping events", "event kernels"),
        (8.1, 0.4, "Population effect", "scalar mixed model"),
    )
    for x, y, title, note in destinations:
        _box(axis, x, y, 2.35, 0.95, title, note, TEAL if y > 2 else AMBER)
        start = (4.1, 2.6) if x < 4 else (6.7, 2.6)
        _arrow(axis, start, (x + 1.18, y + 0.48))
    axis.text(
        5.4,
        4.85,
        "Availability is not validation",
        ha="center",
        weight="bold",
        color=AMBER,
    )
    axis.text(
        5.4,
        0.35,
        "Each route keeps its own assumptions and evidence boundary",
        ha="center",
        color=MUTED,
    )
    _save(figure, path)


def _event_kernel(path: Path) -> None:
    time = np.linspace(-1, 2, 120)
    cue = 0.35 * np.exp(-(((time - 0.2) / 0.3) ** 2))
    reward = 0.5 * np.exp(-(((time - 0.7) / 0.4) ** 2))
    figure, axes = plt.subplots(1, 3, figsize=(10.8, 3.7))
    axes[0].plot(time, cue, color=PURPLE, label="cue")
    axes[0].plot(time, reward, color=TEAL, label="reward")
    axes[0].plot(time, cue + reward, color=AMBER, label="observed overlap")
    axes[0].set_title("Joint encoding problem")
    axes[0].legend(frameon=False, fontsize=7)
    for animal in range(6):
        axes[1].plot(time, cue + animal * 0.025, color=PURPLE, alpha=0.25)
    axes[1].set_title("Fit complete animals")
    axes[2].bar((0, 1), (0.18, 0.03), color=(TEAL, AMBER))
    axes[2].set_xticks((0, 1), ("training", "held-out"))
    axes[2].set_title("Report transport honestly")
    for axis in axes:
        axis.grid(color="#f0edf3")
    _save(figure, path)


def _predictor_contributions(path: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(11.2, 3.9))
    axes[0].axis("off")
    _box(
        axes[0], 0.06, 0.59, 0.88, 0.23, "Full model", "cue · reward · movement", PURPLE
    )
    _arrow(axes[0], (0.5, 0.57), (0.28, 0.39), AMBER)
    _arrow(axes[0], (0.5, 0.57), (0.72, 0.39), TEAL)
    _box(axes[0], 0.04, 0.13, 0.47, 0.22, "Drop reward", "cue · movement", AMBER)
    _box(axes[0], 0.56, 0.13, 0.40, 0.22, "Drop movement", "cue · reward", TEAL)
    axes[0].set(xlim=(0, 1), ylim=(0, 1), title="Declare literal subsets")

    groups = np.arange(1, 7)
    full = np.asarray((0.38, 0.31, 0.42, 0.25, 0.36, 0.29))
    reduced = np.asarray((0.21, 0.19, 0.26, 0.17, 0.20, 0.18))
    for _group, full_score, reduced_score in zip(groups, full, reduced, strict=True):
        axes[1].plot(
            (0, 1),
            (reduced_score, full_score),
            color=LIGHT,
            linewidth=2,
            zorder=1,
        )
        axes[1].scatter(0, reduced_score, color=AMBER, s=25, zorder=2)
        axes[1].scatter(1, full_score, color=PURPLE, s=25, zorder=2)
    axes[1].set(
        title="Pair held-out animals",
        ylabel="Out-of-fold $R^2$",
        xticks=(0, 1),
        xticklabels=("reduced", "full"),
        xlim=(-0.35, 1.35),
    )

    deltas = full - reduced
    axes[2].scatter(deltas, groups, color=TEAL, s=28, zorder=3)
    estimate = float(np.mean(deltas))
    interval = (estimate - 0.06, estimate + 0.06)
    axes[2].axvline(0, color=MUTED, linestyle="--", linewidth=1)
    axes[2].errorbar(
        estimate,
        0.25,
        xerr=((estimate - interval[0],), (interval[1] - estimate,)),
        fmt="o",
        color=PURPLE,
        capsize=4,
        linewidth=2,
    )
    axes[2].set(
        title="Paired sensitivity",
        xlabel=r"$\Delta R^2$",
        ylabel="Held-out animal",
        yticks=groups,
        ylim=(-0.2, 6.7),
    )
    for axis in axes[1:]:
        axis.grid(color="#f0edf3")
    figure.subplots_adjust(wspace=0.42)
    _save(figure, path)


def _variable_duration(path: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(11.2, 3.8))
    time = np.linspace(0.0, 10.0, 501)
    intervals = ((1.0, 3.0), (5.0, 8.5))
    profile = np.asarray([0.15, 0.75, 1.0, 0.35])
    centers = np.linspace(0.0, 1.0, len(profile))
    signal = np.zeros_like(time)
    active = np.zeros_like(time, dtype=bool)
    for start, stop in intervals:
        inside = (time >= start) & (time < stop)
        progress = (time[inside] - start) / (stop - start)
        signal[inside] = np.interp(progress, centers, profile)
        active |= inside
        axes[0].axvspan(start, stop, color=TEAL, alpha=0.12)
    axes[0].plot(time, signal, color=PURPLE, linewidth=2)
    axes[0].scatter(
        [item for interval in intervals for item in interval],
        [0.0] * 4,
        color=AMBER,
        s=22,
        zorder=3,
    )
    axes[0].set(
        title="Keep physical bouts",
        xlabel="Acquisition time (s)",
        ylabel="Response",
    )

    progress_grid = np.linspace(0.0, 1.0, 101)
    axes[1].plot(
        progress_grid,
        np.interp(progress_grid, centers, profile),
        color=PURPLE,
        linewidth=2.3,
    )
    for center, value in zip(centers, profile, strict=True):
        axes[1].plot(center, value, "o", color=TEAL, markersize=5)
    axes[1].set(
        title="Add normalized progress",
        xlabel="Within-bout progress",
        ylabel="Conditional response",
        xlim=(0, 1),
    )

    axes[2].fill_between(time, 0.0, active.astype(float), color=TEAL, alpha=0.3)
    axes[2].plot(time, active.astype(float), color=TEAL, linewidth=1.8)
    axes[2].axhline(0.0, color=PURPLE, linewidth=1.4)
    axes[2].text(
        3.95,
        0.08,
        "outside rows = 0\nnot missing",
        ha="center",
        color=PURPLE,
        weight="bold",
        fontsize=8,
    )
    axes[2].set(
        title="Retain the full denominator",
        xlabel="Acquisition time (s)",
        ylabel="Progress design support",
        ylim=(-0.08, 1.12),
    )
    for axis in axes:
        axis.grid(color="#f0edf3")
    figure.suptitle(
        "Normalized progress supplements physical time—it does not replace it",
        weight="bold",
    )
    figure.tight_layout()
    _save(figure, path)


def _publication(path: Path) -> None:
    figure, axis = _canvas((11, 3.5), (0, 11), (0, 3.5))
    items = (
        ("Evidence bundle", "JSON · HTML · NWB"),
        ("Verify", "schemas · checksums"),
        ("Compare", "estimand · inputs · results"),
        ("Sign", "manifest attestation"),
        ("Deposit", "validated DOI draft"),
    )
    for index, (title, note) in enumerate(items):
        x = 0.15 + index * 2.2
        _box(axis, x, 1.1, 1.75, 1.05, title, note, TEAL if index < 3 else PURPLE)
        if index < 4:
            _arrow(axis, (x + 1.78, 1.62), (x + 2.15, 1.62))
    axis.text(
        5.5,
        3.05,
        "Publication is a verifiable chain, not a final screenshot",
        ha="center",
        weight="bold",
    )
    axis.text(
        5.5,
        0.35,
        "Byte identity and scientific reproduction remain separate claims",
        ha="center",
        color=AMBER,
    )
    _save(figure, path)


if __name__ == "__main__":
    main()
