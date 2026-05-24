from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_skeleton.components.sandbox import apply_patch_request
from runtime_skeleton.interfaces import PatchApplyResult


def apply_patch(
    *,
    repo_root: Path,
    container_name: str,
    patch_section: dict[str, Any],
    skip: bool = False,
) -> PatchApplyResult:
    return apply_patch_request(
        repo_root=repo_root,
        container_name=container_name,
        patch_section=patch_section,
        skip=skip,
    )
