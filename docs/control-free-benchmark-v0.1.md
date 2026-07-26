# Control-free bleaching benchmark v0.1

The first signal-only baseline benchmark is a retained partial failure. Its
protocol and thresholds were frozen in
[`benchmarks/protocol-control-free-v0.1.md`](../benchmarks/protocol-control-free-v0.1.md)
before aggregate execution. The complete 240-run result is
[`benchmarks/control-free-v0.1.json`](../benchmarks/control-free-v0.1.json).

## Results

| Scenario | Method | Correlation | RMSE | Event bias | Pass |
| --- | --- | ---: | ---: | ---: | :---: |
| Single exponential | Double exponential | 0.806 | 0.00310 | -0.25% | no |
| Single exponential | AsLS | 0.772 | 0.00593 | +0.27% | no |
| Double exponential | Double exponential | 0.797 | 0.00318 | -0.24% | no |
| Double exponential | AsLS | 0.510 | 0.00879 | +0.24% | no |
| Large transients | Double exponential | 0.989 | 0.00363 | -0.23% | yes |
| Large transients | AsLS | 0.954 | 0.00817 | +0.36% | yes |
| Slow drift | Double exponential | 0.184 | 0.02117 | -0.08% | no |
| Slow drift | AsLS | 0.583 | 0.00798 | +0.40% | no |
| Motion without control | Double exponential | 0.142 | 0.02846 | -36.85% | limitation |
| Motion without control | AsLS | 0.132 | 0.04857 | -34.44% | limitation |
| Event-locked artefact | Double exponential | 0.951 | 0.00618 | +132.85% | limitation |
| Event-locked artefact | AsLS | 0.823 | 0.01095 | +134.12% | limitation |

Values are medians over 20 seeds. “Pass” requires correlation ≥0.90, RMSE
≤0.015 dF/F and absolute event-amplitude bias ≤20%.

## Interpretation

Both estimators preserve event amplitude exceptionally well in the four bleaching
scenarios. The frozen samplewise-correlation threshold nevertheless rejects the
three small-transient cases because the corrected trace still contains acquisition
noise: baseline correction is not denoising. This reveals that v0.1 partly
conflates two jobs. The threshold remains unchanged in the frozen artifact.

The limitation cases are more important. Slow baseline estimation cannot remove
oscillatory motion without another source of information. Worse, an event-locked
artefact can produce a very high correlation with the true neural waveform while
inflating event amplitude by about 133%. Correlation alone is therefore not a
validity diagnostic.

Double-exponential fitting is a defensible compromise between under- and
over-flexible bleaching models, but subtraction versus division encodes different
assumptions about autofluorescence and indicator bleaching
([Simpson et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/)). AsLS
originated as a smooth lower-envelope method for spectroscopy; its transfer to
photometry is experimental and its smoothness parameter is sampling-rate dependent
([Eilers & Boelens, 2005](https://www.researchgate.net/publication/228961729_Baseline_Correction_with_Asymmetric_Least_Squares_Smoothing)).

## Decision

The two methods remain available as explicitly experimental preprocessing APIs,
with full provenance and signal retention. They are not yet added to the typed
multiverse pipeline. A v0.2 benchmark should separate baseline error from residual
high-frequency noise, test subtraction and division as distinct estimands, and
vary sampling rate before either method is promoted.
