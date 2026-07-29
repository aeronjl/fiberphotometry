# Population inference across core workflows v0.1

fipha now exposes the same animal-level population boundary for three
additional method families: spontaneous transients, state-conditioned band power,
and multi-signal association or coherence. Each adapter materializes inspectable
animal-level cells before any population contrast is calculated.

## One interface, domain-specific denominators

| Workflow | Within-session evidence | Animal-cell rule | Retained denominator |
| --- | --- | --- | --- |
| Spontaneous transient rate | event count and analyzed exposure | pool counts and exposure across sessions | contributing sessions, event count, exposure |
| Transient amplitude, width, or AUC | event-level kinetic summaries | summarize sessions, then aggregate sessions equally | sessions and event count |
| State-conditioned band power | complete gap-bounded Welch windows | integrate the declared band, then average sessions equally | sessions and total Welch windows |
| Lagged association or coherence | valid pairs or complete cross-spectral windows | aggregate the declared scalar across sessions | sessions and actual pair/window support |

These rules are intentionally not interchangeable. The shared population layer
receives their outputs only after each animal-condition cell has been formed.

## Materialize, inspect, infer

Every materializer returns a typed object with:

- domain-specific `animal_estimates`;
- common `population_estimates` containing animal, level, value, source sessions,
  session support, and lower-level observation count;
- `.contrast(PopulationContrastSpec(...))`; and
- `.interaction(group_assignments, PopulationInteractionSpec(...))`.

For spontaneous transient rates:

```python
from fipha.population import PopulationContrastSpec
from fipha.population_workflows import materialize_transient_population

cells = materialize_transient_population(
    quantified_sessions,
    metric="rate_per_minute",
    channel="NAc",
    levels=("pre", "post"),
)

paired = cells.contrast(
    PopulationContrastSpec(
        numerator="post",
        denominator="pre",
        design="paired",
        draws=2_000,
        seed=2026,
    )
)
```

A zero-event animal-session remains valid rate evidence when analyzed exposure is
positive. Its event `observation_count` is zero rather than being dropped or
invented; `source_units` and `support` still show the contributing session.

## Group-by-condition interactions

The same materialized cells can test whether a repeated condition difference
changes between two independent animal groups:

```python
from fipha.population import (
    PopulationGroupAssignment,
    PopulationInteractionSpec,
)

groups = (
    PopulationGroupAssignment("mouse-01", "control"),
    PopulationGroupAssignment("mouse-02", "control"),
    PopulationGroupAssignment("mouse-11", "treatment"),
    PopulationGroupAssignment("mouse-12", "treatment"),
)

interaction = cells.interaction(
    groups,
    PopulationInteractionSpec(
        group_numerator="treatment",
        group_denominator="control",
        condition_numerator="post",
        condition_denominator="pre",
        draws=2_000,
        seed=2026,
    ),
)
```

This works identically after `materialize_state_band_power_population()` and
`materialize_association_population()`. For association, first create session
estimates with `session_estimate_from_lagged()` or
`session_estimate_from_coherence()`.

## Spectral example

```python
cells = materialize_state_band_power_population(
    state_psd_sessions,
    states=("rest", "exploration"),
    frequency_band_hz=(0.5, 2.0),
)

state_contrast = cells.contrast(
    PopulationContrastSpec(
        numerator="exploration",
        denominator="rest",
        design="paired",
    )
)
```

Band edges are interpolated before integration by the spectral workflow. Welch
windows support each session estimate but never become population replicates.

## Association and coherence example

```python
cells = materialize_association_population(
    session_estimates,
    metric="mean_coherence_0.5_2Hz",
    pair_id="dms-green__nacc-red",
    levels=("rest", "exploration"),
    session_aggregation="mean",
)
```

The materialized observation count is the actual number of valid lag pairs or
complete spectral windows carried by the session estimates. It documents support;
it does not determine population weight.

## Current boundary

The common v0.1 population contract is additive: it reports numerator minus
denominator and the two-group difference in those within-animal differences.
Specialist transient and state-band APIs still provide ratio effects and
randomization *p*-values. They are not silently translated into the additive
contract.

The adapters do not choose a transient detector, frequency band, state definition,
lag, channel pair, or session aggregation policy. Those remain declared scientific
choices. Richer count models, continuous moderators, partial pooling, and
multi-factor models remain explicit gaps.

For complete PSD, autocorrelation, lag-association, or coherence outcomes, use the
[vector population-curve workflow](population-curve-inference.md). It retains
the full frequency or lag axis and lower-level support at every point rather than
requiring a scalar band or lag summary.
