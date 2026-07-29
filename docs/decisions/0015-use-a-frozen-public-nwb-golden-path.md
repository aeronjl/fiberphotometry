# SDR-0015: Use a frozen public NWB golden path

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related protocol/report:
  [DANDI 000971 tutorial protocol](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-dandi-000971-tutorial-v0.1.md)

## Context

The first public-data tutorial proves import-to-report execution on four IBL
sessions, but it begins from project-specific tables and cannot demonstrate a
paired signal/isosbestic preprocessing multiverse. A canonical tutorial should
show the product's complete scientific argument while remaining executable and
small enough for real users.

DANDI:000971 provides an immutable CC-BY NWB snapshot with raw dual-site calcium
and isosbestic fluorescence, behavioral timestamps, multiple animals, an official
example notebook, conversion provenance, and an open source study. The complete
Dandiset is approximately 23.5 GB, so an unbounded tutorial would impose an
unreasonable first-run cost.

## Decision

Use six checksum-pinned DANDI:000971 NWB assets as the canonical full-data tutorial
cohort. Freeze the cohort, event definition, animal-level estimand, reference
workflow, and eight-universe robustness space before accessing the selected
cohort's fluorescence outcomes.

Keep the script and declarative scientific specification authoritative. Treat the
narrative Markdown as an explanation of those executable objects, not an
independent analysis implementation. Use a synthetic NWB cohort for fast CI and an
explicit network command for the 2.20 GB public-data reproduction.

## Consequences

Scientists see NWB-native raw import, strict event provenance, reference correction,
multiverse execution, animal-level inference, retained failures, and reproducible
artifacts in one example. The full run is realistic but too large for ordinary CI.
The balanced phenotype-stratified cohort is pedagogical and cannot estimate source
population prevalence or phenotype effects.

## Alternatives considered

- Extend only the existing IBL tutorial: retained as a valuable signal-only and
  irregular-acquisition example, but insufficient for paired reference correction.
- Analyze all DANDI:000971 photometry assets: rejected for the first tutorial due
  to download size, repeated sessions, and the additional longitudinal estimand.
- Use one or two very small files: rejected because honest animal-level inference
  and leave-one-animal-out diagnostics require a visible population boundary.
- Make a notebook authoritative: rejected because hidden state and untested copied
  code weaken reproducibility; a viewing notebook may be added later.

## Revisit trigger

Reconsider the cohort if a smaller immutable, multi-animal NWB dataset with raw
paired channels and equally clear event provenance becomes available, or if user
testing shows the 2.20 GB full run blocks adoption.

## Evidence added later

The frozen six-animal execution completed without source or workflow failures. See
the [v0.1 result](https://github.com/aeronjl/fipha/blob/main/research/dandi-000971-tutorial-results-v0.1.md) and committed
[evidence bundle](https://github.com/aeronjl/fipha/blob/main/benchmarks/dandi-000971-tutorial-v0.1/).
