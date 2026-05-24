from __future__ import annotations

from pathlib import Path

from runtime_skeleton.components.sandbox import create_sandbox_request
from runtime_skeleton.interfaces import SandboxResult


def create_sandbox(*, repo_root: Path, run_id: str, skip: bool = False) -> SandboxResult:
    return create_sandbox_request(repo_root=repo_root, run_id=run_id, skip=skip)
