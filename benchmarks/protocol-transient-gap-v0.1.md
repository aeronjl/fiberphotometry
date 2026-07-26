# Sharp-transient and missing-run benchmark protocol v0.1

Status: **frozen before aggregate execution** (26 July 2026)

This benchmark tests whether timestamp regularization and common missing-data
policies preserve the quantities scientists actually use: waveform shape, peak
amplitude and timing, response-window means, and event contrasts. It follows the
literature review recorded in the machine-readable protocol but does not treat
common practice as validation.

Two acquisition rates (20 and 50 Hz), two event phases, five transient shapes,
and ordinary versus deliberately difficult bandwidths are crossed with small
timestamp jitter, isolated dropped samples, and contiguous gaps. Linear
interpolation, nearest-sample alignment, previous-value duplication, and protected
missingness are compared. Interpolation across a protected contiguous gap appears
only as a negative control.

Ordinary transients must retain peak amplitude within 5%, peak timing within one
sample, and response means and event contrasts within 1%. Stress transients use
15%, two samples, and 5%, respectively. These are prospective engineering limits,
not literature-derived universal biological thresholds. Failures are retained and
reported by transient class.

Protected gaps may never be bridged. Any event whose baseline or response window
touches a protected gap must receive an explicit disposition. Condition-dependent
exclusion must produce a warning.

The complete scenario matrix, policy names, sources, metrics, seed, and thresholds
are frozen in
[`transient-gap-protocol-v0.1.json`](transient-gap-protocol-v0.1.json). Any change
after execution requires a new protocol version.
