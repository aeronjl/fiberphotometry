# Behavioral event-kernel encoding

*Applies to v0.1.*

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/event-kernel-validation.svg" alt="A cue and reward response overlap in time, model fitting retains complete animal trajectories, and a final comparison shows strong training performance but weaker held-out performance.">
  <figcaption><strong>Kernel shape is not enough.</strong> Joint encoding must separate overlapping events and then demonstrate transport to complete held-out animals or sessions.</figcaption>
</figure>

!!! warning "Experimental"
    This is a first vertical slice, not yet a supported inferential workflow. It
    estimates predictive kernels and validates predictions across held-out animals
    or sessions. Grouped-jackknife intervals and the explicitly opt-in simultaneous
    candidate are conditional sensitivity summaries, not promotion-grade confidence
    bands or causal effects.

## Scientific question

How much of a continuously sampled, already-corrected photometry signal is
predictable from overlapping task events and continuous behavioral measurements?

The model is a Gaussian finite-impulse-response (FIR) encoding model:

\[
y(t) = \beta_0 + \sum_e \sum_{\ell \in L_e}
x_e(t-\ell)\beta_{e,\ell} + \sum_c z_c(t)\gamma_c + \epsilon(t).
\]

Each event type has its own declared lag window. Overlapping cue, action, reward,
and omission responses are estimated jointly rather than assigned to separate
peri-event averages. Continuous predictors such as motion are standardized using
training data only. Ridge strength is selected by mean group-wise held-out
\(R^2\), with complete animals or complete sessions kept together.

## Kernel bases

The default `FIRBasisSpec` estimates one unconstrained coefficient per sampled lag,
preserving the original behavior. A lower-dimensional smooth alternative is
explicit:

```python
from fiberphotometry.encoding import EventKernelSpec, RaisedCosineBasisSpec

cue = EventKernelSpec(
    "cue",
    (-1.0, 3.0),
    basis=RaisedCosineBasisSpec(functions=8),
)
```

Raised-cosine functions are linearly spaced across the sampled window and
row-normalized. Their count must not exceed the number of sampled lags, and the
resulting basis must have full column rank. This is a shape assumption and should
be declared as an alternative, not adopted after inspecting a noisy FIR curve.

Fitting occurs in basis space. Every result nevertheless reports the reconstructed
kernel and grouped-jackknife interval on the original lag grid in seconds. It also
stores the basis family, component labels, fitted basis weights and sampled basis
functions. Thus plots remain physically interpretable while the exact fitted
parameterization is reproducible.

## Event values and within-session history

A second kernel can reuse an event train while being multiplied by a declared
per-event value. Setting `lag_events=1` makes that value come from the immediately
previous occurrence within the same session:

```python
from fiberphotometry.encoding import EventKernelSpec, EventModulationSpec

history = EventKernelSpec(
    "cue-by-previous-outcome",
    (-1.0, 3.0),
    source_event="cue",
    modulation=EventModulationSpec(
        value="outcome_code",
        lag_events=1,
        unavailable_value=0.0,
    ),
)
```

The session supplies one finite `outcome_code` per cue through `event_values`.
History resets at recording boundaries and lagged events must be strictly ordered.
FiberPhotometry neither guesses categorical coding nor standardizes these values;
zero must therefore have the intended meaning. Include the unmodulated cue kernel
to interpret the history kernel as a conditional difference around that reference.
Use lag zero for a declared current-event amplitude or duration.

## Variable-duration behavior

`ProgressKernelSpec` models the trajectory within a physical interval without
discarding the rest of the recording. A piecewise-linear basis maps samples inside
each bout to normalized progress; all progress columns are zero outside bouts.

```python
from fiberphotometry.encoding import LinearProgressBasisSpec, ProgressKernelSpec

rear_progress = ProgressKernelSpec(
    "rear-progress",
    source_interval="rear",
    basis=LinearProgressBasisSpec(functions=5),
)
```

The result reconstructs the trajectory and grouped uncertainty on an explicit
progress grid from zero to one while retaining the physical interval source and
bout count. `BehaviorAnnotations.interval_encoding_inputs()` provides aligned
edge events, `duration_s` values, and interval bounds from MoSeq or BORIS inputs.
Onset/offset kernels, duration-modulated kernels, and progress kernels remain
separate declared predictors and should be compared as named alternatives.

This follows the behavioral-regression use case discussed in the
[fiber-photometry analysis primer](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/)
and the multi-signal Gaussian GLM presented in the
[COSYNE 2024 programme, abstract 2-005](https://www.cosyne.org/s/Cosyne2024_program_book.pdf).
Those examples motivate the model family; they do not validate this implementation.

## Inputs and estimand

- One regular time grid and corrected response per session.
- Explicit event times, with a lag window declared for each event type.
- Optional continuous covariates sampled on the response grid.
- Optional physical interval bounds for normalized-progress kernels.
- Optional boolean validity masks for the response and each continuous covariate.
- Stable animal and session identities.

An event coefficient is the conditional response-unit change for one event impulse
at that lag, holding the other declared predictors fixed. A continuous coefficient
is the conditional response-unit change per one training-set standard deviation.
The held-out score is predictive performance, not evidence that a predictor caused
the fluorescence response.

## Safeguards

- FIR matrices are built independently within sessions; convolution never crosses
  a recording boundary.
- Cross-validation holds out complete biological groups.
- Continuous scaling is learned in each training fold and applied unchanged to its
  held-out groups.
- Irregular grids are rejected. Resampling must be an explicit earlier operation.
- Response and selected-covariate masks are combined by an explicit complete-case
  policy. No value is imputed and retained timestamps are never compressed.
- Every session must retain at least 50% and three observations by default;
  both thresholds are configurable and recorded in the result.
- The result reports total, retained and excluded observations, response and
  per-covariate invalid counts, and the number of contiguous retained runs for
  every session.
- Missing predictors, absent event types, duplicate animal/session identities, and
  constant training covariates fail loudly.
- Event kernels fail if masking removes all retained support for any requested lag.
- Progress kernels reject missing, out-of-recording, unordered, overlapping, or
  unsupported interval families; outside-bout time remains retained.
- Every tested ridge penalty and every fold score is retained in the result.
- Delete-one-group kernel refits use the selected penalty unchanged and retain
  every omitted identity.
- Residual diagnostics use only group-held-out predictions; lagged calculations
  restart at session boundaries and on both sides of every excluded span.

## Missingness and coverage

Validity is evidence, not a preprocessing nuisance. `response_valid` and
`continuous_covariate_validity` preserve explicit upstream decisions such as
pose-confidence gates, occlusions, stimulation-artifact windows or unavailable
response samples. Non-finite values are invalid regardless of the supplied mask.
Only covariates named in the model specification contribute to its complete-case
mask.

The result artifact schema v7 contains an `EncodingValidityReport`. Its per-session
records make the model denominator auditable and distinguish invalid response
samples from invalid samples for each selected covariate. Counts can overlap: the
overall excluded count is the union, not the sum of reason counts. Each record also
contains a fingerprint of the exact retained sample indices so robustness workflows
can distinguish equal counts from genuinely identical denominators.

Complete-case fitting is deliberately conservative and does not claim that data
are missing completely at random. If missingness relates to behavior or signal
amplitude, the fitted estimand may describe a selected subset of time. Scientists
should compare retained coverage across animals and conditions and treat large or
structured exclusions as a design problem. The coverage floor is a fail-fast
guardrail, not a universal scientific adequacy threshold.

## Uncertainty and diagnostics

Each event kernel includes a delete-one-group jackknife sensitivity interval. By
default, one complete animal is removed per replicate. The result stores the
full-data coefficient, bias-corrected jackknife estimate, standard error, and
pointwise 95% Student interval at every lag. These intervals quantify sensitivity
of the pooled regularized estimator to independent groups.

They are conditional on the ridge penalty selected using the full dataset. They do
not account for model-selection uncertainty and are not simultaneous across lags.
The first frozen calibration found 93.8–96.0% marginal pointwise coverage but much
lower whole-family coverage, as expected. With few animals, interpret them as
influence-aware sensitivity summaries rather than binary tests.

An explicitly typed `MultiplierSimultaneousBandSpec` asks for one seeded max-*t*
critical value across every evaluated position from every kernel in the model. It
is not the default: the
[480-study calibration](event-kernel-interval-calibration.md) missed its
frozen normalized-progress gate (82.5% versus an 85% minimum). Candidate results
retain method, seed, draw count, family size, critical value and nullable
simultaneous bounds. `KernelUncertaintySpec` remains pointwise-only.

For every animal or session, the model also reports out-of-fold R², RMSE, MAE,
residual bias and spread, lag-1 residual autocorrelation, and Durbin–Watson ratio.
The latter two are descriptive warnings about remaining temporal structure, not
formal p-value-producing tests.

## Current limitations

The response must already have undergone a scientifically defensible correction;
the encoding model does not decide between isosbestic, regression, or control-free
preprocessing. Autocorrelated residuals make ordinary sample-level standard errors
unsafe; the grouped jackknife does not repair a misspecified temporal model. The
workflow still lacks a fully calibrated simultaneous kernel band, selective
inference, nonlinear terms, nested hyperparameter selection,
blocked-within-session validation, and missingness-mechanism models or imputation.

The first [public-data reproduction](tutorials/dandi-000971-event-kernel.md)
retained slightly negative mean animal-held-out prediction in both modeled regions
and selected the largest declared ridge penalty. This validates execution and
failure transparency, not scientific sufficiency. Its v0.2 rerun found substantial
held-out residual autocorrelation and wide group-sensitivity intervals. Named
model multiverses and paired
[predictor-family contribution summaries](predictor-family-contributions.md)
now cover explicit design comparisons. Promotion priorities are nested or
independently frozen penalty selection, blocked validation where scientifically
appropriate, and a new interval protocol after the retained v0.1 progress-kernel
failure.

See the [worked simulation](tutorials/event-kernel-simulation.md) and the
[model-multiverse workflow](event-kernel-multiverse.md).
