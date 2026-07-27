# Serialized artifact schemas v0.1

The primary scientist-facing JSON now identifies itself with
`artifact_type = "event_analysis_result"` and `schema_version = "1"`. Its normative
top-level contract is
[`schemas/event-analysis-result-v1.schema.json`](../schemas/event-analysis-result-v1.schema.json).

Grouped robustness execution also emits `artifact_type =
"multiverse_lane_summary"`, `schema_version = "1"`, governed by
[`schemas/multiverse-lane-summary-v1.schema.json`](../schemas/multiverse-lane-summary-v1.schema.json).
Its magnitudes and practical-effect thresholds are scoped to explicit unit lanes;
it contains no pooled cross-unit median or range.

Cross-bundle reports emit `artifact_type = "evidence_bundle_comparison"` and
`schema_version = "1"`, governed by
[`schemas/evidence-bundle-comparison-v1.schema.json`](../schemas/evidence-bundle-comparison-v1.schema.json).

Publication signing emits `artifact_type = "publication_manifest_attestation"`
and `schema_version = "1"`, governed by
[`schemas/publication-manifest-attestation-v1.schema.json`](../schemas/publication-manifest-attestation-v1.schema.json).
Its detached `.sig` file uses the OpenSSH SSHSIG format.

The nested event-coverage and peri-event inference records each carry their own
`schema_version = "1"`. Analysis plans, study designs, project configuration, and
pipeline specifications retain their existing explicit versions. Provenance
operation lists embedded in xarray/NWB attributes remain append-only diagnostic
records for v0.1 rather than independently stable interchange schemas.

## Compatibility rules

- Additive optional fields may appear within schema v1.
- Existing required field meanings and types do not change within v1.
- Removing or reinterpreting a required field requires schema v2.
- Unknown major versions must be rejected rather than guessed.
- Artifact fingerprints apply to exact bytes or canonicalized payloads as stated
  by the producing API; a migration necessarily produces a new fingerprint.

The JSON Schema intentionally fixes the complete top-level result ledger while
allowing method-specific detail inside preprocessing, analysis, QC, and lineage
objects. Those nested objects already expose their own method or schema versions
where they are intended for round-trip use.
