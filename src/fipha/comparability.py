"""Outcome-blind across-session comparability checks for longitudinal handoff."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

ComparabilitySeverity = Literal["warning", "error"]
ComparabilityStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class SessionComparabilityRecord:
    """Declared identity and outcome-blind QC summaries for one session series."""

    subject: str
    session: str
    series_id: str
    sensor: str
    site: str
    output_variable: str
    unit: str
    preprocessing_fingerprint: str
    finite_fraction: float
    event_coverage_fraction: float | None = None
    baseline_median: float | None = None
    reference_correlation: float | None = None
    sampling_rate_hz: float | None = None
    acquisition_system: str | None = None

    def __post_init__(self) -> None:
        required = (
            "subject",
            "session",
            "series_id",
            "sensor",
            "site",
            "output_variable",
            "unit",
            "preprocessing_fingerprint",
        )
        for name in required:
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        _validate_fraction(self.finite_fraction, "finite_fraction")
        if self.event_coverage_fraction is not None:
            _validate_fraction(
                self.event_coverage_fraction,
                "event_coverage_fraction",
            )
        if self.baseline_median is not None and (
            not np.isfinite(self.baseline_median) or self.baseline_median <= 0
        ):
            raise ValueError("baseline_median must be finite and positive")
        if self.reference_correlation is not None and (
            not np.isfinite(self.reference_correlation)
            or not -1 <= self.reference_correlation <= 1
        ):
            raise ValueError("reference_correlation must lie between -1 and 1")
        if self.sampling_rate_hz is not None and (
            not np.isfinite(self.sampling_rate_hz) or self.sampling_rate_hz <= 0
        ):
            raise ValueError("sampling_rate_hz must be finite and positive")
        if self.acquisition_system is not None:
            acquisition = str(self.acquisition_system).strip()
            if not acquisition:
                raise ValueError("acquisition_system must be non-empty when provided")
            object.__setattr__(self, "acquisition_system", acquisition)


@dataclass(frozen=True)
class SessionComparabilitySpec:
    """Prospective operational thresholds for a longitudinal preflight."""

    minimum_finite_fraction_error: float = 0.80
    minimum_finite_fraction_warning: float = 0.95
    minimum_event_coverage_error: float = 0.50
    minimum_event_coverage_warning: float = 0.80
    maximum_baseline_fold_change_warning: float = 2.0
    maximum_baseline_fold_change_error: float = 4.0
    maximum_reference_correlation_range_warning: float = 0.30
    maximum_reference_correlation_range_error: float = 0.60
    maximum_sampling_rate_ratio_warning: float = 1.20
    maximum_sampling_rate_ratio_error: float = 2.0
    require_same_preprocessing: bool = True
    require_event_coverage: bool = False
    require_baseline_metric: bool = False
    require_reference_metric: bool = False
    require_sampling_rate: bool = False
    minimum_sessions: int = 2
    schema_version: str = "1"

    def __post_init__(self) -> None:
        _validate_nested_minimums(
            self.minimum_finite_fraction_error,
            self.minimum_finite_fraction_warning,
            "finite fraction",
        )
        _validate_nested_minimums(
            self.minimum_event_coverage_error,
            self.minimum_event_coverage_warning,
            "event coverage",
        )
        _validate_nested_maximums(
            self.maximum_baseline_fold_change_warning,
            self.maximum_baseline_fold_change_error,
            "baseline fold change",
            minimum=1.0,
        )
        _validate_nested_maximums(
            self.maximum_reference_correlation_range_warning,
            self.maximum_reference_correlation_range_error,
            "reference-correlation range",
            minimum=0.0,
            maximum=2.0,
        )
        _validate_nested_maximums(
            self.maximum_sampling_rate_ratio_warning,
            self.maximum_sampling_rate_ratio_error,
            "sampling-rate ratio",
            minimum=1.0,
        )
        if self.minimum_sessions < 2:
            raise ValueError("minimum_sessions must be at least two")


@dataclass(frozen=True)
class SessionComparabilityIssue:
    """One actionable reason a longitudinal series warns or fails."""

    severity: ComparabilitySeverity
    code: str
    subject: str
    series_id: str
    sessions: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class SessionComparabilityGroup:
    """Computed across-session diagnostics for one subject and logical series."""

    subject: str
    series_id: str
    sessions: tuple[str, ...]
    minimum_finite_fraction: float
    minimum_event_coverage_fraction: float | None
    baseline_fold_change: float | None
    reference_correlation_range: float | None
    sampling_rate_ratio: float | None
    status: ComparabilityStatus


@dataclass(frozen=True)
class SessionComparabilityReport:
    """Fingerprintable preflight evidence for a Behavio handoff."""

    records: tuple[SessionComparabilityRecord, ...]
    spec: SessionComparabilitySpec
    groups: tuple[SessionComparabilityGroup, ...]
    issues: tuple[SessionComparabilityIssue, ...]
    status: ComparabilityStatus
    input_fingerprint: str
    schema_version: str = "1"

    @property
    def session_keys(self) -> frozenset[tuple[str, str]]:
        """Return subject/session pairs covered by the preflight."""

        return frozenset((record.subject, record.session) for record in self.records)

    def require_ready(self, *, allow_warnings: bool = True) -> None:
        """Refuse failed reports and optionally warning-bearing reports."""

        if self.status == "fail":
            codes = sorted(
                {issue.code for issue in self.issues if issue.severity == "error"}
            )
            raise ValueError("session comparability failed: " + ", ".join(codes))
        if self.status == "warning" and not allow_warnings:
            codes = sorted({issue.code for issue in self.issues})
            raise ValueError("session comparability has warnings: " + ", ".join(codes))

    def to_json(self) -> str:
        """Serialize complete comparability evidence deterministically."""

        return json.dumps(
            {
                "artifact_type": "session_comparability",
                "schema_version": self.schema_version,
                "status": self.status,
                "input_fingerprint": self.input_fingerprint,
                "spec": asdict(self.spec),
                "records": [asdict(record) for record in self.records],
                "groups": [asdict(group) for group in self.groups],
                "issues": [asdict(issue) for issue in self.issues],
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def assess_session_comparability(
    records: Sequence[SessionComparabilityRecord],
    spec: SessionComparabilitySpec | None = None,
) -> SessionComparabilityReport:
    """Assess longitudinal comparability without inspecting neural outcomes."""

    chosen = spec or SessionComparabilitySpec()
    ordered = tuple(
        sorted(records, key=lambda item: (item.subject, item.series_id, item.session))
    )
    if not ordered:
        raise ValueError("session comparability requires at least one record")
    keys = [(item.subject, item.session, item.series_id) for item in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError("subject/session/series_id records must be unique")

    grouped: dict[tuple[str, str], list[SessionComparabilityRecord]] = {}
    for record in ordered:
        grouped.setdefault((record.subject, record.series_id), []).append(record)

    all_groups: list[SessionComparabilityGroup] = []
    all_issues: list[SessionComparabilityIssue] = []
    for (subject, series_id), members in sorted(grouped.items()):
        group, issues = _assess_group(subject, series_id, members, chosen)
        all_groups.append(group)
        all_issues.extend(issues)

    issues_tuple = tuple(all_issues)
    status = _status_from_issues(issues_tuple)
    payload = {
        "records": [asdict(record) for record in ordered],
        "spec": asdict(chosen),
        "groups": [asdict(group) for group in all_groups],
        "issues": [asdict(issue) for issue in issues_tuple],
        "schema_version": "1",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return SessionComparabilityReport(
        records=ordered,
        spec=chosen,
        groups=tuple(all_groups),
        issues=issues_tuple,
        status=status,
        input_fingerprint=fingerprint,
    )


def _assess_group(
    subject: str,
    series_id: str,
    members: Sequence[SessionComparabilityRecord],
    spec: SessionComparabilitySpec,
) -> tuple[SessionComparabilityGroup, tuple[SessionComparabilityIssue, ...]]:
    sessions = tuple(item.session for item in members)
    issues: list[SessionComparabilityIssue] = []

    if len(members) < spec.minimum_sessions:
        issues.append(
            _issue(
                "error",
                "insufficient_sessions",
                subject,
                series_id,
                sessions,
                f"series has {len(members)} session(s); "
                f"requires {spec.minimum_sessions}",
            )
        )

    identity_fields = (
        ("sensor", "sensor_changed"),
        ("site", "site_changed"),
        ("output_variable", "output_variable_changed"),
        ("unit", "unit_changed"),
    )
    for field, code in identity_fields:
        values = {str(getattr(item, field)) for item in members}
        if len(values) > 1:
            issues.append(
                _issue(
                    "error",
                    code,
                    subject,
                    series_id,
                    sessions,
                    f"{field} differs across sessions: {sorted(values)}",
                )
            )
    preprocessing = {item.preprocessing_fingerprint for item in members}
    if len(preprocessing) > 1:
        issues.append(
            _issue(
                "error" if spec.require_same_preprocessing else "warning",
                "preprocessing_changed",
                subject,
                series_id,
                sessions,
                "preprocessing fingerprints differ across sessions",
            )
        )
    acquisition = {
        item.acquisition_system
        for item in members
        if item.acquisition_system is not None
    }
    if len(acquisition) > 1:
        issues.append(
            _issue(
                "warning",
                "acquisition_system_changed",
                subject,
                series_id,
                sessions,
                f"acquisition system differs across sessions: {sorted(acquisition)}",
            )
        )

    for item in members:
        severity = _minimum_severity(
            item.finite_fraction,
            spec.minimum_finite_fraction_error,
            spec.minimum_finite_fraction_warning,
        )
        if severity is not None:
            issues.append(
                _issue(
                    severity,
                    "low_finite_fraction",
                    subject,
                    series_id,
                    (item.session,),
                    f"finite fraction is {item.finite_fraction:.3f}",
                )
            )
        if item.event_coverage_fraction is None:
            issues.append(
                _issue(
                    "error" if spec.require_event_coverage else "warning",
                    "event_coverage_missing",
                    subject,
                    series_id,
                    (item.session,),
                    "event coverage was not supplied",
                )
            )
        else:
            severity = _minimum_severity(
                item.event_coverage_fraction,
                spec.minimum_event_coverage_error,
                spec.minimum_event_coverage_warning,
            )
            if severity is not None:
                issues.append(
                    _issue(
                        severity,
                        "low_event_coverage",
                        subject,
                        series_id,
                        (item.session,),
                        f"event coverage is {item.event_coverage_fraction:.3f}",
                    )
                )

    baseline, baseline_issues = _ratio_diagnostic(
        members,
        "baseline_median",
        "baseline_metric_missing",
        "baseline_fold_change",
        spec.maximum_baseline_fold_change_warning,
        spec.maximum_baseline_fold_change_error,
        spec.require_baseline_metric,
        subject,
        series_id,
        sessions,
    )
    issues.extend(baseline_issues)
    sampling, sampling_issues = _ratio_diagnostic(
        members,
        "sampling_rate_hz",
        "sampling_rate_missing",
        "sampling_rate_ratio",
        spec.maximum_sampling_rate_ratio_warning,
        spec.maximum_sampling_rate_ratio_error,
        spec.require_sampling_rate,
        subject,
        series_id,
        sessions,
    )
    issues.extend(sampling_issues)

    correlations = [
        item.reference_correlation
        for item in members
        if item.reference_correlation is not None
    ]
    correlation_range: float | None = None
    if len(correlations) != len(members):
        issues.append(
            _issue(
                "error" if spec.require_reference_metric else "warning",
                "reference_metric_missing",
                subject,
                series_id,
                sessions,
                "reference correlation is missing for one or more sessions",
            )
        )
    if len(correlations) >= 2:
        correlation_range = float(max(correlations) - min(correlations))
        severity = _maximum_severity(
            correlation_range,
            spec.maximum_reference_correlation_range_warning,
            spec.maximum_reference_correlation_range_error,
        )
        if severity is not None:
            issues.append(
                _issue(
                    severity,
                    "reference_correlation_range",
                    subject,
                    series_id,
                    sessions,
                    f"reference-correlation range is {correlation_range:.3f}",
                )
            )

    event_values = [
        item.event_coverage_fraction
        for item in members
        if item.event_coverage_fraction is not None
    ]
    group_status = _status_from_issues(tuple(issues))
    return (
        SessionComparabilityGroup(
            subject=subject,
            series_id=series_id,
            sessions=sessions,
            minimum_finite_fraction=min(item.finite_fraction for item in members),
            minimum_event_coverage_fraction=(
                min(event_values) if event_values else None
            ),
            baseline_fold_change=baseline,
            reference_correlation_range=correlation_range,
            sampling_rate_ratio=sampling,
            status=group_status,
        ),
        tuple(issues),
    )


def _ratio_diagnostic(
    members: Sequence[SessionComparabilityRecord],
    field: str,
    missing_code: str,
    range_code: str,
    warning: float,
    error: float,
    required: bool,
    subject: str,
    series_id: str,
    sessions: tuple[str, ...],
) -> tuple[float | None, tuple[SessionComparabilityIssue, ...]]:
    values = [
        float(value) for item in members if (value := getattr(item, field)) is not None
    ]
    issues: list[SessionComparabilityIssue] = []
    if len(values) != len(members):
        issues.append(
            _issue(
                "error" if required else "warning",
                missing_code,
                subject,
                series_id,
                sessions,
                f"{field} is missing for one or more sessions",
            )
        )
    ratio = float(max(values) / min(values)) if len(values) >= 2 else None
    if ratio is not None:
        severity = _maximum_severity(ratio, warning, error)
        if severity is not None:
            issues.append(
                _issue(
                    severity,
                    range_code,
                    subject,
                    series_id,
                    sessions,
                    f"{field} maximum/minimum ratio is {ratio:.3f}",
                )
            )
    return ratio, tuple(issues)


def _issue(
    severity: ComparabilitySeverity,
    code: str,
    subject: str,
    series_id: str,
    sessions: tuple[str, ...],
    message: str,
) -> SessionComparabilityIssue:
    return SessionComparabilityIssue(
        severity=severity,
        code=code,
        subject=subject,
        series_id=series_id,
        sessions=sessions,
        message=message,
    )


def _minimum_severity(
    value: float,
    error: float,
    warning: float,
) -> ComparabilitySeverity | None:
    if value < error:
        return "error"
    if value < warning:
        return "warning"
    return None


def _maximum_severity(
    value: float,
    warning: float,
    error: float,
) -> ComparabilitySeverity | None:
    if value > error:
        return "error"
    if value > warning:
        return "warning"
    return None


def _status_from_issues(
    issues: Sequence[SessionComparabilityIssue],
) -> ComparabilityStatus:
    if any(issue.severity == "error" for issue in issues):
        return "fail"
    if issues:
        return "warning"
    return "pass"


def _validate_fraction(value: float, name: str) -> None:
    if not np.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must lie between zero and one")


def _validate_nested_minimums(error: float, warning: float, name: str) -> None:
    _validate_fraction(error, f"{name} error threshold")
    _validate_fraction(warning, f"{name} warning threshold")
    if error > warning:
        raise ValueError(f"{name} error threshold must not exceed warning threshold")


def _validate_nested_maximums(
    warning: float,
    error: float,
    name: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> None:
    if not np.isfinite(warning) or not np.isfinite(error):
        raise ValueError(f"{name} thresholds must be finite")
    if warning < minimum or error < warning:
        raise ValueError(
            f"{name} thresholds must satisfy {minimum} <= warning <= error"
        )
    if maximum is not None and error > maximum:
        raise ValueError(f"{name} error threshold must not exceed {maximum}")
