# Public IBL neural–behavioral forecast

!!! warning "Retained negative predictive result"
    The prior session's DMS feedback contrast did not improve prediction in the
    held-out future session. The workflow remains valuable because that result was
    generated under a content-hashed protocol and is not replaced by a more favorable
    lag, window, or model.

## Scientific question

Does the immediately previous session's DMS correct-minus-incorrect feedback
response improve prediction of trial correctness in one future session, beyond a
stationary behavioral model and linear session progress?

The 18-animal public cohort accompanies the longitudinal visual-learning study by
[Pan-Vazquez, Sanchez Araujo et al. (2024)](https://doi.org/10.1016/j.cub.2024.09.045).
The source paper used richer behavioral and neural encoding models. This benchmark is
a narrower product test, not a reproduction of its principal claims.

## Why two packages?

FiberPhotometry loads the 470-nm-only recordings, verifies source checksums, applies
the previously declared rolling divided-dF/F workflow, and calculates one feedback
contrast per session. Its validated handoff retains every trial and attaches the
previous session's neural summary.

Unspool then owns the explicit session clock, within-session correctness history,
cohort-forward split, model fits, audits, animal-balanced scoring, and paired animal
bootstrap. No behavioral trajectory engine is duplicated inside FiberPhotometry.

## Frozen design

- **Animals:** 18.
- **Source sessions accessed:** 216; orders 0–11 for every animal.
- **Training rows:** 95,717 events from session orders 1–10.
- **Held-out rows:** 11,919 events from order 11.
- **Neural predictor:** order *t−1* DMS correct-minus-incorrect feedback response,
  divided by a fixed 0.01 fractional-dF/F scale.
- **Candidates:** stationary; linear session progress; session progress plus lagged
  DMS contrast.
- **Primary metric:** equally animal-weighted future-session log loss.
- **Uncertainty:** 5,000 paired animal-bootstrap draws, seed `20260727`.

Read the [frozen protocol](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-ibl-unspool-longitudinal-v0.1.md)
before interpreting the result.

## Result

<figure class="doc-figure doc-figure--wide">
  <img src="../../assets/ibl-unspool-longitudinal-v0.1.svg" alt="Animal-level future-session log-loss differences between a session-progress model and the same model augmented with the prior session DMS contrast. Differences vary around zero. The 18-animal mean is negative and its bootstrap interval crosses zero, so lagged DMS does not improve prediction.">
  <figcaption><strong>The lagged neural predictor did not improve the declared forecast.</strong> Positive differences favor adding prior-session DMS; the animal-balanced mean was −0.00091 with a paired 95% bootstrap interval from −0.00470 to +0.00226.</figcaption>
</figure>

| Candidate | Animal-balanced log loss | Pooled log loss | Fit audit |
|---|---:|---:|---|
| Session progress | 0.64316 | 0.63434 | pass |
| Session progress + lagged DMS | 0.64407 | 0.63518 | pass |
| Stationary | 0.65437 | 0.64965 | pass |

The session-progress model had the lowest future-session log loss. Adding lagged DMS
worsened animal-balanced log loss by `0.000907` on average. Only 31.82% of paired
animal-bootstrap draws favored the neural model. Session progress improved the point
estimate relative to the stationary model, but its own paired interval also crossed
zero; this one fold is not enough to claim a general learning-curve advantage.

## Interpretation

This does not imply that DMS dopamine is unrelated to learning. The source paper's
neural quantities were side-, contrast-, region-, and kernel-specific; our predictor
is a coarse feedback contrast from a signal-only preprocessing lane. A one-session
lag may also miss the relevant temporal relationship.

Those are reasons to design new frozen alternatives, not permission to search this
same held-out session. The current result establishes that the first simple bridge
works end to end and that this particular neural summary does not add predictive
value under the declared test.

## Reproduce it

With the cached IBL data and both repositories available:

```bash
uv run --group ibl-validation \
  --with "unspool @ git+https://github.com/aeronjl/unspool@1fca711574c3968cc5ff5b8609c6e40dbe99bf6c" \
  python scripts/run_ibl_unspool_longitudinal_v1.py
```

The committed [machine-readable result](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/ibl-unspool-longitudinal-result-v0.1.json)
retains all source hashes, session neural summaries, the handoff fingerprint, exact
fold membership, model signatures, fit audits, animal-level scores, bootstrap
intervals, package versions, and the final result hash.
