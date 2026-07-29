# Separate overlapping cue and reward responses

## Question

Can a model recover distinct cue and reward kernels when their responses overlap,
while accounting for a continuous motion correlate and testing generalization to
animals it did not see during fitting?

This simulation is deliberately identifiable: eight animals each contribute two
sessions; cues precede rewards by 0.5–0.6 seconds; a known motion term affects the
response; and noise is seeded. It is a regression test of implementation behavior,
not biological validation.

## Run it

From the repository root:

```bash
uv run python examples/event_kernel_encoding.py
```

The complete executable source is
[`examples/event_kernel_encoding.py`](https://github.com/aeronjl/fipha/blob/main/examples/event_kernel_encoding.py).
Its essential model declaration is:

```python
spec = EncodingModelSpec(
    event_kernels=(
        EventKernelSpec("cue", (-0.1, 0.3)),
        EventKernelSpec("reward", (0.0, 0.3)),
    ),
    continuous_covariates=("motion",),
    alpha_grid=(0.0, 0.1, 1.0, 10.0),
    group_by="animal",
    folds=4,
)
result = fit_event_kernel_model(sessions, spec)
```

The command writes `event-kernel-result.json`. The artifact contains the selected
penalty, all candidate-penalty fold scores, exact held-out animal identities,
estimated lag coordinates and coefficients, continuous-covariate scaling, and
sample/session/animal counts. Its validity report also records the complete-case
policy, coverage thresholds, total/retained/excluded denominators, and per-session
exclusion evidence. This planted example has no exclusions; real behavior-aligned
models should inspect that report before interpreting coefficients.

## What success means

The automated fixture requires recovery of both planted kernels within 0.04
response units, recovery of the motion coefficient, animal-held-out mean
\(R^2 > 0.8\), and exactly-once allocation of all eight animals to folds.

This establishes numerical recovery under known assumptions. It does **not** show
that a Gaussian linear model is sufficient for real photometry, that motion is
fully controlled, or that coefficients are causal. Read the
[method contract](../event-kernel-encoding.md) before adapting it to data.
