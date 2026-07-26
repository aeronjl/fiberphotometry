# Outcome-blind pipeline compatibility v0.1

Compatibility preflight answers whether a declared computation can run on the
structure of its intended inputs before fitting or summarizing fluorescence
outcomes. It examines timestamps, dimensions, available variables, declared
operations, and operation parameters. Reports always state
`outcome_values_accessed = false`.

The initial stable issue codes include:

- `asls_requires_regular_sampling`;
- `reference_channel_missing`;
- `baseline_variable_missing`;
- `event_summary_variable_missing`;
- `filter_above_nyquist`;
- `invalid_time_axis`.

`fiberphotometry inspect` includes the report in `preflight.json`. A structurally
incompatible project may be inspected but is stopped before `run` executes
preprocessing. Multiverse preflight reports every materialized universe separately,
including those already excluded by declared scientific compatibility rules.

Structural incompatibility is not a failed or rejected scientific method. It means
the declared workflow omitted something mechanically required—for example, an
explicit regularization operation before AsLS on jittered timestamps. Adding such
an operation changes the workflow and must be prospective when outcomes matter.

The prospective median-rate and relative-gap policy is specified in
[irregular sampling v0.1](irregular-sampling-v0.1.md). A declared resampling
operation before AsLS satisfies the structural clock requirement, while its
interpolation diagnostics and scientific validation remain separately visible.

The distinction is governed by
[SDR-0009](decisions/0009-separate-structural-incompatibility-from-scientific-failure.md).
