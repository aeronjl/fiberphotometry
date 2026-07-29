"""Coordinate-aware dense multi-fiber networks with mouse-level inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from itertools import combinations, pairwise, permutations, product
from math import factorial
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

from fiberphotometry.multisignal import (
    AlignmentPolicy,
    ChannelIdentity,
    LaggedAssociationSpec,
    SignalPairMetadata,
    lagged_association,
)

SpatialEdgeMetric: TypeAlias = Literal[
    "zero_lag_correlation", "peak_absolute_correlation"
]
CorrelationScale: TypeAlias = Literal["raw", "fisher_z"]
SpatialInferenceMetric: TypeAlias = Literal[
    "global_association",
    "distance_bin_association",
    "distance_edge_correlation",
    "site_strength",
]
Design: TypeAlias = Literal["paired", "independent"]
Aggregation: TypeAlias = Literal["mean", "median"]

_MAXIMUM_EXACT_PERMUTATIONS = 40_320


@dataclass(frozen=True)
class SpatialArrayMetadata:
    """Mouse, session, clock, processing, and coordinate identity for one array."""

    subject: str
    session: str
    array_id: str
    channels: tuple[ChannelIdentity, ...]
    clock_id: str
    alignment_policy: AlignmentPolicy
    preprocessing_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "subject",
            "session",
            "array_id",
            "clock_id",
            "preprocessing_fingerprint",
        ):
            cleaned = str(getattr(self, name)).strip()
            if not cleaned:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, cleaned)
        if len(self.channels) < 3:
            raise ValueError("spatial arrays require at least three channels")
        identifiers = [channel.channel_id for channel in self.channels]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("spatial array channel IDs must be unique")
        if self.alignment_policy not in {
            "native_shared_clock",
            "explicitly_resampled",
        }:
            raise ValueError("unsupported spatial array alignment policy")
        missing = [
            channel.channel_id
            for channel in self.channels
            if channel.coordinate is None
        ]
        if missing:
            raise ValueError(
                "spatial array channels require coordinates: " + ", ".join(missing)
            )
        units = {
            channel.coordinate.unit for channel in self.channels if channel.coordinate
        }
        spaces = {
            channel.coordinate.space for channel in self.channels if channel.coordinate
        }
        if len(units) != 1 or len(spaces) != 1:
            raise ValueError("spatial array coordinates must share one unit and space")

    @property
    def coordinate_unit(self) -> str:
        """Return the validated shared coordinate unit."""
        coordinate = self.channels[0].coordinate
        assert coordinate is not None
        return str(coordinate.unit)

    @property
    def coordinate_space(self) -> str:
        """Return the validated shared coordinate space."""
        coordinate = self.channels[0].coordinate
        assert coordinate is not None
        return str(coordinate.space)


@dataclass(frozen=True)
class SpatialDistanceBin:
    """One named half-open physical-distance interval."""

    name: str
    minimum_distance: float
    maximum_distance: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("spatial distance-bin name must be non-empty")
        if (
            not np.isfinite(self.minimum_distance)
            or not np.isfinite(self.maximum_distance)
            or self.minimum_distance < 0
            or self.minimum_distance >= self.maximum_distance
        ):
            raise ValueError("spatial distance bounds must be finite and increasing")

    def contains(self, distance: float) -> bool:
        """Return membership under the half-open [minimum, maximum) policy."""
        return self.minimum_distance <= distance < self.maximum_distance


@dataclass(frozen=True)
class SpatialNodePermutationSpec:
    """Node-label randomization for distance-edge structure within a session.

    When the node-label permutation group is no larger than ``resamples`` it is
    enumerated exactly instead of sampled, so the reported p-value is never finer
    than the design supports.
    """

    resamples: int = 1_000
    seed: int = 0

    def __post_init__(self) -> None:
        if self.resamples < 100:
            raise ValueError("spatial node permutation requires at least 100 resamples")


@dataclass(frozen=True)
class SpatialNetworkSpec:
    """Declare pairwise, distance, aggregation, and spatial-null choices."""

    association: LaggedAssociationSpec = field(default_factory=LaggedAssociationSpec)
    edge_metric: SpatialEdgeMetric = "zero_lag_correlation"
    correlation_scale: CorrelationScale = "fisher_z"
    minimum_edge_support: int = 20
    distance_bins: tuple[SpatialDistanceBin, ...] = ()
    node_permutation: SpatialNodePermutationSpec | None = field(
        default_factory=SpatialNodePermutationSpec
    )

    def __post_init__(self) -> None:
        if self.edge_metric not in {
            "zero_lag_correlation",
            "peak_absolute_correlation",
        }:
            raise ValueError("unsupported spatial edge metric")
        if self.correlation_scale not in {"raw", "fisher_z"}:
            raise ValueError("unsupported spatial correlation scale")
        if self.minimum_edge_support < 2:
            raise ValueError("minimum_edge_support must be at least two")
        names = [item.name for item in self.distance_bins]
        if len(set(names)) != len(names):
            raise ValueError("spatial distance-bin names must be unique")
        ordered = sorted(self.distance_bins, key=lambda item: item.minimum_distance)
        for first, second in pairwise(ordered):
            if second.minimum_distance < first.maximum_distance:
                raise ValueError("spatial distance bins cannot overlap")


@dataclass(frozen=True)
class SpatialNetworkEdge:
    """One retained within-session edge and its physical/evidence denominator."""

    pair_id: str
    first_channel_id: str
    second_channel_id: str
    first_site: str
    second_site: str
    distance: float
    distance_unit: str
    coordinate_space: str
    metric: SpatialEdgeMetric
    value: float
    transformed_value: float
    support: int
    peak_lag_s: float
    continuity_run_count: int
    joint_valid_sample_count: int
    gap_count: int
    within_session_pvalue: float | None
    source_method: str


@dataclass(frozen=True)
class SpatialNetworkEdgeExclusion:
    """One candidate edge excluded before spatial summarization."""

    pair_id: str
    first_channel_id: str
    second_channel_id: str
    distance: float
    reason: str


@dataclass(frozen=True)
class SpatialDistanceSummary:
    """Association summary for one declared physical-distance bin."""

    bin_name: str
    minimum_distance: float
    maximum_distance: float
    distance_unit: str
    association: float
    edge_count: int
    total_support: int
    correlation_scale: CorrelationScale


@dataclass(frozen=True)
class SpatialNodePermutationResult:
    """Within-session node-label null for distance-edge association.

    ``resamples`` is the requested count. ``effective_resamples`` is the number of
    permutations that actually entered the null after undefined ones were dropped,
    and ``pvalue_resolution`` is the finest p-value that count can express.
    """

    performed: bool
    statistic: str
    observed_value: float | None
    pvalue: float | None
    resamples: int
    seed: int
    edge_count: int
    exclusion_reason: str | None
    permutation_group_size: int
    exhaustive: bool
    effective_resamples: int
    undefined_resamples: int
    pvalue_resolution: float | None


@dataclass(frozen=True)
class SpatialNetworkResult:
    """One session network, distance summaries, null, and complete edge ledger."""

    metadata: SpatialArrayMetadata
    spec: SpatialNetworkSpec
    edges: tuple[SpatialNetworkEdge, ...]
    exclusions: tuple[SpatialNetworkEdgeExclusion, ...]
    distance_summaries: tuple[SpatialDistanceSummary, ...]
    global_association: float | None
    spatial_null: SpatialNodePermutationResult | None
    candidate_edge_count: int
    retained_edge_count: int
    evidence_fingerprint: str
    method: str = "pairwise_gap_separated_spatial_network"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize geometry, edges, summaries, null evidence, and provenance."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class SpatialStudySession:
    """Attach an experimental condition to one session network."""

    condition: str
    result: SpatialNetworkResult

    def __post_init__(self) -> None:
        if not self.condition.strip():
            raise ValueError("spatial study condition must be non-empty")


@dataclass(frozen=True)
class SpatialAnimalInferenceSpec:
    """Declare a session-to-mouse contrast for one network estimand."""

    metric: SpatialInferenceMetric
    condition_a: str
    condition_b: str
    distance_bin_name: str | None = None
    site: str | None = None
    design: Design = "paired"
    session_aggregation: Aggregation = "mean"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 10_000
    seed: int = 0

    def __post_init__(self) -> None:
        if self.metric not in {
            "global_association",
            "distance_bin_association",
            "distance_edge_correlation",
            "site_strength",
        }:
            raise ValueError("unsupported spatial inference metric")
        if not self.condition_a.strip() or not self.condition_b.strip():
            raise ValueError("spatial inference conditions must be non-empty")
        if self.condition_a == self.condition_b:
            raise ValueError("spatial inference conditions must differ")
        if (self.metric == "distance_bin_association") != (
            self.distance_bin_name is not None
        ):
            raise ValueError(
                "distance_bin_name is required only for distance-bin inference"
            )
        if (self.metric == "site_strength") != (self.site is not None):
            raise ValueError("site is required only for site-strength inference")
        if self.distance_bin_name is not None and not self.distance_bin_name.strip():
            raise ValueError("distance_bin_name must be non-empty")
        if self.site is not None and not self.site.strip():
            raise ValueError("site must be non-empty")
        if self.design not in {"paired", "independent"}:
            raise ValueError("unsupported spatial inference design")
        if self.session_aggregation not in {"mean", "median"}:
            raise ValueError("unsupported spatial session aggregation")
        if not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must lie between zero and one")
        if self.bootstrap_resamples < 100 or self.permutation_resamples < 100:
            raise ValueError("spatial inference requires at least 100 resamples")


@dataclass(frozen=True)
class SpatialSessionEstimate:
    """One session scalar after dependent edges have been summarized."""

    subject: str
    session: str
    condition: str
    array_id: str
    metric: SpatialInferenceMetric
    value: float
    edge_count: int
    total_support: int


@dataclass(frozen=True)
class SpatialSessionExclusion:
    """One requested session that could not provide the declared estimand."""

    subject: str
    session: str
    condition: str
    array_id: str
    metric: SpatialInferenceMetric
    reason: str


@dataclass(frozen=True)
class SpatialAnimalEstimate:
    """One mouse-condition value after equal-session aggregation."""

    subject: str
    condition: str
    metric: SpatialInferenceMetric
    value: float
    session_count: int
    edge_count: int
    total_support: int


@dataclass(frozen=True)
class SpatialAnimalInferenceResult:
    """Mouse-level contrast, interval, randomization test, and full ledger."""

    spec: SpatialAnimalInferenceSpec
    session_estimates: tuple[SpatialSessionEstimate, ...]
    session_exclusions: tuple[SpatialSessionExclusion, ...]
    animal_estimates: tuple[SpatialAnimalEstimate, ...]
    estimate: float
    interval_low: float
    interval_high: float
    permutation_pvalue: float
    animals_a: tuple[str, ...]
    animals_b: tuple[str, ...]
    excluded_subjects: tuple[str, ...]
    permutation_resamples: int
    effect_direction: str = "condition_b minus condition_a"
    method: str = "equal_session_mouse_bootstrap_and_randomization"


def estimate_spatial_network(
    time: ArrayLike,
    values: ArrayLike,
    metadata: SpatialArrayMetadata,
    spec: SpatialNetworkSpec | None = None,
    *,
    valid: ArrayLike | None = None,
    covariates: ArrayLike | None = None,
    covariate_names: tuple[str, ...] | list[str] | None = None,
) -> SpatialNetworkResult:
    """Estimate every declared site pair without treating edges as replicates."""
    spec = spec or SpatialNetworkSpec()
    time_values, signal_values, valid_values = _validate_array_input(
        time, values, valid, len(metadata.channels)
    )
    coordinates = _coordinate_matrix(metadata)
    edges: list[SpatialNetworkEdge] = []
    exclusions: list[SpatialNetworkEdgeExclusion] = []
    for first_index, second_index in combinations(range(len(metadata.channels)), 2):
        first = metadata.channels[first_index]
        second = metadata.channels[second_index]
        pair_id = f"{metadata.array_id}:{first.channel_id}__{second.channel_id}"
        distance = float(
            np.linalg.norm(coordinates[first_index] - coordinates[second_index])
        )
        pair = SignalPairMetadata(
            subject=metadata.subject,
            session=metadata.session,
            pair_id=pair_id,
            first=first,
            second=second,
            clock_id=metadata.clock_id,
            alignment_policy=metadata.alignment_policy,
            preprocessing_fingerprint=metadata.preprocessing_fingerprint,
        )
        try:
            result = lagged_association(
                time_values,
                signal_values[:, first_index],
                signal_values[:, second_index],
                pair,
                spec.association,
                valid_first=valid_values[:, first_index],
                valid_second=valid_values[:, second_index],
                covariates=covariates,
                covariate_names=covariate_names,
            )
        except ValueError as error:
            exclusions.append(
                SpatialNetworkEdgeExclusion(
                    pair_id,
                    first.channel_id,
                    second.channel_id,
                    distance,
                    f"pair_analysis_failed:{error}",
                )
            )
            continue
        if spec.edge_metric == "zero_lag_correlation":
            index = int(np.argmin(np.abs(np.asarray(result.lags_s))))
            value = float(result.correlation[index])
            support = result.pairs_per_lag[index]
            pvalue = (
                result.blocked_permutation.zero_lag_pvalue
                if result.blocked_permutation is not None
                else None
            )
        else:
            index = int(
                np.argmin(np.abs(np.asarray(result.lags_s) - result.peak_lag_s))
            )
            value = result.peak_correlation
            support = result.pairs_per_lag[index]
            pvalue = (
                result.blocked_permutation.maximum_absolute_pvalue
                if result.blocked_permutation is not None
                else None
            )
        if not np.isfinite(value):
            reason = "edge_metric_is_not_finite"
        elif support < spec.minimum_edge_support:
            reason = "below_minimum_edge_support"
        else:
            reason = None
        if reason is not None:
            exclusions.append(
                SpatialNetworkEdgeExclusion(
                    pair_id,
                    first.channel_id,
                    second.channel_id,
                    distance,
                    reason,
                )
            )
            continue
        edges.append(
            SpatialNetworkEdge(
                pair_id=pair_id,
                first_channel_id=first.channel_id,
                second_channel_id=second.channel_id,
                first_site=first.site,
                second_site=second.site,
                distance=distance,
                distance_unit=metadata.coordinate_unit,
                coordinate_space=metadata.coordinate_space,
                metric=spec.edge_metric,
                value=value,
                transformed_value=_transform(value, spec.correlation_scale),
                support=support,
                peak_lag_s=result.peak_lag_s,
                continuity_run_count=len(result.evidence.continuity.runs),
                joint_valid_sample_count=result.evidence.joint_valid_sample_count,
                gap_count=result.evidence.continuity.gap_count,
                within_session_pvalue=pvalue,
                source_method=result.method,
            )
        )
    summaries = _distance_summaries(edges, spec, metadata.coordinate_unit)
    global_association = _association_summary(edges, spec.correlation_scale)
    spatial_null = (
        _spatial_node_null(edges, metadata, coordinates, spec)
        if spec.node_permutation is not None
        else None
    )
    fingerprint = _fingerprint(
        time_values,
        signal_values,
        valid_values,
        metadata,
        spec,
        covariates,
        covariate_names,
    )
    candidate_count = len(metadata.channels) * (len(metadata.channels) - 1) // 2
    return SpatialNetworkResult(
        metadata=metadata,
        spec=spec,
        edges=tuple(edges),
        exclusions=tuple(exclusions),
        distance_summaries=tuple(summaries),
        global_association=global_association,
        spatial_null=spatial_null,
        candidate_edge_count=candidate_count,
        retained_edge_count=len(edges),
        evidence_fingerprint=fingerprint,
    )


def infer_spatial_network_animals(
    sessions: tuple[SpatialStudySession, ...] | list[SpatialStudySession],
    spec: SpatialAnimalInferenceSpec,
) -> SpatialAnimalInferenceResult:
    """Contrast network summaries after edges→sessions→mice aggregation."""
    if not sessions:
        raise ValueError("spatial inference requires at least one session")
    selected_list: list[SpatialSessionEstimate] = []
    exclusions: list[SpatialSessionExclusion] = []
    for item in sessions:
        session_estimate, reason = _session_estimate(item, spec)
        if session_estimate is not None:
            selected_list.append(session_estimate)
        elif reason is not None:
            result = item.result
            exclusions.append(
                SpatialSessionExclusion(
                    subject=result.metadata.subject,
                    session=result.metadata.session,
                    condition=item.condition,
                    array_id=result.metadata.array_id,
                    metric=spec.metric,
                    reason=reason,
                )
            )
    selected = tuple(selected_list)
    identities = [(item.subject, item.session, item.condition) for item in selected]
    if len(set(identities)) != len(identities):
        raise ValueError("spatial subject-session-condition identities must be unique")
    animals = _animal_estimates(selected, spec)
    first = {
        item.subject: item for item in animals if item.condition == spec.condition_a
    }
    second = {
        item.subject: item for item in animals if item.condition == spec.condition_b
    }
    all_subjects = {item.result.metadata.subject for item in sessions}
    if spec.design == "paired":
        included = tuple(sorted(first.keys() & second.keys()))
        if len(included) < 2:
            raise ValueError("paired spatial inference requires two complete mice")
        animals_a = animals_b = included
        values_a = np.asarray([first[subject].value for subject in included])
        values_b = np.asarray([second[subject].value for subject in included])
        excluded = tuple(sorted(all_subjects - set(included)))
    else:
        overlap = first.keys() & second.keys()
        if overlap:
            raise ValueError(
                "independent spatial inference cannot reuse mice across conditions"
            )
        if len(first) < 2 or len(second) < 2:
            raise ValueError(
                "independent spatial inference requires two mice per condition"
            )
        animals_a = tuple(sorted(first))
        animals_b = tuple(sorted(second))
        values_a = np.asarray([first[subject].value for subject in animals_a])
        values_b = np.asarray([second[subject].value for subject in animals_b])
        excluded = tuple(sorted(all_subjects - set(animals_a) - set(animals_b)))
    estimate = float(
        np.mean(values_b - values_a)
        if spec.design == "paired"
        else np.mean(values_b) - np.mean(values_a)
    )
    rng = np.random.default_rng(spec.seed)
    bootstrap = _bootstrap(values_a, values_b, spec, rng)
    alpha = 1 - spec.confidence_level
    bounds: NDArray[np.float64] = np.asarray(
        np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2]), dtype=float
    )
    null, actual = _randomization(values_a, values_b, spec, rng)
    pvalue = float(
        (1 + np.count_nonzero(np.abs(null) >= abs(estimate))) / (len(null) + 1)
    )
    return SpatialAnimalInferenceResult(
        spec=spec,
        session_estimates=selected,
        session_exclusions=tuple(exclusions),
        animal_estimates=tuple(animals),
        estimate=estimate,
        interval_low=float(bounds[0]),
        interval_high=float(bounds[1]),
        permutation_pvalue=pvalue,
        animals_a=animals_a,
        animals_b=animals_b,
        excluded_subjects=excluded,
        permutation_resamples=actual,
    )


def _validate_array_input(
    time: ArrayLike,
    values: ArrayLike,
    valid: ArrayLike | None,
    channel_count: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    time_values = np.asarray(time, dtype=float)
    signal_values = np.asarray(values, dtype=float)
    if time_values.ndim != 1 or len(time_values) < 3:
        raise ValueError("spatial array time must contain three or more samples")
    if not np.all(np.isfinite(time_values)) or not np.all(np.diff(time_values) > 0):
        raise ValueError("spatial array time must be finite and strictly increasing")
    if signal_values.shape != (len(time_values), channel_count):
        raise ValueError("spatial array values must be time by declared channel")
    if valid is None:
        valid_values = np.ones(signal_values.shape, dtype=bool)
    else:
        valid_values = np.asarray(valid, dtype=bool)
        if valid_values.shape != signal_values.shape:
            raise ValueError("spatial array validity must match values")
    valid_values &= np.isfinite(signal_values)
    return time_values, signal_values, valid_values


def _coordinate_matrix(metadata: SpatialArrayMetadata) -> NDArray[np.float64]:
    output = []
    for channel in metadata.channels:
        coordinate = channel.coordinate
        assert coordinate is not None
        output.append((coordinate.x, coordinate.y, coordinate.z))
    return np.asarray(output, dtype=float)


def _transform(value: float, scale: CorrelationScale) -> float:
    if scale == "raw":
        return value
    clipped = np.clip(value, -1 + 1e-7, 1 - 1e-7)
    return float(np.arctanh(clipped))


def _inverse_transform(value: float, scale: CorrelationScale) -> float:
    return value if scale == "raw" else float(np.tanh(value))


def _association_summary(
    edges: list[SpatialNetworkEdge] | tuple[SpatialNetworkEdge, ...],
    scale: CorrelationScale,
) -> float | None:
    if not edges:
        return None
    transformed = np.asarray([edge.transformed_value for edge in edges])
    return _inverse_transform(float(np.mean(transformed)), scale)


def _distance_summaries(
    edges: list[SpatialNetworkEdge],
    spec: SpatialNetworkSpec,
    unit: str,
) -> list[SpatialDistanceSummary]:
    output = []
    for distance_bin in spec.distance_bins:
        selected = [edge for edge in edges if distance_bin.contains(edge.distance)]
        if not selected:
            continue
        association = _association_summary(selected, spec.correlation_scale)
        assert association is not None
        output.append(
            SpatialDistanceSummary(
                bin_name=distance_bin.name,
                minimum_distance=distance_bin.minimum_distance,
                maximum_distance=distance_bin.maximum_distance,
                distance_unit=unit,
                association=association,
                edge_count=len(selected),
                total_support=sum(edge.support for edge in selected),
                correlation_scale=spec.correlation_scale,
            )
        )
    return output


def _spatial_node_null(
    edges: list[SpatialNetworkEdge],
    metadata: SpatialArrayMetadata,
    coordinates: NDArray[np.float64],
    spec: SpatialNetworkSpec,
) -> SpatialNodePermutationResult:
    permutation = spec.node_permutation
    assert permutation is not None
    statistic_name = "distance_transformed_edge_pearson_correlation"
    node_count = len(metadata.channels)
    group_size = factorial(node_count)
    exhaustive = group_size <= min(permutation.resamples, _MAXIMUM_EXACT_PERMUTATIONS)
    attempted = group_size if exhaustive else permutation.resamples
    if len(edges) < 3:
        return SpatialNodePermutationResult(
            performed=False,
            statistic=statistic_name,
            observed_value=None,
            pvalue=None,
            resamples=permutation.resamples,
            seed=permutation.seed,
            edge_count=len(edges),
            exclusion_reason="fewer_than_three_retained_edges",
            permutation_group_size=group_size,
            exhaustive=exhaustive,
            effective_resamples=0,
            undefined_resamples=0,
            pvalue_resolution=None,
        )
    values = np.asarray([edge.transformed_value for edge in edges])
    distances = np.asarray([edge.distance for edge in edges])
    observed = _safe_correlation(distances, values)
    if observed is None:
        return SpatialNodePermutationResult(
            performed=False,
            statistic=statistic_name,
            observed_value=None,
            pvalue=None,
            resamples=permutation.resamples,
            seed=permutation.seed,
            edge_count=len(edges),
            exclusion_reason="constant_distance_or_edge_values",
            permutation_group_size=group_size,
            exhaustive=exhaustive,
            effective_resamples=0,
            undefined_resamples=0,
            pvalue_resolution=None,
        )
    lookup = {
        channel.channel_id: index for index, channel in enumerate(metadata.channels)
    }
    pairs = [
        (lookup[edge.first_channel_id], lookup[edge.second_channel_id])
        for edge in edges
    ]
    rng = np.random.default_rng(permutation.seed)
    labelings = (
        (np.asarray(item) for item in permutations(range(node_count)))
        if exhaustive
        else (rng.permutation(node_count) for _ in range(permutation.resamples))
    )
    defined: list[float] = []
    for labels in labelings:
        permuted_distances = np.asarray(
            [
                np.linalg.norm(coordinates[labels[first]] - coordinates[labels[second]])
                for first, second in pairs
            ]
        )
        value = _safe_correlation(permuted_distances, values)
        if value is not None:
            defined.append(value)
    undefined = attempted - len(defined)
    if len(defined) < max(2, (attempted + 1) // 2):
        raise ValueError(
            f"spatial node permutation null is undefined for {undefined} of "
            f"{attempted} permutations, leaving {len(defined)} usable draws; "
            "the retained edge geometry cannot support a randomization p-value"
        )
    null = np.asarray(defined)
    pvalue = float(
        (1 + np.count_nonzero(np.abs(null) >= abs(observed))) / (len(null) + 1)
    )
    return SpatialNodePermutationResult(
        performed=True,
        statistic=statistic_name,
        observed_value=observed,
        pvalue=pvalue,
        resamples=permutation.resamples,
        seed=permutation.seed,
        edge_count=len(edges),
        exclusion_reason=None,
        permutation_group_size=group_size,
        exhaustive=exhaustive,
        effective_resamples=len(null),
        undefined_resamples=undefined,
        pvalue_resolution=1 / (len(null) + 1),
    )


def _safe_correlation(
    first: NDArray[np.float64], second: NDArray[np.float64]
) -> float | None:
    if np.std(first) <= np.finfo(float).eps or np.std(second) <= np.finfo(float).eps:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _session_estimate(
    session: SpatialStudySession, spec: SpatialAnimalInferenceSpec
) -> tuple[SpatialSessionEstimate | None, str | None]:
    if session.condition not in {spec.condition_a, spec.condition_b}:
        return None, None
    result = session.result
    if spec.metric == "global_association":
        value = result.global_association
        selected_edges = result.edges
    elif spec.metric == "distance_bin_association":
        summaries = [
            item
            for item in result.distance_summaries
            if item.bin_name == spec.distance_bin_name
        ]
        if len(summaries) != 1:
            return None, "distance_bin_unavailable"
        value = summaries[0].association
        selected_edges = tuple(
            edge
            for edge in result.edges
            if summaries[0].minimum_distance
            <= edge.distance
            < summaries[0].maximum_distance
        )
    elif spec.metric == "distance_edge_correlation":
        if result.spatial_null is None or not result.spatial_null.performed:
            reason = (
                "spatial_null_not_requested"
                if result.spatial_null is None
                else f"spatial_null_unavailable:{result.spatial_null.exclusion_reason}"
            )
            return None, reason
        value = result.spatial_null.observed_value
        selected_edges = result.edges
    else:
        selected_edges = tuple(
            edge
            for edge in result.edges
            if edge.first_site == spec.site or edge.second_site == spec.site
        )
        value = _association_summary(selected_edges, result.spec.correlation_scale)
    if value is None or not selected_edges:
        return None, "requested_metric_has_no_retained_edges"
    return (
        SpatialSessionEstimate(
            subject=result.metadata.subject,
            session=result.metadata.session,
            condition=session.condition,
            array_id=result.metadata.array_id,
            metric=spec.metric,
            value=float(value),
            edge_count=len(selected_edges),
            total_support=sum(edge.support for edge in selected_edges),
        ),
        None,
    )


def _animal_estimates(
    sessions: tuple[SpatialSessionEstimate, ...], spec: SpatialAnimalInferenceSpec
) -> list[SpatialAnimalEstimate]:
    grouped: dict[tuple[str, str], list[SpatialSessionEstimate]] = {}
    for item in sessions:
        grouped.setdefault((item.subject, item.condition), []).append(item)
    output = []
    for (subject, condition), items in sorted(grouped.items()):
        values = np.asarray([item.value for item in items])
        value = (
            float(np.mean(values))
            if spec.session_aggregation == "mean"
            else float(np.median(values))
        )
        output.append(
            SpatialAnimalEstimate(
                subject=subject,
                condition=condition,
                metric=spec.metric,
                value=value,
                session_count=len(items),
                edge_count=sum(item.edge_count for item in items),
                total_support=sum(item.total_support for item in items),
            )
        )
    return output


def _bootstrap(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: SpatialAnimalInferenceSpec,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    output = np.empty(spec.bootstrap_resamples)
    for index in range(spec.bootstrap_resamples):
        if spec.design == "paired":
            selected = rng.integers(0, len(first), len(first))
            output[index] = np.mean(second[selected] - first[selected])
        else:
            sample_a = rng.choice(first, len(first), replace=True)
            sample_b = rng.choice(second, len(second), replace=True)
            output[index] = np.mean(sample_b) - np.mean(sample_a)
    return output


def _randomization(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: SpatialAnimalInferenceSpec,
    rng: np.random.Generator,
) -> tuple[NDArray[np.float64], int]:
    if spec.design == "paired":
        differences = second - first
        if (
            len(differences) <= 16
            and 2 ** len(differences) <= spec.permutation_resamples
        ):
            signs = np.asarray(list(product((-1.0, 1.0), repeat=len(differences))))
        else:
            signs = rng.choice(
                np.asarray([-1.0, 1.0]),
                size=(spec.permutation_resamples, len(differences)),
            )
        return np.mean(signs * differences, axis=1), len(signs)
    combined = np.concatenate((first, second))
    output = np.empty(spec.permutation_resamples)
    for index in range(spec.permutation_resamples):
        shuffled = rng.permutation(combined)
        output[index] = np.mean(shuffled[len(first) :]) - np.mean(
            shuffled[: len(first)]
        )
    return output, len(output)


def _fingerprint(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    valid: NDArray[np.bool_],
    metadata: SpatialArrayMetadata,
    spec: SpatialNetworkSpec,
    covariates: ArrayLike | None,
    covariate_names: tuple[str, ...] | list[str] | None,
) -> str:
    digest = hashlib.sha256()
    for array in (time.astype("<f8"), values.astype("<f8"), valid.astype("u1")):
        digest.update(array.tobytes())
    covariate_values = (
        None if covariates is None else np.asarray(covariates, dtype=float)
    )
    if covariate_values is not None:
        digest.update(covariate_values.astype("<f8").tobytes())
    digest.update(
        json.dumps(
            {
                "metadata": asdict(metadata),
                "spec": asdict(spec),
                "covariate_names": None
                if covariate_names is None
                else list(covariate_names),
            },
            sort_keys=True,
        ).encode()
    )
    return f"sha256:{digest.hexdigest()}"
