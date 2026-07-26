"""Freeze the first sharp-transient and missing-run benchmark contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def protocol() -> dict[str, object]:
    return {
        "schema_version": "transient-gap-protocol-v0.1",
        "status": "frozen_before_aggregate_execution",
        "seed": 20260726,
        "scope": [
            "timestamp_jitter",
            "isolated_dropped_samples",
            "protected_contiguous_gaps",
            "event_windows_intersecting_gaps",
        ],
        "out_of_scope": [
            "behavioral_clock_mapping",
            "variable_duration_trial_warping",
            "model_based_reconstruction",
        ],
        "acquisition": {
            "rates_hz": [20.0, 50.0],
            "duration_s": 12.0,
            "event_time_s": 6.0,
            "event_phase_samples": [0.0, 0.5],
            "timestamp_jitter_fraction": [0.005, 0.02],
        },
        "transients": [
            {"family": "gaussian", "width_samples": 1.5, "class": "stress"},
            {"family": "gaussian", "width_samples": 5.0, "class": "ordinary"},
            {
                "family": "alpha",
                "rise_samples": 2.0,
                "decay_samples": 10.0,
                "class": "stress",
            },
            {
                "family": "alpha",
                "rise_samples": 5.0,
                "decay_samples": 25.0,
                "class": "ordinary",
            },
            {
                "family": "biphasic",
                "width_samples": 5.0,
                "separation_samples": 8.0,
                "class": "ordinary",
            },
        ],
        "perturbations": {
            "isolated_dropout_offsets_samples": [-1, 0, 1],
            "gap_lengths_samples": [2, 5, 20],
            "gap_locations": ["baseline", "event", "response"],
        },
        "policies": {
            "jitter": ["linear_median_rate", "nearest_sample"],
            "isolated_dropout": ["linear", "previous_value", "protected_missing"],
            "contiguous_gap": ["protected_missing", "naive_linear_negative_control"],
        },
        "event_windows_s": {"baseline": [-1.0, 0.0], "response": [0.0, 1.0]},
        "metrics": [
            "normalized_waveform_rmse",
            "peak_amplitude_relative_error",
            "peak_time_error_samples",
            "response_mean_relative_error",
            "event_contrast_relative_error",
            "false_peak_amplitude",
            "reconstructed_window_fraction",
            "event_disposition",
        ],
        "acceptance": {
            "ordinary": {
                "peak_amplitude_relative_error_max": 0.05,
                "peak_time_error_samples_max": 1.0,
                "response_mean_relative_error_max": 0.01,
                "event_contrast_relative_error_max": 0.01,
            },
            "stress": {
                "peak_amplitude_relative_error_max": 0.15,
                "peak_time_error_samples_max": 2.0,
                "response_mean_relative_error_max": 0.05,
                "event_contrast_relative_error_max": 0.05,
            },
            "structural": {
                "protected_gap_bridges_allowed": 0,
                "gap_affected_events_must_be_classified": True,
                "condition_dependent_exclusion_must_warn": True,
            },
            "interpretation": (
                "Engineering thresholds tied to the downstream estimand; the "
                "literature does not establish universal photometry thresholds."
            ),
        },
        "reporting": {
            "retain_all_failures": True,
            "stratify_by_transient_class": True,
            "never_pool_different_metrics": True,
            "naive_gap_interpolation_is_negative_control_only": True,
        },
        "practice_sources": [
            {
                "claim": (
                    "indicator kinetics should govern filtering and temporal reduction"
                ),
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/",
            },
            {
                "claim": "manual artifact removal may fit retained segments separately",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8688475/",
            },
            {
                "claim": "isolated dropped frames are commonly linearly interpolated",
                "url": "https://www.mightexbio.com/fiber-photometry-data-preprocessing-deinterleaving-signals-and-fixing-dropped-frames/",
            },
            {
                "claim": (
                    "published workflows may replace selected artifact regions "
                    "by linear interpolation"
                ),
                "url": "https://www.nature.com/articles/s41467-024-45288-x",
            },
        ],
    }


def main() -> None:
    body = protocol()
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path("benchmarks/transient-gap-protocol-v0.1.json")
    output.write_text(
        json.dumps({**body, "protocol_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(fingerprint)


if __name__ == "__main__":
    main()
