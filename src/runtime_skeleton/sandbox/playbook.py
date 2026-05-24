from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def patch_section_to_playbook_yaml(patch: dict[str, Any]) -> str:
    """Render minimal Ansible playbook YAML from analyzer patch section."""
    plays = patch.get("plays")
    if isinstance(plays, list) and plays:
        return yaml.safe_dump(plays, sort_keys=False, allow_unicode=True)
    raw_yaml = patch.get("raw_yaml")
    if isinstance(raw_yaml, str) and raw_yaml.strip():
        return raw_yaml.strip() + "\n"
    raise ValueError("Patch section has neither non-empty plays nor raw_yaml")


def resolve_playbook_yaml(*, patch: dict[str, Any], repo_root: Path) -> tuple[str, str]:
    """Resolve playbook YAML from inputs/patch.yml or patch section."""
    disk_patch = repo_root / "inputs" / "patch.yml"
    if disk_patch.is_file():
        return disk_patch.read_text(encoding="utf-8"), "inputs_patch_yml"
    return patch_section_to_playbook_yaml(patch), "parsed_patch_section"
