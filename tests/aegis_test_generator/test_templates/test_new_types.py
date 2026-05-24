"""Tests for the three new Phase 2 test types: content_changed, file_mode_changed,
package_version_range.
"""
from __future__ import annotations

import ast
import unittest

import pytest

from aegis_test_generator.test_templates.renderer import RendererError, _func_body
from aegis_test_generator.test_templates.schemas import TestCase, validate_plan
from aegis_test_generator.planner.llm_planner import _shape_check_row


# ---------------------------------------------------------------------------
# content_changed
# ---------------------------------------------------------------------------

class ContentChangedSchemaTests(unittest.TestCase):
    def test_accepted_with_expected(self) -> None:
        plan = validate_plan([{"test_type": "content_changed", "target": "/etc/x", "expected": "old_val"}])
        self.assertEqual(plan.tests[0].test_type, "content_changed")

    def test_shape_check_drops_without_expected(self) -> None:
        warn = _shape_check_row({"test_type": "content_changed", "target": "/etc/x"}, 0)
        self.assertIsNotNone(warn)
        assert warn is not None
        self.assertIn("expected", warn)


class ContentChangedRendererTests(unittest.TestCase):
    def _tc(self, expected: str | None = "old_content") -> TestCase:
        return TestCase.model_validate({
            "test_type": "content_changed",
            "target": "/etc/app.conf",
            "expected": expected,
        })

    def test_body_checks_file_exists(self) -> None:
        body = _func_body(self._tc())
        self.assertIn("assert f.exists", body)

    def test_body_asserts_old_value_absent(self) -> None:
        body = _func_body(self._tc("old_content"))
        self.assertIn("not in f.content_string", body)
        self.assertIn("old_content", body)

    def test_body_is_valid_python(self) -> None:
        body = _func_body(self._tc())
        ast.parse(f"def test_fn(host):\n{body}")

    def test_missing_expected_raises_renderer_error(self) -> None:
        tc = TestCase.model_validate({"test_type": "content_changed", "target": "/x"})
        tc = tc.model_copy(update={"expected": None})
        with self.assertRaises(RendererError):
            _func_body(tc)


# ---------------------------------------------------------------------------
# file_mode_changed
# ---------------------------------------------------------------------------

class FileModeChangedSchemaTests(unittest.TestCase):
    def test_accepted_with_both_modes(self) -> None:
        plan = validate_plan([{
            "test_type": "file_mode_changed",
            "target": "/etc/x",
            "expected": "0600",
            "expected_before": "0644",
        }])
        tc = plan.tests[0]
        self.assertEqual(tc.expected, "0600")
        self.assertEqual(tc.expected_before, "0644")

    def test_shape_check_drops_without_expected(self) -> None:
        warn = _shape_check_row({
            "test_type": "file_mode_changed",
            "target": "/etc/x",
            "expected_before": "0644",
        }, 0)
        self.assertIsNotNone(warn)

    def test_shape_check_drops_without_expected_before(self) -> None:
        warn = _shape_check_row({
            "test_type": "file_mode_changed",
            "target": "/etc/x",
            "expected": "0600",
        }, 0)
        self.assertIsNotNone(warn)
        assert warn is not None
        self.assertIn("expected_before", warn)

    def test_shape_check_passes_with_both(self) -> None:
        warn = _shape_check_row({
            "test_type": "file_mode_changed",
            "target": "/etc/x",
            "expected": "0600",
            "expected_before": "0644",
        }, 0)
        self.assertIsNone(warn)


class FileModeChangedRendererTests(unittest.TestCase):
    def _tc(self, expected: str = "0600", expected_before: str = "0644") -> TestCase:
        return TestCase.model_validate({
            "test_type": "file_mode_changed",
            "target": "/etc/app.conf",
            "expected": expected,
            "expected_before": expected_before,
        })

    def test_body_checks_old_mode_gone(self) -> None:
        body = _func_body(self._tc())
        self.assertIn("!= 0o644", body)

    def test_body_checks_new_mode_set(self) -> None:
        body = _func_body(self._tc())
        self.assertIn("== 0o600", body)

    def test_body_is_valid_python(self) -> None:
        body = _func_body(self._tc())
        ast.parse(f"def test_fn(host):\n{body}")

    def test_various_octal_formats_accepted(self) -> None:
        for fmt_new, fmt_old in [("755", "644"), ("0755", "0644"), ("0o755", "0o644")]:
            body = _func_body(self._tc(fmt_new, fmt_old))
            self.assertIn("0o755", body)
            self.assertIn("0o644", body)

    def test_missing_expected_raises(self) -> None:
        tc = TestCase.model_validate({
            "test_type": "file_mode_changed",
            "target": "/x",
            "expected": "0600",
            "expected_before": "0644",
        })
        tc = tc.model_copy(update={"expected": None})
        with self.assertRaises(RendererError):
            _func_body(tc)

    def test_missing_expected_before_raises(self) -> None:
        tc = TestCase.model_validate({
            "test_type": "file_mode_changed",
            "target": "/x",
            "expected": "0600",
            "expected_before": "0644",
        })
        tc = tc.model_copy(update={"expected_before": None})
        with self.assertRaises(RendererError):
            _func_body(tc)

    def test_invalid_mode_string_raises(self) -> None:
        tc = TestCase.model_validate({
            "test_type": "file_mode_changed",
            "target": "/x",
            "expected": "notamode",
            "expected_before": "0644",
        })
        with self.assertRaises(RendererError):
            _func_body(tc)


# ---------------------------------------------------------------------------
# package_version_range
# ---------------------------------------------------------------------------

class PackageVersionRangeSchemaTests(unittest.TestCase):
    def test_accepted_with_constraint(self) -> None:
        plan = validate_plan([{
            "test_type": "package_version_range",
            "target": "nginx",
            "expected": ">=1.18,<2.0",
        }])
        self.assertEqual(plan.tests[0].test_type, "package_version_range")

    def test_shape_check_drops_without_expected(self) -> None:
        warn = _shape_check_row({"test_type": "package_version_range", "target": "nginx"}, 0)
        self.assertIsNotNone(warn)


class PackageVersionRangeRendererTests(unittest.TestCase):
    def _tc(self, constraint: str = ">=1.18,<2.0") -> TestCase:
        return TestCase.model_validate({
            "test_type": "package_version_range",
            "target": "nginx",
            "expected": constraint,
        })

    def test_body_imports_specifier_set(self) -> None:
        body = _func_body(self._tc())
        self.assertIn("SpecifierSet", body)

    def test_body_checks_installed(self) -> None:
        body = _func_body(self._tc())
        self.assertIn("is_installed", body)

    def test_body_uses_constraint(self) -> None:
        body = _func_body(self._tc(">=1.18,<2.0"))
        self.assertIn(">=1.18,<2.0", body)

    def test_body_is_valid_python(self) -> None:
        body = _func_body(self._tc())
        ast.parse(f"def test_fn(host):\n{body}")

    def test_missing_expected_raises(self) -> None:
        tc = TestCase.model_validate({
            "test_type": "package_version_range",
            "target": "nginx",
            "expected": ">=1.0",
        })
        tc = tc.model_copy(update={"expected": None})
        with self.assertRaises(RendererError):
            _func_body(tc)


if __name__ == "__main__":
    unittest.main()
