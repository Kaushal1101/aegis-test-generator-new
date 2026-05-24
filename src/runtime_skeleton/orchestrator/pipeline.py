from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Callable, Literal

from runtime_skeleton.components.testsuite import DefaultTestSuiteComponent
from runtime_skeleton.diff import compare_results
from runtime_skeleton.input import parse_input
from runtime_skeleton.interfaces import (
    ExceptionClassifier,
    PipelineSnapshot,
    SandboxResult,
    TestSuiteRequest,
    TestSuiteRunner,
)
from runtime_skeleton.sandbox import apply_patch, create_sandbox

_DEFAULT_TESTSUITE = DefaultTestSuiteComponent()
CheckMode = Literal["external", "partial", "in_process"]


def _select_check_mode(
    pre_checks: list[dict[str, Any]] | None,
    post_checks: list[dict[str, Any]] | None,
) -> CheckMode:
    has_pre = pre_checks is not None
    has_post = post_checks is not None
    if has_pre and has_post:
        return "external"
    if has_pre or has_post:
        return "partial"
    return "in_process"


def _normalize_phase(
    *,
    phase: Literal["pre", "post"],
    rows: list[dict[str, Any]] | None,
    runner: TestSuiteRunner | None = None,
    phase_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    result = _DEFAULT_TESTSUITE.run(
        TestSuiteRequest(
            phase=phase,
            phase_checks=rows,
            runner=runner,
            phase_context=phase_context or {},
        )
    )
    checks = result.pre_checks if phase == "pre" else result.post_checks
    messages: list[str] = []
    if result.error:
        messages.append(f"testsuite {phase} phase error: {result.error}")
    for warning in result.warnings:
        messages.append(f"testsuite {phase} phase warning: {warning}")
    return checks, messages


class _CollectorRunner(TestSuiteRunner):
    def __init__(
        self,
        collector: Callable[[str, SandboxResult | None], list[dict[str, Any]]] | None,
    ) -> None:
        self._collector = collector

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self._collector is None:
            return []
        sandbox = context.get("sandbox")
        return self._collector(phase, sandbox)


def _emit_testsuite_message(snap: PipelineSnapshot, message: str) -> None:
    warnings.warn(message, stacklevel=2)
    snap.testsuite_messages.append(message)


def _resolve_runner(
    runner: TestSuiteRunner | None,
    collector: Callable[[str, SandboxResult | None], list[dict[str, Any]]] | None,
) -> TestSuiteRunner:
    if runner is not None:
        return runner
    return _CollectorRunner(collector)


def run_pipeline(
    *,
    repo_root: Path,
    input_path: str | None = None,
    input_json: dict[str, Any] | None = None,
    pre_checks: list[dict[str, Any]] | None = None,
    post_checks: list[dict[str, Any]] | None = None,
    skip_sandbox: bool = False,
    skip_patch_apply: bool = False,
    testsuite_collector: Callable[[str, SandboxResult | None], list[dict[str, Any]]] | None = None,
    runner: TestSuiteRunner | None = None,
    classifier: ExceptionClassifier | None = None,
) -> PipelineSnapshot:
    """Run parse_input -> pre collection -> sandbox/patch -> post collection -> diff.

    Canonical regression order is baseline pre checks, then Sandbox patch, then post
    checks, then Evaluation. If caller supplies both ``pre_checks`` and ``post_checks``,
    those are used in compatibility mode after TestSuite normalization.

    TestSuite runner errors and warnings are surfaced as process warnings and do not
    abort the pipeline. Evaluation still runs on whatever normalized checks were
    collected in each phase.

    Runner selection precedence (for any phase that needs in-process collection):
    explicit ``runner`` first, then a ``testsuite_collector`` callable wrapped in an
    internal adapter, then a no-op runner (returns ``[]``).
    """
    parsed = parse_input(input_path=input_path, input_json=input_json)
    snap = PipelineSnapshot(parsed_input=parsed)
    mode = _select_check_mode(pre_checks, post_checks)
    collector_runner: TestSuiteRunner | None = _resolve_runner(runner, testsuite_collector)

    if mode == "partial":
        partial_msg = (
            "run_pipeline received partial external checks; collecting missing phase in-process"
        )
        _emit_testsuite_message(snap, partial_msg)

    if parsed.error:
        pre_source = pre_checks if mode in {"external", "partial"} else None
        pre_n, pre_messages = _normalize_phase(
            phase="pre",
            rows=pre_source,
            runner=collector_runner,
            phase_context={"input": parsed.parsed},
        )
        for message in pre_messages:
            _emit_testsuite_message(snap, message)
        snap.sandbox = create_sandbox(repo_root=repo_root, run_id="parse-error", skip=True)
        snap.patch_apply = apply_patch(
            repo_root=repo_root,
            container_name="",
            patch_section={},
            skip=True,
        )
        post_n, post_messages = _normalize_phase(
            phase="post",
            rows=post_checks if mode in {"external", "partial"} else None,
            runner=collector_runner,
            phase_context={"sandbox": snap.sandbox, "input": parsed.parsed},
        )
        for message in post_messages:
            _emit_testsuite_message(snap, message)
        snap.diff = compare_results(pre_n, post_n)
        if snap.diff is not None:
            snap.patch_verified = (
                snap.diff.verified_count > 0 and snap.diff.verification_failed_count == 0
            )
        return snap

    parsed_doc = parsed.parsed
    run_id = str((parsed_doc.get("meta") or {}).get("run_id") or "unknown")
    patch_section = parsed_doc.get("patch") or {}

    sandbox = create_sandbox(repo_root=repo_root, run_id=run_id, skip=skip_sandbox)
    snap.sandbox = sandbox

    pre_source = pre_checks if mode in {"external", "partial"} else None
    pre_n, pre_messages = _normalize_phase(
        phase="pre",
        rows=pre_source,
        runner=collector_runner,
        phase_context={"sandbox": sandbox, "input": parsed_doc},
    )
    for message in pre_messages:
        _emit_testsuite_message(snap, message)

    patch_result = apply_patch(
        repo_root=repo_root,
        container_name=sandbox.container_name,
        patch_section=patch_section,
        skip=skip_patch_apply or sandbox.skipped,
    )
    snap.patch_apply = patch_result
    if patch_result.patch_applied:
        snap.execution_phase = "post_patch"

    post_n, post_messages = _normalize_phase(
        phase="post",
        rows=post_checks if mode in {"external", "partial"} else None,
        runner=collector_runner,
        phase_context={"sandbox": sandbox, "input": parsed_doc},
    )
    for message in post_messages:
        _emit_testsuite_message(snap, message)
    snap.diff = compare_results(pre_n, post_n)
    if snap.diff is not None:
        snap.patch_verified = (
            snap.diff.verified_count > 0 and snap.diff.verification_failed_count == 0
        )
    if classifier is not None and snap.diff is not None:
        try:
            c_result = classifier.classify(snap.diff.transitions, parsed_input=parsed_doc)
            ann_by_check = {
                str(a.get("check_id") or ""): a
                for a in c_result.annotations
                if isinstance(a, dict)
            }
            merged: list[dict[str, Any]] = []
            for tr in snap.diff.transitions:
                check_id = str((tr or {}).get("check_id") or "")
                ann = ann_by_check.get(check_id, {})
                merged.append(
                    {
                        **tr,
                        "applicable": ann.get("applicable"),
                        "classification_reason": str(ann.get("reason") or ""),
                    }
                )
            snap.classified_transitions = merged
            for warning in c_result.warnings:
                _emit_testsuite_message(
                    snap,
                    f"classifier warning: {warning}",
                )
        except Exception as exc:
            _emit_testsuite_message(snap, f"classifier error: {exc}")
    return snap
