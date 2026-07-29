# Longitudinal behavior with Unspool

*Applies to v0.1.*

fipha and [Unspool](https://github.com/aeronjl/unspool) have deliberately
different scientific responsibilities.

| fipha owns | Unspool owns |
|---|---|
| signal ingestion, channel identity and QC | explicit longitudinal clocks |
| reference and baseline correction | behavioral and cognitive model families |
| event alignment and neural summaries | forward-session and population holdouts |
| photometry estimands and evidence bundles | parameter/model recovery and trajectory diagnostics |

The boundary is a trial-level table. fipha retains neural values and
provenance while adding the four explicit coordinates required by
`unspool.Study`: subject, session, trial, and session order. Chronology is never
inferred from row order or session names.

Pose trajectories and behavioral bouts enter through the separate
[behavioral ecosystem contract](ecosystem-interoperability.md). They become
declared neural predictors or summaries here only after confidence, clock and
missingness decisions are recorded. Unspool does not replace DeepLabCut, SLEAP,
Keypoint-MoSeq or BORIS, and fipha does not duplicate Unspool's
longitudinal model families.

## Preflight across-session comparability

Before building a longitudinal table, declare one outcome-blind QC record per
session and logical neural series. The full contract and threshold meanings are in
[Across-session comparability](session-comparability.md).

```python
from fipha.comparability import (
    SessionComparabilityRecord,
    assess_session_comparability,
)

comparability = assess_session_comparability(
    [
        SessionComparabilityRecord(
            subject="mouse-1",
            session=session,
            series_id="dms-dlight",
            sensor="dLight1.3b",
            site="DMS",
            output_variable="dff",
            unit="fraction",
            preprocessing_fingerprint=recipe_sha256,
            finite_fraction=finite_fraction,
            event_coverage_fraction=event_coverage,
            baseline_median=baseline_median,
            reference_correlation=reference_correlation,
            sampling_rate_hz=sampling_rate_hz,
        )
        for session in ("day-1", "day-2")
    ]
)
```

## Build the handoff

```python
from fipha import ObservationTable
from fipha.unspool import prepare_unspool_study

events = ObservationTable.from_columns(
    {
        "animal": ["mouse-1", "mouse-1", "mouse-1", "mouse-1"],
        "recording": ["day-1", "day-1", "day-2", "day-2"],
        "event_index": [0, 1, 0, 1],
        "training_day": [0, 0, 1, 1],
        "choice": [0, 1, 1, 1],
        "dms_stimulus_response": [0.08, 0.12, 0.19, 0.24],
    }
)

handoff = prepare_unspool_study(
    events,
    subject="animal",
    session="recording",
    trial="event_index",
    session_order="training_day",
    comparability=comparability,
    require_comparability=True,
)
```

`handoff.columns` is dependency-free and serializable. It retains the original
columns, adds canonical longitudinal coordinates, records the source mapping, and
fingerprints the complete handoff and its comparability evidence. It rejects
duplicate trial keys, ambiguous session chronology, missing coordinates, accidental
replacement of an existing canonical column, failed comparability, and exported
sessions absent from the preflight.

With Unspool installed, construct its immutable study directly:

```python
study = handoff.to_study()
```

For a fully reproducible development environment, pin the current Unspool revision
used to define this contract:

```bash
uv add "unspool @ git+https://github.com/aeronjl/unspool@1fca711574c3968cc5ff5b8609c6e40dbe99bf6c"
```

The package remains separate and optional: installing fipha does not
silently install a behavioral-modeling stack.

## Ask a prospective longitudinal question

```python
from unspool import forward_session_splits

splits = forward_session_splits(study, min_train_sessions=3)
```

Unspool can then compare stationary, smoothly varying, partially pooled, latent-
state, reinforcement-learning, or drift-diffusion accounts using folds that train
only on earlier complete sessions. Neural event summaries can enter as declared
covariates or targets, depending on the scientific question. Any learning landmark
or normalization learned from data must be fitted inside each training fold.

## Relation to the public IBL learning study

Pan-Vazquez, Sanchez Araujo et al. recorded dopamine signals across DMS, DLS, and
NAc throughout acquisition of a visual decision task. Their analyses distinguished
trial-level choices, session-evolving behavioral weights, animal-specific learning
trajectories, and session-specific neural encoding kernels. The study therefore
motivates this boundary: photometry preprocessing alone cannot define a valid
longitudinal behavioral model.

Loewinger et al.'s functional mixed-model framework similarly distinguishes
trial-, session-, and animal-level covariates in photometry experiments. That method
remains a separate planned time-resolved inference route; the Unspool handoff does
not pretend that a scalar neural summary is equivalent to a functional response.

## Evidence boundary

This v0.1 increment validates schema composition, not a biological learning claim.
The next public-data benchmark should freeze:

1. the neural summary exported by fipha;
2. the behavioral outcome and clock modeled by Unspool;
3. training-only transformations and forward-session folds;
4. animal- and session-level denominators; and
5. stationary and smooth alternative models before outcomes are compared.

Sources:

- [Pan-Vazquez, Sanchez Araujo et al. (2024)](https://doi.org/10.1016/j.cub.2024.09.045)
- [Loewinger et al. (2023)](https://doi.org/10.1523/ENEURO.0094-23.2023)
- [Unspool longitudinal data and validation contract](https://github.com/aeronjl/unspool)
