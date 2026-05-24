from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import dspy

from aegis_test_generator.planner.dspy_planner import (
    TestCaseDSPy,
    TestPlanDSPy,
    TestPlanModule,
    make_lm,
)


def _make_plan(*roles: str) -> TestPlanDSPy:
    return TestPlanDSPy(
        tests=[
            TestCaseDSPy(
                test_type="package_installed", target="curl", role=r, reason="test"
            )
            for r in roles
        ]
    )


def _mock_module(plan: TestPlanDSPy) -> TestPlanModule:
    mod = TestPlanModule.__new__(TestPlanModule)
    pred = MagicMock(return_value=MagicMock(plan=plan))
    mod.generate = pred
    mod.review = pred
    return mod


def test_forward_no_review_skips_review_step() -> None:
    plan = _make_plan("verify")
    mod = _mock_module(plan)
    with (
        patch.object(mod, "generate", return_value=MagicMock(plan=plan)) as gen,
        patch.object(mod, "review") as rev,
    ):
        result = mod.forward("yaml: {}", review=False)
    gen.assert_called_once()
    rev.assert_not_called()
    assert result.plan is plan


def test_forward_with_review_calls_both_predictors() -> None:
    initial_plan = _make_plan("guard")
    revised_plan = _make_plan("verify")
    mod = TestPlanModule.__new__(TestPlanModule)
    mod.generate = MagicMock(return_value=MagicMock(plan=initial_plan))
    mod.review = MagicMock(return_value=MagicMock(plan=revised_plan))
    result = mod.forward("yaml: {}", review=True)
    mod.generate.assert_called_once()
    mod.review.assert_called_once()
    assert result.plan is revised_plan
    assert result.initial_plan is initial_plan


def test_forward_review_receives_initial_plan_as_json() -> None:
    initial_plan = _make_plan("guard")
    revised_plan = _make_plan("verify")
    mod = TestPlanModule.__new__(TestPlanModule)
    mod.generate = MagicMock(return_value=MagicMock(plan=initial_plan))
    mod.review = MagicMock(return_value=MagicMock(plan=revised_plan))
    mod.forward("yaml: {}", review=True)
    call_kwargs = mod.review.call_args.kwargs
    parsed = json.loads(call_kwargs["proposed_plan"])
    assert parsed["tests"][0]["role"] == "guard"


def test_make_lm_returns_dspy_lm() -> None:
    lm = make_lm("gpt-4o-mini", api_key="sk-test")
    assert isinstance(lm, dspy.LM)


def test_test_case_dspy_defaults() -> None:
    tc = TestCaseDSPy()
    assert tc.role == "guard"
    assert tc.test_type == ""


def test_test_plan_dspy_empty_tests() -> None:
    plan = TestPlanDSPy()
    assert plan.tests == []
