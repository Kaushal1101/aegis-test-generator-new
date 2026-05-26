# partial_patch — mixed tasks (expect FAIL_VERIFY)
**Date:** 2026-05-26 09:32

**Sandbox:** `runtime-skeleton-sandbox-partial-run-001` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Applied successfully

## Verdict

**PASS_WITH_WARNINGS** — Patch goals verified and no regressions, but coverage gaps were detected. See Coverage Summary for details.

| Verified | Verification failed | Regressed |
|---|---|---|
| 3 | 0 | 0 |

## What the patch does

The playbook contains the following tasks:

- Install curl (succeeds)
- Create a working directory (succeeds)
- Install a package that does not exist (fails)
- Write a marker file only if previous task succeeded (never runs)

Based on the verify-role tests the pipeline generated, the patch is expected to:

- Install the `curl` package
- Create the directory `/opt/myapp`
- Set permissions on `/opt/myapp`
- Remove the `nonexistent-package-aegis-xyz-999` package

## Patch verification tests

These tests confirm the patch achieved its stated goals. Each was expected to fail before the patch and pass after.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `curl` | Ensure curl is installed as expected. | fail | pass | ✓ verified |
| `directory_exists` | `/opt/myapp` | Ensure the working directory is created. | fail | pass | ✓ verified |
| `file_mode` | `/opt/myapp` | Ensure the working directory has the correct permissions. | fail | pass | ✓ verified |
| `package_absent` | `nonexistent-package-aegis-xyz-999` | The package does not exist and should not be installed. | pass | pass | ✓ still passing |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `file_absent` | `/opt/myapp/ready` | The marker file should not be created as the previous task failed. | pass | pass | ✓ still passing |

## Coverage Summary

| Category | Verify tests | Guard tests | Total |
|---|---|---|---|
| `package_integrity` | 2 | 0 | 2 |
| `file_integrity` | 2 | 1 | 3 |
| `file_content` | 0 | 0 | 0 ⚠️ |
| `service_state` | 0 | 0 | 0 |
| `network_posture` | 0 | 0 | 0 |
| `identity` | 0 | 0 | 0 |
| `command_behavior` | 0 | 0 | 0 |

⚠️ Categories marked above have no coverage. They may be blind spots given this patch's intent.
