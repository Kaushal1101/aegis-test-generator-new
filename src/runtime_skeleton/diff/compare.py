from __future__ import annotations

from typing import Any

from runtime_skeleton.components.evaluation import evaluate_checks
from runtime_skeleton.interfaces import DiffResult


def compare_results(
    pre_checks: list[dict[str, Any]],
    post_checks: list[dict[str, Any]],
) -> DiffResult:
    evaluation_result = evaluate_checks(pre_checks=pre_checks or [], post_checks=post_checks or [])
    return DiffResult(
        skipped=evaluation_result.skipped,
        skip_reason=evaluation_result.skip_reason,
        counts=evaluation_result.counts,
        net_change=evaluation_result.net_change,
        regression_detected=evaluation_result.regression_detected,
        regressed_count=evaluation_result.regressed_count,
        fixed_count=evaluation_result.fixed_count,
        verified_count=evaluation_result.verified_count,
        verification_failed_count=evaluation_result.verification_failed_count,
        transitions=evaluation_result.transitions,
    )
