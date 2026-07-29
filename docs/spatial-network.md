# Coordinate-aware dense multi-fiber networks

*Applies to v0.1.*

Use this experimental workflow when three or more simultaneously sampled
photometry channels have physical or atlas coordinates and the question concerns
the spatial organization of their association. It extends the guarded
[pairwise workflow](multisite-multicolor-analysis.md); it does not turn fibers
or edges into independent experimental units.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/spatial-network-contract.svg" alt="A four-fiber coordinate map is converted to gap-aware pairwise edges, summarized by physical-distance bins and a node-label spatial null, then reduced from edges to sessions and equally weighted mouse summaries before a condition contrast.">
  <figcaption><strong>Geometry is evidence, not replication.</strong> Every edge retains its joint-validity denominator. Spatial structure is tested within a session by permuting coordinates across nodes; condition inference proceeds through session summaries to one value per mouse and condition.</figcaption>
</figure>

## Declare one array

Every channel requires a unique ID and a `SpatialCoordinate`. Coordinates must
share both a unit and a named space; millimetres in implant space cannot silently
mix with micrometres in an atlas space.

```python
from fipha.multisignal import ChannelIdentity, SpatialCoordinate
from fipha.spatial_network import SpatialArrayMetadata

channels = tuple(
    ChannelIdentity(
        channel_id=f"fiber-{index}",
        site=site,
        sensor="dLight1.3b",
        role="sensor",
        unit="dF/F",
        fiber_id=f"fiber-{index}",
        coordinate=SpatialCoordinate(x, y, z, unit="um", space="CCF"),
    )
    for index, (site, x, y, z) in enumerate(
        (
            ("DMS-a", 1120, 760, -3180),
            ("DMS-b", 1280, 780, -3200),
            ("NAc-a", 980, 1280, -4020),
            ("NAc-b", 1140, 1300, -4000),
        )
    )
)

metadata = SpatialArrayMetadata(
    subject="mouse-01",
    session="day-01",
    array_id="implant-01",
    channels=channels,
    clock_id="photometry-clock",
    alignment_policy="native_shared_clock",
    preprocessing_fingerprint="sha256:...",
)
```

At least three channels are required because the spatial statistic needs more
than a single pair. The API accepts a single shared timestamp vector and a
time-by-channel value matrix. Use matched-pulse synchronization and explicit
resampling before this boundary when acquisition clocks differ.

## Estimate the session network

```python
from fipha.multisignal import LaggedAssociationSpec
from fipha.spatial_network import (
    SpatialDistanceBin,
    SpatialNetworkSpec,
    SpatialNodePermutationSpec,
    estimate_spatial_network,
)

network = estimate_spatial_network(
    time_s,
    signals,  # time × channel, in metadata channel order
    metadata,
    SpatialNetworkSpec(
        association=LaggedAssociationSpec(
            maximum_lag_s=1.0,
            minimum_pairs_per_lag=100,
        ),
        edge_metric="zero_lag_correlation",
        correlation_scale="fisher_z",
        minimum_edge_support=100,
        distance_bins=(
            SpatialDistanceBin("local", 0, 250),
            SpatialDistanceBin("intermediate", 250, 750),
            SpatialDistanceBin("long", 750, 1500),
        ),
        node_permutation=SpatialNodePermutationSpec(
            resamples=5000,
            seed=2026,
        ),
    ),
    valid=channel_valid,  # optional time × channel mask
    covariates=behavior_design,
    covariate_names=("movement", "reward_kernel"),
)
```

The function materializes every declared pair through `lagged_association`.
Consequently, each edge inherits the same protections as the pairwise API:

- timestamp gaps and invalid samples split continuity runs rather than being
  compressed away;
- a sample contributes only when both channels and all declared covariates are
  valid;
- residualization is fit separately within each continuity run;
- support is retained per lag; and
- optional blocked pairwise nulls remain labeled as within-session sensitivity
  analyses.

The default edge is zero-lag correlation. `peak_absolute_correlation` instead
selects the tested lag with the largest absolute correlation while retaining its
sign and lag. This is association, not directionality or causal connectivity.

## Read the network artifact

`SpatialNetworkResult` contains a complete candidate-edge ledger:

- `edges` records sites, distance, raw and Fisher-transformed values, support,
  peak lag, continuity runs, gaps and any pairwise-null probability;
- `exclusions` records failed pairs, non-finite estimates and insufficient
  support rather than silently shrinking the network;
- `distance_summaries` reports the unweighted mean edge association within each
  declared physical-distance bin;
- `global_association` summarizes all retained edges; and
- `evidence_fingerprint` binds values, masks, geometry, specifications and
  covariate names.

Correlation averaging defaults to Fisher's z scale and returns to correlation
units for reporting. Edges are not weighted by their sample count: support is a
quality denominator, not permission for a long recording or highly sampled pair
to define the biological estimand.

## Test spatial organization within a session

The node-label null asks whether edge association is related to physical distance
more strongly than expected if the observed signals occupied different declared
coordinates. Each draw permutes coordinates across nodes, recomputes all retained
edge distances, and records the Pearson correlation between distance and
transformed edge association.

This preserves the observed signals and network topology. It does not preserve
arbitrary anatomical strata, hemispheres or probe-layout constraints. When those
exchangeability restrictions matter, omit `node_permutation` and treat a custom
restricted null as an extension; an unrestricted p-value would be misleading.
Arrays with too few retained edges or constant distances/values return a typed
`performed=False` result with an exclusion reason.

## Contrast conditions at the mouse level

```python
from fipha.spatial_network import (
    SpatialAnimalInferenceSpec,
    SpatialStudySession,
    infer_spatial_network_animals,
)

study_sessions = [
    SpatialStudySession(condition=row.condition, result=row.network)
    for row in session_results
]

contrast = infer_spatial_network_animals(
    study_sessions,
    SpatialAnimalInferenceSpec(
        metric="distance_bin_association",
        distance_bin_name="local",
        condition_a="baseline",
        condition_b="drug",
        design="paired",
        session_aggregation="mean",
        bootstrap_resamples=10000,
        permutation_resamples=10000,
        seed=2026,
    ),
)
```

Available scalar estimands are global association, one declared distance bin, the
distance-edge correlation, or the mean strength of edges touching one named site.
The aggregation order is fixed:

1. dependent edges become one session scalar;
2. repeated sessions receive equal weight within each mouse and condition; and
3. bootstrap intervals and randomization tests resample or permute mice.

For paired designs, incomplete mice are listed in `excluded_subjects`. The effect
direction is always condition B minus condition A. Edge count and total temporal
support remain attached to both session and mouse summaries but never determine
the number of experimental units. A requested session that cannot produce the
declared estimand is retained in `session_exclusions` with a typed reason.

## Product boundaries and next validation

This API supports descriptive spatial networks, distance gradients and
mouse-level condition contrasts. It intentionally does not claim:

- effective connectivity, information flow or causal influence;
- automatic crosstalk removal or optical source separation;
- anatomical registration from unlabeled device coordinates;
- graph-theoretic independence among edges; or
- validated performance on every dense-array acquisition system.

Run [crosstalk and shared-control review](multisite-multicolor-analysis.md)
and, when applicable, [wavelength-aware optical unmixing](optical-unmixing.md)
before interpreting high zero-lag structure. Raw-system fixtures with known
geometry, injected shared artifacts and repeated animals remain the important
validation gap.
