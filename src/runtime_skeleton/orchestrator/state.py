from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime_skeleton.interfaces import DiffResult, ParsedInputResult, PatchApplyResult, SandboxResult


@dataclass
class PipelineState:
    """Minimal state used by the skeleton orchestrator."""

    repo_root: str
    input_path: str = ""
    input_json: dict[str, Any] | None = None
    execution_phase: str = "pre_patch"
    parsed_input: ParsedInputResult | None = None
    sandbox: SandboxResult | None = None
    patch_apply: PatchApplyResult | None = None
    pre_checks: list[dict[str, Any]] = field(default_factory=list)
    post_checks: list[dict[str, Any]] = field(default_factory=list)
    diff: DiffResult | None = None
