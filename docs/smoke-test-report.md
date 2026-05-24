# Pipeline Smoke Test Report
**Date:** 2026-05-14  
**Script:** `scripts/smoke_pipeline.py`  
**Environment:** macOS, Docker (`python:3.12-slim-bookworm`), ansible-playbook 2.20.4, OpenAI `gpt-4o`

---

## What was tested

Five playbooks were run through the full pipeline end-to-end:

```
Sandbox create (Docker)
  → TestSuite pre  (testinfra against clean container)
  → ansible-playbook apply
  → TestSuite post  (testinfra against patched container)
  → Evaluation  (compare pre vs post, classify transitions)
```

---

## Results

| Playbook | Tests generated | Verified | Verification failed | Regressed | patch_verified | Result |
|---|---|---|---|---|---|---|
| `simple_patch.yml` (install curl) | 1 | 1 | 0 | 0 | True | PASS |
| `patch.yml` (nginx + service) | 2 | 2 | 0 | 0 | True | PASS |
| `complex_patch.yml` (git+curl, dir, config) | 9 | 9 | 0 | 0 | True | PASS |
| `broken_patch.yml` (nonexistent package) | 1 | 0 | 1 | 0 | False | PASS (expected False) |
| `partial_patch.yml` (curl+dir succeed, bad pkg ignored) | 5 | 3 | 0 | 0 | True | PASS |

All 5 cases behaved as expected.

---

## Case details

### simple_patch — install curl
Single `apt` task. LLM generated one `verify`-role `package_installed` test.

```
✓✓ [verify] verified   test_0_package_installed
```

Pre: fail (curl not installed). Post: pass. `patch_verified: True`.

---

### patch — nginx install + service
Two tasks: install nginx, start and enable service. LLM generated two `verify`-role tests.  
Note: on this run the LLM's review pass pruned the `service_enabled` check it generated in a prior run — normal non-determinism at temperature=0.

```
✓✓ [verify] verified   test_0_package_installed
✓✓ [verify] verified   test_1_service_running
```

`patch_verified: True`.

---

### complex_patch — git+curl, /opt/aegis directory, config file
Three tasks: install two packages, create directory with mode/owner, write config file with content.  
LLM generated 9 tests covering all playbook tasks including `file_mode`, `file_owner`, `content_contains`.

```
✓✓ [verify] verified   test_0_package_installed  (git)
✓✓ [verify] verified   test_1_package_installed  (curl)
✓✓ [verify] verified   test_2_directory_exists   (/opt/aegis)
✓✓ [verify] verified   test_3_file_mode          (/opt/aegis, 0o755)
✓✓ [verify] verified   test_4_file_owner         (/opt/aegis, root)
✓✓ [verify] verified   test_5_file_exists        (/opt/aegis/config.conf)
✓✓ [verify] verified   test_6_content_contains   ([aegis]\nversion=1\nmode=strict)
✓✓ [verify] verified   test_7_file_mode          (/opt/aegis/config.conf, 0o644)
✓✓ [verify] verified   test_8_file_owner         (/opt/aegis/config.conf, root)
```

`patch_verified: True`.

**Note:** An earlier run failed on `test_3_file_mode` and `test_7_file_mode` (see Bugs Fixed below). After fixing the renderer, all 9 verified.

---

### broken_patch — nonexistent package
Playbook attempts to install `nonexistent-package-aegis-xyz-999`. ansible-playbook fails, patch is skipped, container is unchanged.

```
✗✗ [verify] verification_failed   test_0_package_installed
```

Pre: fail. Post: still fail (package was never installed). `patch_verified: False`.  
Pipeline correctly identified that the patch did not achieve its goal.

---

### partial_patch — mixed outcome
Playbook installs curl (succeeds), creates `/opt/myapp` directory (succeeds), attempts to install a nonexistent package with `ignore_errors: true` (fails silently), conditionally writes a marker file (skipped).

```
✓✓ [verify] verified     test_0_package_installed  (curl)
✓✓ [verify] verified     test_1_directory_exists   (/opt/myapp)
✓✓ [verify] verified     test_2_file_mode          (/opt/myapp, 0o755)
✗~ [guard ] still_fail   test_3_package_installed  (nonexistent-package)
✓  [guard ] still_pass   test_4_file_absent        (/opt/myapp/ready)
```

The LLM correctly assigned `guard` (not `verify`) to the `ignore_errors` package — it read the playbook intent and did not treat a best-effort task as a patch goal. `still_fail` on that check is informational, not a regression. `patch_verified: True`.

---

## Bugs found and fixed during testing

### 1. Input schema mismatch
**Problem:** `run_pipeline` silently skips the sandbox when `parse_input` fails. The smoke script was passing a minimal `input_json` missing `schema_version`, `diff`, `sensitivity_verdict`, and `predicted_impact`. The parser returned an error, forcing `skip=True` on the sandbox.  
**Fix:** Smoke script updated to pass the full required schema.

### 2. `file_mode` renderer always fails
**Problem:** `host.file(path).mode` returns an integer (e.g., `493` for `0o755`). The renderer was generating `assert host.file(p).mode == '0755'` — integer vs string, always `False`.  
**Fix:** Renderer now converts the expected octal string to a Python octal integer literal: `assert host.file(p).mode == 0o755`.

### 3. `content_contains` crash on missing `expected`
**Problem:** The LLM generated `content_contains` rows without an `expected` value (the substring to search for). `_shape_check_row` passed them through, `validate_plan` passed them, but `render_plan` raised `RendererError`.  
**Fix:** Added `expected: Any = None` to `TestCaseDSPy`, updated `_dspy_dump_to_plan_row` to accept `expected` directly or nested in `args`, and added validation in `_shape_check_row` to drop rows of types requiring `expected` if the field is absent. Updated DSPy signature docstrings to explicitly instruct the LLM to provide `expected` for these types.

### 4. `role` missing from transition dict
**Problem:** `DefaultEvaluationComponent` computed `role` internally but did not include it in the transition dict. Display showed every transition as `[guard]`.  
**Fix:** Added `"role": role` to each transition dict in `evaluation/core.py`.

### 5. DSPy `module.forward()` deprecation
**Problem:** `llm_planner.py` called `module.forward(...)` directly, triggering a DSPy deprecation warning.  
**Fix:** Changed to `module(...)` (standard `__call__` path). Test mocks updated from `mock_mod.forward.return_value` to `mock_mod.return_value`.

---

## Known limitations observed

- **LLM non-determinism:** The nginx case generated 3 tests in one run and 2 in another (the review pass pruned `service_enabled` the second time). Results are consistent in direction but not always identical in test count across runs.
- **`expected` value quality:** The LLM sometimes omits `expected` for `content_contains` tests. The new validation drops these rows with a warning rather than crashing, but coverage is lost. The review pass now explicitly instructs the LLM to include `expected`, which reduced the rate of omission.
- **`service_enabled` inconsistency:** The nginx playbook sets `enabled: true` but the LLM doesn't consistently generate a `service_enabled` test. This is a prompt/coverage gap.
