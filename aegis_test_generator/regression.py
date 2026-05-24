"""Phase 4 regression analysis utilities.

Provides:
- TransitionAnnotation enum mirroring the classifier's annotation_type values
- score_regressions(): sensitivity-weighted severity score from classified transitions
- guard_coverage_sufficiency(): warns when high-sensitivity modified files lack guard coverage
- compute_verdict(): expands the binary PASS/FAIL/PARTIAL into a six-tier verdict
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from aegis_test_generator.test_templates.schemas import TestCase

_IDX_RE = re.compile(r"::test_(\d+)_")

SeverityLabel = Literal["none", "low", "medium", "high", "critical"]

_FLAT_SCORE = 0.3  # used when no sensitivity score is available for a target


class TransitionAnnotation(str, Enum):
    APPLICABLE = "APPLICABLE"         # genuine regression; counts against score
    ENV_ARTIFACT = "ENV_ARTIFACT"     # Docker/sandbox limitation, not a real regression
    FLAKY = "FLAKY"                   # known unstable test
    OUT_OF_SCOPE = "OUT_OF_SCOPE"     # unrelated to patch risk surface


def _bucket_severity(raw_score: float) -> SeverityLabel:
    """Map a 0–1 float to a severity label using upper-bound tiers."""
    if raw_score <= 0.0:
        return "none"
    if raw_score <= 0.25:
        return "low"
    if raw_score <= 0.50:
        return "medium"
    if raw_score <= 0.75:
        return "high"
    return "critical"


def _build_sensitivity_lookup(scored_files: list[Any]) -> dict[str, float]:
    """Convert scored_files list to a {path: score} dict."""
    lookup: dict[str, float] = {}
    for entry in scored_files or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        score = entry.get("score")
        if path and isinstance(score, (int, float)):
            lookup[path] = float(score)
    return lookup


def score_regressions(
    transitions: list[dict[str, Any]],
    sensitivity_scored_files: list[Any],
    plan_lookup: "dict[int, TestCase]",
) -> tuple[float, SeverityLabel]:
    """Compute a 0–1 severity score from applicable regressions.

    Each applicable regression contributes its sensitivity score (if the test
    target appears in scored_files) or a flat 0.3. The raw sum is capped at 1.0
    before bucketing.

    Returns (severity_score, severity_label).
    """
    sensitivity = _build_sensitivity_lookup(sensitivity_scored_files)

    total: float = 0.0
    for t in transitions:
        if t.get("applicable") is not True:
            continue
        status = str(t.get("status") or "")
        if status not in {"regressed", "new_fail"}:
            continue

        check_id = str(t.get("check_id") or "")
        m = _IDX_RE.search(check_id)
        target: str | None = None
        if m is not None:
            idx = int(m.group(1))
            tc = plan_lookup.get(idx)
            if tc is not None:
                target = tc.target

        contrib = sensitivity.get(target, _FLAT_SCORE) if target else _FLAT_SCORE
        total += contrib

    raw = min(total, 1.0)
    return raw, _bucket_severity(raw)


def guard_coverage_sufficiency(
    tests: "list[TestCase]",
    diff_modified: list[Any],
    sensitivity_scored_files: list[Any],
    predicted_impact_files: list[Any],
) -> list[str]:
    """Return warnings for high-sensitivity modified files with no guard coverage.

    For each file in diff_modified whose sensitivity score exceeds 0.5, at least
    one guard test must target that file or anything in predicted_impact_files.
    If the guard neighbourhood is empty for that file, a warning is emitted.
    """
    sensitivity = _build_sensitivity_lookup(sensitivity_scored_files)

    guard_targets: set[str] = {
        tc.target for tc in tests if tc.role == "guard"
    }

    impact_names: set[str] = set()
    for item in predicted_impact_files or []:
        if isinstance(item, str):
            impact_names.add(item)
        elif isinstance(item, dict):
            v = str(item.get("path") or item.get("name") or "")
            if v:
                impact_names.add(v)

    warnings: list[str] = []
    for entry in diff_modified or []:
        if isinstance(entry, str):
            path = entry
        elif isinstance(entry, dict):
            path = str(entry.get("path") or "")
        else:
            continue

        if not path:
            continue

        score = sensitivity.get(path, 0.0)
        if score <= 0.5:
            continue

        covered = (
            path in guard_targets
            or any(t in guard_targets for t in impact_names)
        )
        if not covered:
            impact_hint = ", ".join(sorted(impact_names)[:3]) if impact_names else "—"
            warnings.append(
                f"Coverage Warning: {path} (sensitivity: {score:.2f}) has no guard tests "
                f"covering its dependency surface. "
                f"Consider adding guard tests for: {impact_hint}."
            )

    return warnings


def compute_verdict(
    patch_verified: bool,
    severity: SeverityLabel,
    applicable_regressed_count: int,
    coverage_gaps: list[str],
) -> str:
    """Return a six-tier verdict string.

    Verdicts:
      PASS                — all verify pass, zero applicable regressions
      PASS_WITH_WARNINGS  — all verify pass, zero applicable regressions, coverage gaps present
      PARTIAL_LOW         — verify pass, low-severity regressions
      PARTIAL_HIGH        — verify pass, medium/high/critical regressions
      FAIL_VERIFY         — verify failed, no regressions
      FAIL_BOTH           — verify failed and regressions present
    """
    has_regressions = applicable_regressed_count > 0
    high_severity = severity in {"medium", "high", "critical"}

    if patch_verified and not has_regressions:
        if coverage_gaps:
            return "PASS_WITH_WARNINGS"
        return "PASS"

    if patch_verified and has_regressions:
        return "PARTIAL_HIGH" if high_severity else "PARTIAL_LOW"

    if not patch_verified and has_regressions:
        return "FAIL_BOTH"

    return "FAIL_VERIFY"


_VERDICT_DESCRIPTIONS: dict[str, str] = {
    "PASS": "Patch achieved its goals and introduced no regressions.",
    "PASS_WITH_WARNINGS": (
        "Patch goals verified and no regressions, but coverage gaps were detected. "
        "See Coverage Summary for details."
    ),
    "PARTIAL_LOW": "Patch goals verified; low-severity regressions were introduced.",
    "PARTIAL_HIGH": "Patch goals verified; medium or higher severity regressions were introduced.",
    "FAIL_VERIFY": "Patch did not achieve one or more stated goals. No regressions detected.",
    "FAIL_BOTH": "Patch goals not met and regressions were introduced.",
}


def verdict_description(verdict: str) -> str:
    return _VERDICT_DESCRIPTIONS.get(verdict, verdict)
