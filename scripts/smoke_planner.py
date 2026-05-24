"""Smoke test: run the planner on each example playbook and print results.

Usage:
    PYTHONPATH=src OPENAI_API_KEY=sk-... python scripts/smoke_planner.py

Each playbook is run through plan_from_playbook → validate_plan → render_plan.
Results are printed to stdout; generated files land in outputs/smoke/.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aegis_test_generator.generate import generate_tests  # noqa: E402

PLAYBOOKS = [
    ROOT / "examples" / "simple_patch.yml",
    ROOT / "examples" / "patch.yml",
    ROOT / "examples" / "complex_patch.yml",
]

OUTPUT_DIR = ROOT / "outputs" / "smoke"


def _divider(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)


def run(playbook: Path) -> None:
    _divider(playbook.name)
    result = generate_tests(playbook, output_path=OUTPUT_DIR / playbook.name.replace(".yml", "_tests.py"))

    print(f"\nGenerated {len(result.plan.tests)} test(s):")
    for tc in result.plan.tests:
        role_tag = f"[{tc.role}]"
        expected_part = f"  expected={tc.expected!r}" if tc.expected is not None else ""
        print(f"  {role_tag:<10}  {tc.test_type:<28}  target={tc.target!r}{expected_part}")
        if tc.reason:
            print(f"             reason: {tc.reason}")

    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  ! {w}")

    print(f"\nRendered → {result.path}")
    print("\n--- generated file ---")
    print(result.path.read_text(encoding="utf-8"))


def main() -> None:
    missing = [p for p in PLAYBOOKS if not p.exists()]
    if missing:
        print(f"ERROR: playbook(s) not found: {missing}", file=sys.stderr)
        sys.exit(1)

    failed = 0
    for playbook in PLAYBOOKS:
        try:
            run(playbook)
        except Exception as exc:
            _divider(f"FAILED: {playbook.name}")
            print(f"  {type(exc).__name__}: {exc}")
            failed += 1

    _divider("Summary")
    total = len(PLAYBOOKS)
    print(f"  {total - failed}/{total} playbooks succeeded")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
