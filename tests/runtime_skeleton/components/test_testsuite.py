from __future__ import annotations

import unittest

from runtime_skeleton.components.testsuite import (
    DefaultTestSuiteComponent,
    ManualTestSuiteRunner,
)
from runtime_skeleton.interfaces import TestSuiteRequest as SuiteRequestPayload


def _check(**kwargs: str) -> dict[str, str]:
    base = {
        "suite_id": "s",
        "check_id": "c",
        "status": "pass",
        "title": "",
    }
    base.update(kwargs)
    return base


class TestSuiteComponentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.component = DefaultTestSuiteComponent()

    def test_pass_through_preserves_extra_keys(self) -> None:
        pre = [{"suite_id": "a", "check_id": "b", "status": "fail", "title": "t", "meta": 1}]
        post: list[dict] = []
        result = self.component.run(SuiteRequestPayload(pre_checks=pre, post_checks=post))
        self.assertEqual(len(result.pre_checks), 1)
        row = result.pre_checks[0]
        self.assertEqual(row["meta"], 1)
        self.assertEqual(row["suite_id"], "a")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(result.post_checks, [])
        self.assertFalse(result.skipped)
        self.assertIsNone(result.error)
        self.assertEqual(result.warnings, [])

    def test_none_pre_post_become_empty_lists(self) -> None:
        result = self.component.run(SuiteRequestPayload(pre_checks=None, post_checks=None))
        self.assertEqual(result.pre_checks, [])
        self.assertEqual(result.post_checks, [])
        self.assertEqual(result.warnings, [])

    def test_missing_stable_keys_default_to_empty_strings(self) -> None:
        result = self.component.run(
            SuiteRequestPayload(
                pre_checks=[{"extra": True}],
                post_checks=[{}],
            )
        )
        self.assertEqual(
            result.pre_checks,
            [{"extra": True, "suite_id": "", "check_id": "", "status": "", "title": ""}],
        )
        self.assertEqual(
            result.post_checks,
            [{"suite_id": "", "check_id": "", "status": "", "title": ""}],
        )

    def test_non_dict_rows_skipped_with_warnings(self) -> None:
        bad: list = [_check()]
        bad.append("not-a-dict")  # type: ignore[list-item]
        bad.append(_check(check_id="d2"))

        result = self.component.run(SuiteRequestPayload(pre_checks=bad))

        self.assertEqual(len(result.pre_checks), 2)
        self.assertEqual(result.pre_checks[0]["check_id"], "c")
        self.assertEqual(result.pre_checks[1]["check_id"], "d2")
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("non-dict", result.warnings[0])
        self.assertIn("pre_checks", result.warnings[0])
        self.assertIn("index 1", result.warnings[0])

    def test_does_not_mutate_caller_lists_or_dicts(self) -> None:
        inner = {"suite_id": "x", "check_id": "y"}
        pre = [inner]
        self.component.run(SuiteRequestPayload(pre_checks=pre))
        self.assertEqual(set(inner.keys()), {"suite_id", "check_id"})

    def test_phase_pre_collects_into_pre_checks_only(self) -> None:
        rows = [{"suite_id": "suite", "check_id": "pre-1", "status": "pass"}]
        result = self.component.run(SuiteRequestPayload(phase="pre", phase_checks=rows))
        self.assertEqual(len(result.pre_checks), 1)
        self.assertEqual(result.pre_checks[0]["check_id"], "pre-1")
        self.assertEqual(result.post_checks, [])

    def test_phase_post_collects_into_post_checks_only(self) -> None:
        rows = [{"suite_id": "suite", "check_id": "post-1", "status": "fail"}]
        result = self.component.run(SuiteRequestPayload(phase="post", phase_checks=rows))
        self.assertEqual(result.pre_checks, [])
        self.assertEqual(len(result.post_checks), 1)
        self.assertEqual(result.post_checks[0]["check_id"], "post-1")

    def test_runner_collects_phase_when_phase_checks_not_supplied(self) -> None:
        runner = ManualTestSuiteRunner(
            phase_rows={
                "pre": [{"suite_id": "suite", "check_id": "pre-runner", "status": "pass"}]
            }
        )
        result = self.component.run(SuiteRequestPayload(phase="pre", runner=runner))
        self.assertEqual(len(result.pre_checks), 1)
        self.assertEqual(result.pre_checks[0]["check_id"], "pre-runner")
        self.assertEqual(result.error, None)
        self.assertEqual(result.warnings, [])

    def test_runner_timeout_maps_to_structured_result(self) -> None:
        runner = ManualTestSuiteRunner(phase_errors={"post": TimeoutError("runner timed out")})
        result = self.component.run(SuiteRequestPayload(phase="post", runner=runner))
        self.assertEqual(result.pre_checks, [])
        self.assertEqual(result.post_checks, [])
        self.assertEqual(result.error, "testsuite runner timeout during post phase")
        self.assertEqual(result.warnings, ["runner timed out"])

    def test_runner_exception_maps_to_structured_result(self) -> None:
        runner = ManualTestSuiteRunner(phase_errors={"pre": RuntimeError("runner failed")})
        result = self.component.run(SuiteRequestPayload(phase="pre", runner=runner))
        self.assertEqual(result.pre_checks, [])
        self.assertEqual(result.post_checks, [])
        self.assertEqual(result.error, "testsuite runner error during pre phase")
        self.assertEqual(result.warnings, ["runner failed"])
