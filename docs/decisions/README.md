# Scientific decision records

This directory records consequential scientific and API decisions, including
decisions to defer or reject a method. It is an audit trail, not a claim that every
decision is permanent.

## Status vocabulary

- **Draft:** proposed and open to change; not normative.
- **Accepted:** current project policy.
- **Rejected:** considered but not adopted.
- **Superseded:** replaced by a later numbered record, which must link back.

Decision records state their date, evidence available at that date, alternatives,
consequences and an explicit revisit trigger. Later evidence is appended or linked;
the original reasoning is not silently rewritten.

## Relationship to other documents

- `docs/drafts/` contains working designs and questions. Drafts may change freely
  and must not be cited as package guarantees.
- `benchmarks/protocol-*.md` freezes hypotheses, scenarios and thresholds before
  aggregate execution.
- benchmark JSON files retain complete machine-readable outcomes.
- reports describe results after execution and link to the governing decisions.

## Index

| Record | Status | Decision |
| --- | --- | --- |
| [SDR-0001](0001-record-scientific-decisions.md) | Accepted | Record consequential scientific decisions |
| [SDR-0002](0002-control-free-methods-remain-experimental.md) | Accepted | Keep initial control-free methods experimental |
| [SDR-0003](0003-separate-subtraction-and-division.md) | Accepted | Represent subtraction and division as different transformations |
| [SDR-0004](0004-require-explicit-derived-data-alignment.md) | Accepted | Require explicit alignment for externally derived data |
| [SDR-0005](0005-do-not-infer-photometry-channel-identity.md) | Accepted | Do not infer photometry channel identity from row position |
| [SDR-0006](0006-require-explicit-nwb-session-metadata.md) | Accepted | Require explicit NWB session metadata and avoid invented hardware |
| [SDR-0007](0007-require-explicit-tdt-store-mapping.md) | Accepted | Require explicit TDT stream, channel, and epoc semantics |
| [SDR-0008](0008-open-metadata-versioned-readiness-profile.md) | Accepted | Preserve open metadata while versioning readiness profiles |
| [SDR-0009](0009-separate-structural-incompatibility-from-scientific-failure.md) | Accepted | Preflight structural incompatibility without accessing outcomes |
| [SDR-0010](0010-mixed-models-are-sensitivity-summaries.md) | Accepted | Report scalar mixed models as secondary sensitivity summaries |
| [SDR-0011](0011-regularize-irregular-clocks-prospectively.md) | Accepted | Regularize irregular clocks only through prospective, auditable policy |
| [SDR-0012](0012-protect-missing-event-windows.md) | Accepted | Protect missing event windows instead of silently reconstructing them |
| [SDR-0013](0013-report-event-selection-before-preprocessing.md) | Accepted | Report event selection before and after preprocessing |
| [SDR-0014](0014-resample-animals-for-peri-event-bands.md) | Accepted | Resample animals for peri-event uncertainty |
| [SDR-0015](0015-use-a-frozen-public-nwb-golden-path.md) | Accepted | Use a frozen public NWB golden path |
| [SDR-0016](0016-require-named-multiverse-alternatives.md) | Accepted | Require named, justified multiverse alternatives |
| [SDR-0017](0017-couple-preprocessing-outputs-and-separate-units.md) | Accepted | Couple preprocessing outputs and separate incompatible units |
| [SDR-0018](0018-summarize-robustness-within-unit-lanes.md) | Accepted | Summarize robustness within complete unit lanes |
| [SDR-0019](0019-reject-irrelevant-parameters-and-declare-incompatibility.md) | Accepted | Reject irrelevant parameters and declare incompatibility prospectively |
| [SDR-0020](0020-store-one-reference-signal-and-the-complete-multiverse-ledger.md) | Accepted | Store one reference signal and the complete multiverse ledger |
| [SDR-0021](0021-verify-directory-bundles-and-mark-standalone-nwb-trust.md) | Accepted | Verify directory bundles and mark standalone NWB trust |
| [SDR-0022](0022-separate-byte-identity-from-scientific-reproduction.md) | Accepted | Separate byte identity from scientific reproduction |
| [SDR-0023](0023-sign-manifest-attestations-with-domain-separated-openssh.md) | Accepted | Sign manifest attestations with domain-separated OpenSSH |
| [SDR-0024](0024-generate-deterministic-deposits-from-neutral-metadata.md) | Accepted | Generate deterministic deposits from neutral metadata |
| [SDR-0025](0025-stop-zenodo-automation-at-validated-drafts.md) | Accepted | Stop Zenodo automation at validated drafts |
| [SDR-0026](0026-organize-documentation-by-scientific-question.md) | Accepted | Organize documentation by scientific question |
| [SDR-0027](0027-hold-out-complete-groups-for-event-kernel-models.md) | Accepted | Hold out complete groups for event-kernel models |
| [SDR-0028](0028-retain-weak-event-kernel-validation.md) | Accepted | Retain weak event-kernel validation and keep the API experimental |
| [SDR-0029](0029-treat-event-kernel-intervals-as-conditional-sensitivity.md) | Accepted | Treat grouped event-kernel intervals as conditional sensitivity |
| [SDR-0030](0030-delegate-behavioral-trajectories-to-unspool.md) | Accepted | Delegate behavioral learning trajectories to Unspool |
| [SDR-0031](0031-treat-spontaneous-transients-as-a-method-family.md) | Accepted | Treat spontaneous transients as a method family |
| [SDR-0032](0032-preserve-external-behavior-semantics.md) | Accepted | Preserve external behavior semantics at typed boundaries |
| [SDR-0033](0033-retain-validity-masks-without-compressing-time.md) | Accepted | Retain validity masks without compressing time |
| [SDR-0034](0034-fit-only-explicit-matched-pulse-clock-transforms.md) | Accepted | Fit only explicit matched-pulse clock transforms |
| [SDR-0035](0035-compare-event-kernel-models-only-on-common-evidence.md) | Accepted | Compare event-kernel models only on common evidence |
| [SDR-0036](0036-reconstruct-kernels-from-explicit-typed-bases.md) | Accepted | Reconstruct kernels from explicit typed bases |
| [SDR-0037](0037-model-event-history-as-explicit-within-session-modulation.md) | Accepted | Model event history as explicit within-session modulation |
| [SDR-0038](0038-model-variable-duration-behavior-with-physical-intervals-and-progress.md) | Accepted | Model variable-duration behavior with physical intervals and progress |
| [SDR-0039](0039-treat-predictor-family-drops-as-paired-predictive-sensitivity.md) | Accepted | Treat predictor-family drops as paired predictive sensitivity |
| [SDR-0040](0040-keep-simultaneous-kernel-bands-opt-in-after-failed-calibration.md) | Accepted | Keep simultaneous kernel bands opt-in after failed calibration |
| [SDR-0041](0041-use-format-specific-readers-behind-one-acquisition-boundary.md) | Accepted | Use format-specific readers behind one acquisition boundary |
| [SDR-0042](0042-separate-transient-detection-from-quantification.md) | Accepted | Separate transient detection from quantification |
| [SDR-0043](0043-infer-transient-contrasts-at-the-animal-level.md) | Accepted | Infer transient contrasts at the animal level |
| [SDR-0044](0044-require-comparability-evidence-before-longitudinal-handoff.md) | Accepted | Require comparability evidence before longitudinal handoff |
| [SDR-0045](0045-never-bridge-gaps-or-state-boundaries-in-spectral-analysis.md) | Accepted | Never bridge gaps or state boundaries in spectral analysis |
| [SDR-0046](0046-require-explicit-pairs-and-shared-evidence-for-multisignal-analysis.md) | Accepted | Require explicit pairs and shared evidence for multisignal analysis |
| [SDR-0047](0047-separate-prospective-optical-masks-from-observed-validity.md) | Accepted | Separate prospective optical masks from observed validity |
| [SDR-0048](0048-freeze-transient-thresholds-and-retain-waveform-qc.md) | Accepted | Freeze transient thresholds and retain waveform QC |
| [SDR-0049](0049-make-interval-policy-order-explicit-and-auditable.md) | Accepted | Make interval-policy order explicit and auditable |
| [SDR-0050](0050-preserve-ndx-pose-values-and-declare-link-omissions.md) | Accepted | Preserve ndx-pose values and declare link omissions |
| [SDR-0051](0051-name-observable-multiscale-estimands-and-preserve-denominators.md) | Accepted | Name observable multiscale estimands and preserve denominators |

Use four-digit monotonically increasing identifiers. Copy
[`template.md`](template.md), fill every heading, and add the record to this index.
