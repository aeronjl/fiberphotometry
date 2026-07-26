# Sharp-transient and missing-run benchmark protocol v0.1.1

Status: **metric amendment frozen after v0.1 aggregate inspection**

The v0.1 execution revealed that relative event-contrast error is undefined or
unstable when the true response-minus-baseline contrast is approximately zero, as
it is for a symmetric transient centred on the event boundary. Tiny absolute
errors were consequently reported as very large relative errors.

Version 0.1.1 changes only that denominator: absolute event-contrast error is
normalized by the known simulated peak amplitude. The numerical limits remain 1%
for ordinary transients and 5% for stress transients. Scenarios, policies, seeds,
transient parameters, all other metrics, and all other thresholds are unchanged.

Before this amendment, aggregate pass counts and failing metric values had been
inspected by family and policy. The original protocol, runner, and v0.1 result are
retained. The complete disclosure and parent fingerprint are in
[`transient-gap-protocol-v0.1.1.json`](transient-gap-protocol-v0.1.1.json).
