# TestSuite Component Extraction

## What changed

- Added TestSuite contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `TestSuiteRequest` (`pre_checks` / `post_checks`, optional lists)
  - `TestSuiteResult` (normalized lists plus `skipped`, `skip_reason`, `error`, `warnings`)
  - `TestSuiteComponent` protocol with `run(...) -> TestSuiteResult`
- Exported the new symbols from `src/runtime_skeleton/interfaces/__init__.py`.
- Added the TestSuite component implementation:
  - `src/runtime_skeleton/components/testsuite/core.py` — `DefaultTestSuiteComponent`
  - `src/runtime_skeleton/components/testsuite/__init__.py`
- Updated `src/runtime_skeleton/orchestrator/pipeline.py` so `run_pipeline` passes caller `pre_checks` / `post_checks` through TestSuite normalization before `compare_results` (Evaluation).
- Added tests:
  - `tests/runtime_skeleton/components/test_testsuite.py`
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`

## Two-phase in-process collection update

- `run_pipeline` now supports true two-phase collection when external checks are not supplied:
  - collect pre checks in-process
  - apply patch via Sandbox
  - collect post checks in-process
  - evaluate pre vs post
- Added `testsuite_collector` hook to `run_pipeline` for in-process collection in this skeleton.
- Added phase-aware TestSuite request support:
  - `TestSuiteRequest.phase` (`normalize` / `pre` / `post`)
  - `TestSuiteRequest.phase_checks`
- Mode precedence:
  - if both `pre_checks` and `post_checks` are provided, use compatibility mode (normalize caller lists)
  - if neither is provided, collect both phases in-process
  - if one side is provided, normalize provided side and collect missing side in-process with a warning

## Runner adapter update

- Added runner adapter contract surface in `src/runtime_skeleton/interfaces/contracts.py`:
  - `TestSuiteRunner` protocol with `run_phase(phase, context) -> list[dict[str, Any]]`
  - `TestSuiteRequest.runner` for runner injection (manual/opt-in path)
  - `TestSuiteRequest.phase_context` for phase-scoped runtime context (for example, sandbox data in post phase)
- Added first concrete runner in `src/runtime_skeleton/components/testsuite/core.py`:
  - `ManualTestSuiteRunner` for explicit phase rows and injectable phase errors
- Updated `DefaultTestSuiteComponent` so phase execution uses the injected runner when `phase_checks` are not supplied, while keeping deterministic normalization of required keys:
  - `suite_id`
  - `check_id`
  - `status`
  - `title`
- Error policy remains non-destructive:
  - runner timeout/exception maps to `TestSuiteResult.error` and `warnings`
  - pipeline emits warning messages and continues evaluation with available normalized checks

### Manual activation examples

- Pre phase (no external pre checks supplied):
  - call TestSuite with `TestSuiteRequest(phase="pre", runner=manual_runner)`
- Post phase with sandbox context:
  - call TestSuite with `TestSuiteRequest(phase="post", runner=manual_runner, phase_context={"sandbox": sandbox_result})`
- Compatibility bypass:
  - when both external `pre_checks` and `post_checks` are supplied to `run_pipeline`, runner invocation is skipped and both sides are normalized directly

## Semantic note (regression ordering)

Baseline **pre-checks** and verification **post-checks** bracket **Sandbox** (`create_sandbox`, `apply_patch`). The canonical story is Input → TestSuite (pre evidence) → Sandbox (patch) → TestSuite (post evidence) → Evaluation. The skeleton now supports in-process two-phase collection and still accepts caller-supplied check lists for compatibility.

Patch execution stays in Sandbox, not inside TestSuite.

## Compatibility guarantees

- `run_pipeline(...)` keyword parameters and return type (`PipelineSnapshot`) are unchanged.
- Evaluation still receives normalized `list[dict[str, Any]]` suitable for existing `evaluate_checks` / `compare_results` behavior.
- For well-formed list-of-dicts inputs, observable diff results match the previous path that passed `pre_checks or []` and `post_checks or []` directly into `compare_results`.

## Files changed

- `src/runtime_skeleton/interfaces/contracts.py`
- `src/runtime_skeleton/interfaces/__init__.py`
- `src/runtime_skeleton/components/testsuite/core.py`
- `src/runtime_skeleton/components/testsuite/__init__.py`
- `src/runtime_skeleton/orchestrator/pipeline.py`
- `tests/runtime_skeleton/components/test_testsuite.py`
- `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`

## Follow-up tasks

- Optionally split orchestration so TestSuite is invoked explicitly for pre and post phases once check execution moves out of caller-supplied lists.
- Optionally surface TestSuite warnings on `PipelineSnapshot` for observability.

## Thin Orchestrator hardening update

- Orchestrator mode precedence is now explicit in `run_pipeline`:
  - `external`: both `pre_checks` and `post_checks` supplied -> normalize external lists
  - `partial`: one side supplied -> normalize supplied side and collect missing side in-process with warning
  - `in_process`: neither supplied -> collect both phases in-process
- Sequencing policy remains deterministic across modes:
  - pre phase normalization/collection
  - Sandbox patch application
  - post phase normalization/collection
  - Evaluation diff
- Observability path is centralized:
  - warnings are emitted via one helper and mirrored into `PipelineSnapshot.testsuite_messages`
  - this keeps process warnings and structured snapshot diagnostics aligned.
