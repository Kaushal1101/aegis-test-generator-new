"""DSPy module for structured test-plan generation.

Callers should use ``TestPlanModule`` directly; ``llm_planner.py`` is the only
intended production caller.
"""

from __future__ import annotations

import json
import os
from typing import Any

import dspy
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Permissive output schemas (used by DSPy predictors — not the strict Pydantic
# schemas in test_templates/schemas.py which are validated separately).
# ---------------------------------------------------------------------------


class TestCaseDSPy(BaseModel):
    __test__ = False

    test_type: str = ""
    target: str = ""
    expected: Any = None
    expected_before: Any = None
    args: dict[str, Any] = Field(default_factory=dict)
    role: str = "guard"
    reason: str = ""


class TestPlanDSPy(BaseModel):
    __test__ = False

    tests: list[TestCaseDSPy] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Role-assignment heuristics injected into the signature docstring so every
# DSPy optimiser that reads the docstring inherits them.
# ---------------------------------------------------------------------------

_ROLE_RULES = """\
Role assignment rules:
- Installs a new package → verify, test_type=package_installed
- Removes a package → verify, test_type=package_absent
- Updates a package to a specific version → verify, test_type=package_version
- Creates a new file or directory → verify, test_type=file_exists or directory_exists
- Deletes a file → verify, test_type=file_absent
- Modifies an existing file's content → TWO tests:
    verify, test_type=content_contains  (the new value that must now be present)
    guard,  test_type=content_not_contains  (the old value that must no longer appear)
- Changes a file's permissions → verify, test_type=file_mode
- Changes a file's owner → verify, test_type=file_owner
- Starts or enables a service → verify, test_type=service_running
- Reconfigures a service (changes its config file) → TWO tests:
    verify, test_type=service_running  (service is still up after the config change)
    guard,  test_type=content_contains  (an unrelated config section that must be preserved)
- Anything unchanged by the patch (bystander resource) → guard
- When no input_context is available, default all roles to guard
"""

_SUPPORTED = (
    "file_exists, file_absent, directory_exists, package_installed, package_absent, "
    "content_contains, content_not_contains, content_changed, "
    "file_mode, file_mode_changed, file_owner, binary_executable, "
    "command_succeeds, service_running, service_enabled, port_listening, "
    "user_exists, group_exists, symlink_exists, command_output_contains, "
    "package_version, package_version_range"
)

_GENERATE_DOC = (
    "Generate a JSON test plan for an Ansible playbook.\n\n"
    "Each test must have: test_type (one of supported_types), target (string), "
    'role ("guard" or "verify"), reason (string).\n'
    "For these test_types you MUST also include an 'expected' field (string):\n"
    "  content_contains, content_not_contains → expected is the substring to search for\n"
    "  content_changed → expected is the OLD content substring that must no longer appear\n"
    "  file_mode → expected is the octal mode string e.g. '0644'\n"
    "  file_mode_changed → expected is the NEW mode; also set expected_before to the OLD mode\n"
    "  file_owner → expected is the owner username e.g. 'root'\n"
    "  command_output_contains → expected is the substring expected in stdout\n"
    "  package_version → expected is the exact version string\n"
    "  package_version_range → expected is a PEP-440 specifier e.g. '>=2.0,<3.0'\n\n"
    "For update/maintenance patches (modifying existing files or config): generate PAIRED tests —\n"
    "one verify test asserting the new value is present, and one guard test asserting the\n"
    "old value is gone. This is more valuable than a single test for detecting partial updates.\n\n"
) + _ROLE_RULES

_REVIEW_DOC = (
    "Review and improve a proposed test plan for an Ansible playbook.\n\n"
    "Fix any role mis-assignments, add missing verify checks for stated patch goals, "
    "and add guard checks for things the patch should not touch.\n"
    "Ensure every content_contains, content_not_contains, content_changed, file_mode, "
    "file_mode_changed, file_owner, command_output_contains, package_version, and "
    "package_version_range test includes a non-null 'expected' field. "
    "For file_mode_changed also set 'expected_before' to the old mode.\n"
    "For any file-modification task, check that paired verify+guard tests exist: "
    "a content_contains for the new value AND a content_not_contains for the old value.\n\n"
) + _ROLE_RULES


# ---------------------------------------------------------------------------
# DSPy Signatures
# ---------------------------------------------------------------------------


class GeneratePlanSignature(dspy.Signature):
    playbook_yaml: str = dspy.InputField(desc="Full YAML text of the Ansible playbook")
    context_summary: str = dspy.InputField(
        desc="Optional summary of pipeline input context (empty string if unavailable)"
    )
    supported_types: str = dspy.InputField(
        desc="Comma-separated list of valid test_type values"
    )
    plan: TestPlanDSPy = dspy.OutputField(desc="Structured test plan")


class ReviewPlanSignature(dspy.Signature):
    playbook_yaml: str = dspy.InputField(desc="Full YAML text of the Ansible playbook")
    context_summary: str = dspy.InputField(
        desc="Optional summary of pipeline input context"
    )
    supported_types: str = dspy.InputField(
        desc="Comma-separated list of valid test_type values"
    )
    proposed_plan: str = dspy.InputField(
        desc="JSON representation of the initial test plan to review"
    )
    plan: TestPlanDSPy = dspy.OutputField(desc="Revised test plan")


GeneratePlanSignature.__doc__ = _GENERATE_DOC
ReviewPlanSignature.__doc__ = _REVIEW_DOC


# ---------------------------------------------------------------------------
# DSPy Module
# ---------------------------------------------------------------------------


class TestPlanModule(dspy.Module):
    __test__ = False

    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(GeneratePlanSignature)
        self.review = dspy.Predict(ReviewPlanSignature)

    def forward(
        self,
        playbook_yaml: str,
        context_summary: str = "",
        supported_types: str = _SUPPORTED,
        *,
        review: bool = True,
    ) -> dspy.Prediction:
        initial = self.generate(
            playbook_yaml=playbook_yaml,
            context_summary=context_summary,
            supported_types=supported_types,
        )
        if not review:
            return dspy.Prediction(initial_plan=initial.plan, plan=initial.plan)
        proposed_json = json.dumps(initial.plan.model_dump(), ensure_ascii=False)
        revised = self.review(
            playbook_yaml=playbook_yaml,
            context_summary=context_summary,
            supported_types=supported_types,
            proposed_plan=proposed_json,
        )
        return dspy.Prediction(initial_plan=initial.plan, plan=revised.plan)


def make_lm(model: str, *, api_key: str | None = None) -> dspy.LM:
    """Return a configured ``dspy.LM`` for the given OpenAI model name."""
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    return dspy.LM(f"openai/{model}", api_key=key, temperature=0)
