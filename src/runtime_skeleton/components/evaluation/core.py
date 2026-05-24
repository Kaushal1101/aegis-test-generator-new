from __future__ import annotations

from typing import Any

from runtime_skeleton.interfaces import EvaluationComponent, EvaluationInput, EvaluationResult


def _check_key(check: dict[str, Any]) -> tuple[str, str]:
    return str(check.get("suite_id") or ""), str(check.get("check_id") or "")


def _bucket(status: str | None) -> str:
    normalized_status = (status or "").lower().strip()
    if normalized_status in {"fail", "failed", "error"}:
        return "fail"
    if normalized_status in {"skip", "skipped", "not_applicable"}:
        return "skip"
    return "pass"


def _classify(
    pre: dict[str, Any] | None,
    post: dict[str, Any] | None,
    *,
    role: str = "guard",
) -> str:
    if pre is None and post is not None:
        bucket = _bucket(post.get("status"))
        return "new_fail" if bucket == "fail" else ("new_skip" if bucket == "skip" else "new_pass")
    if pre is not None and post is None:
        bucket = _bucket(pre.get("status"))
        return (
            "removed_fail"
            if bucket == "fail"
            else ("removed_skip" if bucket == "skip" else "removed_pass")
        )

    pre_bucket = _bucket((pre or {}).get("status"))
    post_bucket = _bucket((post or {}).get("status"))

    if pre_bucket == "fail":
        if role == "verify":
            return "verified" if post_bucket != "fail" else "verification_failed"
        if post_bucket != "fail":
            return "fixed"
        return "still_fail"

    if post_bucket == "fail":
        return "regressed"
    if pre_bucket == post_bucket:
        return f"still_{pre_bucket}"
    if pre_bucket == "skip" and post_bucket == "pass":
        return "new_pass"
    if pre_bucket == "pass" and post_bucket == "skip":
        return "regressed"
    return "still_pass"


class DefaultEvaluationComponent(EvaluationComponent):
    """Pure evaluation implementation preserving existing compare semantics."""

    def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        pre_map = {_check_key(check): check for check in (evaluation_input.pre_checks or [])}
        post_map = {_check_key(check): check for check in (evaluation_input.post_checks or [])}
        keys = sorted(set(pre_map) | set(post_map))

        transitions: list[dict[str, Any]] = []
        counts: dict[str, int] = {}

        for key in keys:
            pre = pre_map.get(key)
            post = post_map.get(key)
            role = str((post or pre or {}).get("role") or "guard")
            status = _classify(pre, post, role=role)
            counts[status] = counts.get(status, 0) + 1
            transitions.append(
                {
                    "suite_id": key[0],
                    "check_id": key[1],
                    "title": str((post or pre or {}).get("title") or ""),
                    "role": role,
                    "status": status,
                    "pre": pre,
                    "post": post,
                }
            )

        regressed_count = counts.get("regressed", 0) + counts.get("new_fail", 0)
        fixed_count = counts.get("fixed", 0) + counts.get("new_pass", 0)
        verified_count = counts.get("verified", 0)
        verification_failed_count = counts.get("verification_failed", 0)
        return EvaluationResult(
            skipped=False,
            counts=counts,
            net_change=fixed_count - regressed_count,
            regression_detected=regressed_count > 0,
            regressed_count=regressed_count,
            fixed_count=fixed_count,
            verified_count=verified_count,
            verification_failed_count=verification_failed_count,
            transitions=transitions,
        )


def evaluate_checks(
    pre_checks: list[dict[str, Any]],
    post_checks: list[dict[str, Any]],
) -> EvaluationResult:
    component = DefaultEvaluationComponent()
    return component.evaluate(
        EvaluationInput(
            pre_checks=pre_checks or [],
            post_checks=post_checks or [],
        )
    )

