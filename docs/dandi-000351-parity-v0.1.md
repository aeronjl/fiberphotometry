# DANDI 000351 raw-to-archived parity audit v0.1

Status: **completed; retained structural failure** (26 July 2026)

The [protocol](../benchmarks/protocol-dandi-000351-parity-v0.1.md) froze direct
sample alignment before aggregate execution. All four draft assets matched their
pinned sizes and SHA-256 digests and exposed the expected `raw405,raw470` data,
but none passed the timestamp/shape contract:

- two standard-FP sessions had equal raw and archived lengths but accumulated
  approximately 0.23–0.26 seconds of clock difference;
- WT-stGtACR and datHT-stGtACR sessions stored approximately 130-Hz raw data and
  100-Hz archived dF/F, producing 85,515 and 79,888 fewer archived samples.

Consequently no numerical parity cases were executed, and all scientific gates
remain failed rather than being computed after an unregistered alignment choice.
The [machine-readable result](../benchmarks/dandi-000351-parity-v0.1.json) retains
all four failures.

This is not evidence that the archived dF/F is incorrect. It establishes that the
archive does not support index-wise raw-to-processed reproduction without an
explicit time-alignment policy. Protocol v0.2 freezes timestamp interpolation as a
separate follow-up rather than changing v0.1 after seeing the mismatch.
