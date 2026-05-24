"""Tests for coverage taxonomy and compute_coverage."""
from __future__ import annotations

import unittest

from aegis_test_generator.coverage import (
    ALL_CATEGORIES,
    TEST_TYPE_TO_CATEGORY,
    compute_coverage,
)
from aegis_test_generator.planner.intent import PatchIntent
from aegis_test_generator.test_templates.schemas import TestCase, validate_plan


def _tc(test_type: str, role: str = "guard", **extras) -> TestCase:
    row: dict = {"test_type": test_type, "target": "/x", "role": role}
    row.update(extras)
    if test_type == "file_mode_changed":
        row.setdefault("expected", "0600")
        row.setdefault("expected_before", "0644")
    elif test_type in ("content_changed", "package_version_range", "package_version"):
        row.setdefault("expected", "val")
    return TestCase.model_validate(row)


class TestTypeToCategoryMappingTests(unittest.TestCase):
    def test_all_22_types_are_mapped(self) -> None:
        from aegis_test_generator.planner.llm_planner import SUPPORTED_TEST_TYPES
        for t in SUPPORTED_TEST_TYPES:
            self.assertIn(t, TEST_TYPE_TO_CATEGORY, f"{t!r} has no category mapping")

    def test_mapping_values_are_valid_categories(self) -> None:
        for t, cat in TEST_TYPE_TO_CATEGORY.items():
            self.assertIn(cat, ALL_CATEGORIES, f"{t!r} maps to unknown category {cat!r}")

    def test_package_types_map_to_package_integrity(self) -> None:
        for t in ("package_installed", "package_absent", "package_version", "package_version_range"):
            self.assertEqual(TEST_TYPE_TO_CATEGORY[t], "package_integrity")

    def test_file_integrity_types(self) -> None:
        for t in ("file_exists", "file_absent", "directory_exists", "file_mode",
                  "file_mode_changed", "file_owner", "symlink_exists", "binary_executable"):
            self.assertEqual(TEST_TYPE_TO_CATEGORY[t], "file_integrity")

    def test_file_content_types(self) -> None:
        for t in ("content_contains", "content_not_contains", "content_changed",
                  "command_output_contains"):
            self.assertEqual(TEST_TYPE_TO_CATEGORY[t], "file_content")

    def test_service_types(self) -> None:
        for t in ("service_running", "service_enabled"):
            self.assertEqual(TEST_TYPE_TO_CATEGORY[t], "service_state")

    def test_network_type(self) -> None:
        self.assertEqual(TEST_TYPE_TO_CATEGORY["port_listening"], "network_posture")

    def test_identity_types(self) -> None:
        for t in ("user_exists", "group_exists"):
            self.assertEqual(TEST_TYPE_TO_CATEGORY[t], "identity")

    def test_command_types(self) -> None:
        self.assertEqual(TEST_TYPE_TO_CATEGORY["command_succeeds"], "command_behavior")


class CoverageCategoryAutoAssignTests(unittest.TestCase):
    def test_package_installed_auto_assigned(self) -> None:
        tc = _tc("package_installed")
        self.assertEqual(tc.coverage_category, "package_integrity")

    def test_content_contains_auto_assigned(self) -> None:
        tc = _tc("content_contains")
        self.assertEqual(tc.coverage_category, "file_content")

    def test_service_running_auto_assigned(self) -> None:
        tc = _tc("service_running")
        self.assertEqual(tc.coverage_category, "service_state")

    def test_explicit_override_preserved(self) -> None:
        tc = TestCase.model_validate({
            "test_type": "package_installed",
            "target": "/x",
            "coverage_category": "command_behavior",
        })
        self.assertEqual(tc.coverage_category, "command_behavior")

    def test_all_types_get_a_category(self) -> None:
        from aegis_test_generator.planner.llm_planner import SUPPORTED_TEST_TYPES
        for t in SUPPORTED_TEST_TYPES:
            tc = _tc(t)
            self.assertIsNotNone(tc.coverage_category, f"{t!r} should get auto-assigned category")

    def test_validate_plan_preserves_category(self) -> None:
        plan = validate_plan([{"test_type": "file_exists", "target": "/etc/x"}])
        self.assertEqual(plan.tests[0].coverage_category, "file_integrity")


class ComputeCoverageTests(unittest.TestCase):
    def test_empty_tests_all_zeros(self) -> None:
        cov = compute_coverage([])
        for cat in ALL_CATEGORIES:
            self.assertEqual(cov.stats[cat].total, 0)

    def test_counts_verify_and_guard_separately(self) -> None:
        tests = [
            _tc("package_installed", role="verify"),
            _tc("package_installed", role="guard"),
            _tc("package_installed", role="verify"),
        ]
        cov = compute_coverage(tests)
        self.assertEqual(cov.stats["package_integrity"].verify, 2)
        self.assertEqual(cov.stats["package_integrity"].guard, 1)

    def test_counts_across_categories(self) -> None:
        tests = [
            _tc("file_exists", role="verify"),
            _tc("service_running", role="guard"),
        ]
        cov = compute_coverage(tests)
        self.assertEqual(cov.stats["file_integrity"].verify, 1)
        self.assertEqual(cov.stats["service_state"].guard, 1)

    def test_no_gaps_when_required_categories_covered(self) -> None:
        tests = [
            _tc("package_installed", role="verify"),
            _tc("file_exists", role="guard"),
        ]
        cov = compute_coverage(tests, patch_intent=PatchIntent.INSTALL)
        self.assertEqual(cov.gaps, [])

    def test_gap_flagged_for_missing_required_category(self) -> None:
        # install requires package_integrity and file_integrity
        # only providing file_integrity → package_integrity should be a gap
        tests = [_tc("file_exists", role="verify")]
        cov = compute_coverage(tests, patch_intent=PatchIntent.INSTALL)
        self.assertIn("package_integrity", cov.gaps)

    def test_no_gaps_when_intent_is_none(self) -> None:
        cov = compute_coverage([], patch_intent=None)
        self.assertEqual(cov.gaps, [])

    def test_update_intent_requires_file_content(self) -> None:
        tests = [_tc("package_installed", role="verify")]
        cov = compute_coverage(tests, patch_intent=PatchIntent.UPDATE)
        self.assertIn("file_content", cov.gaps)

    def test_configure_intent_requires_file_content_only(self) -> None:
        tests = []
        cov = compute_coverage(tests, patch_intent=PatchIntent.CONFIGURE)
        self.assertIn("file_content", cov.gaps)
        self.assertNotIn("package_integrity", cov.gaps)

    def test_total_tests_sum(self) -> None:
        tests = [_tc("file_exists"), _tc("service_running"), _tc("package_installed")]
        cov = compute_coverage(tests)
        self.assertEqual(cov.total_tests(), 3)


if __name__ == "__main__":
    unittest.main()
