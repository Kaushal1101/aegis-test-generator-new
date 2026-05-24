# Development Report: aegis-test-generator Phases 1–5
**Date:** 2026-05-14  
**Scope:** Semantic refactor (Phases 1–4), DSPy migration (Phase 5), template expansion, and end-to-end validation

---

## Background

`aegis-test-generator` was originally a regression detection tool. Given an Ansible playbook and a Docker container, it generated testinfra tests, ran them before and after applying the playbook as a patch, and flagged any failures introduced by the patch.

The tool had a fundamental gap: it had no way to distinguish between a test that *should* stay passing (a regression guard) and a test that *should start* passing because of the patch (patch verification). Every test was treated identically. This meant the tool could detect regressions but could not answer the question: *did the patch actually work?*

The work across Phases 1–5 closes that gap and improves the quality of test generation.

---

## Phase 1a — Role field and renderer fix
**Agent:** schema-renderer-agent  
**Files:** `schemas.py`, `renderer.py`

### What was added
A `role` field was added to `TestCase`:

```python
role: Literal["guard", "verify"] = "guard"
```

- `guard` — this check should stay passing after the patch (regression detection)
- `verify` — this check should become passing because of the patch (patch verification)

This single field is what makes the tool dual-purpose. All downstream logic branches on it.

### Bug fixed
The `content_contains` and `content_not_contains` renderer templates were calling `.content_string.decode('utf-8')` on a value that is already a string. This produced broken generated test code. Fixed to use `.content_string` directly.

---

## Phase 1b — Planner prompt
**Agent:** planner-agent  
**Files:** `llm_planner.py`

### What was added
The LLM system prompt was extended with explicit role-assignment heuristics:

| Playbook task | Role assigned |
|---|---|
| Installs a package | `verify` + `package_installed` |
| Removes a package | `verify` + `package_absent` |
| Creates a file or directory | `verify` + `file_exists` / `directory_exists` |
| Deletes a file | `verify` + `file_absent` |
| Writes content to a file | `verify` + `content_contains` |
| Starts or enables a service | `verify` + `service_running` |
| Anything the patch does not touch | `guard` |

A review pass was added: after the initial plan is generated, a second LLM call reviews role assignments and corrects mis-assignments before the plan is validated. `_shape_check_row` was updated to reject invalid role values with a warning rather than a crash.

---

## Phase 2 — Runner role injection
**Agent:** runner-agent  
**Files:** `generate.py`, `testinfra_runner.py`

### What was added
`generate_tests()` previously returned a bare `Path`, discarding the `TestPlan` after rendering. The `TestPlan` holds the role for each test case. Without it, check records produced by the runner had no `role` key and evaluation could not distinguish guard from verify tests.

**`GenerateResult` dataclass** was introduced:

```python
@dataclass(frozen=True)
class GenerateResult:
    path: Path
    plan: TestPlan
    warnings: list[str]
```

`TestinfraRunner` now caches the `TestPlan` after generation. When building check records from the pytest JSON report, it looks up each test by index (parsed from the node ID `test_{index}_{type}`) and injects `"role"` into the check dict. Role now travels end-to-end from the plan into pre/post evidence dictionaries.

---

## Phase 3 — Evaluation transitions
**Agent:** evaluation-agent  
**Files:** `contracts.py`, `evaluation/core.py`, `diff/compare.py`, `pipeline.py`

### What was added
Two new evaluation outcomes were defined for `verify`-role checks:

| Transition | Meaning |
|---|---|
| `verified` | Pre=fail, Post=pass — patch achieved its goal ✓ |
| `verification_failed` | Pre=fail, Post=fail — patch did not work ✗ |

For `guard`-role checks the existing labels (`fixed`, `still_fail`, `regressed`, `still_pass`, etc.) are unchanged.

`_classify()` now accepts a `role` parameter and routes accordingly:

```python
if pre_bucket == "fail":
    if role == "verify":
        return "verified" if post_bucket != "fail" else "verification_failed"
    # guard path unchanged
```

New count fields were added to `EvaluationResult` and `DiffResult`:
- `verified_count: int = 0`
- `verification_failed_count: int = 0`

A new boolean was added to `PipelineSnapshot`:

```python
patch_verified: bool = False
```

Set in `run_pipeline` after evaluation:

```python
snap.patch_verified = (
    snap.diff.verified_count > 0
    and snap.diff.verification_failed_count == 0
)
```

`regression_detected` semantics are unchanged — it is still driven by `regressed_count + new_fail_count`.

---

## Phase 4 — Shared OpenAI client and classifier role awareness
**Agent:** planner-agent  
**Files:** `_openai_client.py` (new), `llm_planner.py`, `llm_classifier.py`

### What was added

**Shared client module** — both `llm_planner.py` and `llm_classifier.py` contained an identical `_call_openai()` function. This was extracted into `aegis_test_generator/_openai_client.py` with typed exception classes:

```python
class OpenAICallError(Exception): ...       # base
class OpenAIConfigError(OpenAICallError): ... # missing key or package
class OpenAIRequestError(OpenAICallError): ...# API failure or empty response
```

Each domain module maps these to its own error hierarchy in a thin wrapper, so callers never need to catch `OpenAICallError` directly.

**Classifier prompt update** — the classifier system prompt was updated to understand `role`. It now distinguishes between:
- `verify`-role + `verification_failed` → patch did not achieve its stated goal (set `applicable=false`)
- `verify`-role + `verified` → expected success (set `applicable=true`)
- `guard`-role + `regressed` → unexpected side effect (set `applicable` based on whether it is genuine)

---

## Phase 5 — DSPy migration
**Agent:** planner-agent  
**Files:** `dspy_planner.py` (new), `llm_planner.py`, `pyproject.toml`

### What was added
The raw OpenAI prompt loop in `llm_planner.py` was replaced with a structured DSPy module. The public API of `plan_from_playbook` and `PlannerResult` did not change — DSPy is an internal implementation detail.

**`dspy_planner.py`** defines:

- `TestCaseDSPy` / `TestPlanDSPy` — permissive Pydantic models used as DSPy output types
- `GeneratePlanSignature` / `ReviewPlanSignature` — DSPy signatures with docstrings containing the role-assignment heuristics (making them available to any future DSPy optimiser)
- `TestPlanModule` — a `dspy.Module` with two `dspy.Predict` predictors: generate then optional review
- `make_lm(model, api_key)` — factory returning a configured `dspy.LM`

**`plan_from_playbook`** now calls:

```python
with dspy.context(lm=resolved_lm):
    prediction = module(
        playbook_yaml=playbook_text,
        context_summary=context_summary,
        supported_types=supported_types,
        review=review,
    )
```

An optional `lm` parameter was added for injecting a pre-built `dspy.LM` (used in tests and for per-call model switching without mutating global state). The `client` parameter is retained for backward compatibility but is unused on the DSPy path.

**Why DSPy over raw prompts:**
- Structured Pydantic output types replace brittle JSON fence-stripping and manual parsing
- Signatures make prompts inspectable and optimisable (future: `dspy.compile` with labelled examples)
- `dspy.context(lm=...)` enables thread-safe per-call model switching

---

## Template expansion
**Files:** `renderer.py`, `llm_planner.py`, `dspy_planner.py`, `schemas.py`

The original 12 test templates were expanded to 19 by adding:

| New type | Testinfra assertion | `expected` required |
|---|---|---|
| `service_enabled` | `host.service(name).is_enabled` | No |
| `port_listening` | `host.socket(spec).is_listening` | No |
| `user_exists` | `host.user(name).exists` | No |
| `group_exists` | `host.group(name).exists` | No |
| `symlink_exists` | `f.exists and f.is_symlink` | No |
| `command_output_contains` | `host.run(cmd).stdout` contains substring | Yes |
| `package_version` | `pkg.is_installed and pkg.version == expected` | Yes |

`schemas.py` needed no change — it derives its allowed types from `SUPPORTED_TEST_TYPES` in `llm_planner.py` at import time.

---

## End-to-end validation

Five playbooks were run through the full pipeline (Docker sandbox → pre-checks → ansible apply → post-checks → evaluation).

| Playbook | Tests | Verified | Failed | patch_verified |
|---|---|---|---|---|
| `simple_patch.yml` — install curl | 1 | 1 | 0 | True |
| `patch.yml` — nginx + service | 2 | 2 | 0 | True |
| `complex_patch.yml` — packages, directory, config file | 9 | 9 | 0 | True |
| `broken_patch.yml` — nonexistent package (expected failure) | 1 | 0 | 1 | False |
| `partial_patch.yml` — partial success with `ignore_errors` | 5 | 3 | 0 | True |

### Notable observations

**Role assignment quality** — on `partial_patch.yml`, the playbook contains an `ignore_errors: true` task installing a nonexistent package. The LLM correctly assigned it `guard` (not `verify`) — it recognised that a best-effort task is not a patch goal. The still-failing guard check produced `still_fail`, which is informational and does not affect `patch_verified` or `regression_detected`.

**Broken patch detection** — `broken_patch.yml` confirmed the `verification_failed` path works end-to-end. The container was left unchanged after ansible failed, both pre and post checks failed on the nonexistent package, and `patch_verified` was correctly `False`.

### Bugs found and fixed during validation

| Bug | Root cause | Fix |
|---|---|---|
| Sandbox silently skipped | Input JSON missing `schema_version`, `diff`, `sensitivity_verdict`, `predicted_impact` fields required by `InputDocument` | Smoke script updated to pass full schema |
| `file_mode` tests always fail | `host.file(p).mode` returns `int`; renderer was generating `== '0755'` (string) | Renderer now converts expected octal string to Python octal literal `0o755` |
| `content_contains` crash on missing `expected` | LLM omitted `expected` field; `_shape_check_row` and `validate_plan` did not catch it; `render_plan` raised `RendererError` | Added `expected` to `TestCaseDSPy`, updated `_dspy_dump_to_plan_row` to accept it from multiple locations, added validation in `_shape_check_row` to drop rows with missing required `expected` |
| Role shown as `guard` on all transitions | `DefaultEvaluationComponent` computed `role` internally but did not include it in the transition dict | Added `"role": role` to each transition entry |
| DSPy deprecation warning | `module.forward(...)` called directly; DSPy prefers `module(...)` | Changed to `module(...)` call; updated test mocks |

---

## Test suite

All changes were covered by unit tests throughout. Final count after all phases:

```
PYTHONPATH=src pytest -q tests/
187 passed, 11 warnings
```

---

## Known limitations

- **LLM non-determinism at temperature=0** — the review pass introduces a second generation step which can produce slightly different test counts across runs (e.g., nginx `service_enabled` appeared in one run and was pruned in another). Outputs are directionally consistent but not byte-identical.
- **`expected` omission rate** — even with the updated prompt, the LLM occasionally omits `expected` for `content_contains` and similar types. The validation layer drops these rows with a warning. Coverage is reduced but the pipeline does not crash.
- **`service_enabled` coverage gap** — playbooks that set `enabled: true` do not consistently produce a `service_enabled` test. The LLM conflates running and enabled into a single `service_running` check.
- **No `guard`-role baseline** — the `python:3.12-slim-bookworm` base image has no pre-installed services or files worth guarding, so all generated tests were `verify`-role. Regression detection was not exercised against a meaningful pre-existing baseline in these smoke tests.
