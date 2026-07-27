# Event-kernel uncertainty and diagnostics protocol v0.1

Status: **frozen before implementation and public-data rerun** (27 July 2026)

## Product question

Can the experimental event-kernel workflow show how strongly pooled kernels depend
on independent animals and whether held-out residuals invalidate a simple Gaussian
FIR description, without presenting naive sample-level standard errors?

## Frozen uncertainty estimand

For every fitted event-lag coefficient, compute delete-one-group jackknife
replicates of the pooled ridge estimator. A group is the declared validation unit:
animal by default or session when explicitly requested. Every replicate:

1. removes the complete group and all of its sessions;
2. rebuilds no event across a recording boundary;
3. uses the ridge penalty selected by the full grouped cross-validation unchanged;
4. refits predictor scaling on the retained groups;
5. retains the omitted group identity.

Report the full-data coefficient, the conventional jackknife bias-corrected
estimate, jackknife standard error, and pointwise two-sided 95% Student interval
with `groups - 1` degrees of freedom. The variance is
`(G - 1) / G` times the sum of squared deviations of delete-one estimates from
their mean.

These intervals describe group influence on a regularized pooled estimator. They
are conditional on the penalty and design selected from the same data, do not
provide selective-inference validity, and are not simultaneous waveform bands.
With six animals they are sensitivity intervals, not a promotion-grade population
analysis. Cross-validation-based model selection can affect uncertainty; this is
explicitly retained as a limitation rather than silently ignored.

## Frozen residual diagnostics

Generate one prediction for every finite observation using a model that excluded
its complete group at the selected full-data penalty. For each held-out group,
report:

- observation and session counts;
- held-out R², RMSE, MAE, residual mean, and residual standard deviation;
- lag-1 residual autocorrelation;
- Durbin–Watson ratio.

Lagged calculations restart at every session boundary. No adjacent pair may cross
recordings. Autocorrelation and Durbin–Watson are descriptive diagnostics only:
do not attach p-values or treat threshold crossing as a formal model-selection
rule. Also report pooled out-of-fold summaries across all groups, preserving the
group-level table so one long recording cannot conceal another animal's failure.

## Frozen validation fixtures

1. The existing independent-noise simulation must continue recovering planted
   overlapping kernels and continuous-covariate effects.
2. Jackknife outputs must contain every group exactly once, finite ordered
   intervals, and planted coefficients inside the pointwise interval at declared
   representative lags in the deterministic heterogeneous fixture.
3. An autoregressive-noise fixture must show materially larger held-out residual
   lag-1 autocorrelation and lower Durbin–Watson than an otherwise matched
   independent-noise fixture.
4. A two-session animal fixture must prove that diagnostics never form lagged
   residual pairs across session boundaries.
5. Sparse and dense-scale behavior must remain numerically covered by the current
   recovery tests, and the complete public workflow must remain deterministic.

These fixtures validate implementation behavior, not repeated-sampling 95%
coverage. Formal coverage calibration across animal count, heterogeneity,
regularization and event density remains a promotion gate.

## Frozen public-data rerun

Rerun the committed DANDI:000971 two-region model without changing its cohort,
preprocessing, events, lag windows, penalty grid, analysis support or group folds.
Append the new uncertainty and diagnostic fields to a v0.2 evidence artifact while
retaining the original v0.1 result unchanged.

Lead with held-out residual behavior and interval width. Do not use the intervals
to declare significance, a DMS/DLS difference, reward-prediction error coding, or
causality. No animal may be removed in response to its diagnostic result.

## Sources available at freeze time

- Lipsitz et al. (1994), [jackknife variance for clustered estimating equations](https://pubmed.ncbi.nlm.nih.gov/7981404/).
- Zhang et al. (2024), [weighted delete-one-cluster jackknife framework](https://pmc.ncbi.nlm.nih.gov/articles/PMC10959512/).
- Markovic et al. (2017), [selective inference with cross-validation](https://arxiv.org/abs/1703.06559).
- Atanasov et al. (2025), [ridge cross-validation with correlated samples](https://proceedings.mlr.press/v267/atanasov25a.html).
- Ali (1984), [Durbin–Watson distribution and power](https://doi.org/10.1093/biomet/71.2.253).
