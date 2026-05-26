#!/usr/bin/env python3
"""Run all Aegis examples end-to-end and write reports to outputs/reports/.

Usage:
    python run_examples.py

Requires:
    - OPENAI_API_KEY in .env or environment
    - Docker running
    - Ansible installed (pip install ansible)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Load .env before importing anything that reads env vars
from dotenv import load_dotenv
load_dotenv()

import os

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from aegis_test_generator.reporter import write_run_report
from aegis_test_generator.runner.testinfra_runner import TestinfraRunner
from runtime_skeleton.orchestrator.pipeline import run_pipeline

REPORTS_DIR = ROOT / "outputs" / "reports"
TESTS_DIR = ROOT / "outputs" / "generated_tests"

EXAMPLES = [
    {
        "name": "simple",
        "input_path": ROOT / "examples" / "simple_input.json",
        "playbook":   ROOT / "examples" / "simple_patch.yml",
        "run_name":   "simple_patch — install curl",
        "report":     "simple.md",
    },
    {
        "name": "complex",
        "input_path": ROOT / "examples" / "complex_input.json",
        "playbook":   ROOT / "examples" / "complex_patch.yml",
        "run_name":   "complex_patch — install git+curl, create /opt/aegis",
        "report":     "complex.md",
    },
    {
        "name": "broken",
        "input_path": ROOT / "examples" / "broken_input.json",
        "playbook":   ROOT / "examples" / "broken_patch.yml",
        "run_name":   "broken_patch — nonexistent package (expect FAIL)",
        "report":     "broken.md",
    },
    {
        "name": "partial",
        "input_path": ROOT / "examples" / "partial_input.json",
        "playbook":   ROOT / "examples" / "partial_patch.yml",
        "run_name":   "partial_patch — mixed tasks (expect FAIL_VERIFY)",
        "report":     "partial.md",
    },
]


def run_example(example: dict) -> bool:
    name      = example["name"]
    run_name  = example["run_name"]
    report_fn = example["report"]

    print(f"\n{'─' * 60}")
    print(f"  {run_name}")
    print(f"{'─' * 60}")

    runner = TestinfraRunner(
        playbook_path=example["playbook"],
        output_path=TESTS_DIR / f"{name}_tests.py",
    )

    try:
        snap = run_pipeline(
            repo_root=ROOT,
            input_path=str(example["input_path"]),
            runner=runner,
        )
    except Exception as exc:
        print(f"  [ERROR] pipeline failed: {exc}")
        return False

    report_path = REPORTS_DIR / report_fn
    try:
        write_run_report(snap, runner, report_path, run_name=run_name)
    except Exception as exc:
        print(f"  [ERROR] report failed: {exc}")
        return False

    diff = snap.diff
    pa   = snap.patch_apply
    sb   = snap.sandbox

    patch_applied = pa.patch_applied if pa else False
    verified      = diff.verified_count if diff else 0
    v_failed      = diff.verification_failed_count if diff else 0
    regressed     = diff.regressed_count if diff else 0
    image         = sb.image if sb and not sb.skipped else "skipped"

    print(f"  Container image : {image}")
    print(f"  Patch applied   : {patch_applied}")
    print(f"  Verified        : {verified}")
    print(f"  Verify failed   : {v_failed}")
    print(f"  Regressed       : {regressed}")
    print(f"  Report          : outputs/reports/{report_fn}")

    if snap.testsuite_messages:
        for msg in snap.testsuite_messages:
            print(f"  [WARN] {msg}")

    return True


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set. Add it to .env or export it.")
        sys.exit(1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nRunning {len(EXAMPLES)} examples...")

    results: dict[str, bool] = {}
    for example in EXAMPLES:
        results[example["name"]] = run_example(example)

    print(f"\n{'═' * 60}")
    print("  Summary")
    print(f"{'═' * 60}")
    for name, ok in results.items():
        status = "ok" if ok else "FAILED"
        report = next(e["report"] for e in EXAMPLES if e["name"] == name)
        print(f"  {name:<12} {status:<8}  outputs/reports/{report}")
    print()


if __name__ == "__main__":
    main()
