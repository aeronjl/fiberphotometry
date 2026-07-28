import json
from dataclasses import replace

import numpy as np
import pytest

from fiberphotometry.multisignal import (
    ChannelIdentity,
    LaggedAssociationSpec,
    SpatialCoordinate,
)
from fiberphotometry.spatial_network import (
    SpatialAnimalInferenceSpec,
    SpatialArrayMetadata,
    SpatialDistanceBin,
    SpatialNetworkSpec,
    SpatialNodePermutationSpec,
    SpatialStudySession,
    estimate_spatial_network,
    infer_spatial_network_animals,
)


def _metadata(
    subject: str = "mouse-01", session: str = "session-01"
) -> SpatialArrayMetadata:
    positions = (0.0, 1.0, 10.0, 11.0)
    channels = tuple(
        ChannelIdentity(
            channel_id=f"fiber-{index}",
            site=f"site-{index}",
            sensor="dLight1.3b",
            role="sensor",
            unit="dF/F",
            fiber_id=f"fiber-{index}",
            coordinate=SpatialCoordinate(position, 0, 0, unit="mm", space="implant"),
        )
        for index, position in enumerate(positions)
    )
    return SpatialArrayMetadata(
        subject=subject,
        session=session,
        array_id="array-01",
        channels=channels,
        clock_id="photometry-clock",
        alignment_policy="native_shared_clock",
        preprocessing_fingerprint="sha256:preprocessing",
    )


def _network_spec(*, spatial_null: bool = True) -> SpatialNetworkSpec:
    return SpatialNetworkSpec(
        association=LaggedAssociationSpec(maximum_lag_s=0.2),
        minimum_edge_support=100,
        distance_bins=(
            SpatialDistanceBin("near", 0, 2),
            SpatialDistanceBin("far", 2, 20),
        ),
        node_permutation=(
            SpatialNodePermutationSpec(resamples=200, seed=5) if spatial_null else None
        ),
    )


def _clustered_signals(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    time = np.arange(0, 40, 0.05)
    first_source = rng.normal(size=len(time))
    second_source = rng.normal(size=len(time))
    values = np.column_stack(
        (
            first_source + rng.normal(0, 0.15, len(time)),
            first_source + rng.normal(0, 0.15, len(time)),
            second_source + rng.normal(0, 0.15, len(time)),
            second_source + rng.normal(0, 0.15, len(time)),
        )
    )
    return time, values


def test_spatial_network_preserves_edges_support_and_distance_structure() -> None:
    time, values = _clustered_signals()

    result = estimate_spatial_network(time, values, _metadata(), _network_spec())

    assert result.candidate_edge_count == 6
    assert result.retained_edge_count == 6
    assert not result.exclusions
    summaries = {item.bin_name: item for item in result.distance_summaries}
    assert summaries["near"].edge_count == 2
    assert summaries["far"].edge_count == 4
    assert summaries["near"].association > 0.95
    assert summaries["far"].association < 0.1
    assert result.global_association is not None
    assert result.spatial_null is not None
    assert result.spatial_null.performed is True
    assert result.spatial_null.observed_value is not None
    assert result.spatial_null.observed_value < -0.8
    assert all(edge.support == len(time) for edge in result.edges)
    assert result.evidence_fingerprint.startswith("sha256:")
    payload = json.loads(result.to_json())
    assert payload["edges"][0]["coordinate_space"] == "implant"
    assert payload["spatial_null"]["statistic"].startswith("distance_transformed")


def test_pairwise_validity_and_gaps_remain_visible_in_edge_evidence() -> None:
    first_time = np.arange(0, 10, 0.05)
    second_time = np.arange(15, 25, 0.05)
    time = np.concatenate((first_time, second_time))
    _, values = _clustered_signals()
    values = values[: len(time)]
    valid = np.ones_like(values, dtype=bool)
    valid[:20, 0] = False

    result = estimate_spatial_network(
        time,
        values,
        _metadata(),
        replace(_network_spec(spatial_null=False), minimum_edge_support=50),
        valid=valid,
    )

    by_pair = {
        frozenset((edge.first_channel_id, edge.second_channel_id)): edge
        for edge in result.edges
    }
    masked = by_pair[frozenset(("fiber-0", "fiber-1"))]
    complete = by_pair[frozenset(("fiber-1", "fiber-2"))]
    assert masked.support == len(time) - 20
    assert complete.support == len(time)
    assert masked.joint_valid_sample_count == len(time) - 20
    assert masked.continuity_run_count >= 2
    assert masked.gap_count >= 1


def test_spatial_metadata_refuses_missing_or_incommensurate_geometry() -> None:
    metadata = _metadata()
    missing = replace(metadata.channels[0], coordinate=None)
    with pytest.raises(ValueError, match="require coordinates"):
        replace(metadata, channels=(missing, *metadata.channels[1:]))

    mixed_unit = replace(
        metadata.channels[0],
        coordinate=SpatialCoordinate(0, 0, 0, unit="um", space="implant"),
    )
    with pytest.raises(ValueError, match="share one unit and space"):
        replace(metadata, channels=(mixed_unit, *metadata.channels[1:]))

    with pytest.raises(ValueError, match="at least three"):
        replace(metadata, channels=metadata.channels[:2])

    with pytest.raises(ValueError, match="cannot overlap"):
        SpatialNetworkSpec(
            distance_bins=(
                SpatialDistanceBin("first", 0, 5),
                SpatialDistanceBin("second", 4, 10),
            )
        )


def test_mouse_inference_aggregates_sessions_before_contrasting_conditions() -> None:
    rng = np.random.default_rng(21)
    time = np.arange(0, 25, 0.05)
    sessions = []
    for mouse_index in range(5):
        subject = f"mouse-{mouse_index}"
        for condition in ("baseline", "drug"):
            for repeat in range(1 + (mouse_index == 0)):
                independent = rng.normal(size=(len(time), 4))
                if condition == "drug":
                    common = rng.normal(size=(len(time), 1))
                    values = common + 0.35 * independent
                else:
                    values = independent
                result = estimate_spatial_network(
                    time,
                    values,
                    _metadata(subject, f"{condition}-{repeat}"),
                    _network_spec(spatial_null=False),
                )
                sessions.append(SpatialStudySession(condition, result))

    _, invalid_values = _clustered_signals(seed=99)
    excluded_result = estimate_spatial_network(
        time,
        invalid_values[: len(time)],
        _metadata("mouse-0", "baseline-insufficient-support"),
        replace(_network_spec(spatial_null=False), minimum_edge_support=10_000),
    )
    sessions.append(SpatialStudySession("baseline", excluded_result))

    inference = infer_spatial_network_animals(
        sessions,
        SpatialAnimalInferenceSpec(
            metric="global_association",
            condition_a="baseline",
            condition_b="drug",
            bootstrap_resamples=200,
            permutation_resamples=200,
            seed=7,
        ),
    )

    assert inference.effect_direction == "condition_b minus condition_a"
    assert inference.estimate > 0.75
    assert len(inference.animal_estimates) == 10
    assert len(inference.session_estimates) == 12
    assert len(inference.session_exclusions) == 1
    assert (
        inference.session_exclusions[0].reason
        == "requested_metric_has_no_retained_edges"
    )
    assert inference.animals_a == inference.animals_b
    assert len(inference.animals_a) == 5
    mouse_zero = [
        item for item in inference.animal_estimates if item.subject == "mouse-0"
    ]
    assert {item.session_count for item in mouse_zero} == {2}
    assert inference.interval_low > 0

    local = infer_spatial_network_animals(
        sessions,
        SpatialAnimalInferenceSpec(
            metric="distance_bin_association",
            distance_bin_name="near",
            condition_a="baseline",
            condition_b="drug",
            bootstrap_resamples=100,
            permutation_resamples=100,
            seed=8,
        ),
    )
    assert local.estimate > 0.75


def test_spatial_inference_refuses_duplicate_session_identities() -> None:
    time, values = _clustered_signals()
    result = estimate_spatial_network(
        time, values, _metadata(), _network_spec(spatial_null=False)
    )
    session = SpatialStudySession("baseline", result)

    with pytest.raises(ValueError, match="identities must be unique"):
        infer_spatial_network_animals(
            [session, session],
            SpatialAnimalInferenceSpec(
                metric="global_association",
                condition_a="baseline",
                condition_b="drug",
                bootstrap_resamples=100,
                permutation_resamples=100,
            ),
        )
