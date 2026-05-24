"""Unit tests for aegis_test_generator.runner.testinfra_runner.

All tests are fully mocked: no Docker, no pytest-json-report, no OpenAI.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from aegis_test_generator.generate import GenerateResult
from aegis_test_generator.planner.llm_planner import PlannerError
from aegis_test_generator.runner.testinfra_runner import (
    TestinfraRunner,
    TestinfraRunnerError,
)
from aegis_test_generator.test_templates.renderer import RendererError
from aegis_test_generator.test_templates.schemas import SchemaValidationError, TestCase, TestPlan


_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "example_patch.yml"


def _sandbox(container_name: str = "aegis-test-1", skipped: bool = False) -> Any:
    sb = MagicMock()
    sb.container_name = container_name
    sb.skipped = skipped
    return sb


def _make_runner(tmp_path: Path) -> TestinfraRunner:
    return TestinfraRunner(
        playbook_path=_FIXTURE,
        output_path=tmp_path / "generated_tests.py",
    )


def _fake_generate_result(
    tmp_path: Path,
    *,
    n_tests: int = 1,
    roles: list[Literal["guard", "verify"]] | None = None,
    warnings: list[str] | None = None,
) -> GenerateResult:
    path = tmp_path / "generated_tests.py"
    r: list[Literal["guard", "verify"]] = (
        list(roles) if roles is not None else ["guard"] * n_tests
    )
    if len(r) != n_tests:
        raise ValueError("roles length must match n_tests")
    tests = [
        TestCase(test_type="file_exists", target=f"/tmp/aegis_runner_mock_{i}", role=r[i])
        for i in range(n_tests)
    ]
    return GenerateResult(path=path, plan=TestPlan(tests=tests), warnings=list(warnings or []))


def _completed(cmd: list[str], rc: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, rc, "", stderr)


def _writing_invoke(report_payload: dict[str, Any] | None, rc: int = 0):
    """Build a fake _invoke_pytest that writes a JSON report alongside its cmd."""

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                report_path = Path(arg.split("=", 1)[1])
                if report_payload is not None:
                    report_path.write_text(json.dumps(report_payload), encoding="utf-8")
                break
        return _completed(cmd, rc=rc)

    return fake


def test_pre_phase_executes_and_returns_records(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::test_pre", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("pre", {"sandbox": _sandbox(), "input": {"diff": {}}})
    assert rows == [
        {
            "suite_id": "testinfra",
            "check_id": "g.py::test_pre",
            "status": "pass",
            "title": "test_pre",
            "role": "guard",
        }
    ]


def test_generate_called_once_then_reused_in_post(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::test_same", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ) as gen_mock, patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("pre", {"sandbox": _sandbox(), "input": {"diff": {}}})
        runner.run_phase("post", {"sandbox": _sandbox(), "input": {"diff": {}}})
    gen_mock.assert_called_once()


def test_post_phase_forwards_input_context_to_generate_tests(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    inp = {"diff": {"added": [{"path": "/x"}]}}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ) as gen_mock, patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("post", {"sandbox": _sandbox(), "input": inp})
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs.get("input_context") == inp


def test_post_phase_without_input_passes_none_to_generate_tests(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ) as gen_mock, patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("post", {"sandbox": _sandbox()})
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs.get("input_context") is None
    assert gen_mock.call_args.kwargs.get("review") is True


def test_post_phase_forwards_review_to_generate_tests(tmp_path: Path) -> None:
    runner = TestinfraRunner(
        playbook_path=_FIXTURE,
        output_path=tmp_path / "generated_tests.py",
        review=False,
    )
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ) as gen_mock, patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("post", {"sandbox": _sandbox()})
    gen_mock.assert_called_once()
    assert gen_mock.call_args.kwargs.get("review") is False


def test_post_phase_non_dict_input_treated_as_absent(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ) as gen_mock, patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("post", {"sandbox": _sandbox(), "input": "bad"})  # type: ignore[dict-item]
    assert gen_mock.call_args.kwargs.get("input_context") is None


def test_unsupported_phase_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with pytest.raises(TestinfraRunnerError):
        runner.run_phase("middle", {"sandbox": _sandbox()})  # type: ignore[arg-type]


def test_missing_sandbox_in_context_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with pytest.raises(TestinfraRunnerError, match="phase_context"):
        runner.run_phase("post", {})


def test_skipped_sandbox_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with pytest.raises(TestinfraRunnerError, match="skipped or container_name"):
        runner.run_phase("post", {"sandbox": _sandbox(skipped=True)})


def test_empty_container_name_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with pytest.raises(TestinfraRunnerError, match="skipped or container_name"):
        runner.run_phase("post", {"sandbox": _sandbox(container_name="   ")})


def test_post_phase_happy_path_records(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {
        "tests": [
            {"nodeid": "g.py::test_0_file_exists", "outcome": "passed"},
            {"nodeid": "g.py::test_1_service_running", "outcome": "failed"},
        ]
    }
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path, n_tests=2),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report, rc=1)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows == [
        {
            "suite_id": "testinfra",
            "check_id": "g.py::test_0_file_exists",
            "status": "pass",
            "title": "test_0_file_exists",
            "role": "guard",
        },
        {
            "suite_id": "testinfra",
            "check_id": "g.py::test_1_service_running",
            "status": "fail",
            "title": "test_1_service_running",
            "role": "guard",
        },
    ]


def test_role_injected_into_records(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {
        "tests": [
            {"nodeid": "g.py::test_0_file_exists", "outcome": "passed"},
            {"nodeid": "g.py::test_1_file_exists", "outcome": "passed"},
        ]
    }
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path, n_tests=2, roles=["verify", "guard"]),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows[0]["role"] == "verify"
    assert rows[1]["role"] == "guard"


def test_role_defaults_to_guard_on_nodeid_mismatch(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::test_foo[param-1]", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path, n_tests=1, roles=["verify"]),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows[0]["role"] == "guard"


def test_generate_warnings_surfaced(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path, warnings=["low disk", "old model"]),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        runner.run_phase("post", {"sandbox": _sandbox()})
    assert "generate: low disk" in runner.last_warnings
    assert "generate: old model" in runner.last_warnings


@pytest.mark.parametrize(
    "outcome, expected_status",
    [
        ("passed", "pass"),
        ("failed", "fail"),
        ("error", "error"),
        ("skipped", "skip"),
        ("xfailed", "pass"),
        ("xpassed", "fail"),
    ],
)
def test_post_phase_status_mapping(tmp_path: Path, outcome: str, expected_status: str) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": f"g.py::test_x_{outcome}", "outcome": outcome}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows[0]["status"] == expected_status


def test_post_phase_unknown_outcome_maps_to_error_with_warning(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::test_x", "outcome": "weird"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows[0]["status"] == "error"
    assert any("unknown pytest outcome" in w for w in runner.last_warnings)


def test_planner_error_wrapped(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        side_effect=PlannerError("boom"),
    ):
        with pytest.raises(TestinfraRunnerError, match="failed to generate"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_schema_error_wrapped(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        side_effect=SchemaValidationError("invalid"),
    ):
        with pytest.raises(TestinfraRunnerError, match="failed to generate"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_renderer_error_wrapped(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        side_effect=RendererError("template missing"),
    ):
        with pytest.raises(TestinfraRunnerError, match="failed to generate"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_pytest_timeout_raises_timeout_error(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else [], timeout=kwargs.get("timeout", 0))

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch(
        "aegis_test_generator.runner.testinfra_runner.subprocess.run",
        side_effect=raise_timeout,
    ):
        with pytest.raises(TimeoutError):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_pytest_filenotfound_wrapped(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch(
        "aegis_test_generator.runner.testinfra_runner.subprocess.run",
        side_effect=FileNotFoundError("no pytest"),
    ):
        with pytest.raises(TestinfraRunnerError, match="could not start pytest"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_pytest_nonstandard_exit_no_report_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        return _completed(cmd, rc=4, stderr="usage error")

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=fake):
        with pytest.raises(TestinfraRunnerError, match="produced no JSON report"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_pytest_nonstandard_exit_with_report_warns_and_continues(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": [{"nodeid": "g.py::test_a", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report, rc=3)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert len(rows) == 1
    assert any("non-standard code 3" in w for w in runner.last_warnings)


def test_report_missing_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        return _completed(cmd, rc=0)

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=fake):
        with pytest.raises(TestinfraRunnerError, match="JSON report not written"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_report_invalid_json_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                Path(arg.split("=", 1)[1]).write_text("not json", encoding="utf-8")
        return _completed(cmd, rc=0)

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=fake):
        with pytest.raises(TestinfraRunnerError, match="not valid JSON"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_report_root_not_object_raises(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                Path(arg.split("=", 1)[1]).write_text("[1,2,3]", encoding="utf-8")
        return _completed(cmd, rc=0)

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=fake):
        with pytest.raises(TestinfraRunnerError, match="root must be a JSON object"):
            runner.run_phase("post", {"sandbox": _sandbox()})


def test_report_tests_not_list_returns_empty_with_warning(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {"tests": "oops"}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert rows == []
    assert any("no 'tests' array" in w for w in runner.last_warnings)


def test_report_test_item_not_dict_dropped_with_warning(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    report = {
        "tests": [
            {"nodeid": "g.py::test_a", "outcome": "passed"},
            "garbage",
            {"nodeid": "g.py::test_b", "outcome": "passed"},
        ]
    }
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("post", {"sandbox": _sandbox()})
    assert [r["check_id"] for r in rows] == ["g.py::test_a", "g.py::test_b"]
    assert any("dropped report.tests[1]" in w for w in runner.last_warnings)


def test_pytest_command_targets_docker_host(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    captured: dict[str, list[str]] = {}

    def fake(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                Path(arg.split("=", 1)[1]).write_text(json.dumps({"tests": []}), encoding="utf-8")
        return _completed(cmd, rc=0)

    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=fake):
        runner.run_phase("post", {"sandbox": _sandbox(container_name="my-box")})
    cmd = captured["cmd"]
    assert "--hosts=docker://my-box" in cmd
    assert any(a.startswith("--json-report-file=") for a in cmd)
    assert any("generated_tests.py" in a for a in cmd)


def test_last_warnings_reset_per_call(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    runner.last_warnings.append("stale")
    report = {"tests": [{"nodeid": "g.py::t", "outcome": "passed"}]}
    with patch(
        "aegis_test_generator.runner.testinfra_runner.generate_tests",
        return_value=_fake_generate_result(tmp_path),
    ), patch.object(runner, "_invoke_pytest", side_effect=_writing_invoke(report)):
        rows = runner.run_phase("pre", {"sandbox": _sandbox()})
    assert len(rows) == 1
    assert runner.last_warnings == []
