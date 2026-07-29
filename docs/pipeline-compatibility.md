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

The single-recording commands (`qc`, `dff`, `align`, `transients`) reuse those
codes where they apply and add codes for failures that occur while resolving a
file into a recording, before any preflight can run:

- `acquisition_source_unreadable`;
- `unrecognized_acquisition_format`;
- `channel_not_found`;
- `event_times_missing`;
- `invalid_event_window`;
- `nwb_session_start_time_missing`.

These are reported as `error: <code>: <message>` on standard error with a
following `hint:` line, and exit status 2. They are documented alongside their
commands in [the command line reference](cli.md).

`fipha inspect` includes the report in `preflight.json`. A structurally
incompatible project may be inspected but is stopped before `run` executes
preprocessing. Multiverse preflight reports every materialized universe separately,
including those already excluded by declared scientific compatibility rules.

Structural incompatibility is not a failed or rejected scientific method. It means
the declared workflow omitted something mechanically required—for example, an
explicit regularization operation before AsLS on jittered timestamps. Adding such
an operation changes the workflow and must be prospective when outcomes matter.

The prospective median-rate and relative-gap policy is specified in
[irregular sampling v0.1](irregular-sampling.md). A declared resampling
operation before AsLS satisfies the structural clock requirement, while its
interpolation diagnostics and scientific validation remain separately visible.
