"""Render a bounded reproduction of Seiler et al. Figures 3E-F and 4E-F."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from figure_style import BLUE, GRID, MUTED, RED, apply_publication_style, save_figure

from fiberphotometry.events import align_events
from fiberphotometry.io.dandi_000971 import (
    from_dandi_000971_nwb,
    rewarded_unrewarded_nose_pokes,
)
from fiberphotometry.preprocess import lowpass_filter, reference_dff

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks/dandi-000971-tutorial-manifest-v0.1.json"
DEFAULT_CACHE = Path.home() / "Library/Caches/fiberphotometry/dandi-000971-tutorial"
DEFAULT_OUTPUT = ROOT / "docs/assets/dandi-000971-source-figure-bounded-v0.1.svg"


@dataclass(frozen=True)
class AnimalPSTH:
    """One animal's event-averaged source-aligned traces and peak scores."""

    animal: str
    phenotype: str
    relative_time: np.ndarray
    traces: dict[tuple[str, str], np.ndarray]
    peak_scores: dict[str, float]


def source_peak_score(
    rewarded: np.ndarray, unrewarded: np.ndarray, relative_time: np.ndarray
) -> float:
    """Match the paper's rewarded-max minus unrewarded-min 0-1.5 s statistic."""
    response = (relative_time >= 0) & (relative_time <= 1.5)
    if not np.any(response):
        raise ValueError("relative_time must include the 0-1.5 s response window")
    return float(np.nanmax(rewarded[response]) - np.nanmin(unrewarded[response]))


def _load_animal(asset: dict[str, object], cache: Path) -> AnimalPSTH:
    path = cache / f"{asset['asset_id']}.nwb"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing checksum-pinned public asset {path}; run the DANDI tutorial first"
        )
    recording = from_dandi_000971_nwb(path)
    recording = lowpass_filter(recording, cutoff_hz=3.0)
    recording = reference_dff(recording, method="ols")
    dff = np.asarray(recording["dff"].values, dtype=float)
    center = np.nanmean(dff, axis=0)
    scale = np.nanstd(dff, axis=0)
    recording["session_z_dff"] = (
        ("time", "channel"),
        (dff - center[None, :]) / scale[None, :],
    )
    event_times, labels = rewarded_unrewarded_nose_pokes(path)
    aligned = align_events(
        recording,
        event_times,
        window=(-2.0, 4.0),
        rate=20.0,
        variable="session_z_dff",
        event_ids=[f"event-{index}" for index in range(len(event_times))],
    )
    label_array = np.asarray(labels)
    traces: dict[tuple[str, str], np.ndarray] = {}
    peak_scores: dict[str, float] = {}
    relative_time = np.asarray(aligned.relative_time.values, dtype=float)
    for region in ("DMS", "DLS"):
        channel = int(np.flatnonzero(aligned.channel.values == region)[0])
        for condition in ("rewarded", "unrewarded"):
            values = np.asarray(
                aligned.values[label_array == condition, :, channel], dtype=float
            )
            traces[(region, condition)] = np.nanmean(values, axis=0)
        peak_scores[region] = source_peak_score(
            traces[(region, "rewarded")],
            traces[(region, "unrewarded")],
            relative_time,
        )
    return AnimalPSTH(
        animal=str(asset["subject"]),
        phenotype=str(asset["family"]).removeprefix("FP-"),
        relative_time=relative_time,
        traces=traces,
        peak_scores=peak_scores,
    )


def _mean_sem(values: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(values)
    return np.nanmean(matrix, axis=0), np.nanstd(matrix, axis=0, ddof=1) / np.sqrt(
        len(matrix)
    )


def _render(animals: list[AnimalPSTH], output: Path) -> None:
    apply_publication_style(hashsalt="dandi-000971-source-figure-bounded-v0.1")
    phenotypes = ("PR", "DPR", "PS")
    figure, axes = plt.subplots(
        2,
        4,
        figsize=(11.6, 5.6),
        gridspec_kw={"width_ratios": (1, 1, 1, 0.9)},
        sharex="col",
        constrained_layout=True,
    )
    colors = {"rewarded": RED, "unrewarded": BLUE}
    styles = {"rewarded": "-", "unrewarded": "--"}
    for row, region in enumerate(("DMS", "DLS")):
        for column in (1, 2):
            axes[row, column].sharey(axes[row, 0])
        for column, phenotype in enumerate(phenotypes):
            axis = axes[row, column]
            selected = [animal for animal in animals if animal.phenotype == phenotype]
            for condition in ("rewarded", "unrewarded"):
                traces = [animal.traces[(region, condition)] for animal in selected]
                mean, sem = _mean_sem(traces)
                for animal, trace in zip(selected, traces, strict=True):
                    axis.plot(
                        animal.relative_time,
                        trace,
                        color=colors[condition],
                        linestyle=styles[condition],
                        linewidth=0.7,
                        alpha=0.25,
                    )
                axis.fill_between(
                    selected[0].relative_time,
                    mean - sem,
                    mean + sem,
                    color=colors[condition],
                    alpha=0.12,
                    linewidth=0,
                )
                axis.plot(
                    selected[0].relative_time,
                    mean,
                    color=colors[condition],
                    linestyle=styles[condition],
                    label=(
                        condition.capitalize()
                        if row == 0 and column == 0
                        else "_nolegend_"
                    ),
                )
            axis.axvline(0, color=MUTED, linewidth=0.8)
            axis.axhline(0, color=GRID, linewidth=0.8)
            axis.set_xlim(-1, 3)
            axis.set_title(phenotype, weight="bold")
            if column == 0:
                axis.set_ylabel(f"{region} session z-score")
            if row == 1:
                axis.set_xlabel("Time from nose poke (s)")

        score_axis = axes[row, 3]
        positions = np.arange(len(phenotypes))
        for position, phenotype in zip(positions, phenotypes, strict=True):
            selected = [animal for animal in animals if animal.phenotype == phenotype]
            scores = np.asarray([animal.peak_scores[region] for animal in selected])
            offsets = np.linspace(-0.08, 0.08, len(scores))
            score_axis.scatter(
                position + offsets,
                scores,
                color=MUTED,
                facecolor="white",
                linewidth=1,
                zorder=3,
            )
            score_axis.plot(
                [position - 0.16, position + 0.16],
                [scores.mean(), scores.mean()],
                color="#26212E",
                linewidth=2,
            )
        score_axis.axhline(0, color=GRID, linewidth=0.8)
        score_axis.set_xticks(positions, phenotypes)
        score_axis.set_ylabel("Rewarded max - unrewarded min (z)")
        score_axis.set_title(f"{region} peak score", weight="bold")
        if row == 1:
            score_axis.set_xlabel("Published phenotype")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.025),
        ncols=2,
    )
    figure.suptitle(
        "Six-animal, single-session partial source-panel reproduction",
        weight="bold",
    )
    save_figure(figure, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    animals = [_load_animal(asset, args.cache_dir) for asset in manifest["assets"]]
    _render(animals, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
