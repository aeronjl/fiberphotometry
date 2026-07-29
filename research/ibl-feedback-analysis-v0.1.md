# Descriptive IBL feedback analysis v0.1

This is an end-to-end workflow demonstration on four public IBL animals, not a
confirmatory biological result. The specification was frozen before calculating
the contrast, but after inspecting session availability, outcome labels, and
trial counts. It is therefore post hoc and is not a preregistration.

## Question and execution

The analysis compares each animal's mean acquired-sample DMS fluorescence change
on correct versus incorrect trials. Change is the mean from 0 to 0.5 seconds
after feedback minus the mean from -0.5 to 0 seconds. The event-level values are
aggregated within animal before a descriptive paired-t interval is calculated.

- 2,507 observations: 1,850 correct and 657 incorrect
- four sessions from four animals
- correct-minus-incorrect estimate: 0.0000960 fluorescence units
- 95% confidence interval: [-0.0000268, 0.0002188]
- paired-t p-value: 0.0886

The executable result, plan, package version, execution time, and input
fingerprint are retained in
[`benchmarks/ibl-feedback-analysis-v0.1.json`](https://github.com/aeronjl/fipha/blob/main/benchmarks/ibl-feedback-analysis-v0.1.json).
The frozen specification is
[`benchmarks/protocol-ibl-feedback-v0.1.md`](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-ibl-feedback-v0.1.md).

## Interpretation boundary

The interval includes zero and the sample contains only four independent
animals. Correctness was observed, not randomized, and may covary with stimulus,
movement, expectation, trial history, and other features. The result neither
establishes a feedback effect nor validates the Gaussian assumption for four
animal-level differences. Its value is demonstrating that the public-data path
can produce an explicit estimand, design-aware aggregation, executable plan, and
auditable result without treating trials as independent animals.
