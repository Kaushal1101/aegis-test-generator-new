"""Optional post-evaluation transition exception classifier."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from runtime_skeleton.interfaces import ClassifierResult

if TYPE_CHECKING:
    from openai import OpenAI

DEFAULT_MODEL = "gpt-4o"


class ClassifierError(Exception):
    """Base error for classifier failures."""


class ClassifierResponseError(ClassifierError):
    """Raised when classifier response shape is invalid."""


def _build_messages(
    transitions: list[dict[str, Any]],
    *,
    parsed_input: dict[str, Any],
) -> list[dict[str, str]]:
    system = (
        "You are a transition exception classifier for regression reporting. "
        "You will be given pipeline input context and evaluation transitions. "
        "Each transition carries a 'role' field: 'verify' means the check was expected "
        "to change because of the patch (e.g. a newly installed package, created file, "
        "or started service); 'guard' means the check should have been unaffected by "
        "the patch. "
        "For each transition, classify it as follows: "
        "a verify-role transition with status 'verification_failed' means the patch did "
        "not achieve its stated goal — set applicable=false and explain the patch intent. "
        "a verify-role transition with status 'verified' is the expected success — "
        "set applicable=true. "
        "a guard-role transition with status 'regressed' is an unexpected side effect — "
        "set applicable=true if it is a genuine regression, applicable=false if it is a "
        "known harmless side effect. "
        "Return JSON only in shape: "
        '{"annotations":[{"check_id":"...","applicable":true|false,"reason":"..."}]} '
        "Do not include fields besides check_id, applicable, reason."
    )
    payload = {
        "input_context": parsed_input,
        "transitions": transitions,
    }
    user = "Classify these transitions:\n" + json.dumps(payload, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _call_openai(
    messages: list[dict[str, str]],
    *,
    client: "OpenAI | None",
    model: str | None,
) -> tuple[str, str]:
    from aegis_test_generator._openai_client import OpenAICallError, call_openai

    try:
        return call_openai(
            messages, client=client, model=model, default_model=DEFAULT_MODEL
        )
    except OpenAICallError as exc:
        raise ClassifierError(str(exc)) from exc


def _parse_annotations(raw: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClassifierResponseError(f"classifier output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ClassifierResponseError("classifier output root must be an object")
    rows = obj.get("annotations")
    if not isinstance(rows, list):
        raise ClassifierResponseError('classifier output must include "annotations" array')
    out: list[dict[str, Any]] = []
    warnings: list[str] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            warnings.append(f"dropped annotations[{idx}]: not an object")
            continue
        cid = row.get("check_id")
        applicable = row.get("applicable")
        reason = row.get("reason")
        if not isinstance(cid, str) or not cid.strip():
            warnings.append(f"dropped annotations[{idx}]: invalid check_id")
            continue
        if not isinstance(applicable, bool):
            warnings.append(f"dropped annotations[{idx}]: applicable must be bool")
            continue
        out.append(
            {
                "check_id": cid.strip(),
                "applicable": applicable,
                "reason": str(reason or ""),
            }
        )
    return out, warnings


def classify_transitions(
    transitions: list[dict[str, Any]],
    *,
    parsed_input: dict[str, Any],
    client: OpenAI | None = None,
    model: str | None = None,
) -> ClassifierResult:
    """Classify transitions as applicable/non-applicable with explicit reasons."""
    messages = _build_messages(transitions, parsed_input=parsed_input)
    raw, used_model = _call_openai(messages, client=client, model=model)
    annotations, warnings = _parse_annotations(raw)
    return ClassifierResult(
        annotations=annotations,
        raw=raw,
        warnings=warnings,
        model=used_model,
    )

