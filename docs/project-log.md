# Project Log

## 2026-05-24 — Phase 3: Coverage Taxonomy and Documentation

### Completed work

- Created `aegis_test_generator/coverage.py`:
  - `CoverageCategory` literal type (7 values: `package_integrity`, `file_integrity`, `file_content`, `service_state`, `network_posture`, `identity`, `command_behavior`)
  - `TEST_TYPE_TO_CATEGORY` mapping all 22 supported test types to their category
  - `INTENT_REQUIRED_CATEGORIES` table: for each `PatchIntent`, the categories that must have at least one test (used to flag ⚠️ blind spots)
  - `CategoryStats`, `CoverageSummary` dataclasses
  - `compute_coverage(tests, *, patch_intent)` — counts verify/guard per category and populates `gaps` list

- Modified `aegis_test_generator/test_templates/schemas.py`:
  - Added `coverage_category: str | None = None` field to `TestCase`
  - Added `model_validator(mode="after")` to auto-assign `coverage_category` from `TEST_TYPE_TO_CATEGORY` when not explicitly set by the LLM

- Modified `aegis_test_generator/reporter.py`:
  - Added coverage summary table section after "Regression guard tests" block
  - Re-classifies patch intent from raw YAML at report time to determine which categories are required
  - Flags ⚠️ on categories with zero coverage when they are required by the patch intent
  - Added `_infer_goal` entries for the three Phase 2 types (`content_changed`, `file_mode_changed`, `package_version_range`)

- Created `docs/coverage-reference.md`:
  - Full test type reference (all 22, grouped by category) with descriptions and typical use cases
  - Coverage category matrix showing which patch scenarios each category addresses
  - Strengths and known gaps documentation

### Tests added
- `tests/aegis_test_generator/test_coverage.py`: 24 tests covering mapping completeness, auto-assignment, and `compute_coverage` gap detection

### Validation
- `python -m pytest tests/` → **302 passed**

---

## 2026-04-22

Implemented the Evaluation component extraction for `runtime_skeleton` based on the session brief.

### Completed work
- Added evaluation contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `EvaluationInput`
  - `EvaluationResult` (DiffResult-compatible fields)
  - `EvaluationComponent` protocol with `evaluate(...)`
- Exported new contract symbols from `src/runtime_skeleton/interfaces/__init__.py`.
- Created the new component package and implementation:
  - `src/runtime_skeleton/components/__init__.py`
  - `src/runtime_skeleton/components/evaluation/__init__.py`
  - `src/runtime_skeleton/components/evaluation/core.py`
- Kept backward compatibility by updating `src/runtime_skeleton/diff/compare.py` to delegate to the evaluation component while still returning `DiffResult`.
- Added tests for transitions and compatibility:
  - `tests/runtime_skeleton/components/test_evaluation.py`
  - `tests/runtime_skeleton/diff/test_compare_compat.py`
- Added migration note:
  - `docs/migrations/evaluation-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_evaluation.py tests/runtime_skeleton/diff/test_compare_compat.py`
- Result: `5 passed`

Implemented the Input component extraction for `runtime_skeleton` based on the session brief.

### Completed work
- Added input contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `InputRequest`
  - `InputResult` (ParsedInputResult-compatible fields)
  - `InputComponent` protocol with `parse(...)`
- Exported new contract symbols from `src/runtime_skeleton/interfaces/__init__.py`.
- Created the new component package and implementation:
  - `src/runtime_skeleton/components/input/__init__.py`
  - `src/runtime_skeleton/components/input/core.py`
- Kept backward compatibility by updating `src/runtime_skeleton/input/parser.py` so `parse_input(...)` delegates to the new input component and still returns `ParsedInputResult`.
- Added tests for input behavior and compatibility:
  - `tests/runtime_skeleton/components/test_input.py`
  - `tests/runtime_skeleton/input/test_parse_input_compat.py`
- Added migration note:
  - `docs/migrations/input-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest tests/runtime_skeleton/components/test_input.py tests/runtime_skeleton/input/test_parse_input_compat.py tests/runtime_skeleton/components/test_evaluation.py tests/runtime_skeleton/diff/test_compare_compat.py`
- Result: `13 passed`

Implemented the Sandbox component extraction for `runtime_skeleton` based on the session brief.

### Completed work
- Added sandbox contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `SandboxCreateRequest`
  - `PatchApplyRequest`
  - `SandboxComponent` protocol with `create(...)` and `apply_patch(...)`
- Exported new contract symbols from `src/runtime_skeleton/interfaces/__init__.py`.
- Created the new component package and implementation:
  - `src/runtime_skeleton/components/sandbox/__init__.py`
  - `src/runtime_skeleton/components/sandbox/core.py`
- Kept backward compatibility by updating sandbox API entrypoints to delegate:
  - `src/runtime_skeleton/sandbox/create.py`
  - `src/runtime_skeleton/sandbox/patch.py`
- Added sandbox behavior and compatibility tests:
  - `tests/runtime_skeleton/components/test_sandbox.py`
  - `tests/runtime_skeleton/sandbox/test_sandbox_compat.py`
- Added migration note:
  - `docs/migrations/sandbox-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_sandbox.py tests/runtime_skeleton/sandbox/test_sandbox_compat.py`
- Result: `16 passed`
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_input.py tests/runtime_skeleton/components/test_evaluation.py tests/runtime_skeleton/components/test_sandbox.py tests/runtime_skeleton/input/test_parse_input_compat.py tests/runtime_skeleton/diff/test_compare_compat.py tests/runtime_skeleton/sandbox/test_sandbox_compat.py`
- Result: `29 passed`

Implemented a Sandbox extraction correction pass to close test coverage gaps from the session brief review.

### Completed work
- Added direct config utility tests:
  - `tests/runtime_skeleton/sandbox/test_config.py`
  - Coverage includes:
    - defaults when `config/sandbox.json` is missing
    - config merge behavior
    - malformed non-object config JSON error
    - invalid `command` type error (`list[str]` enforcement)
- Added direct playbook resolution tests:
  - `tests/runtime_skeleton/sandbox/test_playbook.py`
  - Coverage includes:
    - `inputs/patch.yml` precedence
    - fallback to parsed patch section
    - error when patch section has no usable `plays` or `raw_yaml`
- Expanded legacy compatibility coverage:
  - Updated `tests/runtime_skeleton/sandbox/test_sandbox_compat.py` with stable public entrypoint checks for:
    - `runtime_skeleton.sandbox.load_sandbox_config`
    - `runtime_skeleton.sandbox.resolve_playbook_yaml`
- Updated migration documentation:
  - `docs/migrations/sandbox-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_sandbox.py tests/runtime_skeleton/sandbox/test_sandbox_compat.py tests/runtime_skeleton/sandbox/test_config.py tests/runtime_skeleton/sandbox/test_playbook.py`
- Result: `25 passed`
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_input.py tests/runtime_skeleton/components/test_evaluation.py tests/runtime_skeleton/components/test_sandbox.py tests/runtime_skeleton/input/test_parse_input_compat.py tests/runtime_skeleton/diff/test_compare_compat.py tests/runtime_skeleton/sandbox/test_sandbox_compat.py tests/runtime_skeleton/sandbox/test_config.py tests/runtime_skeleton/sandbox/test_playbook.py`
- Result: `38 passed`

## 2026-04-28

### Architecture note (canonical pipeline sequence)

Documented across project rules so future agents do not reorder stages incorrectly:

- **Regression ordering:** baseline **pre-checks** → **Sandbox** (`create_sandbox`, `apply_patch`) → **post-checks** → **Evaluation** (compare pre vs post).
- **Patch sits between pre and post**, not before all testing or inside TestSuite.
- **Owners:** Sandbox = provisioning + patch; TestSuite = check evidence/normalization; Evaluation = regression interpretation only.

Rules updated: `.cursor/rules/project-outline.mdc`, `.cursor/rules/project-orchestrator-agent.mdc`, `.cursor/rules/testsuite-agent.mdc`, `.cursor/rules/sandbox-agent.mdc`, `.cursor/rules/evaluation-agent.mdc`.

Implemented the TestSuite component extraction for `runtime_skeleton` based on the session brief.

### Completed work
- Added TestSuite contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `TestSuiteRequest`
  - `TestSuiteResult`
  - `TestSuiteComponent` protocol with `run(...)`
- Exported new contract symbols from `src/runtime_skeleton/interfaces/__init__.py`.
- Created the new component package and implementation:
  - `src/runtime_skeleton/components/testsuite/__init__.py`
  - `src/runtime_skeleton/components/testsuite/core.py`
- Kept backward compatibility by updating `src/runtime_skeleton/orchestrator/pipeline.py` so `run_pipeline(...)` sends caller `pre_checks` / `post_checks` through `DefaultTestSuiteComponent` before `compare_results(...)` (deterministic normalization of check dicts, stable keys, warnings for skipped non-dict rows; preserves public `run_pipeline` signature and Evaluation-compatible behavior for well-formed inputs).
- Added tests for TestSuite normalization and orchestrator parity:
  - `tests/runtime_skeleton/components/test_testsuite.py`
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Added migration note:
  - `docs/migrations/testsuite-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_testsuite.py tests/runtime_skeleton/orchestrator/test_testsuite_integration.py tests/runtime_skeleton/diff/test_compare_compat.py`
- Result: `9 passed`
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/`
- Result: `45 passed`

Implemented two-phase in-process TestSuite collection in `run_pipeline` with compatibility fallback.

### Completed work
- Extended TestSuite contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `TestSuiteRequest.phase` (`normalize` / `pre` / `post`)
  - `TestSuiteRequest.phase_checks`
- Updated TestSuite implementation in `src/runtime_skeleton/components/testsuite/core.py` to support phase collection requests while preserving normalization mode.
- Updated `src/runtime_skeleton/orchestrator/pipeline.py` to support:
  - in-process two-phase collection (`pre` then `post`) using `testsuite_collector`
  - compatibility mode when both external `pre_checks` and `post_checks` are supplied
  - partial-input mode (collect missing side in-process and emit warning)
- Expanded tests:
  - `tests/runtime_skeleton/components/test_testsuite.py`
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Updated migration docs:
  - `docs/migrations/testsuite-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/components/test_testsuite.py tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Ran:
  - `PYTHONPATH=src python -m pytest -q tests/runtime_skeleton/`

Implemented the TestSuite runner adapter for phase-based in-process collection (manual activation path).

### Completed work
- Added a swappable runner contract in `src/runtime_skeleton/interfaces/contracts.py`:
  - `TestSuiteRunner` protocol with `run_phase(phase, context)`
  - `TestSuiteRequest.runner`
  - `TestSuiteRequest.phase_context`
- Exported `TestSuiteRunner` from `src/runtime_skeleton/interfaces/__init__.py`.
- Added manual runner adapter in `src/runtime_skeleton/components/testsuite/core.py`:
  - `ManualTestSuiteRunner` (opt-in pre/post rows + injectable phase errors)
- Extended `DefaultTestSuiteComponent` to run phase checks via runner when `phase_checks` are not supplied, while preserving stable key normalization and metadata passthrough.
- Mapped runner failures into structured non-destructive `TestSuiteResult` fields (`error`, `warnings`) for timeout and generic exceptions.
- Kept orchestrator ownership boundaries and sequencing in `src/runtime_skeleton/orchestrator/pipeline.py`:
  - pre collection before patch apply
  - post collection after patch apply
  - compatibility preserved for external `pre_checks`/`post_checks`
  - partial external checks still collect missing phase with warning
- Updated exports in `src/runtime_skeleton/components/testsuite/__init__.py`.
- Expanded tests:
  - `tests/runtime_skeleton/components/test_testsuite.py`
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`

### Validation
- Ran:
  - `PYTHONPATH=src pytest tests/runtime_skeleton/components/test_testsuite.py tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Result: `16 passed`
- Ran:
  - `PYTHONPATH=src pytest -q tests/runtime_skeleton/`
- Result: `54 passed`

Implemented Thin Orchestrator hardening for explicit mode precedence and deterministic policy flow.

### Completed work
- Added manual thin-orchestrator rule:
  - `.cursor/rules/thin-orchestrator-agent.mdc`
- Refactored orchestrator policy flow in `src/runtime_skeleton/orchestrator/pipeline.py`:
  - explicit check mode selection (`external` / `partial` / `in_process`)
  - deterministic pre->patch->post sequencing maintained across all modes
  - centralized warning + snapshot message emission via one helper
- Expanded orchestrator-focused tests in:
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
  - added explicit post-only partial mode check
  - added assertion that external compatibility mode does not emit partial-mode warning
- Updated migration notes:
  - `docs/migrations/testsuite-extraction.md`

### Validation
- Ran:
  - `PYTHONPATH=src pytest tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Ran:
  - `PYTHONPATH=src pytest -q tests/runtime_skeleton/`

Applied a runner adapter gap-closure pass for documentation and observability policy.

### Completed work
- Updated migration notes in `docs/migrations/testsuite-extraction.md` with a dedicated runner adapter section covering:
  - `TestSuiteRunner`
  - `TestSuiteRequest.runner`
  - `TestSuiteRequest.phase_context`
  - `ManualTestSuiteRunner`
  - manual activation examples and compatibility bypass behavior
- Clarified pipeline non-destructive runner failure policy in `src/runtime_skeleton/orchestrator/pipeline.py`:
  - TestSuite phase `error` and `warnings` are emitted as warnings
  - pipeline still runs Evaluation with available normalized checks
- Extended integration coverage in `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`:
  - explicit test that external `pre_checks` + `post_checks` bypass runner invocation
  - explicit test that runner failure emits warning signals and pipeline still returns diff output

### Validation
- Ran:
  - `PYTHONPATH=src pytest tests/runtime_skeleton/components/test_testsuite.py tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
- Result: `16 passed`
- Ran:
  - `PYTHONPATH=src pytest -q tests/runtime_skeleton/`
- Result: `54 passed`

## 2026-05-01

Recorded the **LLM-driven Testinfra test generation** roadmap and scaffolded Phase 1 (package layout + packaging). Rules updated: `.cursor/rules/project-outline.mdc`, `.cursor/rules/project-orchestrator-agent.mdc`; new specialist rule: `.cursor/rules/llm-planner-agent.mdc`.

### Plan (concise)

- **Planner (OpenAI):** read Ansible YAML patch playbook → emit JSON test-plan entries (`test_type`, `target`, optional `expected`, `reason`).
- **Validate:** **`aegis_test_generator/test_templates/schemas.py`** (owner-pasted Pydantic) — enumerated test types (`file_exists`, `file_absent`, `directory_exists`, `package_installed`, `package_absent`, `content_contains`, `content_not_contains`, `file_mode`, `file_owner`, `binary_executable`, `command_succeeds`, `service_running`).
- **Render:** **`aegis_test_generator/test_templates/renderer.py`** — fixed templates only → **`outputs/generated_tests/generated_tests.py`** (no free-form LLM Python).
- **Execute (later):** **`TestSuiteRunner`** + **pytest-testinfra** + **Docker** (`docker://<container>`) for post-phase check collection; **Sandbox** retains **`apply_patch`** between pre and post; **Evaluation** unchanged.

### Completed work (Phase 1 scaffold)

- Added **`aegis_test_generator/`** at repo root:
  - **`aegis_test_generator/__init__.py`**, **`aegis_test_generator/planner/__init__.py`**, **`aegis_test_generator/runner/__init__.py`** (empty stubs)
  - **`aegis_test_generator/test_templates/__init__.py`**, **`schemas.py`**, **`renderer.py`** (blank placeholders for owner code)
- Added **`outputs/generated_tests/.gitkeep`** for generated **`generated_tests.py`** output directory.
- Updated **`pyproject.toml`**:
  - **`packages.find`** `where = ["src", "."]`, **`include = ["runtime_skeleton*", "aegis_test_generator*"]`**
  - optional dependency group **`testinfra`** with **`openai>=1.0`**, **`pytest-testinfra>=10.0`**

### Next steps (tracked in rules) — superseded later in this log entry

Original scaffold notes; **Phase 2** (**`llm_planner.py`**) and **Phase 3** (**schemas**, **renderer**, **`generate.py`**) are now completed below. Next up: Testinfra **`TestSuiteRunner`** and pipeline **`testsuite_collector`** wiring without reordering canonical pre/patch/post.

### Validation

- Ran: `pip install -e "."` then `python -c "import aegis_test_generator; import runtime_skeleton"`
- Result: success (imports OK)

### Completed work (Phase 2: LLM planner module)

Implemented **`aegis_test_generator/planner/llm_planner.py`** per **`.cursor/rules/llm-planner-agent.mdc`**: reads an Ansible playbook from disk (`yaml.safe_load` sanity check), prompts OpenAI Chat Completions JSON object output (`response_format=json_object`; shape `{"tests": [...]}`), trims oversized input at **`MAX_PLAYBOOK_CHARS`** with truncation warnings, and returns **`PlannerResult`** (`tests`, `raw`, `warnings`, resolved **`model`**). **`OPENAI_API_KEY`** must be present when calling without an injected **`client`**; **`OPENAI_MODEL`** defaults to **`gpt-4o`**. Raises **`PlannerError`** / **`PlaybookLoadError`** / **`PlannerResponseError`** instead of informal failures; lazy-imports **`openai`** after the env check so mocks-based tests run without **`[testinfra]`** extras.

- Wired public exports from **`aegis_test_generator/planner/__init__.py`** (`__all__`).
- Tests: **`tests/aegis_test_generator/planner/test_llm_planner.py`** (mock **`OpenAI`** client via **`unittest.mock.MagicMock`**; covers happy path, fenced JSON, malformed/wrong shape, per-row drop warnings, empty-after-filter, file-not-found, invalid YAML before network, truncation in prompt payload, missing API key, wrapped API failures). Test package scaffolding: **`tests/aegis_test_generator/__init__.py`**, **`tests/aegis_test_generator/planner/__init__.py`**.
- Fixture: **`tests/fixtures/example_patch.yml`** (mirrors **`examples/patch.yml`**).

**Remaining roadmap (post–Phase 2):** ~~schemas/renderer~~ (**done in Phase 3** below); Testinfra **`TestSuiteRunner`** + pipeline wiring (**Phase 4+**).

### Validation (Phase 2)

- Ran: `pip install -e "."` then `pytest -q tests/aegis_test_generator/planner/`
- Result: tests passed (`11 passed` at capture time)

### Completed work (Phase 3: schemas, renderer, generate helper)

Per **`.cursor/rules/renderer-agent.mdc`**, implemented fixed-template rendering (only pre-written templates emit Python tests; validated LLM rows never become executable code directly).

Files:

- **`aegis_test_generator/test_templates/schemas.py`** — Pydantic **`TestCase`** / **`TestPlan`**, **`SchemaValidationError`**, **`validate_plan(rows)`**, **`extra="forbid"`**, **`target`** non-empty, **`test_type`** constrained via **`SUPPORTED_TEST_TYPES`** from **`llm_planner`**; **`ValidationError`** wrapped so callers need not depend on pydantic. **`TestCase`** / **`TestPlan`** declare **`__test__ = False`** so pytest does not mis-collect **`Test*`-named models**.
- **`aegis_test_generator/test_templates/renderer.py`** — **`RendererError`**; **`render_plan`** defaults to repo-root **`outputs/generated_tests/generated_tests.py`**, **`mkdir`** on parents; module header plus one **`test_<index>_<test_type>(host)`** per row using **`host.file`** / **`host.package`** / **`host.run`** / **`host.service`**; targets and expectations embedded with **`repr()`**. **`expected`** required for **`content_contains`**, **`content_not_contains`**, **`file_mode`**, **`file_owner`**. Twelve **`test_type`** literals covered: **`file_exists`**, **`file_absent`**, **`directory_exists`**, **`package_installed`**, **`package_absent`**, **`content_contains`**, **`content_not_contains`**, **`file_mode`**, **`file_owner`**, **`binary_executable`**, **`command_succeeds`**, **`service_running`**.
- **`aegis_test_generator/generate.py`** — **`generate_tests(playbook_path, output_path=None, *, client=None, model=None)`** → **`plan_from_playbook`** → **`validate_plan`** → **`render_plan`**.
- **`aegis_test_generator/test_templates/__init__.py`** — re-exports **`TestCase`**, **`TestPlan`**, **`SchemaValidationError`**, **`validate_plan`**, **`render_plan`**, **`RendererError`**.
- **`aegis_test_generator/__init__.py`** — exports **`generate_tests`**.

Tests: **`tests/aegis_test_generator/test_templates/test_schemas.py`**, **`test_renderer.py`**; smoke **`tests/aegis_test_generator/test_generate.py`** (mocked **`plan_from_playbook`**, playbook path **`tests/fixtures/example_patch.yml`**).

**Remaining roadmap:** Testinfra **`TestSuiteRunner`** + pipeline wiring (Phase 4+).

### Validation (Phase 3)

- Ran: `pytest -q tests/aegis_test_generator/test_templates/ tests/aegis_test_generator/test_generate.py`
- Result: **`25 passed`**
- Ran: `pytest -q tests/aegis_test_generator/` (Phase 3 + planner + **`test_generate`** — full package tests)
- Result: **`36 passed`**

### Completed work (Phase 4: Testinfra runner + pipeline `runner=`)

Implemented a concrete **`TestSuiteRunner`** that drives the LLM planner → schemas → renderer chain and executes the generated tests with **`pytest-testinfra`** over **Docker**, plus the wiring that lets callers inject any runner into **`run_pipeline`**.

Files added:

- **`aegis_test_generator/runner/testinfra_runner.py`** — **`TestinfraRunner`** dataclass implementing **`TestSuiteRunner`** (`run_phase`); **`TestinfraRunnerError`**; `DEFAULT_PYTEST_TIMEOUT_S = 300`.
  - `pre` phase → always `[]`.
  - `post` phase → reads **`sandbox`** from `phase_context`, calls **`generate_tests(playbook_path)`**, runs `pytest <file> --hosts=docker://<container_name> --json-report --json-report-file=<tmp> -q --no-header`, parses JSON report, returns normalized check dicts (`suite_id="testinfra"`, `check_id=<nodeid>`, `status`, `title`).
  - Outcome mapping: `passed→pass`, `failed→fail`, `error→error`, `skipped→skip`, `xfailed→pass`, `xpassed→fail`, unknown→`error` + warning.
  - Hard-fail (raise) for: missing/skipped sandbox, planner/schema/renderer errors (wrapped), subprocess `FileNotFoundError`, non-standard pytest exit code without report, missing/invalid JSON report. Subprocess timeout raises **`TimeoutError`**, which TestSuite already maps to a structured warning.
  - Soft warnings (recorded on `runner.last_warnings`): unknown pytest outcomes, `tests` array missing/wrong-typed, non-dict rows in report, non-standard pytest exit code that still produced a report.
- **`aegis_test_generator/runner/__init__.py`** — re-exports.
- **`tests/aegis_test_generator/runner/__init__.py`**, **`tests/aegis_test_generator/runner/test_testinfra_runner.py`** — fully-mocked unit tests (no Docker, no `pytest-json-report` needed) covering: pre/post phases, all outcome mappings, sandbox absence/skip/empty container, all generator-error wrappings, timeout, FileNotFoundError, exit-code/report combinations, malformed JSON report bodies, command-shape assertions, `last_warnings` reset.
- **`tests/runtime_skeleton/orchestrator/test_pipeline_runner_wiring.py`** — integration tests for `run_pipeline(runner=...)`: both phases invoked, runner takes precedence over `testsuite_collector`, external `pre_checks`/`post_checks` still bypass the runner, partial-mode runner-only-on-missing-phase, runner failure non-destructive, no-runner backward compat.
- **`docs/migrations/testinfra-runner.md`** — activation, precedence, phase semantics, status mapping, failure policy, optional dependency notes.

Files changed:

- **`src/runtime_skeleton/orchestrator/pipeline.py`** — added optional **`runner: TestSuiteRunner | None = None`** parameter to **`run_pipeline`**; new **`_resolve_runner(runner, collector)`** helper makes precedence explicit (runner > collector wrap > no-op). Existing `testsuite_collector` semantics unchanged when `runner` is not supplied.
- **`pyproject.toml`** — `[testinfra]` extra now includes **`pytest-json-report>=1.5`** alongside `openai` and `pytest-testinfra`.
- **`aegis_test_generator/runner/testinfra_runner.py`** — `TestinfraRunner` and `TestinfraRunnerError` opt out of pytest collection via `__test__ = False` (matches Phase 3's `TestCase`/`TestPlan` pattern).

### Validation (Phase 4)

- Ran: `pytest -q tests/aegis_test_generator/runner/`
- Result: **`27 passed`**
- Ran: `pytest -q tests/runtime_skeleton/orchestrator/`
- Result: **`13 passed`**
- Ran: `pytest -q tests/` (full repo)
- Result: **`124 passed`**

**Roadmap status:** end-to-end functional path is now in place. Optional follow-ups: real-Docker integration test guarded by `pytest.importorskip` and `docker` availability; richer report fields (e.g. `metadata` with phase durations); per-test severity propagation if Evaluation grows it.

## 2026-05-05

### Improvement Plan v1 — decided and documented

Analysed the end-to-end pipeline output from two sample runs (simple and complex) and identified the highest-impact improvements that do not require new components or contract changes.

**Decision: 3 improvements selected for implementation; 1 deferred.**

Selected improvements (full plan in `docs/improvement-plan-v1.md`):

1. **Context enrichment** — Forward `diff`, `sensitivity_verdict`, and `predicted_impact` from the parsed input JSON through `phase_context["input"]` all the way into the LLM planner prompt. The LLM currently only sees the raw Ansible YAML.

2. **Negative / regression guard tests** — Extend the planner prompt (once context enrichment is in place) to explicitly request `file_absent`/`package_absent` tests for items in `diff.removed`, and "bystander unchanged" checks for high-sensitivity files that were not in `predicted_impact`. Implemented in the same pass as improvement 1 since they share `_build_messages()`.

3. **Two-stage LLM self-review** — Add a second OpenAI call in `llm_planner.py` that reviews and filters the initial plan before it reaches the renderer. Gated behind `review=True` (default on).

Deferred improvement (see `docs/future-enhancements.md`):
- Functional `command_succeeds` tests for every installed binary — deferred until the self-review pass is in place to guard against command hallucination.

### Component impact (no new components, no contract changes)

| File | Change |
|---|---|
| `orchestrator/pipeline.py` | Add `"input": parsed.parsed` to `phase_context` for both pre and post phases |
| `testinfra_runner.py` | Extract `input_context` from `phase_context`, forward to `generate_tests()` |
| `generate.py` | Add `input_context` and `review` parameters, forward to `plan_from_playbook()` |
| `llm_planner.py` | Accept `input_context`; `_build_messages()` enriched with diff/sensitivity/guard instructions; `_review_plan()` and `_build_review_messages()` helpers for second LLM call |

### Implementation phases

- **Phase A** (Improvements 1+2 together): context enrichment + negative test prompt. All in `_build_messages()` and its data path.
- **Phase B** (Improvement 3): self-review pass. Standalone second LLM call inside `llm_planner.py`.

### New docs created

- `docs/improvement-plan-v1.md` — full architectural plan with data flow diagrams, file-by-file change list, implementation order, and risks.
- `docs/future-enhancements.md` — deferred ideas with rationale.

### Completed work (Improvement Plan v1 — Phase A)

Implemented **context enrichment** and **negative / regression guard prompt rules** for the LLM planner without adding components or contract changes.

- `src/runtime_skeleton/orchestrator/pipeline.py` — `phase_context` for pre and post includes `"input": parsed.parsed` (parse-error path uses the same shape).
- `aegis_test_generator/generate.py` — `generate_tests(..., input_context=...)` forwards to `plan_from_playbook`.
- `aegis_test_generator/runner/testinfra_runner.py` — post phase passes `context["input"]` through when it is a `dict`.
- `aegis_test_generator/planner/llm_planner.py` — `plan_from_playbook(..., input_context=None)`; helpers for diff / sensitivity / predicted impact summary; guard rules appended to the system prompt when context is present.

### Validation (Phase A)

- Ran: `PYTHONPATH=src python -m pytest tests/ -q`
- Result: `133 passed`

### Completed work (Improvement Plan v1 — Phase B)

Implemented the **two-stage LLM review** pass after the initial plan call.

- `aegis_test_generator/planner/llm_planner.py` — `plan_from_playbook(..., review=True)` (default): `_build_review_messages()`, second `_call_openai`, `_extract_plan_rows` on review output; `PlannerResult.raw` reflects the reviewed JSON when review runs; `_review_diff_warnings()` adds messages such as `review: dropped N planned test row(s)` / `review: added N test row(s)`.
- `aegis_test_generator/generate.py` — `generate_tests(..., review=True)` forwarded to `plan_from_playbook`.
- `aegis_test_generator/runner/testinfra_runner.py` — dataclass field `review: bool = True`; passed through to `generate_tests`.

Planner unit tests default `review=False` when only a single mocked completion is wired; new tests cover two-call review behaviour, single-call when `review=False`, and drop-count warnings.

### Validation (Phase B)

- Ran: `PYTHONPATH=src python -m pytest tests/ -q`
- Result: `137 passed`

## 2026-05-08

### Improvement Plan v2 (hybrid pre/post + explicit exception reporting)

Documented and implemented `docs/improvement-plan-v2-hybrid.md` to improve
regression evidence quality while preserving component ownership boundaries.

### Completed work

- Added plan/rules documentation:
  - `docs/improvement-plan-v2-hybrid.md`
  - `.cursor/rules/exception-classifier-agent.mdc`
  - Updated `.cursor/rules/project-outline.mdc`
  - Updated `.cursor/rules/project-orchestrator-agent.mdc`
  - Updated `.cursor/rules/testsuite-runner-agent.mdc`
  - Updated `.cursor/rules/thin-orchestrator-agent.mdc`

- Added classifier contracts and snapshot field in:
  - `src/runtime_skeleton/interfaces/contracts.py`
    - `ClassifierResult`
    - `ExceptionClassifier` protocol
    - `PipelineSnapshot.classified_transitions`
  - `src/runtime_skeleton/interfaces/__init__.py` exports updated.

- Added optional classifier package:
  - `aegis_test_generator/classifier/__init__.py`
  - `aegis_test_generator/classifier/llm_classifier.py`
    - JSON-only OpenAI call
    - strict parse/shape checks
    - row-drop warnings for malformed annotations
    - `classify_transitions(...)` returning `ClassifierResult`

- Updated orchestrator sequencing in:
  - `src/runtime_skeleton/orchestrator/pipeline.py`
    - Sandbox is created before pre in-process phase for valid parsed inputs.
    - Pre phase receives sandbox+input context in normal flow.
    - Added optional `classifier=` parameter to `run_pipeline`.
    - Added additive annotation merge into `snapshot.classified_transitions`.
    - Classifier warnings/errors are surfaced via `testsuite_messages` and process warnings.

- Updated Testinfra runner behavior in:
  - `aegis_test_generator/runner/testinfra_runner.py`
    - Pre phase now executes generated checks.
    - Generated test module path is cached on runner instance and reused in post.
    - Existing error/status mapping behavior preserved.

- Added/updated tests:
  - `tests/aegis_test_generator/classifier/test_llm_classifier.py` (new)
  - `tests/runtime_skeleton/orchestrator/test_pipeline_runner_wiring.py`
    - classifier success/failure wiring
    - updated sandbox context expectation for pre phase
  - `tests/runtime_skeleton/orchestrator/test_testsuite_integration.py`
    - updated in-process collector sandbox context expectation
  - `tests/aegis_test_generator/runner/test_testinfra_runner.py`
    - pre-phase execution assertions
    - generate-once reuse across pre/post
    - warnings reset behavior adjusted for executing pre path

### Validation

- Ran: `PYTHONPATH=src python -m pytest tests/ -q`
- Result: `145 passed`

## 2026-05-11

LLM planner Phase 1b: `role` field (`guard` / `verify`) in prompts, guard rules, review pass, and shape-check.

### Completed work

- **`aegis_test_generator/planner/llm_planner.py`**
  - System prompt in `_build_messages()` now requires `role` on each row, documents `guard` vs `verify`, and allows only `test_type`, `target`, `expected`, `reason`, and `role` keys per row.
  - `_GUARD_RULES` extended with role assignment rules tied to DIFF SUMMARY, removed paths, bystander SENSITIVITY checks, and default `guard` when no context.
  - `_build_review_messages()` system prompt requires `role` on every row and instructs preserving or correcting roles vs playbook / DIFF SUMMARY.
  - `_shape_check_row()` drops rows with an explicit invalid `role` (with a clear warning); missing `role` still passes shape-check for Pydantic defaulting.

- **`tests/aegis_test_generator/planner/test_llm_planner.py`**
  - Mock JSON payloads updated to include `role` on rows where applicable.
  - Added `PlannerPromptAndShapeTests` covering `_shape_check_row` role handling, `_build_messages` / guard-rules content, and `_build_review_messages` role mention.

### Validation

- Ran: `PYTHONPATH=src pytest -q tests/aegis_test_generator/planner/`
- Result: `25 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `152 passed`

## 2026-05-12

Schema + renderer Phase 1a: `TestCase.role` and `content_string` rendering fix.

### Completed work

- **`aegis_test_generator/test_templates/schemas.py`**
  - Added `role: Literal["guard", "verify"] = "guard"` to `TestCase` (after `reason`), with `from typing import Literal` import. Rows without `role` default to `"guard"`; `extra="forbid"` unchanged.
- **`aegis_test_generator/test_templates/renderer.py`**
  - Fixed `content_contains` and `content_not_contains` templates: `host.file(...).content_string` is a `str` in testinfra, so removed erroneous `.decode(...)` usage; assertions now use `content_string` directly.
- **`tests/aegis_test_generator/test_templates/test_schemas.py`**
  - Added five tests: default `role`, `verify` / `guard` acceptance, invalid `role` value, and `role=None` rejection via `SchemaValidationError`.
- **`tests/aegis_test_generator/test_templates/test_renderer.py`**
  - Added `test_content_contains_no_decode` and `test_content_not_contains_no_decode` asserting rendered bodies include `content_string` and omit `.decode(`.

### Validation

- Ran: `PYTHONPATH=src pytest -q tests/aegis_test_generator/test_templates/`
- Result: `31 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `159 passed`

## 2026-05-13

Runner Phase 2: `GenerateResult`, cached `TestPlan`, and `role` on check records.

### Completed work

- **`aegis_test_generator/generate.py`**
  - Added frozen dataclass `GenerateResult` (`path`, `plan`, `warnings`).
  - `generate_tests()` now returns `GenerateResult` instead of a bare `Path`.
- **`aegis_test_generator/__init__.py`**
  - Exports `GenerateResult` alongside `generate_tests`.
- **`aegis_test_generator/runner/testinfra_runner.py`**
  - Caches `_test_plan` from generation; `_role_for_nodeid()` maps pytest nodeids (`::test_{index}_`) to `TestPlan.tests[index].role`, defaulting to `"guard"`.
  - Check records include `"role"` next to `suite_id`, `check_id`, `status`, `title`.
  - Planner warnings from generation are appended to `last_warnings` with prefix `generate: `.
- **`tests/aegis_test_generator/test_generate.py`** — assertions use `GenerateResult.path`.
- **`tests/aegis_test_generator/runner/test_testinfra_runner.py`** — mocks return `GenerateResult`; added `test_role_injected_into_records`, `test_role_defaults_to_guard_on_nodeid_mismatch`, `test_generate_warnings_surfaced`.

Note: `GenerateResult` is not re-exported from `aegis_test_generator.test_templates` to avoid a circular import (`generate` → `test_templates.renderer` loads the `test_templates` package `__init__`).

### Validation

- Ran: `PYTHONPATH=src pytest -q tests/aegis_test_generator/runner/ tests/aegis_test_generator/test_generate.py`
- Result: `36 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `162 passed`

### Evaluation Phase 3: `verified` / `verification_failed`, counts, `patch_verified`

#### Completed work

- **`src/runtime_skeleton/interfaces/contracts.py`**
  - `EvaluationResult` and `DiffResult`: `verified_count`, `verification_failed_count` (after `fixed_count`).
  - `PipelineSnapshot`: `patch_verified: bool = False`.
- **`src/runtime_skeleton/components/evaluation/core.py`**
  - `_classify(..., *, role="guard")`: verify-role uses `verified` / `verification_failed` when pre bucket is fail; guard behavior unchanged for other cases.
  - `evaluate()`: reads `role` from post or pre dict; aggregates `verified_count` / `verification_failed_count`.
- **`src/runtime_skeleton/diff/compare.py`** — copies new count fields into `DiffResult`.
- **`src/runtime_skeleton/orchestrator/pipeline.py`** — after each `compare_results`, sets `patch_verified` when `verified_count > 0` and `verification_failed_count == 0`.
- **`tests/runtime_skeleton/components/test_evaluation.py`** — nine tests for verify/guard transitions, counts, and `regression_detected` with verify-only vs mixed guard regression.
- **`tests/runtime_skeleton/orchestrator/test_pipeline_runner_wiring.py`** — three tests for `patch_verified` on external pre/post checks.

#### Validation

- Ran: `PYTHONPATH=src pytest -q tests/runtime_skeleton/components/test_evaluation.py tests/runtime_skeleton/orchestrator/test_pipeline_runner_wiring.py`
- Result: `25 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `174 passed`

## 2026-05-13 (Phase 4)

Planner Phase 4: shared OpenAI client extracted and classifier prompt taught the `role` vocabulary.

### Completed work

- **`aegis_test_generator/_openai_client.py`** (new)
  - Owns the JSON-object chat completion call shared by planner and classifier.
  - Exposes `call_openai(messages, *, client, model, default_model)` plus an exception hierarchy: `OpenAICallError` (base), `OpenAIConfigError` (missing `OPENAI_API_KEY` or `openai` package), `OpenAIRequestError` (API failure or empty content).
  - Resolves model via `model or os.environ["OPENAI_MODEL"] or default_model`; lazy-imports `openai` only when no client is injected.
- **`aegis_test_generator/planner/llm_planner.py`**
  - `_call_openai` reduced to a wrapper that calls the shared helper and maps `OpenAIConfigError → PlannerError`, `OpenAIRequestError → PlannerResponseError`. Removed now-unused `import os` and the lazy `openai` import from this function. `_FENCE_PATTERN`, `_extract_plan_rows`, `_shape_check_row`, etc. unchanged.
- **`aegis_test_generator/classifier/llm_classifier.py`**
  - `_call_openai` reduced to a wrapper that maps any `OpenAICallError` to `ClassifierError`. Removed now-unused `import os`.
  - System prompt in `_build_messages` rewritten to teach the model the `role` field semantics and the verify-role / guard-role transition outcomes (`verification_failed`, `verified`, `regressed`).
- **`tests/aegis_test_generator/test_openai_client.py`** (new) — six tests cover success, default-model fallback, env-model override, missing `OPENAI_API_KEY`, API failures, and empty content.
- **`tests/aegis_test_generator/classifier/test_llm_classifier.py`** — added `test_build_messages_mentions_role` asserting the system prompt mentions `role`, `verify`, `guard`, and `verification_failed`.

### Validation

- Ran: `PYTHONPATH=src pytest -q tests/aegis_test_generator/test_openai_client.py tests/aegis_test_generator/classifier/`
- Result: `12 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `181 passed`

## 2026-05-13 (Phase 5)

Planner Phase 5: DSPy replaces the raw OpenAI chat loop in `plan_from_playbook`; public `PlannerResult` contract unchanged.

### Completed work

- **`pyproject.toml`** — added `dspy-ai>=2.5` to the `testinfra` optional extra (alongside `openai`).
- **`aegis_test_generator/planner/dspy_planner.py`** (new)
  - Permissive Pydantic models `TestCaseDSPy` / `TestPlanDSPy` for DSPy structured outputs (`__test__ = False` to avoid pytest collection as test classes).
  - `GeneratePlanSignature` / `ReviewPlanSignature` with docstrings assigned after class body so role heuristics are visible to the LM.
  - `TestPlanModule`: `generate` then optional `review` pass; `make_lm(model, api_key=...)` wraps `dspy.LM("openai/{model}", ...)`.
- **`aegis_test_generator/planner/llm_planner.py`**
  - `plan_from_playbook(..., lm=None)` optional injected `dspy.LM`; `client` kept for compatibility but unused on the DSPy path.
  - Flow: dotenv load → read YAML → truncate → require `OPENAI_API_KEY` when `lm` is omitted → `dspy.context(lm)` → `TestPlanModule.forward` with `supported_types` from `SUPPORTED_TEST_TYPES`, `context_summary` from `_dspy_context_summary` (description / list predicted impact / legacy diff+sensitivity+impact block when present).
  - Rows shaped via `_dspy_dump_to_plan_row` then existing `_shape_check_row`; `raw` is JSON of DSPy dumps; removed `_build_messages`, `_build_review_messages`, `_call_openai`, `_GUARD_RULES`, `_review_diff_warnings`.
- **`tests/aegis_test_generator/planner/test_dspy_planner.py`** (new) — module forward/review wiring, `make_lm`, Pydantic defaults.
- **`tests/aegis_test_generator/planner/test_llm_planner.py`** — planner tests mock `_get_module` and `dspy.context`; removed prompt-string and old OpenAI-specific cases; added four `plan_from_playbook` DSPy-focused tests.

### Validation

- Ran: `PYTHONPATH=src pytest -q tests/aegis_test_generator/planner/` (with `[testinfra]` env including `dspy-ai`)
- Result: `24 passed`
- Ran: `PYTHONPATH=src pytest -q tests/`
- Result: `180 passed`

## 2026-05-24

### Improvement Plan (new phases) — context

Identified three gaps in the existing system and drafted a four-phase improvement plan (`docs/improvement-plan-phases.md`):
1. Sandboxes simulate clean installs only — no pre-existing state for update/maintenance patches.
2. Test generation skews toward install assertions; no coverage taxonomy or documentation.
3. Regression detection is binary (pass/fail only) — no severity weighting, exception classification, or coverage sufficiency checks.

Repo initialised and pushed to `https://github.com/Kaushal1101/aegis-test-generator-new.git` at this point.

---

### Phase 1: Pre-State Sandbox Infrastructure ✅

Goal: make sandboxes simulate real enterprise machines so update patches are tested against a realistic "before" state.

#### Completed work

- **`src/runtime_skeleton/sandbox/state.py`** (new) — `sandbox_state_to_playbook_yaml()` converts a `sandbox_state` dict (packages, files, services, users) into an Ansible setup playbook. `resolve_state_yaml()` mirrors `resolve_playbook_yaml`: disk file (`inputs/sandbox_state.yml`) takes precedence over the parsed section.
- **`src/runtime_skeleton/sandbox/setup.py`** (new) — thin `apply_setup()` wrapper, mirrors `sandbox/patch.py`.
- **`src/runtime_skeleton/sandbox/config.py`** — added `IMAGE_PROFILES` dict with four named presets (`minimal`, `debian-full`, `ubuntu-lts`, `rhel-compat`). Non-Python images carry `bootstrap_commands` (run via `docker exec` before Ansible) to install Python. `load_sandbox_config()` now resolves `profile` before merging explicit keys.
- **`src/runtime_skeleton/input/models.py`** — added `SandboxStatePackage`, `SandboxStateFile`, `SandboxStateService`, `SandboxStateUser`, `SandboxStateSection` models; `InputDocument` gains optional `sandbox_state: SandboxStateSection` field.
- **`src/runtime_skeleton/interfaces/contracts.py`** — added `SetupApplyRequest`, `SetupApplyResult` dataclasses; `SandboxComponent` protocol extended with `apply_setup()`; `PipelineSnapshot` gains `setup_apply: SetupApplyResult | None`.
- **`src/runtime_skeleton/interfaces/__init__.py`** — exported `SetupApplyRequest`, `SetupApplyResult`.
- **`src/runtime_skeleton/components/sandbox/core.py`** — added `apply_setup()` method to `DefaultSandboxComponent` (same pattern as `apply_patch`: resolve YAML → write inventory → run ansible-playbook; empty state with no disk file skips gracefully as `no_state`); added `apply_setup_request()` function; `create()` now runs `bootstrap_commands` via `docker exec` after container start if the config supplies them.
- **`src/runtime_skeleton/components/sandbox/__init__.py`** — exported `apply_setup_request`.
- **`src/runtime_skeleton/sandbox/__init__.py`** — exported `apply_setup`, `IMAGE_PROFILES`, `resolve_state_yaml`, `sandbox_state_to_playbook_yaml`.
- **`src/runtime_skeleton/orchestrator/pipeline.py`** — pipeline now runs `CREATE SANDBOX → APPLY SETUP STATE → PRE-PHASE → APPLY PATCH → POST-PHASE → EVALUATE`; `run_pipeline` gains `skip_setup: bool = False` parameter; setup result stored in `snap.setup_apply`.
- **`aegis_test_generator/planner/dspy_planner.py`** — `_ROLE_RULES` updated to generate paired tests for file-modification tasks: `content_contains` verify (new value) + `content_not_contains` guard (old value gone); same pattern for service reconfiguration.
- **`tests/runtime_skeleton/sandbox/test_state.py`** (new) — 17 tests for playbook generation and YAML resolution.
- **`tests/runtime_skeleton/components/test_sandbox_setup.py`** (new) — 8 tests for `apply_setup` (skip paths, success/failure/exec-error mapping, disk file precedence).
- **`tests/runtime_skeleton/sandbox/test_config_profiles.py`** (new) — 6 tests for profile resolution, override behaviour, unknown profile error.

#### Validation

- Ran: `pytest -q tests/runtime_skeleton/`
- Result: **`108 passed`** (77 pre-existing + 31 new)

---

### Phase 2: Update-Focused Test Generation ✅

Goal: shift test generation to produce higher-quality tests for edit/update patches and seed the LLM with diff-specific context.

#### Completed work

- **`aegis_test_generator/planner/intent.py`** (new) — `PatchIntent` enum (`install`, `update`, `remove`, `configure`, `mixed`). `classify_patch_intent(playbook_yaml, diff_modified=...)` walks every task in every play: `lineinfile`/`replace`/`blockinfile` → UPDATE; `apt state=latest` → UPDATE; `copy`/`template` to a `diff.modified` path → UPDATE; `apt state=present` → INSTALL; `apt state=absent` → REMOVE; `file state=absent` → REMOVE; multiple conflicting signals → MIXED; `update + configure` collapses to UPDATE.
- **`aegis_test_generator/planner/llm_planner.py`** — `SUPPORTED_TEST_TYPES` extended to 22 types; `_TYPES_REQUIRING_EXPECTED` updated; `_TYPES_REQUIRING_EXPECTED_BEFORE` added for `file_mode_changed`; `_shape_check_row` validates `expected_before`; `_dspy_dump_to_plan_row` passes through `expected_before`; `_format_priority_targets()` added — lists modified files ordered by sensitivity score and flags ≥0.5 as HIGH RISK; `_dspy_context_summary()` now accepts `patch_intent` keyword and appends the priority targets block when `diff.modified` is non-empty; `plan_from_playbook()` classifies intent and passes it into the context summary.
- **`aegis_test_generator/planner/dspy_planner.py`** — `_SUPPORTED` updated with three new types; `TestCaseDSPy` gains `expected_before: Any = None`; `_GENERATE_DOC` and `_REVIEW_DOC` document new types and the paired-test requirement.
- **`aegis_test_generator/test_templates/schemas.py`** — `TestCase` gains `expected_before: str | None = None`.
- **`aegis_test_generator/test_templates/renderer.py`** — three new match cases:
  - `content_changed`: asserts old value substring is absent from the file (`f.exists` + `old_val not in f.content_string`).
  - `file_mode_changed`: parses both `expected_before` and `expected` as octal; renders `f.mode != old_oct` + `f.mode == new_oct`.
  - `package_version_range`: imports `packaging.specifiers.SpecifierSet` inline; checks `pkg.is_installed` and `pkg.version in SpecifierSet(constraint)`.
- **`tests/aegis_test_generator/test_templates/test_schemas.py`** — parametrize fixtures updated for new types.
- **`tests/aegis_test_generator/test_templates/test_renderer.py`** — `_row()` updated for new types.
- **`tests/aegis_test_generator/planner/test_intent.py`** (new) — 18 tests covering all intent signals, mixed cases, edge cases (invalid YAML, empty playbook, service-only → MIXED).
- **`tests/aegis_test_generator/planner/test_context_summary.py`** (new) — 6 tests for intent injection and priority target generation.
- **`tests/aegis_test_generator/test_templates/test_new_types.py`** (new) — 21 tests covering schema validation and renderer output for all three new test types.

#### Validation

- Ran: `pytest -q tests/`
- Result: **`278 passed`** (180 pre-existing + 98 new)

