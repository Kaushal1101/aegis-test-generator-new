from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def sandbox_state_to_playbook_yaml(state: dict[str, Any]) -> str:
    """Convert a sandbox_state dict into an Ansible setup playbook that pre-populates
    a container to simulate a real machine before the pre-phase tests run.
    """
    tasks: list[dict[str, Any]] = []

    # Packages (apt install, ordered before files so dependencies are available)
    for pkg in state.get("packages", []):
        if isinstance(pkg, str):
            name, version = pkg, None
        else:
            name = pkg.get("name", "")
            version = pkg.get("version")
        if not name:
            continue
        pkg_spec = f"{name}={version}" if version else name
        tasks.append({
            "name": f"Install {name}",
            "apt": {"name": pkg_spec, "state": "present", "update_cache": True},
        })

    # Ensure parent directories exist before writing files
    dirs_created: set[str] = set()
    for file_def in state.get("files", []):
        if not isinstance(file_def, dict):
            continue
        path = file_def.get("path", "")
        parent = str(Path(path).parent) if path else ""
        if parent and parent != "/" and parent not in dirs_created:
            dirs_created.add(parent)
            tasks.append({
                "name": f"Ensure directory {parent}",
                "file": {"path": parent, "state": "directory", "mode": "0755"},
            })

    # Files
    for file_def in state.get("files", []):
        if not isinstance(file_def, dict):
            continue
        path = file_def.get("path", "")
        if not path:
            continue
        copy_args: dict[str, Any] = {"dest": path, "content": file_def.get("content", "")}
        if "mode" in file_def:
            copy_args["mode"] = file_def["mode"]
        if "owner" in file_def:
            copy_args["owner"] = file_def["owner"]
        tasks.append({"name": f"Write {path}", "copy": copy_args})

    # Services (note: containers without systemd will skip these gracefully)
    for svc in state.get("services", []):
        if not isinstance(svc, dict):
            continue
        name = svc.get("name", "")
        if not name:
            continue
        svc_args: dict[str, Any] = {"name": name}
        if "state" in svc:
            svc_args["state"] = svc["state"]
        if "enabled" in svc:
            svc_args["enabled"] = svc["enabled"]
        tasks.append({"name": f"Configure service {name}", "service": svc_args})

    # Users
    for user_def in state.get("users", []):
        if not isinstance(user_def, dict):
            continue
        name = user_def.get("name", "")
        if not name:
            continue
        user_args: dict[str, Any] = {"name": name, "state": "present"}
        if "uid" in user_def:
            user_args["uid"] = user_def["uid"]
        tasks.append({"name": f"Create user {name}", "user": user_args})

    if not tasks:
        raise ValueError("sandbox_state produced no setup tasks")

    play = [{
        "name": "Initialize sandbox state",
        "hosts": "sandbox",
        "gather_facts": False,
        "tasks": tasks,
    }]
    return yaml.safe_dump(play, sort_keys=False, allow_unicode=True)


def resolve_state_yaml(*, sandbox_state: dict[str, Any], repo_root: Path) -> tuple[str, str]:
    """Resolve setup YAML from inputs/sandbox_state.yml or the sandbox_state section.

    Mirrors resolve_playbook_yaml: disk file takes precedence so operators can
    drop a hand-crafted playbook without modifying the input document.
    """
    disk_state = repo_root / "inputs" / "sandbox_state.yml"
    if disk_state.is_file():
        return disk_state.read_text(encoding="utf-8"), "inputs_sandbox_state_yml"
    return sandbox_state_to_playbook_yaml(sandbox_state), "parsed_sandbox_state"
