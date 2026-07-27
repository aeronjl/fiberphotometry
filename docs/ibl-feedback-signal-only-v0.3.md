# IBL feedback signal-only v0.3 readiness record

Status: **protocol frozen; fluorescence outcomes not yet accessed** (26 July 2026)

Historical readiness record. The protocol was subsequently amended with a full
audit trail and executed; see the [v0.3.2 results](ibl-feedback-signal-only-results-v0.3.2.md).

The signal-only readiness gate passed with 383 eligible sessions across all 18
held-out animals. Twenty-four candidate sessions lacked 20 usable events in both
feedback conditions after the strict rolling-baseline boundary rule; the four
development animals remained excluded.

The cohort generator never loaded ROI fluorescence columns. It used only schema,
timestamps, wavelength/include flags, ROI labels, and behavioural event labels to
freeze eligibility. The resulting manifest fingerprint is
`38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6`.

The typed multiverse contains 15 executable workflows: two baseline estimators ×
two normalization families × three windows, plus the paper's rolling dF/F
comparator × three windows. Three rolling/subtractive combinations remain visible
as incompatible rather than disappearing from the decision space. Its protocol
fingerprint is
`abcec0a742a20869b7522c1cd700391371764afb9fa60778e16579a7876f05fc`.

This is a readiness result, not a fluorescence result. No correct-minus-incorrect
photometry contrast, interval, specification curve, or animal influence estimate
has yet been calculated. The executable contract is in the
[frozen protocol](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-ibl-feedback-signal-only-v0.3.md).
