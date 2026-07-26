# Analysis-tool landscape

This is a design audit, not a claim that an existing package is defective. The
tools optimise for different users and experimental systems.

| Tool | Primary environment | Strength | Boundary relevant here |
|---|---|---|---|
| pMAT | MATLAB / deployed GUI | Accessible common workflow and figures | Constrained analysis surface; MATLAB source workflow |
| GuPPy | Python GUI/notebooks | Multiple acquisition inputs; active and established | Application-oriented architecture and legacy environment assumptions |
| PhAT | Python GUI | Modular interactive exploration; several normalisations | GUI is central; not a general inference foundation |
| FiPhA | R/Shiny | Multiple photometry modalities and interactive QC | R application/export workflow |
| Pyfiber | Python | Integrates operant behaviour and photometry | Specialised around its behavioural workflow |
| FiPhoPHA | Python | Bootstrap CIs and permutation tests for waveforms | Post-hoc inference rather than end-to-end data model/preprocessing |
| photometry_FLMM / fastFMM | R | Nested functional mixed models and joint intervals | Specialised inference; distributional/model assumptions |
| PASTa | MATLAB | Signal processing and broad acquisition support | MATLAB-based analysis environment |
| ndx-fiber-photometry | NWB extension | Structured acquisition metadata and NWB storage | Standard, not a complete analysis library |

## What remains unoccupied

The credible gap is not “fiber photometry in Python”—GuPPy, Pyfiber, PhAT, and
FiPhoPHA already refute that. It is a maintained library layer joining:

- labelled, vendor-neutral and NWB-compatible data;
- explicit, benchmarked preprocessing alternatives;
- event alignment that retains the experimental hierarchy;
- inference across animals with stated exchangeability/model assumptions;
- reusable provenance and validation fixtures.

## Stress tests against the project thesis

### “One package can become the default”

Possible, but only through interoperability and trust. Existing tools have papers,
users, and active maintainers. Compatibility adapters and numerical comparison are
more credible than declaring replacement.

### “NWB-native is automatically an advantage”

NWB is valuable for archival metadata and DANDI integration, and DANDI 001084
demonstrates real fiber-photometry use. However, forcing NWB objects through every
numerical function would increase dependency and complexity. NWB should be a
first-class boundary with tested round trips.

### “Robust regression solves motion correction”

It improves resistance to transients under a linear shared-artefact model. It
cannot establish that the reference lacks biological sensitivity, correct nonlinear
or lagged artefacts automatically, or separate motion from biology when both are
event-locked. Diagnostics and experimental controls remain necessary.

### “Nonparametric inference avoids assumptions”

Bootstrap and permutation procedures still assume a valid resampling or exchangeability
unit. Resampling trials as though they were independent animals is not rescued by
being nonparametric. The package must make the randomisation unit structural.

### “Functional mixed models settle waveform inference”

They offer an unusually coherent account of nesting and simultaneous uncertainty,
but require smoothness, model specification, and likelihood assumptions. They should
be benchmarked alongside design-respecting randomisation methods.

## Sources

- [pMAT paper](https://doi.org/10.1016/j.pbb.2020.173093)
- [GuPPy paper](https://doi.org/10.1038/s41598-021-03626-9)
- [PhAT protocol](https://doi.org/10.1002/cpz1.763)
- [FiPhA paper](https://doi.org/10.1117/1.NPh.11.1.014305)
- [Pyfiber paper](https://doi.org/10.1038/s41598-023-43565-1)
- [FiPhoPHA paper](https://doi.org/10.1523/ENEURO.0221-25.2025)
- [Functional mixed-model paper](https://doi.org/10.7554/eLife.95802)
- [Artifact-correction study](https://doi.org/10.1117/1.NPh.12.2.025003)
- [NWB ecosystem](https://doi.org/10.7554/eLife.78362)
- [ndx-fiber-photometry](https://github.com/catalystneuro/ndx-fiber-photometry)
- [DANDI 001084 example](https://docs.dandiarchive.org/example-notebooks/001084/HoweLab/001084_demo/)
- [IBL photometry loading guide](https://docs.internationalbrainlab.org/notebooks_external/loading_photometry_data.html)
