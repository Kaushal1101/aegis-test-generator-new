# Aegis Coverage Reference

This document describes the test coverage taxonomy used by Aegis, including the
seven coverage categories, all 22 supported test types, known strengths, and
known gaps. Use this as a guide when interpreting per-run coverage summaries.

---

## Coverage Categories

Aegis assigns every generated test to one of seven coverage categories based on
its `test_type`. The category is auto-assigned and appears in the per-run
coverage summary table.

| Category | What It Covers |
|---|---|
| `package_integrity` | Software inventory — packages installed, absent, at the right version |
| `file_integrity` | File system state — existence, permissions, ownership, symlinks, executables |
| `file_content` | Configuration correctness — what files contain or no longer contain |
| `service_state` | Daemon / process lifecycle — running and enabled at boot |
| `network_posture` | Exposed ports — which ports are open and listening |
| `identity` | Users and groups — accounts and groups that must exist |
| `command_behavior` | Script / binary execution — commands that must succeed or produce expected output |

---

## Test Type Reference

All 22 test types Aegis can generate, grouped by category.

### package_integrity

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `package_installed` | Package is present on the system | Confirm an install step worked | `nginx` |
| `package_absent` | Package has been removed | Confirm an uninstall step worked | `telnet` |
| `package_version` | Package is at an exact version | Pin a specific release | `nginx=1.24.0` |
| `package_version_range` | Package version satisfies a semver constraint (e.g. `>=2.0,<3.0`) | Version-bump patches where an exact pin isn't known yet | `openssl` |

### file_integrity

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `file_exists` | Path exists and is a regular file | Confirm config/binary was deployed | `/etc/nginx/nginx.conf` |
| `file_absent` | Path does not exist | Confirm cleanup removed a file | `/etc/legacy.conf` |
| `directory_exists` | Path exists and is a directory | Confirm a directory was created | `/var/lib/app` |
| `file_mode` | File has an exact octal permission (e.g. `0644`) | Validate permissions set by a task | `/etc/ssh/sshd_config` |
| `file_mode_changed` | File mode changed from `expected_before` to `expected` | Permissions update patches | `/etc/app/settings.conf` |
| `file_owner` | File is owned by a specific user:group | Validate ownership set by a task | `/opt/app/data` |
| `symlink_exists` | Path is a symbolic link | Confirm a symlink was created | `/usr/local/bin/app` |
| `binary_executable` | File exists and is executable | Confirm a script/binary was installed with correct permissions | `/usr/local/bin/deploy.sh` |

### file_content

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `content_contains` | File contains an expected substring | Verify a config key/value was written | `/etc/nginx/nginx.conf` |
| `content_not_contains` | File does not contain a substring | Verify an old value was removed (guard for update patches) | `/etc/nginx/nginx.conf` |
| `content_changed` | File content no longer contains the `expected` baseline value | Verify a file was actually modified (update patches) | `/etc/app/config.ini` |
| `command_output_contains` | Output of a shell command contains an expected substring | Verify runtime state not reflected in a static file | `systemctl status nginx` |

### service_state

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `service_running` | Service is active / running | Confirm a service was started or restarted | `nginx` |
| `service_enabled` | Service is enabled to start at boot | Confirm systemd unit was enabled | `nginx` |

### network_posture

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `port_listening` | A port is open and accepting connections | Confirm a server was started on the expected port | `443` |

### identity

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `user_exists` | A system user exists | Confirm a service account was created | `appuser` |
| `group_exists` | A system group exists | Confirm a group was created | `appgroup` |

### command_behavior

| Test type | Description | Typical use case | Example target |
|---|---|---|---|
| `command_succeeds` | A shell command exits with code 0 | Confirm a script or binary runs without error | `/opt/app/healthcheck.sh` |

---

## Coverage Category Matrix

Which enterprise patch scenarios each category is most relevant to:

| Category | Install | Update | Remove | Configure | Mixed |
|---|---|---|---|---|---|
| `package_integrity` | ✓ required | ✓ required | ✓ required | — | ✓ required |
| `file_integrity` | ✓ required | — | ✓ required | — | ✓ required |
| `file_content` | — | ✓ required | — | ✓ required | ✓ required |
| `service_state` | recommended | recommended | — | recommended | recommended |
| `network_posture` | recommended | — | — | — | — |
| `identity` | recommended | — | — | — | — |
| `command_behavior` | — | — | — | — | — |

**Required** categories are flagged ⚠️ in the coverage summary when they have zero tests.
**Recommended** categories are not flagged but represent common blind spots.

---

## Strengths

Aegis tests well in the following areas:

- **Package management** — install, remove, exact version, and semver range assertions
  are all first-class test types with full renderer support.
- **File existence and integrity** — file/directory/symlink existence, ownership, and
  permissions are reliably verifiable via Testinfra's `host.file()` API.
- **Configuration content** — substring presence/absence checks cover the most common
  form of configuration correctness in Ansible playbooks (lineinfile, template, copy).
- **Update detection** — `content_changed` and `file_mode_changed` are specifically
  designed for update patches, where the goal is to confirm a file changed rather than
  confirm a specific value is present.
- **Paired test generation** — for update patches, Aegis generates paired verify + guard
  tests (new value present AND old value absent), reducing false positives.

---

## Known Gaps

The following scenarios are currently outside Aegis's testing surface:

- **Network connectivity between containers** — Testinfra's `host.socket()` can check
  that a port is open on the container, but cannot test outbound connectivity to
  other services or DNS resolution.
- **Database state** — there is no test type for querying a running database. Schema
  migrations, row counts, and application-level data integrity are not testable.
- **Application-level behavior** — HTTP endpoint health checks, application log
  parsing, and multi-service integration tests require a live application stack that
  the single-container sandbox does not provide.
- **Windows targets** — all test types assume a Linux/systemd environment. Windows
  registry, services (SCM), and MSI packages are not supported.
- **Systemd service state on minimal images** — the `python:3.12-slim-bookworm`
  (minimal) profile has no `systemd`. Service state tests will fail on this image
  unless the `ubuntu-lts` or `rhel-compat` profile is used.
- **Flaky or environment-dependent tests** — Aegis does not yet annotate or suppress
  tests that fail due to Docker environment limitations (e.g., no internet access,
  missing kernel modules). This is planned for Phase 4.
- **Severity-weighted regression scoring** — all regressions are currently treated
  equally regardless of how sensitive the affected file is. Phase 4 will address this.
