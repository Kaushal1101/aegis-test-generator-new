# broken_patch (nonexistent package — expect verification_failed)
**Date:** 2026-05-14 08:56

**Sandbox:** `runtime-skeleton-sandbox-smoke-broken` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Not applied — ansible_run_failed

## Verdict

**FAIL** — patch did not achieve one or more of its stated goals.

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
| `package_installed` | `nonexistent-package-aegis-xyz-999` | The playbook attempts to install a package that does not exist. The test should verify that the package is not installed. | fail | fail | ✗ verification failed |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

*(No guard-role tests were generated for this run.)*
