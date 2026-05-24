from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from runtime_skeleton.interfaces import (
    TestSuiteComponent,
    TestSuiteRequest,
    TestSuiteResult,
    TestSuiteRunner,
)


def _as_stable_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_check_dict(check: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(check)
    merged["suite_id"] = _as_stable_str(merged.get("suite_id"))
    merged["check_id"] = _as_stable_str(merged.get("check_id"))
    merged["status"] = _as_stable_str(merged.get("status"))
    merged["title"] = _as_stable_str(merged.get("title"))
    return merged


def _normalize_phase(
    rows: list[dict[str, Any]] | None,
    label: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if rows is None:
        return [], []
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(rows):
        if not isinstance(item, dict):
            warnings.append(f"testsuite: skipped non-dict entry at index {i} in {label}")
            continue
        out.append(_normalize_check_dict(item))
    return out, warnings


def _invoke_runner(
    *,
    phase: Literal["pre", "post"],
    runner: TestSuiteRunner | None,
    context: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    if runner is None:
        return [], None, []
    try:
        rows = runner.run_phase(phase, context)
        return rows, None, []
    except TimeoutError as exc:
        return [], f"testsuite runner timeout during {phase} phase", [str(exc)]
    except Exception as exc:  # pragma: no cover - defensive fallback
        return [], f"testsuite runner error during {phase} phase", [str(exc)]


@dataclass
class ManualTestSuiteRunner(TestSuiteRunner):
    """Minimal opt-in runner for in-process TestSuite phase collection."""

    phase_rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    phase_errors: dict[str, Exception] = field(default_factory=dict)

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _ = context
        maybe_exc = self.phase_errors.get(phase)
        if maybe_exc is not None:
            raise maybe_exc
        return list(self.phase_rows.get(phase, []))


class DefaultTestSuiteComponent(TestSuiteComponent):
    """Deterministic normalization of pre/post check lists for Evaluation."""

    def run(self, request: TestSuiteRequest) -> TestSuiteResult:
        if request.phase in {"pre", "post"}:
            phase_rows = request.phase_checks
            error: str | None = None
            runner_warnings: list[str] = []
            if phase_rows is None:
                phase_rows, error, runner_warnings = _invoke_runner(
                    phase=request.phase,
                    runner=request.runner,
                    context=request.phase_context,
                )
            phase_warnings: list[str]
            normalized_rows, phase_warnings = _normalize_phase(
                phase_rows,
                f"{request.phase}_checks",
            )
            merged_warnings = runner_warnings + phase_warnings
            if request.phase == "pre":
                return TestSuiteResult(
                    pre_checks=normalized_rows,
                    warnings=merged_warnings,
                    error=error,
                )
            return TestSuiteResult(
                post_checks=normalized_rows,
                warnings=merged_warnings,
                error=error,
            )

        pre, w_pre = _normalize_phase(request.pre_checks, "pre_checks")
        post, w_post = _normalize_phase(request.post_checks, "post_checks")
        return TestSuiteResult(
            pre_checks=pre,
            post_checks=post,
            warnings=w_pre + w_post,
        )
