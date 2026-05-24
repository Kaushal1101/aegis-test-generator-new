"""High-level playbook → validated plan → rendered Testinfra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aegis_test_generator.planner.llm_planner import plan_from_playbook
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
    return GenerateResult(path=path, plan=plan, warnings=result.warnings)
