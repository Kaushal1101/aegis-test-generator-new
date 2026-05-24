# Testinfra Runner Migration Notes

This note covers Phase 4: a concrete `TestSuiteRunner` (`TestinfraRunner`) that runs LLM-generated Testinfra tests against a sandbox container, plus the new `runner=` parameter on `run_pipeline`.

## Files added

- `aegis_test_generator/runner/testinfra_runner.py` — `TestinfraRunner` adapter and `TestinfraRunnerError`.
- `aegis_test_generator/runner/__init__.py` — re-exports `TestinfraRunner`, `TestinfraRunnerError`, `DEFAULT_PYTEST_TIMEOUT_S`.
- `tests/aegis_test_generator/runner/__init__.py`
- `tests/aegis_test_generator/runner/test_testinfra_runner.py` — 27 fully-mocked unit tests.
- `tests/runtime_skeleton/orchestrator/test_pipeline_runner_wiring.py` — 6 integration tests for the new `runner=` parameter.
- `docs/migrations/testinfra-runner.md` (this file).

## Files changed

- `src/runtime_skeleton/orchestrator/pipeline.py` — `run_pipeline` now accepts an optional `runner: TestSuiteRunner | None`.
- `pyproject.toml` — `[testinfra]` extra now includes `pytest-json-report>=1.5`.

## Activation

Inject any `TestSuiteRunner` into `run_pipeline(..., runner=...)`. The pipeline's existing pre → Sandbox patch → post → Evaluation order is unchanged.

```python
from pathlib import Path

from aegis_test_generator.runner import TestinfraRunner
from runtime_skeleton.orchestrator.pipeline import run_pipeline

snap = run_pipeline(
    repo_root=Path("."),
    input_path="examples/sample_input.json",
    runner=TestinfraRunner(playbook_path=Path("examples/patch.yml")),
)
```

The runner reads `phase_context["sandbox"]` (a `SandboxResult`) at `run_phase` time and uses `sandbox.container_name` to build the Testinfra Docker host string `docker://<container_name>`.

## Runner-selection precedence

Inside `run_pipeline`, the active runner is resolved as:

1. The explicit `runner=` argument when provided.
2. Otherwise, a `_CollectorRunner` wrapping the legacy `testsuite_collector=` callable.
3. Otherwise, a no-op `_CollectorRunner(None)` returning `[]` for any phase.

This preserves backward compatibility — existing `testsuite_collector=` callers behave exactly as before.

## Phase semantics

- `pre` → always returns `[]`. There are no LLM-generated infrastructure checks before the patch is applied; baseline checks for the canonical pre/post diff come from caller-supplied `pre_checks` or another runner.
- `post` → calls `generate_tests(playbook_path)` (planner → schemas → renderer), runs `pytest <generated_file> --hosts=docker://<container_name> --json-report --json-report-file=<tmp>` in a subprocess, parses the report, and returns normalized `CheckRecord`-shaped dicts (`suite_id="testinfra"`, `check_id=<nodeid>`, `status`, `title`).

## Pytest outcome → CheckStatus mapping

| pytest outcome | CheckStatus |
|---|---|
| `passed` | `pass` |
| `failed` | `fail` |
| `error`  | `error` |
| `skipped` | `skip` |
| `xfailed` | `pass` (expected fail occurred) |
| `xpassed` | `fail` (expected fail did not occur) |
| anything else | `error` (warning appended to `runner.last_warnings`) |

## Failure policy (non-destructive)

`TestinfraRunner` raises `TestinfraRunnerError` (or `TimeoutError`) for hard failures:

- `phase_context["sandbox"]` missing, sandbox skipped, or `container_name` empty.
- `generate_tests` raises `PlannerError`, `SchemaValidationError`, or `RendererError`.
- `pytest` subprocess cannot start (`FileNotFoundError`).
- `pytest` exits with a non-standard code (not 0/1) and writes no JSON report.
- JSON report file is missing or not valid JSON, or root is not an object.

`TimeoutError` is raised when the pytest subprocess exceeds `timeout_s` (default 300 s).

The TestSuite component catches both, sets `TestSuiteResult.error`/`warnings`, and the pipeline emits them via `PipelineSnapshot.testsuite_messages` while `Evaluation` proceeds with whatever checks were collected.

Soft warnings (e.g. unknown pytest outcome, `tests` array missing in report, individual non-dict report rows, non-standard pytest exit codes that still produced a report) are appended to `runner.last_warnings` and do not raise.

## Optional dependency

```bash
pip install -e ".[testinfra]"
```

This installs `openai`, `pytest-testinfra`, and `pytest-json-report`. The runner module imports `openai` only lazily through the planner, so importing `TestinfraRunner` itself remains cheap.
