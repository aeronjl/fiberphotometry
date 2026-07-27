# Compare plausible event-kernel models

!!! warning "Experimental"
    This workflow compares held-out prediction across manually declared model
    specifications. It does not choose a scientifically correct model, establish
    causal contributions, or yet generate basis/history/duration alternatives.

## Scientific question

Does an event-kernel conclusion depend on a defensible choice of event families,
lag windows, continuous covariates or regularization grid?

A single design matrix hides that question. The encoding multiverse instead fits
named, justified `EncodingModelSpec` alternatives to one fixed session collection
and retains every success or failure. The reference is a declared comparator, not
the presumed truth.

## Declare alternatives before fitting

```python
from fiberphotometry import (
    EncodingModelAlternative,
    EncodingMultiverseSpec,
    run_encoding_multiverse,
)

multiverse = EncodingMultiverseSpec(
    alternatives=(
        EncodingModelAlternative(
            name="cue-only",
            rationale="Minimal task-event reference model.",
            model=cue_only_spec,
        ),
        EncodingModelAlternative(
            name="cue-and-reward",
            rationale="Separate delayed reward responses from cue responses.",
            model=cue_reward_spec,
        ),
        EncodingModelAlternative(
            name="cue-reward-motion",
            rationale="Test whether measured motion adds predictive value.",
            model=cue_reward_motion_spec,
        ),
    ),
    reference="cue-only",
    intent="exploratory",
)
result = run_encoding_multiverse(sessions, multiverse)
```

Names must be unique, rationales non-empty, and complete model specifications
distinct. `materialize_encoding_multiverse()` assigns stable 16-character IDs
from each name and computational specification before any response is fitted.
Editing prose alone does not change computational identity.

All alternatives must share:

- animal-versus-session grouping;
- fold count;
- sampling tolerance; and
- minimum session coverage and observation thresholds.

Changing those fields changes the predictive target or evidence-admission policy
and therefore belongs in a separate multiverse. Event kernels, windows,
continuous predictors and candidate ridge penalties may differ.

## Direct versus descriptive comparison

Each fitted model retains the per-session fingerprint of its exact complete-case
sample indices. A held-out mean \(R^2\) delta is emitted only when an alternative
and the reference used identical retained timestamps under the common validation
policy.

If covariate validity changes the fitted rows, both held-out scores remain visible
but the comparison status is `descriptive_only` and the delta is null. Equal row
counts are insufficient: two models can exclude different moments and therefore
answer different predictive questions.

The summary reports successful, failed, directly comparable and descriptive-only
universe counts plus the directly comparable score range. It does not name a
winner. A higher held-out score can motivate an independently tested model; it
does not establish that a predictor caused the photometry signal.

## Failures remain evidence

Missing events, unsupported lags, insufficient coverage, constant training
covariates and every other fit exception become `failed` universe records with
their error text. They remain in the total declared denominator. A fragile design
cannot improve the summary by disappearing.

If the reference fails, no alternative receives a delta. This preserves the
declared comparison rather than silently promoting another model after outcome
access.

## Run the executable simulation

```bash
uv run python examples/event_kernel_multiverse.py
```

The script compares cue-only, cue-plus-reward and cue/reward/motion models on a
seeded eight-animal simulation. It writes
`event-kernel-multiverse-result.json`, including full fitted model artifacts and
the comparison ledger.

## Current boundary and next extensions

This v0.1 surface enumerates complete model specifications rather than generating
a factorial decision graph. Coefficients at unlike lags or in unlike bases should
not be pooled into one magnitude range. The immediate extensions are typed basis
families, trial-history predictors, variable-duration/progress kernels and
predictor-family contribution summaries. Each must preserve the fixed validation
policy, exact-denominator evidence and retained failures established here.

The general rationale follows the
[multiverse scientific contract](multiverse-contract-v0.1.md). Event-kernel-specific
rules are recorded in
[SDR-0035](decisions/0035-compare-event-kernel-models-only-on-common-evidence.md).
