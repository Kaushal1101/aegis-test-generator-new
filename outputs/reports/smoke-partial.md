# partial_patch (curl+dir succeed, bad package ignored)
**Date:** 2026-05-14 08:57

**Sandbox:** `runtime-skeleton-sandbox-smoke-partial` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Applied successfully

## Verdict

**PASS** — patch achieved its goals and introduced no regressions.

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

## Patch verification tests

These tests confirm the patch achieved its stated goals. Each was expected to fail before the patch and pass after.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `curl` | Ensure curl is installed | fail | pass | ✓ verified |
| `directory_exists` | `/opt/myapp` | Ensure the working directory is created | fail | pass | ✓ verified |
| `file_mode` | `/opt/myapp` | Ensure the directory has the correct permissions | fail | pass | ✓ verified |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `nonexistent-package-aegis-xyz-999` | Attempt to install a non-existent package | fail | fail | ~ still failing |
| `file_absent` | `/opt/myapp/ready` | Marker file should not exist as the task never runs | pass | pass | ✓ still passing |
