# SDR-0046: Require explicit pairs and shared evidence for multisignal analysis

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

Multi-site and multi-color photometry can produce high correlations for biological
and non-biological reasons. Shared movement, task events, bleaching, reference
channels, detector paths, spectral bleed-through, and common preprocessing can all
create apparent coupling. Separate invalid samples or clocks make the denominator
ambiguous. Treating fibers, sessions, windows, or frequency bins as independent
animals compounds that ambiguity.

Cross-correlation, coherence, and phase also answer different questions. A peak lag
is not automatically a transmission delay; high coherence does not imply causal
interaction; and optical contamination cannot be established or excluded from
correlation alone.

## Decision

Every multisignal analysis begins with an ordered, explicitly identified signal
pair and one shared timestamp vector after any separately documented synchronization
or resampling.

- Channel metadata declares site, sensor, role, units, wavelength and optional
  detector, fiber, and coordinate identity; roles are never inferred.
- Invalidity in either signal, any declared covariate, or the shared clock splits
  joint continuity. Cross-channel pairs and spectral windows never cross a gap.
- Optical/crosstalk diagnostics retain metadata flags, control loading, raw
  association, and control-residualized association. Status is `no_flag` or
  `review`; absence of a flag is not evidence that crosstalk is absent.
- Lagged association reports physical lag convention and pair counts. Optional
  event/behavior residualization fits the declared design separately within each
  continuity run and retains coefficients, rank, and variance explained.
- A within-session null may randomly re-pair complete temporal blocks, but pairs are
  still formed only within blocks and the block duration must exceed twice the lag
  range.
- Coherence and phase pool power and complex cross-spectra by complete Welch-window
  count before deriving coherence. Run-level coherence values are not averaged.
- State conditioning consumes non-overlapping user-supplied epochs and preserves
  each epoch as a separate joint-continuity partition.
- Group inference begins from one declared scalar per session, aggregates sessions
  within animal-condition cells, and resamples or permutes animals.

## Alternatives considered

- **Infer channel meaning from wavelength or column order.** Rejected because
  acquisition conventions do not establish biological role.
- **Correlate independently cleaned signals on compressed timestamps.** Rejected
  because different masks and removed gaps create artificial adjacency.
- **Automatically regress the reference channel.** Rejected because correction
  changes the estimand and the reference may contain biological or wavelength-
  specific structure.
- **Average coherence across runs.** Rejected because runs with one and many Welch
  windows would receive equal weight and coherence is nonlinear in the spectra.
- **Treat a near-zero peak as crosstalk.** Rejected because common biological input
  and task locking can produce the same pattern.
- **Treat sites or sessions as independent replicates.** Rejected because the animal
  is the experimental unit for ordinary group comparisons.

## Consequences

The API requires more metadata and retains more evidence than a two-array
correlation helper. Joint missingness can reduce support substantially, and short
runs may contribute no coherence windows. Covariate-adjusted association remains
conditional on the supplied design. Blocked and animal-level randomization answer
different questions and are reported separately.

Coordinates can be stored prospectively, but pairwise results do not yet provide a
spatial covariance model for dense arrays. Crosstalk correction, spectral unmixing,
and hemodynamic models remain separate unimplemented transformations.

## Revisit trigger

Revisit after validation on two independently documented dual-site or dual-color
datasets with raw optical metadata and controls, or when a dense-array dataset
requires a mouse-aware spatial model rather than pairwise summaries.
