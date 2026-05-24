from __future__ import annotations

import unittest

from runtime_skeleton.components.evaluation import DefaultEvaluationComponent, evaluate_checks
from runtime_skeleton.interfaces import EvaluationInput, EvaluationResult


def _check(
    suite_id: str,
    check_id: str,
    status: str,
    title: str = "",
    role: str | None = None,
) -> dict[str, str]:
    row: dict[str, str] = {
        "suite_id": suite_id,
        "check_id": check_id,
        "status": status,
        "title": title,
    }
    if role is not None:
        row["role"] = role
    return row


class EvaluationComponentTests(unittest.TestCase):
    def test_transition_classification_covers_required_cases(self) -> None:
        pre_checks = [
            _check("suite", "fixed", "fail"),
            _check("suite", "regressed", "pass"),
            _check("suite", "still_pass", "pass"),
            _check("suite", "still_fail", "fail"),
            _check("suite", "still_skip", "skip"),
            _check("suite", "skip_to_pass", "skip"),
            _check("suite", "pass_to_skip", "pass"),
            _check("suite", "removed_fail", "fail"),
            _check("suite", "removed_pass", "pass"),
            _check("suite", "removed_skip", "skip"),
        ]
        post_checks = [
            _check("suite", "fixed", "pass"),
            _check("suite", "regressed", "fail"),
            _check("suite", "still_pass", "pass"),
            _check("suite", "still_fail", "fail"),
            _check("suite", "still_skip", "skip"),
            _check("suite", "skip_to_pass", "pass"),
            _check("suite", "pass_to_skip", "skip"),
            _check("suite", "new_fail", "fail"),
            _check("suite", "new_pass", "pass"),
            _check("suite", "new_skip", "skip"),
        ]

        result = evaluate_checks(pre_checks=pre_checks, post_checks=post_checks)
        by_check_id = {row["check_id"]: row["status"] for row in result.transitions}

        self.assertEqual(by_check_id["fixed"], "fixed")
        self.assertEqual(by_check_id["regressed"], "regressed")
        self.assertEqual(by_check_id["still_pass"], "still_pass")
        self.assertEqual(by_check_id["still_fail"], "still_fail")
        self.assertEqual(by_check_id["still_skip"], "still_skip")
        self.assertEqual(by_check_id["skip_to_pass"], "new_pass")
        self.assertEqual(by_check_id["pass_to_skip"], "regressed")
        self.assertEqual(by_check_id["new_fail"], "new_fail")
        self.assertEqual(by_check_id["new_pass"], "new_pass")
        self.assertEqual(by_check_id["new_skip"], "new_skip")
        self.assertEqual(by_check_id["removed_fail"], "removed_fail")
        self.assertEqual(by_check_id["removed_pass"], "removed_pass")
        self.assertEqual(by_check_id["removed_skip"], "removed_skip")

    def test_aggregates_and_regression_flags_match_existing_semantics(self) -> None:
        pre_checks = [
            _check("suite", "fixed", "fail"),
            _check("suite", "regressed", "pass"),
            _check("suite", "pass_to_skip", "pass"),
        ]
        post_checks = [
            _check("suite", "fixed", "pass"),
            _check("suite", "regressed", "fail"),
            _check("suite", "pass_to_skip", "skip"),
            _check("suite", "new_fail", "error"),
            _check("suite", "new_pass", "pass"),
        ]

        result = evaluate_checks(pre_checks=pre_checks, post_checks=post_checks)

        self.assertEqual(result.counts["fixed"], 1)
        self.assertEqual(result.counts["regressed"], 2)
        self.assertEqual(result.counts["new_fail"], 1)
        self.assertEqual(result.counts["new_pass"], 1)
        self.assertEqual(result.regressed_count, 3)
        self.assertEqual(result.fixed_count, 2)
        self.assertEqual(result.net_change, -1)
        self.assertTrue(result.regression_detected)
        self.assertFalse(result.skipped)

    def test_evaluation_component_uses_contract_types(self) -> None:
        component = DefaultEvaluationComponent()
        evaluation_input = EvaluationInput(
            pre_checks=[_check("suite", "a", "pass")],
            post_checks=[_check("suite", "a", "pass")],
        )

        result = component.evaluate(evaluation_input)

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.counts, {"still_pass": 1})

    def test_verify_role_fail_to_pass_is_verified(self) -> None:
        pre = [_check("s", "c", "fail", role="verify")]
        post = [_check("s", "c", "pass", role="verify")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "verified")

    def test_verify_role_fail_to_fail_is_verification_failed(self) -> None:
        pre = [_check("s", "c", "fail", role="verify")]
        post = [_check("s", "c", "fail", role="verify")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "verification_failed")

    def test_verify_role_pass_to_fail_is_regressed(self) -> None:
        pre = [_check("s", "c", "pass", role="verify")]
        post = [_check("s", "c", "fail", role="verify")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "regressed")

    def test_verify_role_pass_to_pass_is_still_pass(self) -> None:
        pre = [_check("s", "c", "pass", role="verify")]
        post = [_check("s", "c", "pass", role="verify")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "still_pass")

    def test_guard_role_fail_to_pass_is_fixed(self) -> None:
        pre = [_check("s", "c", "fail", role="guard")]
        post = [_check("s", "c", "pass", role="guard")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "fixed")

    def test_guard_role_fail_to_fail_is_still_fail(self) -> None:
        pre = [_check("s", "c", "fail", role="guard")]
        post = [_check("s", "c", "fail", role="guard")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.transitions[0]["status"], "still_fail")

    def test_verified_count_in_result(self) -> None:
        pre = [
            _check("s", "v", "fail", role="verify"),
            _check("s", "g", "pass", role="guard"),
        ]
        post = [
            _check("s", "v", "pass", role="verify"),
            _check("s", "g", "pass", role="guard"),
        ]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.verified_count, 1)
        self.assertEqual(result.verification_failed_count, 0)

    def test_verification_failed_count_in_result(self) -> None:
        pre = [_check("s", "v", "fail", role="verify")]
        post = [_check("s", "v", "fail", role="verify")]
        result = evaluate_checks(pre_checks=pre, post_checks=post)
        self.assertEqual(result.verification_failed_count, 1)
        self.assertEqual(result.verified_count, 0)

    def test_regression_detected_unchanged_by_verify(self) -> None:
        pre_verify_only = [_check("s", "v", "fail", role="verify")]
        post_verify_only = [_check("s", "v", "fail", role="verify")]
        result = evaluate_checks(pre_checks=pre_verify_only, post_checks=post_verify_only)
        self.assertFalse(result.regression_detected)
        self.assertEqual(result.transitions[0]["status"], "verification_failed")

        pre_mixed = [
            _check("s", "v", "fail", role="verify"),
            _check("s", "g", "pass", role="guard"),
        ]
        post_mixed = [
            _check("s", "v", "fail", role="verify"),
            _check("s", "g", "fail", role="guard"),
        ]
        result_mixed = evaluate_checks(pre_checks=pre_mixed, post_checks=post_mixed)
        self.assertTrue(result_mixed.regression_detected)
        by_id = {t["check_id"]: t["status"] for t in result_mixed.transitions}
        self.assertEqual(by_id["v"], "verification_failed")
        self.assertEqual(by_id["g"], "regressed")


if __name__ == "__main__":
    unittest.main()

