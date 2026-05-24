"""High-level playbook → validated plan → rendered Testinfra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis_test_generator.planner.llm_planner import plan_from_playbook
from aegis_test_generator.regression import guard_coverage_sufficiency
from aegis_test_generator.test_templates.renderer import render_plan
from aegis_test_generator.test_templates.schemas import TestPlan, validate_plan


@dataclass(frozen=True)
class GenerateResult:
    path: Path
    plan: TestPlan
    warnings: list[str]


def generate_tests(
    playbook_path: Path,
    output_path: Path | None = None,
    *,
    client: Any = None,
    model: str | None = None,
    input_context: dict[str, Any] | None = None,
    review: bool = True,
) -> GenerateResult:
    """Planner → validate → render; propagate typed planner and schema/renderer errors."""
    result = plan_from_playbook(
        playbook_path,
        client=client,
        model=model,
        input_context=input_context,
        review=review,
    )
    plan = validate_plan(result.tests)
    path = render_plan(plan, output_path=output_path)

    warnings = list(result.warnings)
    if input_context:
        diff = input_context.get("diff") or {}
        sv = input_context.get("sensitivity_verdict") or {}
        pi = input_context.get("predicted_impact") or {}
        sufficiency_warnings = guard_coverage_sufficiency(
            plan.tests,
            diff_modified=diff.get("modified") or [],
            sensitivity_scored_files=sv.get("scored_files") or [],
            predicted_impact_files=pi.get("files") or [],
        )
        warnings.extend(sufficiency_warnings)

    return GenerateResult(path=path, plan=plan, warnings=warnings)
