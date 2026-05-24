"""Tests for Phase 4 regression analysis utilities."""
from __future__ import annotations

import unittest

from aegis_test_generator.regression import (
    TransitionAnnotation,
    _bucket_severity,
    compute_verdict,
    guard_coverage_sufficiency,
    score_regressions,
    verdict_description,
)
from aegis_test_generator.test_templates.schemas import TestCase


def _tc(test_type: str, target: str, role: str = "guard", **extras) -> TestCase:
    row: dict = {"test_type": test_type, "target": target, "role": role}
    row.update(extras)
    if test_type == "file_mode_changed":
        row.setdefault("expected", "0600")
        row.setdefault("expected_before", "0644")
    elif test_type in ("content_changed", "package_version_range", "package_version"):
        row.setdefault("expected", "val")
    return TestCase.model_validate(row)


def _transition(
    check_id: str,
    status: str,
    applicable: bool | None = None,
    annotation_type: str = "",
) -> dict:
    t: dict = {"check_id": check_id, "status": status, "role": "guard"}
    if applicable is not None:
        t["applicable"] = applicable
    if annotation_type:
        t["annotation_type"] = annotation_type
    return t


class BucketSeverityTests(unittest.TestCase):
    def test_zero_is_none(self) -> None:
        self.assertEqual(_bucket_severity(0.0), "none")

    def test_just_above_zero_is_low(self) -> None:
        self.assertEqual(_bucket_severity(0.1), "low")

    def test_boundary_low_to_medium(self) -> None:
        self.assertEqual(_bucket_severity(0.26), "medium")

    def test_high_range(self) -> None:
        self.assertEqual(_bucket_severity(0.7), "high")

    def test_max_is_critical(self) -> None:
        self.assertEqual(_bucket_severity(1.0), "critical")


class ScoreRegressionsTests(unittest.TestCase):
    # plan_lookup must map index → TestCase; check_id format: "suite::test_0_name"

    def _make_plan(self, targets: list[str]) -> dict:
        return {i: _tc("file_exists", t) for i, t in enumerate(targets)}

    def test_no_transitions_returns_zero_none(self) -> None:
        score, label = score_regressions([], [], {})
        self.assertEqual(score, 0.0)
        self.assertEqual(label, "none")

    def test_non_applicable_transitions_ignored(self) -> None:
        t = _transition("suite::test_0_foo", "regressed", applicable=False)
        score, label = score_regressions([t], [], self._make_plan(["/x"]))
        self.assertEqual(score, 0.0)

    def test_applicable_regression_uses_flat_score_when_no_sensitivity(self) -> None:
        t = _transition("suite::test_0_foo", "regressed", applicable=True)
        score, label = score_regressions([t], [], self._make_plan(["/x"]))
        self.assertAlmostEqual(score, 0.3)
        self.assertEqual(label, "medium")  # 0.3 falls in (0.25, 0.50] → medium

    def test_applicable_regression_uses_sensitivity_score(self) -> None:
        scored = [{"path": "/etc/nginx.conf", "score": 0.9}]
        plan = self._make_plan(["/etc/nginx.conf"])
        t = _transition("suite::test_0_foo", "regressed", applicable=True)
        score, label = score_regressions([t], scored, plan)
        self.assertAlmostEqual(score, 0.9)
        self.assertEqual(label, "critical")

    def test_multiple_regressions_summed_and_capped_at_1(self) -> None:
        plan = self._make_plan(["/etc/a", "/etc/b"])
        scored = [
            {"path": "/etc/a", "score": 0.7},
            {"path": "/etc/b", "score": 0.8},
        ]
        transitions = [
            _transition("suite::test_0_a", "regressed", applicable=True),
            _transition("suite::test_1_b", "regressed", applicable=True),
        ]
        score, label = score_regressions(transitions, scored, plan)
        self.assertEqual(score, 1.0)  # capped
        self.assertEqual(label, "critical")

    def test_new_fail_also_counted(self) -> None:
        t = _transition("suite::test_0_foo", "new_fail", applicable=True)
        score, _ = score_regressions([t], [], self._make_plan(["/x"]))
        self.assertGreater(score, 0.0)

    def test_non_regression_statuses_not_counted(self) -> None:
        for status in ("verified", "still_pass", "fixed"):
            t = _transition("suite::test_0_foo", status, applicable=True)
            score, label = score_regressions([t], [], self._make_plan(["/x"]))
            self.assertEqual(score, 0.0, f"expected 0 for status={status}")


class GuardCoverageSufficiencyTests(unittest.TestCase):
    def _scored(self, path: str, score: float) -> dict:
        return {"path": path, "score": score}

    def test_no_modified_files_no_warnings(self) -> None:
        w = guard_coverage_sufficiency([], [], [], [])
        self.assertEqual(w, [])

    def test_low_sensitivity_file_no_warning(self) -> None:
        tests = [_tc("content_contains", "/etc/nginx.conf")]
        w = guard_coverage_sufficiency(
            tests,
            diff_modified=["/etc/nginx.conf"],
            sensitivity_scored_files=[self._scored("/etc/nginx.conf", 0.3)],
            predicted_impact_files=[],
        )
        self.assertEqual(w, [])

    def test_high_sensitivity_with_guard_coverage_no_warning(self) -> None:
        tests = [_tc("content_contains", "/etc/nginx.conf", role="guard")]
        w = guard_coverage_sufficiency(
            tests,
            diff_modified=["/etc/nginx.conf"],
            sensitivity_scored_files=[self._scored("/etc/nginx.conf", 0.9)],
            predicted_impact_files=[],
        )
        self.assertEqual(w, [])

    def test_high_sensitivity_no_guard_emits_warning(self) -> None:
        w = guard_coverage_sufficiency(
            [],
            diff_modified=["/etc/nginx.conf"],
            sensitivity_scored_files=[self._scored("/etc/nginx.conf", 0.9)],
            predicted_impact_files=[],
        )
        self.assertEqual(len(w), 1)
        self.assertIn("/etc/nginx.conf", w[0])
        self.assertIn("Coverage Warning", w[0])

    def test_impact_file_coverage_satisfies_check(self) -> None:
        tests = [_tc("service_running", "nginx", role="guard")]
        w = guard_coverage_sufficiency(
            tests,
            diff_modified=["/etc/nginx/nginx.conf"],
            sensitivity_scored_files=[self._scored("/etc/nginx/nginx.conf", 0.8)],
            predicted_impact_files=["nginx"],
        )
        self.assertEqual(w, [])

    def test_dict_diff_modified_entries_parsed(self) -> None:
        w = guard_coverage_sufficiency(
            [],
            diff_modified=[{"path": "/etc/app.conf"}],
            sensitivity_scored_files=[self._scored("/etc/app.conf", 0.9)],
            predicted_impact_files=[],
        )
        self.assertEqual(len(w), 1)
        self.assertIn("/etc/app.conf", w[0])

    def test_warning_includes_impact_hint(self) -> None:
        w = guard_coverage_sufficiency(
            [],
            diff_modified=["/etc/x"],
            sensitivity_scored_files=[self._scored("/etc/x", 0.9)],
            predicted_impact_files=["nginx", "port 443"],
        )
        self.assertTrue(any("nginx" in line or "port 443" in line for line in w))


class ComputeVerdictTests(unittest.TestCase):
    def test_pass_no_regressions_no_gaps(self) -> None:
        self.assertEqual(compute_verdict(True, "none", 0, []), "PASS")

    def test_pass_with_warnings_when_gaps_present(self) -> None:
        self.assertEqual(compute_verdict(True, "none", 0, ["gap"]), "PASS_WITH_WARNINGS")

    def test_partial_low_for_low_severity(self) -> None:
        self.assertEqual(compute_verdict(True, "low", 1, []), "PARTIAL_LOW")

    def test_partial_high_for_medium(self) -> None:
        self.assertEqual(compute_verdict(True, "medium", 1, []), "PARTIAL_HIGH")

    def test_partial_high_for_high(self) -> None:
        self.assertEqual(compute_verdict(True, "high", 1, []), "PARTIAL_HIGH")

    def test_partial_high_for_critical(self) -> None:
        self.assertEqual(compute_verdict(True, "critical", 2, []), "PARTIAL_HIGH")

    def test_fail_verify_no_regressions(self) -> None:
        self.assertEqual(compute_verdict(False, "none", 0, []), "FAIL_VERIFY")

    def test_fail_both_regressions_and_verify_fail(self) -> None:
        self.assertEqual(compute_verdict(False, "low", 2, []), "FAIL_BOTH")

    def test_all_verdicts_have_descriptions(self) -> None:
        for v in ("PASS", "PASS_WITH_WARNINGS", "PARTIAL_LOW", "PARTIAL_HIGH",
                  "FAIL_VERIFY", "FAIL_BOTH"):
            desc = verdict_description(v)
            self.assertTrue(len(desc) > 10, f"{v!r} description too short")


class TransitionAnnotationTests(unittest.TestCase):
    def test_enum_values(self) -> None:
        self.assertEqual(TransitionAnnotation.APPLICABLE.value, "APPLICABLE")
        self.assertEqual(TransitionAnnotation.ENV_ARTIFACT.value, "ENV_ARTIFACT")
        self.assertEqual(TransitionAnnotation.FLAKY.value, "FLAKY")
        self.assertEqual(TransitionAnnotation.OUT_OF_SCOPE.value, "OUT_OF_SCOPE")

    def test_str_comparison(self) -> None:
        self.assertEqual(TransitionAnnotation.APPLICABLE, "APPLICABLE")


if __name__ == "__main__":
    unittest.main()
