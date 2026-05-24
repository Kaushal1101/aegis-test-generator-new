from __future__ import annotations

import unittest
import warnings
from pathlib import Path

from runtime_skeleton.components.testsuite import DefaultTestSuiteComponent
from runtime_skeleton.diff import compare_results
from runtime_skeleton.interfaces import TestSuiteRequest as SuiteRequestPayload
from runtime_skeleton.orchestrator.pipeline import run_pipeline


def _checks() -> tuple[list[dict], list[dict]]:
    pre = [{"suite_id": "svc", "check_id": "nginx", "status": "pass", "title": "p"}]
    post = [{"suite_id": "svc", "check_id": "nginx", "status": "fail", "title": "p"}]
    return pre, post


class PipelineTestSuiteIntegrationTests(unittest.TestCase):
    def test_run_pipeline_diff_matches_testsuite_then_compare_results(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        pre, post = _checks()
        input_path = str(repo_root / "examples/sample_input.json")

        snap = run_pipeline(
            repo_root=repo_root,
            input_path=input_path,
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
        )
        ts = DefaultTestSuiteComponent().run(SuiteRequestPayload(pre_checks=pre, post_checks=post))
        expected = compare_results(ts.pre_checks, ts.post_checks)

        self.assertIsNotNone(snap.diff)
        assert snap.diff is not None
        self.assertEqual(snap.diff.counts, expected.counts)
        self.assertEqual(snap.diff.net_change, expected.net_change)
        self.assertEqual(snap.diff.regression_detected, expected.regression_detected)
        self.assertEqual(snap.diff.transitions, expected.transitions)

    def test_legacy_compare_results_parity_for_wellformed_lists(self) -> None:
        pre, post = _checks()
        direct = compare_results(pre, post)
        ts = DefaultTestSuiteComponent().run(SuiteRequestPayload(pre_checks=pre, post_checks=post))
        via_ts = compare_results(ts.pre_checks, ts.post_checks)
        self.assertEqual(direct.counts, via_ts.counts)
        self.assertEqual(direct.transitions, via_ts.transitions)

    def test_in_process_collection_runs_pre_then_post(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        input_path = str(repo_root / "examples/sample_input.json")
        order: list[str] = []
        sandbox_contexts: list[bool] = []

        def collector(phase: str, sandbox) -> list[dict]:
            order.append(phase)
            sandbox_contexts.append(sandbox is not None)
            if phase == "pre":
                return [{"suite_id": "svc", "check_id": "nginx", "status": "pass"}]
            return [{"suite_id": "svc", "check_id": "nginx", "status": "fail"}]

        snap = run_pipeline(
            repo_root=repo_root,
            input_path=input_path,
            skip_sandbox=True,
            skip_patch_apply=True,
            testsuite_collector=collector,
        )
        self.assertEqual(order, ["pre", "post"])
        self.assertEqual(sandbox_contexts, [True, True])
        assert snap.diff is not None
        self.assertTrue(snap.diff.regression_detected)

    def test_partial_external_checks_warns_and_collects_missing_phase(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        input_path = str(repo_root / "examples/sample_input.json")
        phases: list[str] = []

        def collector(phase: str, _sandbox) -> list[dict]:
            phases.append(phase)
            return [{"suite_id": "svc", "check_id": f"{phase}-id", "status": "pass"}]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=repo_root,
                input_path=input_path,
                pre_checks=[{"suite_id": "svc", "check_id": "nginx", "status": "pass"}],
                skip_sandbox=True,
                skip_patch_apply=True,
                testsuite_collector=collector,
            )
        self.assertEqual(phases, ["post"])
        self.assertTrue(any("partial external checks" in str(w.message) for w in caught))
        assert snap.diff is not None
        self.assertTrue(any("partial external checks" in msg for msg in snap.testsuite_messages))

    def test_external_pre_and_post_checks_bypass_runner_invocation(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        input_path = str(repo_root / "examples/sample_input.json")
        phases: list[str] = []
        pre, post = _checks()

        def collector(phase: str, _sandbox) -> list[dict]:
            phases.append(phase)
            return [{"suite_id": "svc", "check_id": f"{phase}-id", "status": "pass"}]

        snap = run_pipeline(
            repo_root=repo_root,
            input_path=input_path,
            pre_checks=pre,
            post_checks=post,
            skip_sandbox=True,
            skip_patch_apply=True,
            testsuite_collector=collector,
        )
        self.assertEqual(phases, [])
        assert snap.diff is not None
        self.assertTrue(snap.diff.regression_detected)
        self.assertFalse(any("partial external checks" in msg for msg in snap.testsuite_messages))

    def test_partial_post_only_collects_missing_pre(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        input_path = str(repo_root / "examples/sample_input.json")
        phases: list[str] = []

        def collector(phase: str, _sandbox) -> list[dict]:
            phases.append(phase)
            return [{"suite_id": "svc", "check_id": f"{phase}-id", "status": "pass"}]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=repo_root,
                input_path=input_path,
                post_checks=[{"suite_id": "svc", "check_id": "nginx", "status": "pass"}],
                skip_sandbox=True,
                skip_patch_apply=True,
                testsuite_collector=collector,
            )
        self.assertEqual(phases, ["pre"])
        self.assertTrue(any("partial external checks" in str(w.message) for w in caught))
        assert snap.diff is not None
        self.assertTrue(any("partial external checks" in msg for msg in snap.testsuite_messages))

    def test_runner_failures_emit_warnings_and_pipeline_continues(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        input_path = str(repo_root / "examples/sample_input.json")

        def collector(phase: str, _sandbox) -> list[dict]:
            if phase == "pre":
                raise TimeoutError("pre timed out")
            return [{"suite_id": "svc", "check_id": "post-id", "status": "fail"}]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            snap = run_pipeline(
                repo_root=repo_root,
                input_path=input_path,
                skip_sandbox=True,
                skip_patch_apply=True,
                testsuite_collector=collector,
            )
        rendered = [str(w.message) for w in caught]
        self.assertTrue(any("testsuite pre phase error" in msg for msg in rendered))
        self.assertTrue(any("testsuite pre phase warning" in msg for msg in rendered))
        assert snap.diff is not None
        self.assertTrue(snap.diff.regression_detected)
        self.assertTrue(any("testsuite pre phase error" in msg for msg in snap.testsuite_messages))
        self.assertTrue(any("testsuite pre phase warning" in msg for msg in snap.testsuite_messages))
