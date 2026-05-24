"""Tests for aegis_test_generator.test_templates.schemas."""

from __future__ import annotations

import pydantic

import pytest

from aegis_test_generator.planner.llm_planner import SUPPORTED_TEST_TYPES
from aegis_test_generator.test_templates.schemas import (
    SchemaValidationError,
    TestCase,
    TestPlan,
    validate_plan,
)


def test_validate_plan_happy_single_minimal_row() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x"}]
    plan = validate_plan(rows)
    assert isinstance(plan, TestPlan)
    assert len(plan.tests) == 1
    tc = plan.tests[0]
    assert tc.test_type == "file_exists"
    assert tc.target == "/tmp/x"
    assert tc.expected is None
    assert tc.reason is None


@pytest.mark.parametrize("test_type", SUPPORTED_TEST_TYPES)
def test_validate_plan_each_test_type_accepted(test_type: str) -> None:
    extras: dict[str, object] = {}
    if test_type in (
        "content_contains",
        "content_not_contains",
        "file_mode",
        "file_owner",
    ):
        extras["expected"] = (
            "needle" if test_type.startswith("content_") else "644" if test_type == "file_mode" else "root"
        )
    rows = [{"test_type": test_type, "target": "/x", **extras}]
    plan = validate_plan(rows)
    assert plan.tests[0].test_type == test_type


def test_validate_plan_raises_on_unknown_type() -> None:
    rows = [{"test_type": "not_supported", "target": "/"}]
    with pytest.raises(SchemaValidationError) as excinfo:
        validate_plan(rows)
    assert isinstance(excinfo.value.__cause__, pydantic.ValidationError)


def test_validate_plan_raises_on_empty_rows() -> None:
    with pytest.raises(SchemaValidationError):
        validate_plan([])


def test_validate_plan_raises_on_missing_target() -> None:
    rows = [{"test_type": "file_exists"}]
    with pytest.raises(SchemaValidationError):
        validate_plan(rows)


def test_validate_plan_raises_blank_target() -> None:
    rows = [{"test_type": "file_exists", "target": "  "}]
    with pytest.raises(SchemaValidationError):
        validate_plan(rows)


def test_validate_plan_raises_on_non_list() -> None:
    with pytest.raises(SchemaValidationError, match="list"):
        validate_plan({})  # type: ignore[arg-type]


def test_validate_plan_rejects_unknown_extra_fields() -> None:
    rows = [{"test_type": "file_exists", "target": "/x", "extra_col": True}]
    with pytest.raises(SchemaValidationError):
        validate_plan(rows)


def test_testcase_optional_fields_default_none() -> None:
    tc = TestCase(test_type="file_exists", target="/a")
    assert tc.expected is None
    assert tc.reason is None


def test_role_defaults_to_guard() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x"}]
    plan = validate_plan(rows)
    assert plan.tests[0].role == "guard"


def test_role_verify_accepted() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x", "role": "verify"}]
    plan = validate_plan(rows)
    assert plan.tests[0].role == "verify"


def test_role_guard_accepted() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x", "role": "guard"}]
    plan = validate_plan(rows)
    assert plan.tests[0].role == "guard"


def test_role_invalid_value_raises() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x", "role": "unknown"}]
    with pytest.raises(SchemaValidationError):
        validate_plan(rows)


def test_role_none_raises() -> None:
    rows = [{"test_type": "file_exists", "target": "/tmp/x", "role": None}]
    with pytest.raises(SchemaValidationError):
        validate_plan(rows)
