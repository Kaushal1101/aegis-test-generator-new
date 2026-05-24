from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from runtime_skeleton.input.models import DerivedSummary, InputDocument
from runtime_skeleton.interfaces import InputComponent, InputRequest, InputResult

_EXPECTED_SECTIONS = frozenset(
    {"patch", "diff", "sensitivity_verdict", "predicted_impact", "apply"}
)


def _load_raw(input_path: str | None, input_json: dict[str, Any] | None) -> dict[str, Any]:
    if input_json is not None:
        if not isinstance(input_json, dict):
            raise ValueError("input_json must be a JSON object")
        return input_json
    if not input_path:
        raise ValueError("Either input_path or input_json is required")
    p = Path(input_path)
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def build_derived(doc: InputDocument) -> DerivedSummary:
    added = [x.path for x in doc.diff.added]
    modified = [x.path for x in doc.diff.modified]
    removed = [x.path for x in doc.diff.removed]
    errors = [x.path for x in doc.diff.errors]
    high = [x.path for x in doc.sensitivity_verdict.scored_files if (x.score or 0) >= 0.75]
    predicted = [x.path for x in doc.predicted_impact.files]
    materialized = sorted(set(added + modified + removed))
    predicted_not_materialized = sorted([p for p in predicted if p not in materialized])
    materialized_not_predicted = sorted([m for m in materialized if m not in predicted])
    return DerivedSummary(
        verdict=doc.sensitivity_verdict.verdict,
        diff_added_paths=added,
        diff_modified_paths=modified,
        diff_removed_paths=removed,
        diff_error_paths=errors,
        high_sensitivity_paths=high,
        predicted_not_materialized=predicted_not_materialized,
        materialized_not_predicted=materialized_not_predicted,
    )


class DefaultInputComponent(InputComponent):
    """Input component implementation preserving existing parser semantics."""

    def parse(self, input_request: InputRequest) -> InputResult:
        try:
            raw = _load_raw(input_request.input_path, input_request.input_json)
            doc = InputDocument.model_validate(raw)
            if doc.schema_version != "1.0":
                raise ValueError(f"Unsupported schema_version: {doc.schema_version}")

            warnings: list[str] = []
            declared = set(doc.meta.sections_present)
            if declared and declared != _EXPECTED_SECTIONS:
                missing = sorted(_EXPECTED_SECTIONS - declared)
                extra = sorted(declared - _EXPECTED_SECTIONS)
                if missing:
                    warnings.append(f"meta.sections_present missing entries: {missing}")
                if extra:
                    warnings.append(f"meta.sections_present unexpected entries: {extra}")

            derived = build_derived(doc)
            return InputResult(
                parsed=doc.model_dump(mode="json"),
                derived=derived.model_dump(mode="json"),
                warnings=warnings,
                error=None,
            )
        except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            return InputResult(parsed={}, derived={}, warnings=[], error=str(exc))


def parse_input_request(
    *,
    input_path: str | None = None,
    input_json: dict[str, Any] | None = None,
) -> InputResult:
    component = DefaultInputComponent()
    return component.parse(
        InputRequest(
            input_path=input_path,
            input_json=input_json,
        )
    )
