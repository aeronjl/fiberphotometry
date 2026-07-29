"""Explicit scalar mixed-model sensitivity summaries via statsmodels."""

from __future__ import annotations

import hashlib
import html
import json
import warnings
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version

import numpy as np

from fipha.design import ObservationTable, StudyDesign, Unit, validate_design
from fipha.inference import Estimand


@dataclass(frozen=True)
class ScalarMixedModelSpec:
    nested_random_intercept_unit: str | None = "session"
    random_condition_slope: bool = True
    confidence: float = 0.95
    reml: bool = True
    optimizer: str = "lbfgs"
    role: str = "sensitivity_analysis"
    schema_version: str = "1"


@dataclass(frozen=True)
class ScalarMixedModelResult:
    spec: ScalarMixedModelSpec
    estimate: float
    standard_error: float
    confidence_interval: tuple[float, float]
    p_value: float
    converged: bool
    observations: int
    groups: int
    nested_units: int | None
    group_intercept_variance: float
    group_condition_slope_variance: float | None
    intercept_slope_covariance: float | None
    nested_intercept_variance: float | None
    residual_variance: float
    engine: str
    engine_version: str
    input_fingerprint: str
    warnings: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_html(self) -> str:
        """Render a compact standalone sensitivity report."""
        warning_items = (
            "".join(f"<li>{html.escape(value)}</li>" for value in self.warnings)
            or "<li>None recorded</li>"
        )
        lower, upper = self.confidence_interval
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Scalar mixed-model sensitivity summary</title>
<style>body{{font:16px system-ui;max-width:780px;margin:3rem auto;padding:0 1rem}}
table{{border-collapse:collapse}}
th,td{{padding:.5rem;border:1px solid #bbb;text-align:left}}
.caution{{background:#fff3cd;padding:1rem;border-left:4px solid #b58105}}</style></head>
<body><h1>Scalar mixed-model sensitivity summary</h1>
<p class="caution"><strong>Secondary sensitivity estimand.</strong> This event-level
model does not replace the primary animal-level analysis.</p>
<table><tr><th>Estimate</th><td>{self.estimate:.8g}</td></tr>
<tr><th>{self.spec.confidence:.0%} interval</th><td>[{lower:.8g}, {upper:.8g}]</td></tr>
<tr><th>Standard error</th><td>{self.standard_error:.8g}</td></tr>
<tr><th>p-value</th><td>{self.p_value:.8g}</td></tr>
<tr><th>Converged</th><td>{str(self.converged).lower()}</td></tr>
<tr><th>Groups / observations</th><td>{self.groups} / {self.observations}</td></tr>
<tr><th>Engine</th><td>{html.escape(self.engine)}
{html.escape(self.engine_version)}</td></tr>
</table><h2>Warnings</h2><ul>{warning_items}</ul>
<p>Input fingerprint: <code>{self.input_fingerprint}</code></p></body></html>"""


def fit_scalar_mixed_model(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    spec: ScalarMixedModelSpec | None = None,
) -> ScalarMixedModelResult:
    """Fit a two-level fixed contrast with declared nested random intercepts."""
    spec = spec or ScalarMixedModelSpec()
    validate_design(table, design).raise_for_errors()
    if spec.schema_version != "1":
        raise ValueError("unsupported scalar mixed-model schema version")
    if not 0 < spec.confidence < 1:
        raise ValueError("mixed-model confidence must lie between zero and one")
    if spec.role != "sensitivity_analysis":
        raise ValueError("scalar mixed models are currently sensitivity analyses")
    try:
        import pandas as pd  # type: ignore[import-untyped]
        import statsmodels.formula.api as smf  # type: ignore[import-untyped]
    except ImportError as error:
        raise ValueError(
            "scalar mixed models require the optional 'stats' dependencies"
        ) from error

    factor = next(
        item for item in design.factors if item.name == estimand.contrast.factor
    )
    group = next(
        item for item in design.units if item.name == estimand.aggregation_unit
    )
    labels = np.asarray(table.values(factor.column), dtype=object)
    outcome = np.asarray(table.values(estimand.outcome), dtype=float)
    groups = np.asarray(table.values(group.column), dtype=object)
    keep = np.isfinite(outcome) & np.isin(
        labels, (estimand.contrast.denominator, estimand.contrast.numerator)
    )
    group_values = groups[keep].astype(str)
    frame_data: dict[str, object] = {
        "outcome": outcome[keep],
        "condition": (labels[keep] == estimand.contrast.numerator).astype(float),
        "group": group_values,
    }
    model_warnings = []
    nested_count: int | None = None
    variance_components = None
    if spec.nested_random_intercept_unit is not None:
        nested = _nested_unit(design, spec.nested_random_intercept_unit, group.name)
        nested_values = np.asarray(table.values(nested.column), dtype=object)[
            keep
        ].astype(str)
        frame_data["nested"] = nested_values
        nested_count = len(set(nested_values.tolist()))
        per_group = {
            value: len(set(nested_values[group_values == value].tolist()))
            for value in set(group_values.tolist())
        }
        if any(count > 1 for count in per_group.values()):
            variance_components = {"nested": "0 + C(nested)"}
        else:
            model_warnings.append(
                "nested_random_intercept_not_estimable_one_nested_unit_per_group"
            )
            nested_count = None
    frame = pd.DataFrame(frame_data)
    if frame["group"].nunique() < 2:
        raise ValueError("scalar mixed models require at least two aggregation groups")
    if set(frame["condition"].unique()) != {0.0, 1.0}:
        raise ValueError("scalar mixed models require both contrast levels")
    model = smf.mixedlm(
        "outcome ~ condition",
        frame,
        groups=frame["group"],
        re_formula="1 + condition" if spec.random_condition_slope else "1",
        vc_formula=variance_components,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted = model.fit(reml=spec.reml, method=spec.optimizer, disp=False)
    model_warnings.extend(str(item.message) for item in caught)
    interval = fitted.conf_int(alpha=1 - spec.confidence).loc["condition"]
    nested_variance = (
        float(fitted.vcomp[0])
        if variance_components is not None and len(fitted.vcomp)
        else None
    )
    slope_variance = (
        float(fitted.cov_re.iloc[1, 1]) if spec.random_condition_slope else None
    )
    intercept_slope = (
        float(fitted.cov_re.iloc[0, 1]) if spec.random_condition_slope else None
    )
    return ScalarMixedModelResult(
        spec,
        float(fitted.fe_params["condition"]),
        float(fitted.bse_fe["condition"]),
        (float(interval.iloc[0]), float(interval.iloc[1])),
        float(fitted.pvalues["condition"]),
        bool(fitted.converged),
        int(fitted.nobs),
        int(frame["group"].nunique()),
        nested_count,
        float(fitted.cov_re.iloc[0, 0]),
        slope_variance,
        intercept_slope,
        nested_variance,
        float(fitted.scale),
        "statsmodels.MixedLM",
        _statsmodels_version(),
        _fingerprint(table, design, estimand, spec),
        tuple(model_warnings),
    )


def _nested_unit(design: StudyDesign, name: str, group: str) -> Unit:
    declared = {unit.name: unit for unit in design.units}
    if name not in declared:
        raise ValueError("nested random-intercept unit is not declared")
    current = declared[name]
    visited = set()
    while current.name != group:
        if current.name in visited or current.nested_within is None:
            raise ValueError("nested random-intercept unit must lie within group unit")
        visited.add(current.name)
        current = declared[current.nested_within]
    return declared[name]


def _fingerprint(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    spec: ScalarMixedModelSpec,
) -> str:
    payload = {
        "table": table.columns,
        "design": json.loads(design.to_json()),
        "estimand": asdict(estimand),
        "spec": asdict(spec),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _statsmodels_version() -> str:
    try:
        return version("statsmodels")
    except PackageNotFoundError:
        return "unknown"
