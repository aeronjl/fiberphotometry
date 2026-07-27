# Behavioral event-kernel encoding

!!! warning "Experimental"
    This is a first vertical slice, not yet a supported inferential workflow. It
    estimates predictive kernels and validates predictions across held-out animals
    or sessions. It does not provide coefficient uncertainty or causal effects.

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

This follows the behavioral-regression use case discussed in the
[fiber-photometry analysis primer](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/)
and the multi-signal Gaussian GLM presented in the
[COSYNE 2024 programme, abstract 2-005](https://www.cosyne.org/s/Cosyne2024_program_book.pdf).
Those examples motivate the model family; they do not validate this implementation.

## Inputs and estimand

- One regular time grid and corrected response per session.
- Explicit event times, with a lag window declared for each event type.
- Optional continuous covariates sampled on the response grid.
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
- Missing predictors, absent event types, duplicate animal/session identities, and
  constant training covariates fail loudly.
- Every tested ridge penalty and every fold score is retained in the result.

## Current limitations

The response must already have undergone a scientifically defensible correction;
the encoding model does not decide between isosbestic, regression, or control-free
preprocessing. Autocorrelated residuals make ordinary pointwise standard errors
unsafe, so this release intentionally omits them. It also lacks interactions,
nonlinear terms, nested hyperparameter selection, blocked-within-session validation,
missing-data imputation, and formal comparison between plausible design matrices.

The first [public-data reproduction](tutorials/dandi-000971-event-kernel.md)
retained slightly negative mean animal-held-out prediction in both modeled regions
and selected the largest declared ridge penalty. This validates execution and
failure transparency, not scientific sufficiency. The next step is animal-level
coefficient uncertainty and residual/model diagnostics, followed by a newly
specified expanded or nested regularization design.

See the [worked simulation](tutorials/event-kernel-simulation.md) and
[SDR-0027](decisions/0027-hold-out-complete-groups-for-event-kernel-models.md).
The promotion decision is recorded in
[SDR-0028](decisions/0028-retain-weak-event-kernel-validation.md).
