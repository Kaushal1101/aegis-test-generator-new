from __future__ import annotations

import unittest

from runtime_skeleton.components.evaluation import evaluate_checks
from runtime_skeleton.diff import compare_results
from runtime_skeleton.interfaces import DiffResult


def _check(suite_id: str, check_id: str, status: str, title: str = "") -> dict[str, str]:
    return {
        "suite_id": suite_id,
        "check_id": check_id,
        "status": status,
        "title": title,
    }


class CompareCompatibilityTests(unittest.TestCase):
    def test_compare_results_matches_evaluation_component_output(self) -> None:
        pre_checks = [
            _check("suite", "fixed", "fail", "Fix me"),
            _check("suite", "regressed", "pass", "Break me"),
            _check("suite", "removed_skip", "skip", "Skip removed"),
            _check("suite", "unchanged", "pass", "No change"),
        ]
        post_checks = [
            _check("suite", "fixed", "pass", "Fixed now"),
            _check("suite", "regressed", "fail", "Regressed now"),
            _check("suite", "new_fail", "failed", "New failing test"),
            _check("suite", "unchanged", "pass", "No change"),
        ]

        eval_result = evaluate_checks(pre_checks=pre_checks, post_checks=post_checks)
        diff_result = compare_results(pre_checks=pre_checks, post_checks=post_checks)

        self.assertEqual(diff_result.counts, eval_result.counts)
        self.assertEqual(diff_result.net_change, eval_result.net_change)
        self.assertEqual(diff_result.regression_detected, eval_result.regression_detected)
        self.assertEqual(diff_result.regressed_count, eval_result.regressed_count)
        self.assertEqual(diff_result.fixed_count, eval_result.fixed_count)
        self.assertEqual(diff_result.transitions, eval_result.transitions)
        self.assertEqual(diff_result.skipped, eval_result.skipped)
        self.assertEqual(diff_result.skip_reason, eval_result.skip_reason)

    def test_compare_results_returns_diff_result_for_public_api(self) -> None:
        diff_result = compare_results(
            pre_checks=[_check("suite", "x", "pass")],
            post_checks=[_check("suite", "x", "pass")],
        )

        self.assertIsInstance(diff_result, DiffResult)


if __name__ == "__main__":
    unittest.main()

