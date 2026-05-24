from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_SANDBOX: dict[str, Any] = {
    # Debian slim with Python pre-installed so Ansible docker connection works.
    "image": "python:3.12-slim-bookworm",
    "container_name_prefix": "runtime-skeleton-sandbox",
    "command": ["sleep", "infinity"],
    "ansible_python_interpreter": "/usr/local/bin/python",
}


def load_sandbox_config(repo_root: Path) -> dict[str, Any]:
    """Load config/sandbox.json and merge with defaults."""
    cfg = dict(DEFAULT_SANDBOX)
    cfg_path = repo_root / "config" / "sandbox.json"
    if cfg_path.is_file():
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{cfg_path} must contain a JSON object")
        cfg.update(loaded)
    cmd = cfg.get("command")
    if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
        raise ValueError("sandbox command must be a list[str]")
    apy = cfg.get("ansible_python_interpreter")
    if apy is not None and (not isinstance(apy, str) or not apy.strip()):
        raise ValueError("ansible_python_interpreter must be a non-empty string")
    return cfg
