from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from runtime_skeleton.interfaces import (
    PatchApplyRequest,
    PatchApplyResult,
    SandboxComponent,
    SandboxCreateRequest,
    SandboxResult,
)
from runtime_skeleton.sandbox.config import load_sandbox_config
from runtime_skeleton.sandbox.playbook import resolve_playbook_yaml

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


def _safe_run_id(run_id: str) -> str:
    cleaned = _SAFE_NAME.sub("-", run_id.strip()).strip("-")
    return (cleaned or "run")[:56]


class DefaultSandboxComponent(SandboxComponent):
    """Sandbox component implementation preserving existing behavior."""

    def create(self, request: SandboxCreateRequest) -> SandboxResult:
        if request.skip:
            return SandboxResult(skipped=True, skip_reason="skip_requested")

        try:
            cfg = load_sandbox_config(request.repo_root)
        except (OSError, ValueError) as exc:
            return SandboxResult(skipped=True, skip_reason="config_error", error=str(exc))

        container_name = f"{cfg['container_name_prefix']}-{_safe_run_id(request.run_id)}"
        image = str(cfg["image"])
        cmd = ["docker", "run", "-d", "--name", container_name, image, *list(cfg["command"])]

        try:
            docker_info = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, timeout=30
            )
            if docker_info.returncode != 0:
                return SandboxResult(
                    skipped=True,
                    skip_reason="docker_unavailable",
                    error=(docker_info.stderr or docker_info.stdout or "docker info failed").strip(),
                )
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if cp.returncode != 0:
                return SandboxResult(
                    skipped=True,
                    skip_reason="docker_run_failed",
                    error=(cp.stderr or cp.stdout).strip(),
                )
            return SandboxResult(
                skipped=False,
                container_name=container_name,
                container_id=(cp.stdout or "").strip(),
                image=image,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SandboxResult(skipped=True, skip_reason="docker_error", error=str(exc))

    def apply_patch(self, request: PatchApplyRequest) -> PatchApplyResult:
        if request.skip:
            return PatchApplyResult(skipped=True, skip_reason="skip_requested")
        if not request.container_name:
            return PatchApplyResult(skipped=True, skip_reason="missing_container")
        if shutil.which("ansible-playbook") is None:
            return PatchApplyResult(skipped=True, skip_reason="ansible_not_found")

        try:
            playbook_yaml, source = resolve_playbook_yaml(
                patch=request.patch_section,
                repo_root=request.repo_root,
            )
        except (OSError, ValueError) as exc:
            return PatchApplyResult(
                skipped=True,
                skip_reason="playbook_resolve_failed",
                error=str(exc),
            )

        # Keep under repo-root ``artifacts/`` so a stray ``./runtime_skeleton/`` folder
        # never shadows the installed ``runtime_skeleton`` package during setuptools discovery.
        out_dir = request.repo_root / "artifacts" / "patch"
        out_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = out_dir / "inventory.ini"
        playbook_path = out_dir / "playbook.yml"
        log_path = out_dir / "ansible.log"

        try:
            s_cfg = load_sandbox_config(request.repo_root)
        except (OSError, ValueError) as exc:
            return PatchApplyResult(
                skipped=True,
                skip_reason="config_error",
                error=str(exc),
            )
        interp = str(s_cfg.get("ansible_python_interpreter") or "/usr/local/bin/python")

        inventory_path.write_text(
            "[sandbox]\n"
            f"{request.container_name} ansible_connection=docker ansible_user=root "
            f"ansible_python_interpreter={interp}\n",
            encoding="utf-8",
        )
        playbook_path.write_text(playbook_yaml, encoding="utf-8")

        cmd = [
            "ansible-playbook",
            "-i",
            str(inventory_path),
            str(playbook_path),
            "-v",
        ]
        env = os.environ.copy()
        env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        try:
            cp = subprocess.run(
                cmd, capture_output=True, text=True, timeout=900, env=env
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PatchApplyResult(
                skipped=False,
                error=f"ansible_exec_error: {exc}",
                source=source,
                log_path=str(log_path),
                patch_applied=False,
            )

        log_path.write_text((cp.stdout or "") + "\n\n" + (cp.stderr or ""), encoding="utf-8")
        return PatchApplyResult(
            skipped=False,
            error=None if cp.returncode == 0 else "ansible_run_failed",
            returncode=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            log_path=str(log_path),
            source=source,
            patch_applied=cp.returncode == 0,
        )


def create_sandbox_request(*, repo_root: Any, run_id: str, skip: bool = False) -> SandboxResult:
    component = DefaultSandboxComponent()
    return component.create(
        SandboxCreateRequest(
            repo_root=repo_root,
            run_id=run_id,
            skip=skip,
        )
    )


def apply_patch_request(
    *,
    repo_root: Any,
    container_name: str,
    patch_section: dict[str, Any],
    skip: bool = False,
) -> PatchApplyResult:
    component = DefaultSandboxComponent()
    return component.apply_patch(
        PatchApplyRequest(
            repo_root=repo_root,
            container_name=container_name,
            patch_section=patch_section,
            skip=skip,
        )
    )
