"""End-to-end pipeline smoke test.

Runs the full sequence for two example playbooks:
  Sandbox create → TestSuite pre → apply_patch → TestSuite post → Evaluate

Usage:
    PYTHONPATH=src OPENAI_API_KEY=sk-... python scripts/smoke_pipeline.py

Requires: Docker running, ansible-playbook on PATH, testinfra + pytest-json-report installed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aegis_test_generator.reporter import write_run_report  # noqa: E402
from aegis_test_generator.runner.testinfra_runner import TestinfraRunner  # noqa: E402
from runtime_skeleton.orchestrator.pipeline import run_pipeline  # noqa: E402

REPORTS_DIR = ROOT / "outputs" / "reports"

def _make_input(run_id: str, playbook: Path) -> dict:
    return {
        "schema_version": "1.0",
        "meta": {
            "run_id": run_id,
            "sections_present": ["patch", "diff", "sensitivity_verdict", "predicted_impact", "apply"],
        },
        "patch": {"raw_yaml": playbook.read_text()},
        "diff": {"added": [], "modified": [], "removed": [], "errors": []},
        "sensitivity_verdict": {"verdict": "low", "scored_files": []},
        "predicted_impact": {"files": []},
        "apply": {},
    }


CASES = [
    {
        "name": "simple_patch (install curl)",
        "playbook": ROOT / "examples" / "simple_patch.yml",
        "input_json": _make_input("smoke-simple", ROOT / "examples" / "simple_patch.yml"),
        "expect_verified": True,
    },
    {
        "name": "patch (nginx install + service)",
        "playbook": ROOT / "examples" / "patch.yml",
        "input_json": _make_input("smoke-nginx", ROOT / "examples" / "patch.yml"),
        "expect_verified": True,
    },
    {
        "name": "complex_patch (git+curl, directory, config file)",
        "playbook": ROOT / "examples" / "complex_patch.yml",
        "input_json": _make_input("smoke-complex", ROOT / "examples" / "complex_patch.yml"),
        "expect_verified": True,
    },
    {
        "name": "broken_patch (nonexistent package — expect verification_failed)",
        "playbook": ROOT / "examples" / "broken_patch.yml",
        "input_json": _make_input("smoke-broken", ROOT / "examples" / "broken_patch.yml"),
        "expect_verified": False,
    },
    {
        "name": "partial_patch (curl+dir succeed, bad package ignored)",
        "playbook": ROOT / "examples" / "partial_patch.yml",
        "input_json": _make_input("smoke-partial", ROOT / "examples" / "partial_patch.yml"),
        "expect_verified": True,
    },
]


def _divider(label: str, char: str = "=") -> None:
    print(f"\n{char * 64}")
    print(f"  {label}")
    print(char * 64)


def _cleanup(container_prefix: str) -> None:
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={container_prefix}", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    for name in result.stdout.strip().splitlines():
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _print_checks(label: str, checks: list[dict]) -> None:
    print(f"\n  {label} ({len(checks)} check(s)):")
    for c in checks:
        role = c.get("role", "guard")
        status = c.get("status", "?")
        title = c.get("title", c.get("check_id", "?"))
        symbol = {"pass": "✓", "fail": "✗", "skip": "~", "error": "!"}.get(status, "?")
        print(f"    {symbol} [{role:<6}] {status:<5}  {title}")


def _print_transitions(transitions: list[dict]) -> None:
    print(f"\n  Transitions ({len(transitions)}):")
    for t in transitions:
        role = t.get("role", "guard")
        status = t.get("transition", t.get("status", "?"))
        check_id = t.get("check_id", "?")
        title = check_id.rsplit("::", 1)[-1] if "::" in check_id else check_id
        symbols = {
            "verified": "✓✓", "still_pass": "✓", "fixed": "✓+",
            "verification_failed": "✗✗", "regressed": "✗", "still_fail": "✗~",
        }
        sym = symbols.get(status, "  ")
        print(f"    {sym} [{role:<6}] {status:<22}  {title}")


def run_case(case: dict) -> bool:
    _divider(case["name"])
    playbook: Path = case["playbook"]
    input_json: dict = case["input_json"]
    run_id: str = input_json["meta"]["run_id"]
    expect_verified: bool = case.get("expect_verified", True)

    _cleanup(f"runtime-skeleton-sandbox-{run_id}")

    runner = TestinfraRunner(
        playbook_path=playbook,
        output_path=ROOT / "outputs" / "smoke" / f"{run_id}_tests.py",
        review=True,
    )

    print(f"\n  Playbook : {playbook.name}")
    print(f"  Run ID   : {run_id}")

    try:
        snap = run_pipeline(
            repo_root=ROOT,
            input_json=input_json,
            runner=runner,
        )
    except Exception as exc:
        print(f"\n  PIPELINE ERROR: {type(exc).__name__}: {exc}")
        return False
    finally:
        _cleanup(f"runtime-skeleton-sandbox-{run_id}")

    # Sandbox
    sb = snap.sandbox
    if sb and not sb.skipped:
        print(f"\n  Sandbox  : {sb.container_name} (image={sb.image})")
    elif sb:
        print(f"\n  Sandbox  : skipped — {sb.skip_reason}")

    # Patch
    pa = snap.patch_apply
    if pa:
        status = "applied" if pa.patch_applied else f"skipped ({pa.skip_reason})"
        print(f"  Patch    : {status}")

    # Pre/post checks (from runner warnings if available)
    if runner.last_warnings:
        print(f"\n  Runner warnings: {runner.last_warnings}")

    # Diff / evaluation
    diff = snap.diff
    if diff is None:
        print("\n  No diff produced.")
        return False

    # Reconstruct pre/post from transitions for display
    pre_checks = [
        {"check_id": t["check_id"], "title": t.get("title", ""), "role": t.get("role", "guard"),
         "status": t.get("pre_status", "?")}
        for t in (diff.transitions or []) if t.get("pre_status")
    ]
    post_checks = [
        {"check_id": t["check_id"], "title": t.get("title", ""), "role": t.get("role", "guard"),
         "status": t.get("post_status", "?")}
        for t in (diff.transitions or []) if t.get("post_status")
    ]
    if pre_checks:
        _print_checks("Pre-patch", pre_checks)
    if post_checks:
        _print_checks("Post-patch", post_checks)

    _print_transitions(diff.transitions or [])

    _divider("Results", char="-")
    print(f"  patch_verified      : {snap.patch_verified}")
    print(f"  regression_detected : {diff.regression_detected}")
    print(f"  verified_count      : {diff.verified_count}")
    print(f"  verification_failed : {diff.verification_failed_count}")
    print(f"  regressed_count     : {diff.regressed_count}")
    print(f"  still_pass_count    : {diff.counts.get('still_pass', 0)}")

    if snap.testsuite_messages:
        print(f"\n  Pipeline messages:")
        for m in snap.testsuite_messages:
            print(f"    ! {m}")

    behaved_as_expected = (snap.patch_verified == expect_verified) and not diff.regression_detected
    label = "PASS" if behaved_as_expected else "FAIL"
    expected_label = "verified" if expect_verified else "verification_failed"
    print(f"\n  Expected: patch_verified={expect_verified} ({expected_label}) → {label}")

    report_path = REPORTS_DIR / f"{run_id}.md"
    write_run_report(snap, runner, report_path, run_name=case["name"])
    print(f"  Report  : {report_path}")

    return behaved_as_expected


def main() -> None:
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        print("Run:  export OPENAI_API_KEY=sk-...", file=sys.stderr)
        sys.exit(1)

    results: list[tuple[str, bool]] = []
    for case in CASES:
        ok = run_case(case)
        results.append((case["name"], ok))

    _divider("Summary")
    for name, ok in results:
        symbol = "✓" if ok else "✗"
        print(f"  {symbol}  {name}")


if __name__ == "__main__":
    main()
