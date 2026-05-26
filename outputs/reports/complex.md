# complex_patch — install git+curl, create /opt/aegis
**Date:** 2026-05-26 09:31

**Sandbox:** `runtime-skeleton-sandbox-complex-run-001` (image: `python:3.12-slim-bookworm`)  
**Patch apply:** Applied successfully

## Verdict

**PASS** — Patch achieved its goals and introduced no regressions.

| Verified | Verification failed | Regressed |
|---|---|---|
| 9 | 0 | 0 |

## What the patch does

The playbook contains the following tasks:

- Install git and curl
- Create aegis working directory
- Write aegis config file

Based on the verify-role tests the pipeline generated, the patch is expected to:

- Install the `git` package
- Install the `curl` package
- Create the directory `/opt/aegis`
- Set permissions on `/opt/aegis`
- Set ownership of `/opt/aegis`
- Create the file `/opt/aegis/config.conf`
- Write expected content to `/opt/aegis/config.conf`
- Set permissions on `/opt/aegis/config.conf`
- Set ownership of `/opt/aegis/config.conf`

## Patch verification tests

These tests confirm the patch achieved its stated goals. Each was expected to fail before the patch and pass after.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `package_installed` | `git` | Ensure git is installed as specified in the playbook. | fail | pass | ✓ verified |
| `package_installed` | `curl` | Ensure curl is installed as specified in the playbook. | fail | pass | ✓ verified |
| `directory_exists` | `/opt/aegis` | Ensure the aegis working directory is created. | fail | pass | ✓ verified |
| `file_mode` | `/opt/aegis` | Ensure the aegis directory has the correct permissions. | fail | pass | ✓ verified |
| `file_owner` | `/opt/aegis` | Ensure the aegis directory is owned by root. | fail | pass | ✓ verified |
| `file_exists` | `/opt/aegis/config.conf` | Ensure the aegis config file is created. | fail | pass | ✓ verified |
| `content_contains` | `/opt/aegis/config.conf` | Ensure the aegis config file contains the correct configuration. | fail | pass | ✓ verified |
| `file_mode` | `/opt/aegis/config.conf` | Ensure the aegis config file has the correct permissions. | fail | pass | ✓ verified |
| `file_owner` | `/opt/aegis/config.conf` | Ensure the aegis config file is owned by root. | fail | pass | ✓ verified |

## Regression guard tests

These tests confirm the patch did not accidentally break anything it was not supposed to touch. They were expected to keep passing throughout.

| Test type | Target | Reason | Pre | Post | Result |
|---|---|---|---|---|---|
| `content_not_contains` | `/opt/aegis/config.conf` | Ensure the aegis config file does not contain any old configuration values. | fail | pass | ✓ fixed |

## Coverage Summary

| Category | Verify tests | Guard tests | Total |
|---|---|---|---|
| `package_integrity` | 2 | 0 | 2 |
| `file_integrity` | 6 | 0 | 6 |
| `file_content` | 1 | 1 | 2 |
| `service_state` | 0 | 0 | 0 |
| `network_posture` | 0 | 0 | 0 |
| `identity` | 0 | 0 | 0 |
| `command_behavior` | 0 | 0 | 0 |
