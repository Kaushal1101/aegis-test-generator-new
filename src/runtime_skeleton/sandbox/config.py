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

# Named image profiles for common enterprise target environments.
# bootstrap_commands are run via `docker exec` before Ansible connects, so
# images without Python can still be managed (Python is required for most modules).
IMAGE_PROFILES: dict[str, dict[str, Any]] = {
    "minimal": {
        "image": "python:3.12-slim-bookworm",
        "ansible_python_interpreter": "/usr/local/bin/python",
    },
    "debian-full": {
        "image": "debian:bookworm",
        "ansible_python_interpreter": "/usr/bin/python3",
        "bootstrap_commands": ["apt-get update -qq && apt-get install -y -qq python3"],
    },
    "ubuntu-lts": {
        "image": "ubuntu:22.04",
        "ansible_python_interpreter": "/usr/bin/python3",
        "bootstrap_commands": ["apt-get update -qq && apt-get install -y -qq python3"],
    },
    "rhel-compat": {
        "image": "rockylinux:9",
        "ansible_python_interpreter": "/usr/bin/python3",
        "bootstrap_commands": ["dnf install -y python3"],
    },
}


def load_sandbox_config(repo_root: Path) -> dict[str, Any]:
    """Load config/sandbox.json and merge with defaults.

    If a ``profile`` key is present it is resolved against IMAGE_PROFILES first,
    then any explicit keys in the file override the profile values.
    """
    cfg = dict(DEFAULT_SANDBOX)
    cfg_path = repo_root / "config" / "sandbox.json"
    if cfg_path.is_file():
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{cfg_path} must contain a JSON object")
        profile = loaded.get("profile")
        if profile is not None:
            if profile not in IMAGE_PROFILES:
                raise ValueError(
                    f"Unknown sandbox profile '{profile}'. "
                    f"Valid profiles: {list(IMAGE_PROFILES)}"
                )
            cfg.update(IMAGE_PROFILES[profile])
        cfg.update({k: v for k, v in loaded.items() if k != "profile"})
    cmd = cfg.get("command")
    if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
        raise ValueError("sandbox command must be a list[str]")
    apy = cfg.get("ansible_python_interpreter")
    if apy is not None and (not isinstance(apy, str) or not apy.strip()):
        raise ValueError("ansible_python_interpreter must be a non-empty string")
    return cfg
