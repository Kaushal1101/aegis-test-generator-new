# simple_patch — install curl
**Date:** 2026-05-26 09:31

**Sandbox:** `runtime-skeleton-sandbox-simple-run-001` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Applied successfully

## Verdict

**PASS** — Patch achieved its goals and introduced no regressions.

| Verified | Verification failed | Regressed |
|---|---|---|
| 2 | 0 | 0 |

## What the patch does

The playbook contains the following tasks:

- Install curl

Based on the verify-role tests the pipeline generated, the patch is expected to:

- Install the `curl` package
- Create the file `/usr/bin/curl`

## Patch verification tests

These tests confirm the patch achieved its stated goals. Each was expected to fail before the patch and pass after.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `curl` | The playbook installs the curl package. | fail | pass | ✓ verified |
| `file_exists` | `/usr/bin/curl` | The curl binary should exist after installation. | fail | pass | ✓ verified |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

*(No guard-role tests were generated for this run.)*

## Coverage Summary

| Category | Verify tests | Guard tests | Total |
|---|---|---|---|
| `package_integrity` | 1 | 0 | 1 |
| `file_integrity` | 1 | 0 | 1 |
| `file_content` | 0 | 0 | 0 |
| `service_state` | 0 | 0 | 0 |
| `network_posture` | 0 | 0 | 0 |
| `identity` | 0 | 0 | 0 |
| `command_behavior` | 0 | 0 | 0 |
