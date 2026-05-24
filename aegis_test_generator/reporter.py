"""Human-readable markdown report writer for a completed pipeline run.

Produces one .md file per run containing:
  - What the patch does (inferred from playbook task names)
  - What the pipeline expects to change (verify-role tests)
  - What the pipeline guards against (guard-role tests)
  - Per-test results with the LLM's stated reason and transition outcome
  - Final verdict
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from aegis_test_generator.runner.testinfra_runner import TestinfraRunner
    from runtime_skeleton.interfaces import PipelineSnapshot

_IDX_RE = re.compile(r"::test_(\d+)_")

_STATUS_SYMBOL = {
    "verified": "✓ verified",
    "verification_failed": "✗ verification failed",
    "still_pass": "✓ still passing",
    "still_fail": "~ still failing",
    "regressed": "✗ regressed",
    "fixed": "✓ fixed",
    "new_pass": "✓ new pass",
    "new_fail": "✗ new fail",
}


def _task_names_from_yaml(raw_yaml: str) -> list[str]:
    """Extract task names from a playbook YAML string."""
    try:
        plays = yaml.safe_load(raw_yaml)
        if not isinstance(plays, list):
            return []
        names: list[str] = []
        for play in plays:
            if not isinstance(play, dict):
                continue
            for task in play.get("tasks") or []:
                if isinstance(task, dict):
                    name = task.get("name") or task.get("action") or ""
                    if name:
                        names.append(str(name))
        return names
    except Exception:
        return []


def _idx_from_check_id(check_id: str) -> int | None:
    m = _IDX_RE.search(check_id)
    return int(m.group(1)) if m else None


def _pre_post_status(t: dict[str, Any]) -> tuple[str, str]:
    pre = (t.get("pre") or {}).get("status") or "—"
    post = (t.get("post") or {}).get("status") or "—"
    return pre, post


def _verdict_line(patch_verified: bool, regression_detected: bool) -> str:
    if patch_verified and not regression_detected:
        return "**PASS** — patch achieved its goals and introduced no regressions."
    if not patch_verified and not regression_detected:
        return "**FAIL** — patch did not achieve one or more of its stated goals."
    if regression_detected and patch_verified:
        return "**PARTIAL** — patch goals verified but regressions were introduced."
    return "**FAIL** — patch goals not met and regressions were introduced."


def write_run_report(
    snap: "PipelineSnapshot",
    runner: "TestinfraRunner | None",
    output_path: Path,
    *,
    run_name: str = "",
) -> Path:
    """Write a markdown report for one pipeline run. Returns the written path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parsed_input = snap.parsed_input
    parsed: dict[str, Any] = (
        parsed_input.parsed
        if parsed_input is not None and hasattr(parsed_input, "parsed")
        else (parsed_input if isinstance(parsed_input, dict) else {})
    )
    patch_section = parsed.get("patch") or {}
    raw_yaml = patch_section.get("raw_yaml") or ""
    task_names = _task_names_from_yaml(raw_yaml)

    test_plan = runner._test_plan if runner is not None else None
    transitions: list[dict[str, Any]] = []
    if snap.diff is not None:
        transitions = snap.diff.transitions or []

    # Build a lookup: test index → TestCase
    plan_lookup: dict[int, Any] = {}
    if test_plan is not None:
        for i, tc in enumerate(test_plan.tests):
            plan_lookup[i] = tc

    # Enrich each transition with its TestCase
    enriched: list[dict[str, Any]] = []
    for t in transitions:
        check_id = t.get("check_id", "")
        idx = _idx_from_check_id(check_id)
        tc = plan_lookup.get(idx) if idx is not None else None
        pre_status, post_status = _pre_post_status(t)
        enriched.append({
            "check_id": check_id,
            "role": t.get("role", "guard"),
            "status": t.get("status", ""),
            "pre": pre_status,
            "post": post_status,
            "test_type": tc.test_type if tc else "",
            "target": tc.target if tc else "",
            "reason": tc.reason or "" if tc else "",
        })

    verify_rows = [e for e in enriched if e["role"] == "verify"]
    guard_rows = [e for e in enriched if e["role"] == "guard"]

    diff = snap.diff
    patch_verified = snap.patch_verified
    regression_detected = diff.regression_detected if diff else False
    verified_count = diff.verified_count if diff else 0
    vfailed_count = diff.verification_failed_count if diff else 0
    regressed_count = diff.regressed_count if diff else 0

    sb = snap.sandbox
    pa = snap.patch_apply
    sandbox_line = (
        f"`{sb.container_name}` (image: `{sb.image}`)"
        if sb and not sb.skipped
        else f"skipped — {sb.skip_reason if sb else 'unknown'}"
    )
    patch_line = (
        "Applied successfully"
        if pa and pa.patch_applied
        else f"Not applied — {pa.skip_reason or pa.error if pa else 'unknown'}"
    )

    lines: list[str] = []

    # ── Header ───────────────────────────────────────────────────────────────
    title = run_name or "Pipeline Run"
    lines += [
        f"# {title}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**Sandbox:** {sandbox_line}  ",
        f"**Patch apply:** {patch_line}",
        "",
        f"## Verdict",
        "",
        _verdict_line(patch_verified, regression_detected),
        "",
        f"| Verified | Verification failed | Regressed |",
        f"|---|---|---|",
        f"| {verified_count} | {vfailed_count} | {regressed_count} |",
        "",
    ]

    # ── What the patch does ───────────────────────────────────────────────────
    lines += ["## What the patch does", ""]
    if task_names:
        lines.append("The playbook contains the following tasks:")
        lines.append("")
        for name in task_names:
            lines.append(f"- {name}")
    else:
        lines.append("*(Playbook task names could not be extracted.)*")
    lines.append("")

    # Infer goals from verify-role tests
    if verify_rows:
        lines.append(
            "Based on the verify-role tests the pipeline generated, "
            "the patch is expected to:"
        )
        lines.append("")
        for e in verify_rows:
            action = _infer_goal(e["test_type"], e["target"])
            lines.append(f"- {action}")
    lines.append("")

    # ── Patch verification tests ──────────────────────────────────────────────
    lines += ["## Patch verification tests", ""]
    lines.append(
        "These tests confirm the patch achieved its stated goals. "
        "Each was expected to fail before the patch and pass after."
    )
    lines.append("")

    if verify_rows:
        lines += [
            "| Test type | Target | Reason | Pre | Post | Result |",
            "|---|---|---|---|---|---|",
        ]
        for e in verify_rows:
            sym = _STATUS_SYMBOL.get(e["status"], e["status"])
            reason = e["reason"] or "—"
            lines.append(
                f"| `{e['test_type']}` | `{e['target']}` "
                f"| {reason} | {e['pre']} | {e['post']} | {sym} |"
            )
    else:
        lines.append("*(No verify-role tests were generated for this run.)*")
    lines.append("")

    # ── Regression guard tests ────────────────────────────────────────────────
    lines += ["## Regression guard tests", ""]
    lines.append(
        "These tests confirm the patch did not accidentally break "
        "anything it was not supposed to touch. "
        "They were expected to keep passing throughout."
    )
    lines.append("")

    if guard_rows:
        lines += [
            "| Test type | Target | Reason | Pre | Post | Result |",
            "|---|---|---|---|---|---|",
        ]
        for e in guard_rows:
            sym = _STATUS_SYMBOL.get(e["status"], e["status"])
            reason = e["reason"] or "—"
            lines.append(
                f"| `{e['test_type']}` | `{e['target']}` "
                f"| {reason} | {e['pre']} | {e['post']} | {sym} |"
            )
    else:
        lines.append("*(No guard-role tests were generated for this run.)*")
    lines.append("")

    # ── Pipeline messages ─────────────────────────────────────────────────────
    messages = snap.testsuite_messages or []
    if messages:
        lines += ["## Pipeline warnings", ""]
        for m in messages:
            lines.append(f"- {m}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _infer_goal(test_type: str, target: str) -> str:
    """Convert a test_type + target into a plain-English goal statement."""
    m = {
        "package_installed": f"Install the `{target}` package",
        "package_absent": f"Remove the `{target}` package",
        "package_version": f"Set `{target}` to the expected version",
        "file_exists": f"Create the file `{target}`",
        "file_absent": f"Delete the file `{target}`",
        "directory_exists": f"Create the directory `{target}`",
        "symlink_exists": f"Create a symlink at `{target}`",
        "content_contains": f"Write expected content to `{target}`",
        "content_not_contains": f"Remove disallowed content from `{target}`",
        "file_mode": f"Set permissions on `{target}`",
        "file_owner": f"Set ownership of `{target}`",
        "service_running": f"Start the `{target}` service",
        "service_enabled": f"Enable the `{target}` service at boot",
        "port_listening": f"Open port `{target}`",
        "user_exists": f"Create the user `{target}`",
        "group_exists": f"Create the group `{target}`",
        "command_succeeds": f"Ensure `{target}` runs successfully",
        "command_output_contains": f"Ensure `{target}` produces expected output",
        "binary_executable": f"Install the executable `{target}`",
    }
    return m.get(test_type, f"`{test_type}` on `{target}`")
