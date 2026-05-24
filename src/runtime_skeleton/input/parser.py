from __future__ import annotations

from typing import Any

from runtime_skeleton.components.input import build_derived as _build_derived
from runtime_skeleton.components.input import parse_input_request
from runtime_skeleton.input.models import DerivedSummary, InputDocument
from runtime_skeleton.interfaces import ParsedInputResult


def build_derived(doc: InputDocument) -> DerivedSummary:
    return _build_derived(doc)


def parse_input(
    *,
    input_path: str | None = None,
    input_json: dict[str, Any] | None = None,
) -> ParsedInputResult:
    component_result = parse_input_request(
        input_path=input_path,
        input_json=input_json,
    )
    return ParsedInputResult(
        parsed=component_result.parsed,
        derived=component_result.derived,
        warnings=component_result.warnings,
        error=component_result.error,
    )
