# Scalar mixed-model sensitivity summary v0.1

Enable the optional secondary summary with:

```toml
[analysis.inference]
intent = "exploratory"
randomized = false
scalar_mixed_model = true
acknowledged_assumptions = [
  "approximately_gaussian_unit_differences",
  "complete_pairs",
  "estimand_matches_question",
  "independent_aggregation_units",
]
```

Requires the `stats` extra; see [Install](getting-started/install.md).
The CLI then writes `mixed-model.json` and a standalone `mixed-model.html` evidence
view, fingerprints both in the manifest, and embeds the JSON in NWB export.

The model uses an event-level fixed contrast, animal random intercept and
condition slope, and a nested session random intercept when more than one session
occurs within at least one animal. If that session component is not estimable it
is omitted with an explicit warning. The optimizer, REML policy, convergence,
normal-theory interval, variance estimates, engine version, and input hash remain
machine-readable.

This is a sensitivity estimand. It does not replace the primary animal-level
analysis or guarantee the same weighting of sessions and trials. Disagreement is
reported for scientific inspection.

The frozen [v0.2 parity fixture](https://github.com/aeronjl/fipha/blob/main/benchmarks/mixed-model-parity-v0.2.json)
matches direct statsmodels estimates, standard errors, and confidence intervals in
unbalanced-event and unbalanced-nested-session scenarios. This validates numerical
plumbing, not interval coverage or universal model adequacy. Statsmodels documents
the random-effects and variance-component formulation and notes that its standard
fixed-effect confidence intervals are normal-theory intervals:

- <https://www.statsmodels.org/stable/generated/statsmodels.formula.api.mixedlm.html>
- <https://www.statsmodels.org/stable/generated/statsmodels.regression.mixed_linear_model.MixedLMResults.html>
