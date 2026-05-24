"""Testinfra runner adapter for the runtime_skeleton TestSuite pipeline.

Implements the ``TestSuiteRunner`` protocol from
``runtime_skeleton.interfaces.contracts``. The first executed phase generates a
Testinfra test module from an Ansible playbook (via the LLM planner +
fixed-template renderer), executes it with ``pytest`` against the sandbox
container over Docker, and returns normalized check records. The generated test
module path is cached and reused in subsequent phases.

Failures (missing sandbox, generation errors, subprocess crashes, malformed
report) raise ``TestinfraRunnerError`` (or ``TimeoutError`` for hard timeouts),
which the TestSuite component surfaces as a warning while the pipeline keeps
running with available check lists (non-destructive policy).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from aegis_test_generator.generate import generate_tests
from aegis_test_generator.planner.llm_planner import PlannerError
from aegis_test_generator.test_templates.renderer import RendererError
from aegis_test_generator.test_templates.schemas import SchemaValidationError, TestPlan

__all__ = [
    "DEFAULT_PYTEST_TIMEOUT_S",
    "TestinfraRunner",
    "TestinfraRunnerError",
]


DEFAULT_PYTEST_TIMEOUT_S = 300

_NODEID_INDEX_RE = re.compile(r"::test_(\d+)_")


class TestinfraRunnerError(RuntimeError):
    """Raised by TestinfraRunner for hard failures the TestSuite should surface."""

    __test__ = False


_PYTEST_OUTCOME_MAP: dict[str, str] = {
    "passed": "pass",
    "failed": "fail",
    "error": "error",
    "skipped": "skip",
    "xfailed": "pass",
    "xpassed": "fail",
}


@dataclass
class TestinfraRunner:
    """``TestSuiteRunner`` adapter wrapping plan -> render -> pytest/Testinfra.

    Construction parameters configure the LLM planner (``client``, ``model``)
    and where the generated Testinfra module is written (``output_path``).
    The Docker container target is read from ``phase_context["sandbox"]`` at
    ``run_phase`` time, so the same runner instance can be reused across
    different sandboxes if desired.

    ``review`` (default ``True``): when set, ``plan_from_playbook`` runs a second LLM call
    to filter the proposed checks before rendering.
    """

    __test__ = False

    playbook_path: Path
    output_path: Path | None = None
    client: Any = None
    model: str | None = None
    timeout_s: int = DEFAULT_PYTEST_TIMEOUT_S
    suite_id: str = "testinfra"
    review: bool = True
    last_warnings: list[str] = field(default_factory=list)
    _generated_file: Path | None = field(default=None, init=False, repr=False)
    _test_plan: TestPlan | None = field(default=None, init=False, repr=False)

    def run_phase(
        self,
        phase: Literal["pre", "post"],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self.last_warnings = []
        if phase not in {"pre", "post"}:
            raise TestinfraRunnerError(f"unsupported phase: {phase!r}")
        container_name = self._require_container_name(context)
        raw_input = context.get("input") if isinstance(context, dict) else None
        input_context = raw_input if isinstance(raw_input, dict) else None
        generated_file = self._generated_file
        if generated_file is None:
            generated_file = self._generate(self.playbook_path, input_context=input_context)
            self._generated_file = generated_file
        with tempfile.TemporaryDirectory(prefix="aegis-testinfra-") as tmp:
            report_path = Path(tmp) / "report.json"
            cmd = self._build_pytest_command(generated_file, container_name, report_path)
            completed = self._invoke_pytest(cmd, timeout=self.timeout_s)
            self._guard_pytest_exit(completed, report_path)
            report = self._load_report(report_path)
        return list(self._records_from_report(report))

    def _require_container_name(self, context: dict[str, Any]) -> str:
        sandbox = context.get("sandbox") if isinstance(context, dict) else None
        if sandbox is None:
            raise TestinfraRunnerError(
                "TestinfraRunner requires phase_context['sandbox'] for test execution"
            )
        skipped = bool(getattr(sandbox, "skipped", False))
        container_name = str(getattr(sandbox, "container_name", "") or "").strip()
        if skipped or not container_name:
            raise TestinfraRunnerError(
                "TestinfraRunner cannot run: sandbox is skipped or container_name is empty"
            )
        return container_name

    def _generate(
        self,
        playbook_path: Path,
        input_context: dict[str, Any] | None,
    ) -> Path:
        try:
            result = generate_tests(
                playbook_path,
                output_path=self.output_path,
                client=self.client,
                model=self.model,
                input_context=input_context,
                review=self.review,
            )
            self._test_plan = result.plan
            for w in result.warnings:
                self.last_warnings.append(f"generate: {w}")
            return result.path
        except (PlannerError, SchemaValidationError, RendererError) as exc:
            raise TestinfraRunnerError(f"failed to generate Testinfra tests: {exc}") from exc

    def _role_for_nodeid(self, nodeid: str) -> str:
        if self._test_plan is None:
            return "guard"
        m = _NODEID_INDEX_RE.search(nodeid)
        if m is None:
            return "guard"
        idx = int(m.group(1))
        if 0 <= idx < len(self._test_plan.tests):
            return self._test_plan.tests[idx].role
        return "guard"

    def _build_pytest_command(
        self,
        generated_file: Path,
        container_name: str,
        report_path: Path,
    ) -> list[str]:
        return [
            sys.executable,
            "-m",
            "pytest",
            str(generated_file),
            f"--hosts=docker://{container_name}",
            "--json-report",
            f"--json-report-file={report_path}",
            "-q",
            "--no-header",
        ]

    def _invoke_pytest(
        self,
        cmd: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"pytest exceeded {timeout}s while running Testinfra tests"
            ) from exc
        except FileNotFoundError as exc:
            raise TestinfraRunnerError(f"could not start pytest subprocess: {exc}") from exc

    def _guard_pytest_exit(
        self,
        completed: subprocess.CompletedProcess[str],
        report_path: Path,
    ) -> None:
        rc = completed.returncode
        if rc in (0, 1):
            return
        snippet = (completed.stderr or completed.stdout or "").strip().splitlines()[-1:] or [""]
        if not report_path.exists():
            raise TestinfraRunnerError(
                f"pytest exited with code {rc} and produced no JSON report; last line: {snippet[0]!r}"
            )
        self.last_warnings.append(
            f"pytest exited with non-standard code {rc}; last line: {snippet[0]!r}"
        )

    def _load_report(self, report_path: Path) -> dict[str, Any]:
        if not report_path.exists():
            raise TestinfraRunnerError(
                f"pytest JSON report not written to {report_path}; ensure pytest-json-report is installed"
            )
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TestinfraRunnerError(f"pytest JSON report is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise TestinfraRunnerError("pytest JSON report root must be a JSON object")
        return data

    def _records_from_report(self, report: dict[str, Any]) -> Iterable[dict[str, Any]]:
        tests = report.get("tests")
        if not isinstance(tests, list):
            self.last_warnings.append(
                "pytest JSON report has no 'tests' array; returning empty results"
            )
            return []
        records: list[dict[str, Any]] = []
        for index, item in enumerate(tests):
            if not isinstance(item, dict):
                self.last_warnings.append(f"dropped report.tests[{index}]: not an object")
                continue
            nodeid = str(item.get("nodeid") or f"unknown[{index}]")
            outcome = str(item.get("outcome") or "")
            status = _PYTEST_OUTCOME_MAP.get(outcome, "error")
            if outcome and outcome not in _PYTEST_OUTCOME_MAP:
                self.last_warnings.append(
                    f"unknown pytest outcome {outcome!r} for {nodeid!r}; mapped to 'error'"
                )
            title = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid
            records.append(
                {
                    "suite_id": self.suite_id,
                    "check_id": nodeid,
                    "status": status,
                    "title": title,
                    "role": self._role_for_nodeid(nodeid),
                }
            )
        return records
