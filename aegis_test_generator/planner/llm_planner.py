"""LLM-driven test plan generation from Ansible playbook YAML.

Loads a playbook file, validates YAML, optionally truncates long inputs, then runs a
DSPy ``TestPlanModule`` (structured predictors) under ``dspy.context`` to obtain test
rows for later validation by ``test_templates/schemas.py``.

Environment variables
-----------------------
``OPENAI_API_KEY``
    Required when ``plan_from_playbook`` is called without a pre-built ``lm`` and
    without an injected ``client`` (``client`` is retained for backward compatibility
    but is not used by the DSPy path).
``OPENAI_MODEL``
    Optional. Defaults to ``gpt-4o`` when not set and ``model=`` is not passed.

``.env``
    Before resolving credentials, loads the nearest ``.env`` file: first ancestor
    directory of ``playbook_path`` that contains ``.env``, else ``dotenv_find`` from the
    current working directory.

Truncation
----------
Playbooks longer than ``MAX_PLAYBOOK_CHARS`` characters are truncated to that
length with a ``\\n# ... TRUNCATED ...`` marker appended. A warning is added to
``PlannerResult.warnings``.

Input context
-------------
Optional ``input_context`` (typically the parsed pipeline input JSON) may be passed
to ``plan_from_playbook``. When provided, a readable summary (description, predicted
impact, diff / sensitivity / impact blocks when present) is passed to the DSPy module
as ``context_summary``.

Review pass
-----------
When ``review`` is ``True`` (default), the DSPy module runs a second predictor that
revises the initial plan. Disable with ``review=False`` to save latency and quota.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from openai import OpenAI

__all__ = [
    "DEFAULT_MODEL",
    "MAX_PLAYBOOK_CHARS",
    "PlannerError",
    "PlannerResponseError",
    "PlannerResult",
    "PlaybookLoadError",
    "SUPPORTED_TEST_TYPES",
    "plan_from_playbook",
]

DEFAULT_MODEL = "gpt-4o"
MAX_PLAYBOOK_CHARS = 40_000

SUPPORTED_TEST_TYPES: tuple[str, ...] = (
    "file_exists",
    "file_absent",
    "directory_exists",
    "package_installed",
    "package_absent",
    "content_contains",
    "content_not_contains",
    "content_changed",
    "file_mode",
    "file_mode_changed",
    "file_owner",
    "binary_executable",
    "command_succeeds",
    "service_running",
    "service_enabled",
    "port_listening",
    "user_exists",
    "group_exists",
    "symlink_exists",
    "command_output_contains",
    "package_version",
    "package_version_range",
)

_TRUNCATION_MARKER = "\n# ... TRUNCATED ..."
_MAX_SENSITIVITY_ROWS = 10

_MODULE: Any = None  # lazily initialised ``TestPlanModule`` singleton


def _get_module() -> Any:
    global _MODULE
    if _MODULE is None:
        from aegis_test_generator.planner.dspy_planner import TestPlanModule

        _MODULE = TestPlanModule()
    return _MODULE


def _load_dotenv(playbook_path: Path) -> None:
    """Populate os.environ from a project ``.env`` without requiring manual export."""
    try:
        from dotenv import find_dotenv
        from dotenv import load_dotenv as dotenv_load
    except ImportError:
        return
    resolved = playbook_path.resolve()
    directory = resolved.parent if resolved.is_file() else resolved
    while True:
        candidate = directory / ".env"
        if candidate.is_file():
            dotenv_load(candidate)
            return
        parent = directory.parent
        if parent == directory:
            found = find_dotenv(usecwd=True)
            if found:
                dotenv_load(found)
            return
        directory = parent


class PlannerError(Exception):
    """Base error for planner failures (configuration, missing deps)."""


class PlaybookLoadError(PlannerError):
    """Playbook file could not be read or YAML is invalid."""


class PlannerResponseError(PlannerError):
    """DSPy or downstream shaping failed or produced no valid plan rows."""


@dataclass(frozen=True)
class PlannerResult:
    """Result of planning from a playbook; rows are not Pydantic-validated yet."""

    tests: list[dict[str, Any]]
    raw: str
    warnings: list[str]
    model: str


def plan_from_playbook(
    playbook_path: Path,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
    input_context: dict[str, Any] | None = None,
    review: bool = True,
    lm: Any | None = None,
) -> PlannerResult:
    """Load ``playbook_path``, run DSPy planning, return shaped test rows."""
    del client  # retained for backward compatibility; DSPy uses ``lm`` / env key
    _load_dotenv(playbook_path)

    text = _load_playbook_text(playbook_path)
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PlaybookLoadError(f"Invalid YAML in playbook: {exc}") from exc

    playbook_text, truncate_warnings = _maybe_truncate(text)
    resolved_model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

    if lm is None and not os.environ.get("OPENAI_API_KEY"):
        raise PlannerError(
            "OPENAI_API_KEY is required when no client is passed to plan_from_playbook"
        )

    import dspy

    from aegis_test_generator.planner.dspy_planner import make_lm

    resolved_lm = lm if lm is not None else make_lm(
        resolved_model,
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    from aegis_test_generator.planner.intent import classify_patch_intent

    ctx = input_context if isinstance(input_context, dict) else None
    diff_modified: list[str] = []
    if ctx:
        diff = ctx.get("diff") or {}
        if isinstance(diff, dict):
            diff_modified = _paths_from_diff_entries(diff.get("modified", []))
    intent = classify_patch_intent(playbook_text, diff_modified=diff_modified)
    if ctx:
        context_summary = _dspy_context_summary(ctx, patch_intent=intent)
    else:
        context_summary = f"PATCH INTENT: {intent.value.upper()}"
    supported_types = ", ".join(SUPPORTED_TEST_TYPES)
    module = _get_module()

    try:
        with dspy.context(lm=resolved_lm):
            prediction = module(
                playbook_yaml=playbook_text,
                context_summary=context_summary,
                supported_types=supported_types,
                review=review,
            )
    except Exception as exc:
        raise PlannerResponseError(f"DSPy prediction failed: {exc}") from exc

    raw_plan = prediction.plan
    raw_rows = [tc.model_dump() for tc in raw_plan.tests]

    valid: list[dict[str, Any]] = []
    warnings: list[str] = list(truncate_warnings)
    for index, dumped in enumerate(raw_rows):
        row = _dspy_dump_to_plan_row(dumped)
        warn = _shape_check_row(row, index)
        if warn is not None:
            warnings.append(warn)
        else:
            valid.append(row)

    if not valid:
        raise PlannerResponseError("DSPy returned no valid test cases after shaping")

    return PlannerResult(
        tests=valid,
        raw=json.dumps(raw_rows, ensure_ascii=False),
        warnings=warnings,
        model=resolved_model,
    )


_TYPES_REQUIRING_EXPECTED: frozenset[str] = frozenset({
    "content_contains",
    "content_not_contains",
    "content_changed",
    "file_mode",
    "file_mode_changed",
    "file_owner",
    "command_output_contains",
    "package_version",
    "package_version_range",
})

# These types additionally require expected_before (the pre-patch value)
_TYPES_REQUIRING_EXPECTED_BEFORE: frozenset[str] = frozenset({
    "file_mode_changed",
})


def _dspy_dump_to_plan_row(dumped: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "test_type": dumped.get("test_type") or "",
        "target": dumped.get("target") or "",
    }
    role = dumped.get("role")
    if role is not None:
        row["role"] = role
    reason = dumped.get("reason")
    if isinstance(reason, str) and reason.strip():
        row["reason"] = reason.strip()
    # Accept expected directly on the row or nested inside args
    expected = dumped.get("expected")
    if expected is None:
        args = dumped.get("args")
        if isinstance(args, dict):
            expected = args.get("expected")
    if expected is not None:
        row["expected"] = expected
    expected_before = dumped.get("expected_before")
    if expected_before is not None:
        row["expected_before"] = expected_before
    return row


def _load_playbook_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PlaybookLoadError(f"Playbook not found: {path}") from exc
    except OSError as exc:
        raise PlaybookLoadError(f"Could not read playbook {path}: {exc}") from exc


def _maybe_truncate(text: str) -> tuple[str, list[str]]:
    if len(text) <= MAX_PLAYBOOK_CHARS:
        return text, []
    truncated = text[:MAX_PLAYBOOK_CHARS] + _TRUNCATION_MARKER
    warn = (
        f"Playbook truncated from {len(text)} to {MAX_PLAYBOOK_CHARS} characters "
        f"(see {_TRUNCATION_MARKER.strip()})"
    )
    return truncated, [warn]


def _paths_from_diff_entries(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return []
    paths: list[str] = []
    for item in entries:
        if isinstance(item, dict):
            p = item.get("path")
            if isinstance(p, str) and p.strip():
                paths.append(p.strip())
        elif isinstance(item, str) and item.strip():
            paths.append(item.strip())
    return paths


def _predicted_impact_paths(impact: Any) -> set[str]:
    if not isinstance(impact, dict):
        return set()
    files = impact.get("files")
    if not isinstance(files, list):
        return set()
    out: set[str] = set()
    for item in files:
        if isinstance(item, dict):
            p = item.get("path")
            if isinstance(p, str) and p.strip():
                out.add(p.strip())
    return out


def _top_scored_files(sensitivity: Any, *, limit: int) -> list[tuple[str, float]]:
    if not isinstance(sensitivity, dict):
        return []
    rows = sensitivity.get("scored_files")
    if not isinstance(rows, list):
        return []
    scored: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        p = row.get("path")
        if not isinstance(p, str) or not p.strip():
            continue
        raw_score = row.get("score", 0.0)
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0
        scored.append((p.strip(), score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def _format_pipeline_diff_summary(input_context: dict[str, Any]) -> str:
    """DIFF / sensitivity / predicted-impact block (pipeline-shaped ``input_context``)."""
    diff = input_context.get("diff")
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    if isinstance(diff, dict):
        added = _paths_from_diff_entries(diff.get("added"))
        modified = _paths_from_diff_entries(diff.get("modified"))
        removed = _paths_from_diff_entries(diff.get("removed"))

    sv = input_context.get("sensitivity_verdict")
    scored = _top_scored_files(sv, limit=_MAX_SENSITIVITY_ROWS)

    pi = input_context.get("predicted_impact")
    impact_sorted = sorted(_predicted_impact_paths(pi))

    def _paths_line(label: str, paths: list[str]) -> str:
        if not paths:
            return f"    {label}: (none)"
        return f"    {label}: " + ", ".join(paths)

    lines: list[str] = [
        "DIFF SUMMARY:",
        _paths_line("added", added),
        _paths_line("modified", modified),
        _paths_line("removed", removed),
        "",
        "SENSITIVITY (higher score means higher change risk; "
        f"top {_MAX_SENSITIVITY_ROWS} by score):",
    ]
    if scored:
        for path, score in scored:
            lines.append(f"    {path}  score={score}")
    else:
        lines.append("    (none)")
    lines.extend(
        [
            "",
            "PREDICTED IMPACT (paths the upstream system expects this patch to touch):",
        ]
    )
    if impact_sorted:
        lines.append("    " + ", ".join(impact_sorted))
    else:
        lines.append("    (none)")
    return "\n".join(lines)


def _format_priority_targets(
    diff_modified: list[str],
    scored_files: list[tuple[str, float]],
) -> str:
    """Explicit priority section for high-sensitivity modified files.

    Guides the LLM to generate targeted paired (verify + guard) tests for each
    modified file rather than generic ones.
    """
    if not diff_modified:
        return ""
    score_map = {p: s for p, s in scored_files}
    ordered = sorted(diff_modified, key=lambda p: score_map.get(p, 0.0), reverse=True)
    lines = [
        "PRIORITY UPDATE TEST TARGETS (modified files, ordered by sensitivity score):",
    ]
    for path in ordered:
        score = score_map.get(path, 0.0)
        risk = " [HIGH RISK]" if score >= 0.5 else ""
        lines.append(f"    {path}  score={score:.2f}{risk}")
    lines.append(
        "\nFor EACH target above: generate a verify test for the expected new "
        "content/state AND a guard test confirming unrelated sections are preserved."
    )
    return "\n".join(lines)


def _dspy_context_summary(
    ctx: dict[str, Any],
    *,
    patch_intent: Any | None = None,
) -> str:
    """Readable ``context_summary`` string for the DSPy module."""
    parts: list[str] = []

    if patch_intent is not None:
        intent_val = patch_intent.value if hasattr(patch_intent, "value") else str(patch_intent)
        parts.append(f"PATCH INTENT: {intent_val.upper()}")

    desc = ctx.get("description")
    if isinstance(desc, str) and desc.strip():
        parts.append(f"Description: {desc.strip()}")

    predicted = ctx.get("predicted_impact") or ctx.get("PREDICTED_IMPACT")
    if isinstance(predicted, list) and predicted:
        parts.append("Predicted impact: " + ", ".join(str(x) for x in predicted))

    pi = ctx.get("predicted_impact")
    if ctx.get("diff") or ctx.get("sensitivity_verdict") or isinstance(pi, dict):
        legacy = _format_pipeline_diff_summary(ctx).strip()
        if legacy:
            parts.append(legacy)

    # Diff-seeded priority targets section for update patches
    diff = ctx.get("diff") or {}
    if isinstance(diff, dict):
        modified = _paths_from_diff_entries(diff.get("modified", []))
        sv = ctx.get("sensitivity_verdict")
        scored = _top_scored_files(sv, limit=_MAX_SENSITIVITY_ROWS)
        priority_block = _format_priority_targets(modified, scored)
        if priority_block:
            parts.append(priority_block)

    return "\n\n".join(parts)


_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _strip_json_fences(raw_text: str) -> str:
    text = raw_text.strip()
    match = _FENCE_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return text


def _extract_plan_rows(raw_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    stripped = _strip_json_fences(raw_text)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise PlannerResponseError(f"Model output is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PlannerResponseError('expected top-level JSON object with key "tests"')

    if "tests" not in parsed or not isinstance(parsed["tests"], list):
        raise PlannerResponseError('expected {"tests": [...]} with "tests" as a JSON array')

    tests_list = parsed["tests"]
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, row in enumerate(tests_list):
        warn = _shape_check_row(row, index)
        if warn is not None:
            warnings.append(warn)
        else:
            assert isinstance(row, dict)
            valid.append(row)

    if not valid:
        raise PlannerResponseError("no valid plan rows after validation")

    return valid, warnings


def _shape_check_row(row: Any, index: int) -> str | None:
    if not isinstance(row, dict):
        return f"dropped tests[{index}]: row is not a JSON object"
    test_type = row.get("test_type")
    if test_type not in SUPPORTED_TEST_TYPES:
        return f"dropped tests[{index}]: invalid or missing test_type={test_type!r}"
    target = row.get("target")
    if not isinstance(target, str) or not target.strip():
        return f"dropped tests[{index}]: target must be a non-empty string"
    role = row.get("role")
    if role is not None and role not in ("guard", "verify"):
        return f"dropped tests[{index}]: role must be 'guard' or 'verify', got {role!r}"
    if test_type in _TYPES_REQUIRING_EXPECTED and row.get("expected") is None:
        return f"dropped tests[{index}]: test_type={test_type!r} requires a non-null 'expected' value"
    if test_type in _TYPES_REQUIRING_EXPECTED_BEFORE and row.get("expected_before") is None:
        return (
            f"dropped tests[{index}]: test_type={test_type!r} requires a non-null 'expected_before' value "
            "(the mode before the patch)"
        )
    return None
