from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aegis_test_generator.planner.dspy_planner import TestCaseDSPy, TestPlanDSPy
from aegis_test_generator.planner.llm_planner import (
    MAX_PLAYBOOK_CHARS,
    PlannerError,
    PlannerResponseError,
    PlannerResult,
    PlaybookLoadError,
    _extract_plan_rows,
    _shape_check_row,
    plan_from_playbook,
)

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "example_patch.yml"


def _make_prediction(roles: tuple[str, ...] = ("guard",)) -> MagicMock:
    plan = TestPlanDSPy(
        tests=[
            TestCaseDSPy(
                test_type="package_installed",
                target="curl",
                role=r,
                reason="test",
                args={},
            )
            for r in roles
        ]
    )
    return MagicMock(plan=plan)


class LlmPlannerTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        fake_lm = MagicMock()
        pred = _make_prediction(("verify",))
        with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
            "dspy.context"
        ):
            mock_mod = MagicMock()
            mock_mod.return_value = pred
            gm.return_value = mock_mod
            result = plan_from_playbook(_FIXTURE, lm=fake_lm, model="gpt-test-model", review=False)
        self.assertIsInstance(result, PlannerResult)
        self.assertEqual(len(result.tests), 1)
        self.assertEqual(result.tests[0]["test_type"], "package_installed")
        self.assertEqual(result.tests[0]["target"], "curl")
        self.assertEqual(result.tests[0]["role"], "verify")
        self.assertEqual(result.model, "gpt-test-model")
        self.assertEqual(result.warnings, [])
        mock_mod.assert_called_once()

    def test_malformed_json_raises(self) -> None:
        with self.assertRaises(PlannerResponseError) as ctx:
            _extract_plan_rows("not json at all")
        self.assertIn("JSON", str(ctx.exception))

    def test_wrong_shape_missing_tests_raises(self) -> None:
        with self.assertRaises(PlannerResponseError) as ctx:
            _extract_plan_rows(json.dumps({"data": []}))
        self.assertIn("tests", str(ctx.exception))

    def test_per_row_drop_warns(self) -> None:
        fake_lm = MagicMock()
        plan = TestPlanDSPy(
            tests=[
                TestCaseDSPy(
                    test_type="package_installed", target="nginx", role="guard", reason="r"
                ),
                TestCaseDSPy(
                    test_type="unknown_type", target="x", role="guard", reason="r"
                ),
            ]
        )
        pred = MagicMock(plan=plan)
        with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
            "dspy.context"
        ):
            mock_mod = MagicMock()
            mock_mod.return_value = pred
            gm.return_value = mock_mod
            result = plan_from_playbook(_FIXTURE, lm=fake_lm, review=False)
        self.assertEqual(len(result.tests), 1)
        self.assertEqual(result.tests[0]["test_type"], "package_installed")
        self.assertTrue(any("tests[1]" in w for w in result.warnings))

    def test_all_rows_invalid_raises(self) -> None:
        fake_lm = MagicMock()
        plan = TestPlanDSPy(
            tests=[
                TestCaseDSPy(test_type="bad", target="a", role="guard", reason="r"),
                TestCaseDSPy(test_type="wrong", target="b", role="guard", reason="r"),
            ]
        )
        pred = MagicMock(plan=plan)
        with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
            "dspy.context"
        ):
            mock_mod = MagicMock()
            mock_mod.return_value = pred
            gm.return_value = mock_mod
            with self.assertRaises(PlannerResponseError) as ctx:
                plan_from_playbook(_FIXTURE, lm=fake_lm, review=False)
        self.assertIn("no valid", str(ctx.exception).lower())

    def test_file_not_found_no_forward_call(self) -> None:
        with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
            "dspy.context"
        ):
            mock_mod = MagicMock()
            gm.return_value = mock_mod
            with self.assertRaises(PlaybookLoadError):
                plan_from_playbook(Path("/nope/does-not-exist-llm-planner.yml"), lm=MagicMock())
        mock_mod.assert_not_called()

    def test_invalid_yaml_raises_before_forward(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("{not valid yaml: [\n")
            bad_path = Path(f.name)
        try:
            with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
                "dspy.context"
            ):
                mock_mod = MagicMock()
                gm.return_value = mock_mod
                with self.assertRaises(PlaybookLoadError):
                    plan_from_playbook(bad_path, lm=MagicMock(), review=False)
        finally:
            bad_path.unlink(missing_ok=True)
        mock_mod.assert_not_called()

    def test_truncation_warning(self) -> None:
        long_body = "a" * (MAX_PLAYBOOK_CHARS + 100)
        fake_lm = MagicMock()
        plan = TestPlanDSPy(
            tests=[
                TestCaseDSPy(
                    test_type="file_exists", target="/tmp/x", role="guard", reason="r"
                )
            ]
        )
        pred = MagicMock(plan=plan)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(long_body)
            path = Path(f.name)
        try:
            with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
                "dspy.context"
            ):
                mock_mod = MagicMock()
                mock_mod.return_value = pred
                gm.return_value = mock_mod
                result = plan_from_playbook(path, lm=fake_lm, review=False)
        finally:
            path.unlink(missing_ok=True)

        self.assertTrue(any("truncat" in w.lower() for w in result.warnings))
        kwargs = mock_mod.call_args.kwargs
        self.assertIn("# ... TRUNCATED ...", kwargs["playbook_yaml"])

    def test_missing_api_key_without_lm(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("- hosts: all\n  tasks: []\n")
            path = Path(f.name)
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                with self.assertRaises(PlannerError) as ctx:
                    plan_from_playbook(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    def test_dspy_error_wrapped(self) -> None:
        fake_lm = MagicMock()
        with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch(
            "dspy.context"
        ):
            mock_mod = MagicMock()
            mock_mod.side_effect = RuntimeError("boom")
            gm.return_value = mock_mod
            with self.assertRaises(PlannerResponseError) as ctx:
                plan_from_playbook(_FIXTURE, lm=fake_lm, review=False)
        self.assertIn("DSPy prediction failed", str(ctx.exception))


class PlannerShapeTests(unittest.TestCase):
    def test_role_guard_row_passes_shape_check(self) -> None:
        row = {"test_type": "file_exists", "target": "/tmp/x", "role": "guard"}
        self.assertIsNone(_shape_check_row(row, 0))

    def test_role_verify_row_passes_shape_check(self) -> None:
        row = {"test_type": "file_exists", "target": "/tmp/x", "role": "verify"}
        self.assertIsNone(_shape_check_row(row, 0))

    def test_role_invalid_value_dropped(self) -> None:
        row = {"test_type": "file_exists", "target": "/tmp/x", "role": "bad_value"}
        msg = _shape_check_row(row, 3)
        self.assertIsNotNone(msg)
        self.assertIn("tests[3]", msg)
        self.assertIn("role", msg)

    def test_role_missing_passes_shape_check(self) -> None:
        row = {"test_type": "file_exists", "target": "/tmp/x"}
        self.assertIsNone(_shape_check_row(row, 0))


def test_plan_from_playbook_returns_planner_result(tmp_path: Path) -> None:
    pb = tmp_path / "play.yml"
    pb.write_text(
        "- hosts: all\n  tasks:\n    - name: install curl\n      apt:\n        name: curl\n"
    )
    fake_lm = MagicMock()
    pred = _make_prediction(("verify",))
    with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch("dspy.context"):
        mock_mod = MagicMock()
        mock_mod.return_value = pred
        gm.return_value = mock_mod
        result = plan_from_playbook(pb, lm=fake_lm)
    assert len(result.tests) == 1
    assert result.tests[0]["role"] == "verify"


def test_plan_from_playbook_filters_invalid_rows(tmp_path: Path) -> None:
    pb = tmp_path / "play.yml"
    pb.write_text("- hosts: all\n  tasks: []\n")
    fake_lm = MagicMock()
    plan = TestPlanDSPy(
        tests=[
            TestCaseDSPy(
                test_type="package_installed", target="curl", role="guard", reason="r"
            ),
            TestCaseDSPy(
                test_type="unknown_type_xyz", target="x", role="guard", reason="r"
            ),
        ]
    )
    pred = MagicMock(plan=plan)
    with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch("dspy.context"):
        mock_mod = MagicMock()
        mock_mod.return_value = pred
        gm.return_value = mock_mod
        result = plan_from_playbook(pb, lm=fake_lm)
    assert len(result.tests) == 1
    assert len(result.warnings) >= 1


def test_plan_from_playbook_raises_on_empty_valid_tests(tmp_path: Path) -> None:
    pb = tmp_path / "play.yml"
    pb.write_text("- hosts: all\n  tasks: []\n")
    fake_lm = MagicMock()
    plan = TestPlanDSPy(
        tests=[TestCaseDSPy(test_type="bad_type", target="x", role="guard", reason="r")]
    )
    pred = MagicMock(plan=plan)
    with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch("dspy.context"):
        mock_mod = MagicMock()
        mock_mod.return_value = pred
        gm.return_value = mock_mod
        with pytest.raises(PlannerResponseError):
            plan_from_playbook(pb, lm=fake_lm)


def test_plan_from_playbook_uses_input_context_summary(tmp_path: Path) -> None:
    pb = tmp_path / "play.yml"
    pb.write_text("- hosts: all\n  tasks: []\n")
    fake_lm = MagicMock()
    plan = TestPlanDSPy(
        tests=[
            TestCaseDSPy(
                test_type="package_installed", target="curl", role="verify", reason="r"
            )
        ]
    )
    pred = MagicMock(plan=plan)
    ctx = {"description": "Install curl", "predicted_impact": ["curl installed"]}
    with patch("aegis_test_generator.planner.llm_planner._get_module") as gm, patch("dspy.context"):
        mock_mod = MagicMock()
        mock_mod.return_value = pred
        gm.return_value = mock_mod
        plan_from_playbook(pb, lm=fake_lm, input_context=ctx)
    call_kwargs = mock_mod.call_args.kwargs
    assert "Install curl" in call_kwargs.get("context_summary", "")
