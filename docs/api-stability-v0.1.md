# API stability policy for v0.1

Status: **release-candidate boundary**. This policy takes effect for the first
published `0.1.x` release; the current `0.1.0.dev0` build remains developmental.

## Supported surface

The supported v0.1 API is deliberately smaller than everything importable from the
package root. Its machine-readable declaration is
`fiberphotometry.stability.SUPPORTED_API_V0_1` and covers:

- the `EventAnalysis`, `EventSession`, `Preprocessing`, configuration, result,
  coverage, and peri-event inference workflow types;
- canonical recording construction and validation;
- tabular and TDT project schemas/loaders, project configuration, and NWB export;
- verified project evidence reading from manifest directories and NWB files;
- semantic cross-bundle comparison and reproducibility reporting;
- detached OpenSSH publication signing and allowed-signers verification;
- validated, deterministic repository/DOI archival packaging and verification;
- sandbox-first creation and validation of unpublished Zenodo draft deposits;
- the direct event-coverage and peri-event inference entry points.

Within a `0.1.x` line, supported names will not be removed or have required
arguments added without defaults. Bug fixes may tighten validation when existing
behavior could silently produce an invalid scientific result.

## Experimental surface

Control-free baselines, regularization policy, multiverse execution, scalar mixed
models, and lower-level resampling functions remain experimental. Representative
names are listed in `EXPERIMENTAL_API_V0_1`; the label applies to the method family,
not only those symbols. Experimental APIs retain provenance and tests but may
change between minor releases when validation exposes a scientific problem.

Diagnostic and integration-specific modules that are neither listed as supported
nor documented as experimental are internal-for-stability purposes despite being
importable. Their current visibility is not a compatibility promise.

## Deprecation

Supported APIs receive a `DeprecationWarning`, migration text, and at least one
minor release of overlap before removal. Serialized v1 artifacts are not silently
rewritten: readers must reject unknown major schema versions and migrations must
produce a new artifact with recorded source version.

Security fixes and corrections preventing scientifically invalid output may bypass
the overlap period. Such changes require release notes and a scientific decision
record explaining the risk.

## Versioning interpretation

Before 1.0, Python package minor versions may contain deliberate experimental API
changes. Patch releases preserve supported interfaces and v1 artifact schemas.
The eventual 1.0 boundary will be based on usability and external reproduction,
not simply elapsed development time.
