# Metadata completeness profile v0.1

Every loaded project now produces a typed metadata report for three separate
questions:

- **Analysis:** can the declared computation be traced to identified sessions,
  fingerprinted inputs, and an explicit event factor?
- **NWB:** is the metadata required by the current NWB writer present?
- **Publication/reuse:** does the project satisfy FiberPhotometry's minimal v0.1
  descriptive profile?

The last status is not certification against a journal, repository, FAIR rubric,
or ontology. It is an actionable minimum intended to prevent obviously anonymous
or uninterpretable exports.

## Configuration

Metadata are deliberately open-ended:

```toml
[metadata]
experimenters = ["A. Scientist"]
institution = "Example University"
lab = "Example Lab"
experiment_description = "Cue-evoked fluorescence in a within-animal design"
protocol = "https://doi.org/example"
species = "Mus musculus"
indicator = "GCaMP8m"
brain_regions = ["dorsomedial striatum"]
acquisition_system = "TDT Synapse"
data_license = "CC-BY-4.0"

# Lab-specific fields are retained and reported as unrecognized, not rejected.
implant_batch = "2026-07-A"
```

The recognized publication fields are experimenters, institution, lab,
experiment description, protocol, species, indicator, brain regions, acquisition
system, and data license. Session start times remain session-level fields because
they can vary and NWB requires a timezone-aware value.

## Output

`fiberphotometry inspect project.toml` includes `metadata_completeness` in its
preflight JSON. A run additionally writes `metadata.json`, fingerprints it in the
manifest, and embeds the same assessment in each exported NWB file.

Each check has a stable code, target(s), status, scope, and remediation. Each
target reports `ready` or `incomplete` plus the exact missing check codes. Missing
publication metadata does not silently block an otherwise declared exploratory
analysis; downstream release policies can choose to enforce the readiness status.

The openness and versioning policy is recorded in
[SDR-0008](decisions/0008-open-metadata-versioned-readiness-profile.md).
