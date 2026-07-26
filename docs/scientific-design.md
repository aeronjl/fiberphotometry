# Scientific design proposal

## Objective

Build a Python library that makes fiber photometry analysis composable,
auditable, and statistically honest from acquired signals through multi-animal
inference. The library should standardise interfaces and provenance while
allowing scientifically contested methods to coexist and be benchmarked.

## Non-goals for the first release

- A GUI or complete replacement for every vendor's acquisition software.
- A universal preprocessing recipe.
- Inferring cellular firing or transmitter concentration from bulk fluorescence.
- Treating trials or time samples as independent biological replicates.
- Reimplementing functional mixed models before numerical parity can be tested.

## Scientific contract

1. **Raw signals are immutable.** Every transformation creates a named output.
2. **Identity is structural.** Subject, session, channel, region, event, and trial
   cannot be discarded by a convenience operation.
3. **Assumptions are output.** Parameters, method names, exclusions, software
   versions, and diagnostics travel with results.
4. **The experimental unit is explicit.** Resampling and validation operate at
   the animal or randomisation unit unless a design justifies otherwise.
5. **Alternatives remain comparable.** OLS, robust regression, control-channel,
   and control-free methods share interfaces but do not share unearned claims.
6. **Defaults require benchmarks.** A method becomes a default only after tests
   on simulations, negative controls, and heterogeneous public data.

## Data model

The initial in-memory representation is an `xarray.Dataset`:

- `time`: monotonically increasing acquisition time;
- `channel`: fluorophore, wavelength-derived signal, or ROI identity;
- `signal(time, channel)`: primary fluorescence;
- optional `reference(time, channel)`: matched control measurement;
- coordinates/attributes: subject, session, sensor, region, wavelength, units;
- derived variables: validity masks, fitted baseline, corrected fluorescence;
- separate event tables keyed by subject/session/event identifiers.

NWB is an interchange and archive layer, not the internal computational API.
Adapters should map `ndx-fiber-photometry` objects into the canonical model and
round-trip metadata without requiring every algorithm to depend on PyNWB.

## Preprocessing sequence under test

The package should expose a pipeline graph rather than silently enforcing an
order. The first benchmarked path will test:

1. acquisition validity and saturation/dropout masks;
2. sampling diagnostics and optional resampling;
3. low-pass filtering appropriate to indicator kinetics;
4. reference fitting with OLS and Huber IRLS comparators;
5. fitted-reference dF/F with denominator diagnostics;
6. optional slow-baseline models for recordings without a valid reference;
7. event alignment without averaging away trials or animals.

The 2025 methodological study by Jean-Richard-dit-Bressel and McNally reports
advantages for filtering, IRLS, and fitted-reference dF/F, while also warning
that detrending inputs before dF/F can undermine the calculation. This is a
high-priority independent reproduction target, not an unquestioned authority.

## Inference strategy

Inference is a separate layer from preprocessing. The initial API should support:

- animal-level bootstrap confidence intervals;
- permutation tests whose exchangeability scheme mirrors the design;
- scalar mixed models for pre-specified summaries;
- adapters/export for functional mixed modelling in `fastFMM`;
- multiplicity-aware simultaneous or cluster procedures for whole waveforms.

Jean-Richard-dit-Bressel et al. (2020) demonstrate useful waveform bootstrap and
permutation approaches and explicitly study false-positive control. Loewinger et
al. (2025) show that functional linear mixed models can represent nested trials,
sessions, and animals while providing joint confidence intervals. FiPhoPHA
argues for fewer distributional assumptions. These answer different questions;
the project should encode each method's estimand and assumptions rather than
collapse them into a single “significance” command.

## Benchmark programme

### Synthetic ground truth

Factorially vary:

- neural transient amplitude, duration, overlap, and event jitter;
- linear and nonlinear shared artefacts;
- reference contamination by biology;
- exponential and non-exponential bleaching;
- motion locked to the behavioural event;
- haemodynamic-like components and channel lag;
- saturation, dropped frames, discontinuities, and uneven sampling;
- subjects, sessions, trials, imbalance, and random-effect magnitude;
- null, pointwise, sustained, and time-shifted group effects.

Score signal recovery, bias, RMSE, event-effect recovery, interval coverage,
family-wise error, power, and runtime. Failure cases must remain in the suite.

### Public data

1. **IBL public photometry:** hundreds of standardised decision-making sessions,
   aligned behaviour, multiple regions, manual inclusion masks, and existing
   local adapter code. Useful for cross-session and cross-animal robustness.
2. **DANDI 001084:** NWB/`ndx-fiber-photometry` multifiber recordings with rich
   hardware metadata. Useful for NWB round trips and multi-ROI handling.
3. **Published package example data:** where licensing permits, reproduce pMAT,
   GuPPy, FiPhoPHA, and FLMM worked results to establish numerical comparisons.
4. **Negative controls:** recordings with fluorophore/control conditions and
   shuffled or non-causal events should be prioritised during dataset curation.

## Decision gates

- **0.1:** canonical model, simulations, reference fitting, alignment, IBL and NWB
  read paths, provenance, diagnostic plots.
- **0.2:** animal-aware resampling and scalar mixed models with coverage tests.
- **0.3:** validated functional inference bridge and simultaneous intervals.
- **1.0:** two acquisition families plus NWB independently reproduced by outside
  users, stable schema, public benchmark report, and documented failure modes.

## Key references

- Bruno et al. (2021), pMAT. <https://doi.org/10.1016/j.pbb.2020.173093>
- Sherathiya et al. (2021), GuPPy. <https://doi.org/10.1038/s41598-021-03626-9>
- Jean-Richard-dit-Bressel et al. (2020), event-related inference.
  <https://doi.org/10.3389/fnmol.2020.00014>
- Loewinger et al. (2025), functional linear mixed models.
  <https://doi.org/10.7554/eLife.95802>
- Jean-Richard-dit-Bressel & McNally (2025), artifact correction.
  <https://doi.org/10.1117/1.NPh.12.2.025003>
- Simpson et al. (2024), fiber photometry primer.
  <https://doi.org/10.1016/j.neuron.2023.11.012>
- Rübel et al. (2022), NWB ecosystem. <https://doi.org/10.7554/eLife.78362>
