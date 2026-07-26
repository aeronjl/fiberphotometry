# Experimental-design and scalar-inference schema v1

The inference layer separates open observation metadata from the small set of
relationships needed for valid resampling. It does not impose a neuroscience
ontology: `animal`, `fly`, `well`, or `organoid` can all be declared units.

```python
from fiberphotometry import Factor, ObservationTable, StudyDesign, Unit

observations = ObservationTable.from_columns(
    {
        "event_id": ["e1", "e2", "e3", "e4"],
        "animal": ["a", "a", "b", "b"],
        "condition": ["control", "drug", "control", "drug"],
        "outcome": [0.1, 0.4, -0.1, 0.3],
        "virus": ["GCaMP", "GCaMP", "GCaMP", "GCaMP"],
    }
)
design = StudyDesign(
    observation_id="event_id",
    units=(
        Unit("animal", "animal"),
        Unit("event", "event_id", nested_within="animal"),
    ),
    factors=(Factor("condition", "condition", "categorical", assignment_unit="event"),),
)
```

The undeclared `virus` column is preserved. Only metadata used in inference
needs typed semantics. `validate_design()` checks unique observations,
functional nesting, factor assignment levels, missing declarations, and severe
imbalance before an inferential function runs.

`StudyDesign` serializes to versioned JSON. Version 1 supports strictly nested
units and categorical or continuous factors. Crossed units, arbitrary formulas,
and missing-data models are rejected or deferred rather than guessed.

## Initial inference operations

- `hierarchical_bootstrap` recursively samples a declared unit path and retains
  distinct identities for duplicate sampled units.
- `permutation_test` supports paired sign flips and label shuffling at an
  explicitly declared assignment unit, optionally within blocks.
- `Estimand` currently represents a scalar, two-level difference of unit-level
  means. Unit-level aggregation prevents animals with more trials from silently
  receiving more population weight.

Both operations are experimental. Percentile, basic, and BCa intervals are
available and must be selected explicitly; Monte Carlo permutation p-values and exact paired sign-flip tests are
supported. Results retain the random seed and full sampled distribution. Paired
inference rejects incomplete units instead of silently dropping them. No
multiple-comparison correction or time-resolved simultaneous interval is
implied. Calibration results are in
[`benchmarks/results-v0.5.md`](../benchmarks/results-v0.5.md).

`unit_t_interval()` provides Welch and paired-t comparators on aggregation-unit
means. These encode stronger distributional assumptions than randomization
inference but showed appropriate finite-sample Gaussian coverage in
[`benchmarks/results-v0.7.md`](../benchmarks/results-v0.7.md).

Missingness requires an estimand decision. The observed-data contrast describes
available events; a complete-data contrast requires assumptions or a model for
unobserved outcomes. The library does not relabel observed-data coverage as
recovery of a complete-data effect.

An end-to-end public IBL example converts acquired-sample DMS feedback responses
from four animals into 2,507 event observations. The declared
animal→session→event hierarchy validates successfully while retaining the
imbalanced 1,850 correct and 657 incorrect trials. The script does not claim
that feedback is randomized or that this four-animal contrast supports
population inference; it demonstrates the data/design boundary. See
[`benchmarks/ibl-observation-table-v0.1.json`](../benchmarks/ibl-observation-table-v0.1.json).
