"""Run the frozen DANDI:000251 transient construct-validation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from pynwb import NWBHDF5IO

from fipha import make_recording
from fipha.transients import TransientDetectionSpec, detect_transients

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/dandi-000251-transients-manifest-v0.1.json"
OUTPUT = ROOT / "benchmarks/dandi-000251-transients-results-v0.1.json"
WINDOW = (0.6, 2.1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(asset: dict[str, Any], cache: Path) -> Path:
    path = cache / Path(asset["path"]).name
    valid = (
        path.exists()
        and path.stat().st_size == asset["size"]
        and _sha256(path) == asset["sha256"]
    )
    if not valid:
        url = f"https://api.dandiarchive.org/api/assets/{asset['asset_id']}/download/"
        urllib.request.urlretrieve(url, path)
    if path.stat().st_size != asset["size"] or _sha256(path) != asset["sha256"]:
        raise RuntimeError(f"checksum or size mismatch for {asset['path']}")
    return path


def _load(path: Path, subject: str, condition: str):
    with NWBHDF5IO(path, "r", load_namespaces=True) as io:
        nwb = io.read()
        fluorescence = nwb.processing["ophys"]["fluorescence"]
        if fluorescence.rate is None or fluorescence.starting_time is None:
            raise RuntimeError("frozen fluorescence schema requires rate-based time")
        values = np.asarray(fluorescence.data[:], dtype=float)
        time = float(fluorescence.starting_time) + np.arange(len(values)) / float(
            fluorescence.rate
        )
        trials = nwb.trials.to_dataframe()
        teleports = np.asarray(trials["teleport"].dropna(), dtype=float)
        rewards = np.asarray(trials["rew"].dropna(), dtype=float)
        session = str(nwb.session_id)
    recording = make_recording(
        time=time,
        signal=values,
        channel_names=["VS_dLight"],
        subject=subject,
        session=session,
        attrs={
            "source_dataset": "DANDI:000251/draft",
            "source_condition": condition,
            "source_signal": "archived dF/F",
        },
    )
    return recording, teleports, rewards


def _universes() -> dict[str, TransientDetectionSpec]:
    return {
        f"{mode}-{multiplier}mad-{baseline}": TransientDetectionSpec(
            threshold_mode=mode,  # type: ignore[arg-type]
            threshold=float(multiplier),
            baseline_statistic=baseline,  # type: ignore[arg-type]
            baseline_duration_s=0.9,
            baseline_gap_s=0.1,
            noise_window_s=15.0,
            minimum_distance_s=0.2,
            maximum_gap_factor=3.0,
            require_complete_shape=True,
            bin_width_s=30.0,
        )
        for mode in ("global_mad", "rolling_mad")
        for multiplier in (3, 5)
        for baseline in ("median", "minimum")
    }


def event_hit_fraction(
    peaks: np.ndarray,
    event_times: np.ndarray,
    window: tuple[float, float] = WINDOW,
) -> float | None:
    """Return the fraction of external events followed by at least one peak."""
    if not len(event_times):
        return None
    hits = [
        np.any((peaks >= event + window[0]) & (peaks <= event + window[1]))
        for event in event_times
    ]
    return float(np.mean(hits))


def peak_jaccard(
    first: np.ndarray, second: np.ndarray, tolerance: float = 0.1
) -> float:
    """One-to-one tolerant Jaccard agreement between two sorted peak sets."""
    used: set[int] = set()
    matches = 0
    for value in first:
        candidates = np.flatnonzero(np.abs(second - value) <= tolerance)
        available = [int(index) for index in candidates if int(index) not in used]
        if available:
            chosen = min(available, key=lambda index: abs(float(second[index] - value)))
            used.add(chosen)
            matches += 1
    union = len(first) + len(second) - matches
    return float(matches / union) if union else 1.0


def shifted_hit_distribution(
    peaks_by_session: list[np.ndarray],
    events_by_session: list[np.ndarray],
    bounds_by_session: list[tuple[float, float]],
) -> list[float]:
    """Generate the frozen 999-offset animal-mean circular-shift null."""
    output = []
    for index in range(1, 1000):
        fractions = []
        for peaks, events, (start, stop) in zip(
            peaks_by_session, events_by_session, bounds_by_session, strict=True
        ):
            duration = stop - start
            shifted = start + ((events - start + duration * index / 1000) % duration)
            fraction = event_hit_fraction(peaks, shifted)
            if fraction is not None:
                fractions.append(fraction)
        output.append(float(np.mean(fractions)))
    return output


def _session_result(
    asset: dict[str, Any], recording: Any, teleports: np.ndarray, rewards: np.ndarray
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "subject": asset["subject"],
        "condition": asset["condition"],
        "asset_id": asset["asset_id"],
        "session": recording.attrs["session"],
        "sample_count": int(recording.sizes["time"]),
        "duration_s": float(recording.time.values[-1] - recording.time.values[0]),
        "teleport_count": len(teleports),
        "reward_count": len(rewards),
        "universes": {},
    }
    for universe_id, spec in _universes().items():
        result = detect_transients(recording, variable="signal", spec=spec)
        peaks = np.asarray([event.peak_time for event in result.events], dtype=float)
        summary = result.summaries[0]
        output["universes"][universe_id] = {
            "spec": asdict(spec),
            "accepted_count": len(result.events),
            "excluded_count": len(result.exclusions),
            "exclusion_counts": {
                reason: sum(item.reason == reason for item in result.exclusions)
                for reason in sorted({item.reason for item in result.exclusions})
            },
            "summary": asdict(summary),
            "peak_times": peaks.tolist(),
            "teleport_hit_fraction": event_hit_fraction(peaks, teleports),
            "reward_hit_fraction_0_2s": event_hit_fraction(
                peaks, rewards, window=(0.0, 2.0)
            ),
        }
    return output


def _aggregate(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    teleport_sessions = [
        item for item in sessions if item["condition"] == "three_teleport"
    ]
    aggregate: dict[str, Any] = {}
    universe_ids = list(_universes())
    for universe_id in universe_ids:
        peaks = [
            np.asarray(item["universes"][universe_id]["peak_times"], dtype=float)
            for item in teleport_sessions
        ]
        events = []
        bounds = []
        for item in teleport_sessions:
            asset_path = item["_cache_path"]
            _, teleports, _ = _load(
                Path(asset_path), item["subject"], item["condition"]
            )
            events.append(teleports)
            bounds.append((0.0, item["duration_s"]))
        observed_values = [
            item["universes"][universe_id]["teleport_hit_fraction"]
            for item in teleport_sessions
        ]
        observed = float(np.mean(observed_values))
        null = shifted_hit_distribution(peaks, events, bounds)
        aggregate[universe_id] = {
            "animal_hit_fractions": observed_values,
            "mean_teleport_hit_fraction": observed,
            "null_mean": float(np.mean(null)),
            "null_95_interval": [
                float(np.quantile(null, 0.025)),
                float(np.quantile(null, 0.975)),
            ],
            "upper_tail_probability": (1 + sum(value >= observed for value in null))
            / 1000,
        }
    agreements = []
    for session in sessions:
        for first_index, first in enumerate(universe_ids):
            for second in universe_ids[first_index + 1 :]:
                agreements.append(
                    {
                        "subject": session["subject"],
                        "condition": session["condition"],
                        "first": first,
                        "second": second,
                        "jaccard": peak_jaccard(
                            np.asarray(session["universes"][first]["peak_times"]),
                            np.asarray(session["universes"][second]["peak_times"]),
                        ),
                    }
                )
    return {
        "external_enrichment": aggregate,
        "agreement": {
            "pairwise_session_comparisons": agreements,
            "minimum_jaccard": min(item["jaccard"] for item in agreements),
            "median_jaccard": float(
                np.median([item["jaccard"] for item in agreements])
            ),
            "maximum_jaccard": max(item["jaccard"] for item in agreements),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / "Library/Caches/fipha/dandi-000251-transients",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    sessions = []
    for asset in manifest["assets"]:
        path = _download(asset, args.cache)
        recording, teleports, rewards = _load(
            path, asset["subject"], asset["condition"]
        )
        item = _session_result(asset, recording, teleports, rewards)
        item["_cache_path"] = str(path)
        sessions.append(item)
    aggregate = _aggregate(sessions)
    for item in sessions:
        item.pop("_cache_path")
    payload = {
        "schema_version": "dandi-000251-transients-results-v0.1",
        "scientific_protocol": "protocol-dandi-000251-transients-v0.1",
        "manifest_sha256": _sha256(MANIFEST),
        "claim_boundary": (
            "construct validation against task timing; not raw-preprocessing, "
            "manual-event, or biological tonic validation"
        ),
        "sessions": sessions,
        "aggregate": aggregate,
    }
    payload["result_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "aggregate": aggregate}, indent=2))


if __name__ == "__main__":
    main()
