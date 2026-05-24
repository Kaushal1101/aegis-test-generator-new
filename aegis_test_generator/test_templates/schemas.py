"""Pydantic models for validated LLM test plans."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from aegis_test_generator.planner.llm_planner import SUPPORTED_TEST_TYPES


class SchemaValidationError(ValueError):
    """Plan rows failed validation; callers need not depend on pydantic."""

    __slots__ = ()


_ALLOWED_TEST_TYPES = frozenset(SUPPORTED_TEST_TYPES)


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    __test__ = False

    test_type: str
    target: str
    expected: str | int | bool | None = None
    reason: str | None = None
    role: Literal["guard", "verify"] = "guard"

    @field_validator("test_type")
    @classmethod
    def supported_type(cls, v: object) -> str:
        if not isinstance(v, str) or v not in _ALLOWED_TEST_TYPES:
            raise ValueError(
                "test_type must be one of: " + ", ".join(sorted(_ALLOWED_TEST_TYPES))
            )
        return v

    @field_validator("target")
    @classmethod
    def non_empty_target(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("target must be a non-empty string")
        return v


class TestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    __test__ = False

    tests: list[TestCase] = Field(min_length=1)


def validate_plan(rows: list[dict]) -> TestPlan:
    """Validate planner rows into a ``TestPlan``; raises ``SchemaValidationError`` on failure."""
    if not isinstance(rows, list):
        raise SchemaValidationError("plan rows must be a list")
    try:
        return TestPlan.model_validate({"tests": rows})
    except ValidationError as exc:
        raise SchemaValidationError(str(exc)) from exc
