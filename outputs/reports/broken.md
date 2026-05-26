# broken_patch — nonexistent package (expect FAIL)
**Date:** 2026-05-26 09:32

**Sandbox:** `runtime-skeleton-sandbox-broken-run-001` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Not applied — ansible_run_failed

## Verdict

**FAIL_VERIFY** — Patch did not achieve one or more stated goals. No regressions detected.

| Verified | Verification failed | Regressed |
|---|---|---|
| 0 | 1 | 0 |

## What the patch does

The playbook contains the following tasks:

- Install a package that does not exist

Based on the verify-role tests the pipeline generated, the patch is expected to:

- Install the `nonexistent-package-aegis-xyz-999` package

## Patch verification tests

These tests confirm the patch achieved its stated goals. Each was expected to fail before the patch and pass after.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `nonexistent-package-aegis-xyz-999` | The playbook intends to install a package that does not exist. | fail | fail | ✗ verification failed |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

*(No guard-role tests were generated for this run.)*

## Coverage Summary

| Category | Verify tests | Guard tests | Total |
|---|---|---|---|
| `package_integrity` | 1 | 0 | 1 |
| `file_integrity` | 0 | 0 | 0 ⚠️ |
| `file_content` | 0 | 0 | 0 |
| `service_state` | 0 | 0 | 0 |
| `network_posture` | 0 | 0 | 0 |
| `identity` | 0 | 0 | 0 |
| `command_behavior` | 0 | 0 | 0 |

⚠️ Categories marked above have no coverage. They may be blind spots given this patch's intent.
