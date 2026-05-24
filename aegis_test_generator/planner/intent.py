"""Heuristic patch intent classifier.

Classifies the dominant intent of an Ansible playbook as one of:
    install, update, remove, configure, mixed

The result is injected into the LLM context summary so the planner generates
test types that match the patch's nature (e.g. update patches get paired
content_contains + content_not_contains tests instead of just file_exists).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import yaml


class PatchIntent(str, Enum):
    INSTALL = "install"
    UPDATE = "update"
    REMOVE = "remove"
    CONFIGURE = "configure"
    MIXED = "mixed"


# Ansible modules whose presence strongly implies modifying existing files
_UPDATE_MODULES = frozenset({"lineinfile", "replace", "blockinfile"})

# Package managers; intent depends on 'state'
_PKG_MODULES = frozenset({"apt", "yum", "dnf", "package", "pip", "gem"})

# Keys that are task metadata, not module names
_TASK_META_KEYS = frozenset({
    "name", "when", "register", "notify", "tags", "become", "become_user",
    "ignore_errors", "failed_when", "changed_when", "loop", "with_items",
    "with_list", "vars", "environment", "no_log", "block", "rescue", "always",
    "listen", "timeout", "delegate_to", "run_once",
})


def _iter_tasks(playbook: list[Any]):
    """Yield every task dict from all plays, pre_tasks, post_tasks, and handlers."""
    for play in playbook:
        if not isinstance(play, dict):
            continue
        for section in ("tasks", "pre_tasks", "post_tasks", "handlers"):
            for task in play.get(section) or []:
                if isinstance(task, dict):
                    yield task


def _module_args(task: dict[str, Any], module: str) -> dict[str, Any]:
    """Return the args dict for a module in a task, handling both dict and string forms."""
    val = task.get(module)
    if isinstance(val, dict):
        return val
    return {}


def classify_patch_intent(
    playbook_yaml: str,
    *,
    diff_modified: list[str] | None = None,
) -> PatchIntent:
    """Classify a patch's primary intent from its playbook YAML.

    Uses simple heuristics: module names + state values + diff context.
    Returns MIXED when the playbook combines multiple intent types.
    """
    try:
        parsed = yaml.safe_load(playbook_yaml)
    except yaml.YAMLError:
        return PatchIntent.MIXED

    if not isinstance(parsed, list) or not parsed:
        return PatchIntent.MIXED

    signals: set[str] = set()
    modified_set = set(diff_modified or [])

    for task in _iter_tasks(parsed):
        for key in task:
            if key in _TASK_META_KEYS:
                continue

            # Direct update-signal modules
            if key in _UPDATE_MODULES:
                signals.add("update")
                continue

            # template / copy — intent depends on whether dest is in diff.modified
            if key in ("template", "copy"):
                args = _module_args(task, key)
                dest = str(args.get("dest", "") or "")
                if modified_set and any(
                    dest == p or dest.endswith("/" + p.lstrip("/")) or p.endswith("/" + dest.lstrip("/"))
                    for p in modified_set
                ):
                    signals.add("update")
                else:
                    signals.add("configure")
                continue

            # Package managers
            if key in _PKG_MODULES:
                args = _module_args(task, key)
                state = str(args.get("state", "present")).lower()
                if state in ("latest", "upgraded"):
                    signals.add("update")
                elif state == "absent":
                    signals.add("remove")
                else:
                    signals.add("install")
                continue

            # file module — state=absent means removal
            if key == "file":
                args = _module_args(task, key)
                state = str(args.get("state", "")).lower()
                if state == "absent":
                    signals.add("remove")
                # directory/file creation — configure, not install
                elif state in ("directory", "touch", "link", "hard"):
                    signals.add("configure")
                continue

            # service / systemd — typically accompanies another intent, not a primary signal
            # command / shell — too generic to classify
            # (leave signals unchanged for these)

    if not signals:
        return PatchIntent.MIXED

    if len(signals) == 1:
        return {
            "install": PatchIntent.INSTALL,
            "update": PatchIntent.UPDATE,
            "remove": PatchIntent.REMOVE,
            "configure": PatchIntent.CONFIGURE,
        }.get(next(iter(signals)), PatchIntent.MIXED)

    # update + configure together is still an update (changing existing configs)
    if signals == {"update", "configure"}:
        return PatchIntent.UPDATE

    return PatchIntent.MIXED
