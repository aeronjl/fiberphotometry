"""Semantic reproducibility comparisons across verified project evidence bundles."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from fipha.results import ProjectEvidenceBundle

DifferenceCategory = Literal[
    "configuration",
    "specification",
    "data",
    "quality",
    "outcome",
    "execution",
    "provenance",
]


@dataclass(frozen=True)
class EvidenceDifference:
    """One typed semantic difference between evidence records."""

    category: DifferenceCategory
    path: str
    left: Any
    right: Any


@dataclass(frozen=True)
class BundleComparison:
    """Byte, project, and scientific agreement for two evidence bundles."""

    left_source: str
    right_source: str
    left_kind: str
    right_kind: str
    comparable: bool
    byte_identical: bool | None
    same_project: bool
    scientifically_equivalent: bool
    absolute_tolerance: float
    relative_tolerance: float
    differences: tuple[EvidenceDifference, ...]
    truncated: bool = False
    artifact_type: Literal["evidence_bundle_comparison"] = "evidence_bundle_comparison"
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        status = "reproduced" if self.scientifically_equivalent else "different"
        lines = [
            "# Evidence bundle comparison",
            "",
            f"**Scientific result:** {status}",
            "",
            f"- Left: `{self.left_source}` ({self.left_kind})",
            f"- Right: `{self.right_source}` ({self.right_kind})",
            f"- Comparable: {str(self.comparable).lower()}",
            f"- Same project fingerprint: {str(self.same_project).lower()}",
            f"- Byte-identical: {_optional_bool(self.byte_identical)}",
            f"- Tolerances: absolute {self.absolute_tolerance:g}, "
            f"relative {self.relative_tolerance:g}",
            "",
            "## Differences",
            "",
        ]
        if not self.differences:
            lines.append("No semantic or provenance differences detected.")
        else:
            lines.extend(
                (
                    "| Category | Path | Left | Right |",
                    "| --- | --- | --- | --- |",
                )
            )
            lines.extend(
                f"| {item.category} | `{item.path}` | "
                f"{_markdown_value(item.left)} | {_markdown_value(item.right)} |"
                for item in self.differences
            )
        if self.truncated:
            lines.extend(("", "_Difference list truncated at the requested limit._"))
        return "\n".join(lines) + "\n"

    def write_markdown(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.write_text(self.to_markdown(), encoding="utf-8")
        return destination.resolve()


def compare_project_evidence(
    left: ProjectEvidenceBundle,
    right: ProjectEvidenceBundle,
    *,
    absolute_tolerance: float = 0.0,
    relative_tolerance: float = 0.0,
    max_differences: int = 200,
) -> BundleComparison:
    """Compare specifications and outcomes without conflating volatile provenance."""
    _validate_comparison_options(
        absolute_tolerance, relative_tolerance, max_differences
    )
    collector = _DifferenceCollector(
        absolute_tolerance, relative_tolerance, max_differences
    )
    same_project = left.project_sha256 == right.project_sha256
    if not same_project:
        collector.add(
            "configuration",
            "project_sha256",
            left.project_sha256,
            right.project_sha256,
        )
    if left.status != right.status:
        collector.add("execution", "status", left.status, right.status)
    comparable = left.kind == right.kind and left.kind != "incomplete"
    if left.kind != right.kind:
        collector.add("specification", "kind", left.kind, right.kind)
    elif left.kind == "analysis":
        _compare_analysis(left, right, collector)
    elif left.kind == "multiverse":
        _compare_multiverse(left, right, collector)
    byte_identical = _byte_identical(left, right)
    substantive = [
        item for item in collector.differences if item.category != "provenance"
    ]
    return BundleComparison(
        str(left.source),
        str(right.source),
        left.kind,
        right.kind,
        comparable,
        byte_identical,
        same_project,
        comparable and not substantive and not collector.truncated,
        absolute_tolerance,
        relative_tolerance,
        tuple(collector.differences),
        collector.truncated,
    )


def _compare_analysis(
    left: ProjectEvidenceBundle,
    right: ProjectEvidenceBundle,
    collector: _DifferenceCollector,
) -> None:
    left_record = left.analysis
    right_record = right.analysis
    if left_record is None or right_record is None:
        collector.add("execution", "analysis", left_record, right_record)
        return
    analysis_fields: tuple[tuple[str, DifferenceCategory], ...] = (
        ("spec", "specification"),
        ("preprocessing", "specification"),
        ("configuration_sha256", "configuration"),
        ("data_summary", "data"),
        ("event_coverage", "data"),
        ("quality_reports", "quality"),
        ("processing_lineage", "quality"),
        ("timecourse", "outcome"),
        ("blocked_by", "execution"),
    )
    for key, category in analysis_fields:
        collector.compare(category, key, left_record.get(key), right_record.get(key))
    left_outcome = left_record.get("analysis")
    right_outcome = right_record.get("analysis")
    collector.compare(
        "outcome",
        "analysis",
        _without_provenance(left_outcome),
        _without_provenance(right_outcome),
    )
    for key in ("executed_at_utc", "package_version"):
        collector.compare(
            "provenance",
            f"analysis.{key}",
            _mapping_value(left_outcome, key),
            _mapping_value(right_outcome, key),
        )


def _compare_multiverse(
    left: ProjectEvidenceBundle,
    right: ProjectEvidenceBundle,
    collector: _DifferenceCollector,
) -> None:
    left_record = left.multiverse
    right_record = right.multiverse
    if left_record is None or right_record is None:
        collector.add("execution", "multiverse", left_record, right_record)
        return
    collector.compare(
        "specification", "spec", left_record.get("spec"), right_record.get("spec")
    )
    collector.compare(
        "outcome",
        "leave_one_out",
        left_record.get("leave_one_out"),
        right_record.get("leave_one_out"),
    )
    _compare_universes(left_record, right_record, collector)
    collector.compare(
        "outcome",
        "robustness_summary",
        left.robustness_summary,
        right.robustness_summary,
    )


def _compare_universes(left: Any, right: Any, collector: _DifferenceCollector) -> None:
    left_universes = _universes_by_id(left)
    right_universes = _universes_by_id(right)
    collector.compare(
        "specification",
        "universes.ids",
        sorted(left_universes),
        sorted(right_universes),
    )
    for identifier in sorted(left_universes.keys() & right_universes.keys()):
        left_universe = left_universes[identifier]
        right_universe = right_universes[identifier]
        universe_fields: tuple[tuple[str, DifferenceCategory], ...] = (
            ("choices", "specification"),
            ("pipeline", "specification"),
            ("status", "execution"),
            ("estimate", "outcome"),
            ("confidence_interval", "outcome"),
            ("p_value", "outcome"),
            ("blocked_by", "execution"),
            ("error", "execution"),
            ("is_reference", "specification"),
        )
        for key, category in universe_fields:
            collector.compare(
                category,
                f"universes.{identifier}.{key}",
                left_universe.get(key),
                right_universe.get(key),
            )


def _universes_by_id(record: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(record, Mapping):
        return {}
    universes = record.get("universes")
    if not isinstance(universes, list):
        return {}
    return {
        str(item["universe_id"]): item
        for item in universes
        if isinstance(item, dict) and "universe_id" in item
    }


def _without_provenance(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    return {
        key: child
        for key, child in value.items()
        if key not in {"executed_at_utc", "package_version"}
    }


def _mapping_value(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else None


def _byte_identical(
    left: ProjectEvidenceBundle, right: ProjectEvidenceBundle
) -> bool | None:
    if left.source_format != right.source_format:
        return None
    if left.source_format == "nwb":
        return left.files[0].sha256 == right.files[0].sha256
    left_files = {item.name: item.sha256 for item in left.files}
    right_files = {item.name: item.sha256 for item in right.files}
    return left_files == right_files


@dataclass
class _DifferenceCollector:
    absolute_tolerance: float
    relative_tolerance: float
    limit: int
    differences: list[EvidenceDifference] = field(default_factory=list)
    truncated: bool = False

    def add(
        self, category: DifferenceCategory, path: str, left: Any, right: Any
    ) -> None:
        if len(self.differences) >= self.limit:
            self.truncated = True
            return
        self.differences.append(EvidenceDifference(category, path, left, right))

    def compare(
        self, category: DifferenceCategory, path: str, left: Any, right: Any
    ) -> None:
        if self.truncated:
            return
        if _numbers(left, right):
            if not math.isclose(
                float(left),
                float(right),
                abs_tol=self.absolute_tolerance,
                rel_tol=self.relative_tolerance,
            ):
                self.add(category, path, left, right)
            return
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            keys = sorted(set(left) | set(right), key=str)
            for key in keys:
                self.compare(
                    category,
                    f"{path}.{key}",
                    left.get(key, _MISSING),
                    right.get(key, _MISSING),
                )
            return
        if isinstance(left, list | tuple) and isinstance(right, list | tuple):
            if len(left) != len(right):
                self.add(category, f"{path}.length", len(left), len(right))
            for index, (left_item, right_item) in enumerate(
                zip(left, right, strict=False)
            ):
                self.compare(category, f"{path}[{index}]", left_item, right_item)
            return
        if left != right:
            self.add(category, path, _visible(left), _visible(right))


class _Missing:
    pass


_MISSING = _Missing()


def _visible(value: Any) -> Any:
    return "<missing>" if value is _MISSING else value


def _numbers(left: Any, right: Any) -> bool:
    return (
        isinstance(left, int | float)
        and not isinstance(left, bool)
        and isinstance(right, int | float)
        and not isinstance(right, bool)
    )


def _validate_comparison_options(
    absolute_tolerance: float, relative_tolerance: float, max_differences: int
) -> None:
    if not math.isfinite(absolute_tolerance) or absolute_tolerance < 0:
        raise ValueError("absolute_tolerance must be finite and nonnegative")
    if not math.isfinite(relative_tolerance) or relative_tolerance < 0:
        raise ValueError("relative_tolerance must be finite and nonnegative")
    if not isinstance(max_differences, int) or max_differences < 1:
        raise ValueError("max_differences must be a positive integer")


def _optional_bool(value: bool | None) -> str:
    return "unknown" if value is None else str(value).lower()


def _markdown_value(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, default=str)
    if len(rendered) > 120:
        rendered = rendered[:117] + "..."
    return rendered.replace("|", "\\|").replace("\n", " ")
