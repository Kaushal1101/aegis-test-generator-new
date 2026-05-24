"""Tests for the new ``runner=`` parameter on ``run_pipeline``.

Asserts: runner is invoked for both phases by default; runner takes precedence
over the older ``testsuite_collector`` callable; external pre/post checks
still bypass the runner; runner failures are non-destructive (warning surfaced,
pipeline continues).
"""

from __future__ import annotations

import unittest
import warnings
from pathlib import Path
from typing import Any, Literal

from runtime_skeleton.interfaces import ClassifierResult, TestSuiteRunner as _RunnerProtocol
from runtime_skeleton.orchestrator.pipeline import run_pipeline


class _ContextCapturingRunner(_RunnerProtocol):
    """Records full phase_context dicts for assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self.calls.append((phase, dict(context)))
        return []


class _RecordingRunner(_RunnerProtocol):
    """Runner that records calls and returns canned rows per phase."""

    def __init__(
        self,
        rows: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.rows = rows or {}
        self.calls: list[tuple[str, bool]] = []

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self.calls.append((phase, context.get("sandbox") is not None))
        return list(self.rows.get(phase, []))


class _BoomRunner(_RunnerProtocol):
    def __init__(self, when: str) -> None:
        self.when = when

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if phase == self.when:
            raise RuntimeError(f"runner exploded during {phase}")
        return []


class _RecordingClassifier:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    def classify(
        self,
        transitions: list[dict[str, Any]],
        *,
        parsed_input: dict[str, Any],
    ) -> ClassifierResult:
        self.calls.append(list(transitions))
        anns = [
            {
                "check_id": str((t or {}).get("check_id") or ""),
                "applicable": False,
                "reason": "explicitly reported for review",
            }
            for t in transitions
        ]
        return ClassifierResult(annotations=anns, raw="{}", warnings=[], model="mock")


def _input_path() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root / "examples/sample_input.json")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class PipelineRunnerWiringTests(unittest.TestCase):
    def test_runner_invoked_for_both_phases_when_no_external_checks(self) -> None:
        runner = _RecordingRunner(
            rows={
                "pre": [{"suite_id": "x", "check_id": "a", "status": "pass"}],
                "post": [{"suite_id": "x", "check_id": "a", "status": "fail"}],
            }
        )
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            skip_sandbox=True,
            skip_patch_apply=True,
            runner=runner,
        )
        phases = [c[0] for c in runner.calls]
        self.assertEqual(phases, ["pre", "post"])
        sandbox_seen = [c[1] for c in runner.calls]
        self.assertEqual(sandbox_seen, [True, True])
        assert snap.diff is not None
        self.assertTrue(snap.diff.regression_detected)

    def test_runner_takes_precedence_over_testsuite_collector(self) -> None:
        called: list[str] = []

        def collector(phase: str, _sandbox) -> list[dict]:
            called.append(phase)
            return [{"suite_id": "c", "check_id": phase, "status": "pass"}]

        runner = _RecordingRunner(
            rows={
                "pre": [{"suite_id": "r", "check_id": "pre", "status": "pass"}],
                "post": [{"suite_id": "r", "check_id": "post", "status": "pass"}],
            }
        )
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            skip_sandbox=True,
            skip_patch_apply=True,
            testsuite_collector=collector,
            runner=runner,
        )
        self.assertEqual(called, [])
        self.assertEqual([c[0] for c in runner.calls], ["pre", "post"])
        assert snap.diff is not None

    def test_runner_bypassed_for_external_pre_and_post_checks(self) -> None:
        runner = _RecordingRunner(rows={"pre": [], "post": []})
        pre = [{"suite_id": "ext", "check_id": "a", "status": "pass"}]
        post = [{"suite_id": "ext", "check_id": "a", "status": "fail"}]
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
            runner=runner,
        )
        self.assertEqual(runner.calls, [])
        assert snap.diff is not None
        self.assertTrue(snap.diff.regression_detected)

    def test_runner_invoked_only_for_missing_phase_in_partial_mode(self) -> None:
        runner = _RecordingRunner(
            rows={"post": [{"suite_id": "r", "check_id": "post", "status": "fail"}]}
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=_repo_root(),
                input_path=_input_path(),
                pre_checks=[{"suite_id": "ext", "check_id": "a", "status": "pass"}],
                skip_sandbox=True,
                skip_patch_apply=True,
                runner=runner,
            )
        self.assertEqual([c[0] for c in runner.calls], ["post"])
        self.assertTrue(any("partial external checks" in str(w.message) for w in caught))
        assert snap.diff is not None

    def test_runner_failure_is_non_destructive_and_warns(self) -> None:
        runner = _BoomRunner(when="post")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=_repo_root(),
                input_path=_input_path(),
                skip_sandbox=True,
                skip_patch_apply=True,
                runner=runner,
            )
        rendered = [str(w.message) for w in caught]
        self.assertTrue(any("testsuite post phase error" in m for m in rendered))
        assert snap.diff is not None
        self.assertTrue(any("testsuite post phase error" in m for m in snap.testsuite_messages))

    def test_no_runner_no_collector_backward_compatible_empty_collection(self) -> None:
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            skip_sandbox=True,
            skip_patch_apply=True,
        )
        assert snap.diff is not None
        self.assertEqual(snap.diff.counts.get("pass", 0), 0)
        self.assertEqual(snap.diff.counts.get("fail", 0), 0)

    def test_phase_context_includes_parsed_input_for_pre_and_post(self) -> None:
        runner = _ContextCapturingRunner()
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            skip_sandbox=True,
            skip_patch_apply=True,
            runner=runner,
        )
        self.assertEqual([c[0] for c in runner.calls], ["pre", "post"])
        for _phase, ctx in runner.calls:
            self.assertIn("input", ctx)
            self.assertIsInstance(ctx["input"], dict)
            self.assertIn("diff", ctx["input"])
            self.assertIn("patch", ctx["input"])
        assert snap.parsed_input is not None
        self.assertEqual(runner.calls[0][1]["input"], snap.parsed_input.parsed)
        self.assertEqual(runner.calls[1][1]["input"], snap.parsed_input.parsed)

    def test_parse_error_path_passes_input_in_post_phase_context(self) -> None:
        runner = _ContextCapturingRunner()
        snap = run_pipeline(repo_root=_repo_root(), input_json={}, runner=runner)
        self.assertTrue(snap.parsed_input and snap.parsed_input.error)
        self.assertEqual([c[0] for c in runner.calls], ["pre", "post"])
        pre_ctx, post_ctx = runner.calls[0][1], runner.calls[1][1]
        self.assertIn("input", pre_ctx)
        self.assertIn("input", post_ctx)
        assert snap.parsed_input is not None
        self.assertEqual(pre_ctx["input"], snap.parsed_input.parsed)
        self.assertEqual(post_ctx["input"], snap.parsed_input.parsed)
        self.assertIn("sandbox", post_ctx)

    def test_classifier_annotations_are_additive(self) -> None:
        runner = _RecordingRunner(
            rows={
                "pre": [{"suite_id": "x", "check_id": "a", "status": "fail"}],
                "post": [{"suite_id": "x", "check_id": "a", "status": "pass"}],
            }
        )
        classifier = _RecordingClassifier()
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            skip_sandbox=True,
            skip_patch_apply=True,
            runner=runner,
            classifier=classifier,
        )
        assert snap.diff is not None
        self.assertEqual(len(classifier.calls), 1)
        self.assertIsNotNone(snap.classified_transitions)
        assert snap.classified_transitions is not None
        self.assertEqual(len(snap.classified_transitions), len(snap.diff.transitions))
        self.assertIn("applicable", snap.classified_transitions[0])
        self.assertIn("classification_reason", snap.classified_transitions[0])

    def test_classifier_failure_is_non_destructive(self) -> None:
        class _BoomClassifier:
            def classify(self, transitions: list[dict[str, Any]], *, parsed_input: dict[str, Any]) -> ClassifierResult:
                raise RuntimeError("classifier exploded")

        runner = _RecordingRunner(
            rows={
                "pre": [{"suite_id": "x", "check_id": "a", "status": "pass"}],
                "post": [{"suite_id": "x", "check_id": "a", "status": "fail"}],
            }
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=_repo_root(),
                input_path=_input_path(),
                skip_sandbox=True,
                skip_patch_apply=True,
                runner=runner,
                classifier=_BoomClassifier(),
            )
        assert snap.diff is not None
        self.assertIsNone(snap.classified_transitions)
        self.assertTrue(any("classifier error" in str(w.message) for w in caught))

    def test_patch_verified_true_when_all_verify_pass(self) -> None:
        pre = [{"suite_id": "ext", "check_id": "v1", "status": "fail", "role": "verify"}]
        post = [{"suite_id": "ext", "check_id": "v1", "status": "pass", "role": "verify"}]
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
        )
        assert snap.diff is not None
        self.assertTrue(snap.patch_verified)

    def test_patch_verified_false_when_no_verify_tests(self) -> None:
        pre = [{"suite_id": "ext", "check_id": "g1", "status": "pass", "role": "guard"}]
        post = [{"suite_id": "ext", "check_id": "g1", "status": "pass", "role": "guard"}]
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
        )
        assert snap.diff is not None
        self.assertFalse(snap.patch_verified)

    def test_patch_verified_false_when_verification_failed(self) -> None:
        pre = [{"suite_id": "ext", "check_id": "v1", "status": "fail", "role": "verify"}]
        post = [{"suite_id": "ext", "check_id": "v1", "status": "fail", "role": "verify"}]
        snap = run_pipeline(
            repo_root=_repo_root(),
            input_path=_input_path(),
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
        )
        assert snap.diff is not None
        self.assertFalse(snap.patch_verified)


if __name__ == "__main__":
    unittest.main()
