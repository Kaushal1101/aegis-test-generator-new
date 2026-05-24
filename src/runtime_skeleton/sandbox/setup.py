from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_skeleton.components.sandbox import apply_setup_request
from runtime_skeleton.interfaces import SetupApplyResult


def apply_setup(
    *,
    repo_root: Path,
    container_name: str,
    sandbox_state: dict[str, Any],
    skip: bool = False,
) -> SetupApplyResult:
    return apply_setup_request(
        repo_root=repo_root,
        container_name=container_name,
        sandbox_state=sandbox_state,
        skip=skip,
    )
