# Multi-site and multi-color association

Use this experimental workflow when two processed photometry signals were measured
from different sites, sensors, colors, or cell classes and the question is how they
vary together.

The workflow deliberately separates four claims:

1. the signals have declared identities and a defensible shared clock;
2. optical metadata or shared controls raise contamination concerns;
3. within-session signals show lagged or frequency-specific association; and
4. a scalar association summary differs across animals or conditions.

None of those claims, alone or together, establishes neural communication or
causality.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/multisignal-evidence-contract.svg" alt="Two explicitly identified photometry channels pass through shared-clock and joint-validity checks, then branch to crosstalk review, lagged association, coherence and phase, and animal-level inference.">
  <figcaption><strong>One pair, four evidence layers.</strong> Signal identity and joint continuity come first. Optical review remains distinct from statistical association; session summaries enter animal-level inference only after sessions have been aggregated within animals.</figcaption>
</figure>

## Declare the pair

```python
from fiberphotometry import (
    ChannelIdentity,
    SignalPairMetadata,
    SpatialCoordinate,
)

green = ChannelIdentity(
    channel_id="dms-green",
    site="DMS",
    sensor="dLight1.3b",
    role="sensor",
    unit="dF/F",
    excitation_wavelength_nm=470,
    emission_wavelength_nm=525,
    detector_id="detector-green",
    fiber_id="fiber-dms",
    coordinate=SpatialCoordinate(1200, 800, -3200, space="CCF"),
)

red = ChannelIdentity(
    channel_id="nacc-red",
    site="NAcC",
    sensor="rDA3m",
    role="sensor",
    unit="dF/F",
    excitation_wavelength_nm=560,
    emission_wavelength_nm=600,
    detector_id="detector-red",
    fiber_id="fiber-nacc",
)

pair = SignalPairMetadata(
    subject="mouse-01",
    session="day-01",
    pair_id="dms-green__nacc-red",
    first=green,
    second=red,
    clock_id="photometry-clock",
    alignment_policy="native_shared_clock",
    preprocessing_fingerprint="sha256:...",
)
```

Roles are declared, not inferred from wavelength or row position. Use
`role="unclassified"` when the biological role is genuinely unknown. Optional
coordinates feed the separate
[dense-array spatial workflow](spatial-network-v0.1.md); neither API treats sites
as independent animals.

Every analysis accepts one timestamp vector. `alignment_policy` can be:

- `native_shared_clock` when both values were sampled on the same clock; or
- `explicitly_resampled` after a separately documented synchronization and
  resampling operation.

The functions do not align two clocks implicitly. Use
[matched-pulse clock synchronization](clock-synchronization-v0.1.md) first.

## Joint continuity is the denominator

A paired sample is usable only when both signals, both supplied validity masks,
and every supplied residualization covariate are finite and valid. Invalidity in
either signal splits the pair. Timestamp gaps split both signals together.

`JointContinuityEvidence` records:

- each channel's invalid sample count;
- joint and covariate invalidity;
- jointly valid samples;
- nominal sampling rate and interval variation; and
- the exact continuity runs used downstream.

Irregular clocks are refused under the same
[gap-aware spectral contract](spectral-state-analysis-v0.1.md). No function
compresses time or forms cross-channel pairs across a missing region.

## Lagged association

```python
from fiberphotometry import (
    BlockPermutationSpec,
    LaggedAssociationSpec,
    lagged_association,
)

lagged = lagged_association(
    time_s,
    dms_signal,
    nacc_signal,
    pair,
    LaggedAssociationSpec(
        maximum_lag_s=2.0,
        detrend="constant",
        minimum_pairs_per_lag=100,
        blocked_permutation=BlockPermutationSpec(
            block_duration_s=20.0,
            resamples=2000,
            seed=2026,
        ),
    ),
    valid_first=dms_valid,
    valid_second=nacc_valid,
)
```

The correlation is energy-normalized after detrending each continuity run. A
positive lag means the second signal occurs later than the first. The result keeps
`pairs_per_lag`; support naturally falls at longer lags. `peak_lag_s` is the largest
absolute tested association, not a propagation-time estimate.

The optional blocked null divides each valid run into complete non-overlapping
blocks. It randomly re-pairs first-signal blocks with second-signal blocks and
recomputes associations **within each block only**. This preserves much of each
signal's temporal structure without creating pairs at shuffled block boundaries.
The block duration must exceed twice the requested maximum lag. The result reports
separate null probabilities for zero lag and the maximum absolute lag statistic.

This is a within-session sensitivity analysis. When animals are available, the
animal remains the inferential unit.

## Remove declared shared event or behavior structure

Pass a sample-by-covariate matrix to fit the same named design separately to both
signals within each continuity run:

```python
residualized = lagged_association(
    time_s,
    dms_signal,
    nacc_signal,
    pair,
    LaggedAssociationSpec(maximum_lag_s=2.0),
    covariates=behavior_design,
    covariate_names=(
        "movement_energy",
        "reward_kernel",
        "choice_kernel",
    ),
)
```

Covariates can be continuous behavior traces or explicit event-design columns.
Non-constant columns are standardized within each run; an intercept is always fit.
`ResidualizationEvidence` retains active covariates, design rank, both coefficient
vectors, and variance explained for every run. Optional ridge regularization is
declared through `ResidualizationSpec`.

This answers “does association remain after projecting out this design?” It does
not guarantee confound removal: omitted variables, measurement error, lagged
effects, and collider structures remain possible. For rich event designs, build
the design explicitly rather than residualizing against event timestamps alone.

## Review possible crosstalk and shared drivers

```python
from fiberphotometry import assess_crosstalk

review = assess_crosstalk(
    time_s,
    dms_signal,
    nacc_signal,
    pair,
    shared_control=motion_or_hemodynamic_control,
    control_name="shared-motion-control",
)
```

The review combines declared hardware and wavelength metadata with association
diagnostics. It can flag:

- a shared detector or fiber;
- close excitation or emission wavelengths;
- high zero-lag association or a near-zero peak; and
- strong loading of both signals on a supplied control.

When a control is supplied, the report also fits it to both signals and returns the
control-residualized zero-lag association. The status vocabulary is intentionally
`no_flag` or `review`, never “crosstalk absent.” Thresholds are configurable product
defaults, not universal optical cutoffs. The function does not unmix or correct
signals automatically.

## Coherence and relative phase

```python
from fiberphotometry import (
    SpectralAnalysisSpec,
    coherence_phase,
    summarize_coherence_band,
)

spectral_spec = SpectralAnalysisSpec(
    window_duration_s=20.0,
    overlap_fraction=0.5,
    window="hann",
    detrend="constant",
    maximum_frequency_hz=10.0,
)

cross_spectrum = coherence_phase(
    time_s,
    dms_signal,
    nacc_signal,
    pair,
    spectral_spec,
)

slow_band = summarize_coherence_band(cross_spectrum, (0.5, 2.0))
```

Within each joint continuity run, the implementation estimates both power spectra
and the complex cross-spectrum with the same complete Welch windows. It pools those
spectra in proportion to complete window count before calculating magnitude-squared
coherence. This is different from averaging run-level coherence values.

The returned phase is the angle of `conjugate(FFT(first)) * FFT(second)`. Phase is
unstable where cross-power or coherence is negligible, so interpret it only in a
prospectively meaningful band. `summarize_coherence_band` reports mean band
coherence and the angle of the integrated complex cross-spectrum; frequency bins
are not treated as replicates.

## Condition coherence on supplied states

```python
from fiberphotometry import StateEpoch, state_conditioned_coherence

states = (
    StateEpoch("exploration", 12.0, 48.0, "bout-001"),
    StateEpoch("rest", 55.0, 91.0, "bout-002"),
)

by_state = state_conditioned_coherence(
    time_s,
    dms_signal,
    nacc_signal,
    pair,
    states,
    spectral_spec,
)
```

State labels are user supplied and half-open. Overlap is refused. Separate epochs
remain separate joint continuity runs even when they share a label or touch in
time. FiberPhotometry does not discover behavior states; use the
[behavioral interoperability boundary](ecosystem-interoperability-v0.1.md) and
bring the resulting intervals onto the declared photometry clock.

## Infer across animals

First extract one scalar per session—at a declared lag or across a declared
frequency band—then contrast conditions:

```python
from fiberphotometry import (
    AssociationAnimalInferenceSpec,
    infer_association_animals,
    session_estimate_from_coherence,
)

session_estimates = (
    session_estimate_from_coherence(mouse_01_rest, "rest", (0.5, 2.0)),
    session_estimate_from_coherence(mouse_01_explore, "explore", (0.5, 2.0)),
    # additional sessions and animals
)

inference = infer_association_animals(
    session_estimates,
    AssociationAnimalInferenceSpec(
        metric="mean_coherence_0.5_2Hz",
        pair_id="dms-green__nacc-red",
        condition_a="explore",
        condition_b="rest",
        design="paired",
        seed=2026,
    ),
)
```

For the shared support, influence, simultaneous-band, and group-by-condition
contract, pass the same session estimates to
`materialize_association_population()`. The resulting animal-condition cells can
call `.contrast()` or `.interaction()` while retaining the actual pair/window
support as provenance. See
[population inference across core workflows](population-workflow-adapters-v0.1.md).

For complete lag-association or coherence curves, use the
[population-curve workflow](population-curve-inference-v0.1.md). It retains valid
pairs or complete joint Welch windows at every axis point and provides simultaneous
animal-level uncertainty across the declared lag or frequency range. Population
phase inference is intentionally not implied by this coherence route.

`session_estimate_from_lagged` provides the corresponding physical-lag route and
retains its pair-count support and blocked zero-lag probability when available.

Sessions are aggregated equally within each animal-condition combination. Paired
inference bootstraps complete animals and sign-flips animal differences;
independent inference resamples animals and permutes animal labels. Fibers, sites,
sessions, windows, frequency bins, and time samples never enter as independent
replicates.

## Current limits

- Association and coherence do not identify direction, communication, or causal
  influence.
- Control residualization is conditional on the supplied design and is not spectral
  unmixing or hemodynamic correction.
- Coherence uses Welch windows, not a multitaper estimator.
- Phase uncertainty and animal-level circular inference are not yet implemented.
- Dense arrays can carry coordinates, but spatial covariance and mouse-aware
  multi-site models remain a roadmap item.
- Optogenetic artifact masks and sensor/isobestic validity diagnostics are separate
  upcoming product layers.

The governing rationale is recorded in
[SDR-0046](decisions/0046-require-explicit-pairs-and-shared-evidence-for-multisignal-analysis.md).
