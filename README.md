# Aegis Test Generator

LLM-driven infrastructure test generation and regression detection for Ansible patch playbooks.

## What it does

Given an Ansible patch playbook (and optionally a diff/sensitivity report from an upstream analyser), Aegis:

1. **Classifies** the patch intent (install / update / remove / configure / mixed).
2. **Generates** a validated Testinfra test plan using a two-pass DSPy planner, producing paired verify + guard tests for update patches.
3. **Spins up** a Docker sandbox pre-populated with the machine's existing state (`sandbox_state`).
4. **Runs** the generated tests before and after applying the patch.
5. **Evaluates** the pre/post transitions and reports: did the patch achieve its goals, and did it introduce regressions?

## Architecture

```
Input JSON
    │
    ▼
parse_input()
    │
    ▼
create_sandbox()          ← Docker container (configurable image profile)
    │
    ▼
apply_setup()             ← Pre-populate machine state (packages, files, services, users)
    │
    ▼
PRE-PHASE TESTS           ← LLM plans + renders Testinfra module; pytest runs it
    │
    ▼
apply_patch()             ← ansible-playbook inside container
    │
    ▼
POST-PHASE TESTS          ← same Testinfra module re-executed
    │
    ▼
evaluate()                ← classify each pre→post transition
    │
    ▼
report                    ← PASS / FAIL / PARTIAL verdict + transition table
```

## Key components

| Package | Location | Responsibility |
|---|---|---|
| `aegis_test_generator` | `aegis_test_generator/` | LLM planning, schema validation, Testinfra rendering, runner |
| `runtime_skeleton` | `src/runtime_skeleton/` | Sandbox lifecycle, patch application, evaluation, pipeline orchestration |

### Test generation

- **`planner/intent.py`** — classifies patch intent from playbook YAML + diff context.
- **`planner/llm_planner.py`** — drives DSPy structured prediction; injects patch intent and diff-seeded priority targets into the context summary.
- **`planner/dspy_planner.py`** — `TestPlanModule` (generate + review pass); role assignment rules.
- **`test_templates/schemas.py`** — Pydantic `TestCase` / `TestPlan` validation (22 supported test types).
- **`test_templates/renderer.py`** — fixed-template Testinfra module generation (no free-form LLM Python).
- **`runner/testinfra_runner.py`** — executes generated tests against a Docker container via `pytest --hosts=docker://`.

### Sandbox

- **`sandbox/state.py`** — converts `sandbox_state` section to an Ansible setup playbook for pre-populating machine state.
- **`sandbox/config.py`** — configurable image profiles (`minimal`, `debian-full`, `ubuntu-lts`, `rhel-compat`) with bootstrap commands for Python installation.

### Evaluation

- Transitions classified as: `verified`, `verification_failed`, `regressed`, `fixed`, `still_pass`, `still_fail`, `new_pass`, `new_fail`, etc.
- Verdict: `PASS`, `FAIL`, `PARTIAL` based on verify-role outcomes and regression count.

## Supported test types (22)

| Category | Types |
|---|---|
| Package management | `package_installed`, `package_absent`, `package_version`, `package_version_range` |
| File / directory | `file_exists`, `file_absent`, `directory_exists`, `file_mode`, `file_mode_changed`, `file_owner`, `symlink_exists`, `binary_executable` |
| File content | `content_contains`, `content_not_contains`, `content_changed`, `command_output_contains` |
| Services | `service_running`, `service_enabled` |
| Network | `port_listening` |
| Users / groups | `user_exists`, `group_exists` |
| Commands | `command_succeeds` |

## Quick start

```python
from pathlib import Path
from runtime_skeleton.orchestrator.pipeline import run_pipeline
from aegis_test_generator.runner.testinfra_runner import TestinfraRunner

runner = TestinfraRunner(playbook_path=Path("examples/patch.yml"))

snapshot = run_pipeline(
    repo_root=Path(".").resolve(),
    input_path="examples/sample_input.json",
    runner=runner,
)

print(snapshot.diff.regression_detected)
print(snapshot.patch_verified)
```

## Sandbox pre-state (update/maintenance patches)

Add a `sandbox_state` section to your input JSON to simulate a real machine before testing:

```json
{
  "sandbox_state": {
    "profile": "ubuntu-lts",
    "packages": [
      {"name": "nginx", "version": "1.18.0"}
    ],
    "files": [
      {
        "path": "/etc/nginx/nginx.conf",
        "content": "worker_processes 1;\n",
        "mode": "0644",
        "owner": "root"
      }
    ]
  }
}
```

Or place a hand-crafted `inputs/sandbox_state.yml` Ansible playbook — it takes precedence over the parsed section.

## Image profiles

| Profile | Image | Notes |
|---|---|---|
| `minimal` | `python:3.12-slim-bookworm` | Default; Python pre-installed |
| `debian-full` | `debian:bookworm` | Python installed via bootstrap |
| `ubuntu-lts` | `ubuntu:22.04` | Python installed via bootstrap |
| `rhel-compat` | `rockylinux:9` | Python installed via bootstrap (`dnf`) |

Set `"profile": "<name>"` in `config/sandbox.json`. Any key from the profile can be overridden.

## Configuration

`config/sandbox.json` (optional, merged over defaults):

```json
{
  "profile": "ubuntu-lts",
  "container_name_prefix": "aegis-sandbox"
}
```

## Running tests

```bash
pytest tests/
```

All 278 tests run without Docker or a live OpenAI key.

## Improvement plan

See [`docs/improvement-plan-phases.md`](docs/improvement-plan-phases.md) for the active roadmap.

| Phase | Status |
|---|---|
| 1 — Pre-State Sandbox Infrastructure | ✅ Complete |
| 2 — Update-Focused Test Generation | ✅ Complete |
| 3 — Coverage Taxonomy and Documentation | ✅ Complete |
| 4 — Complete the Regression Component | ✅ Complete |

## Development log

See [`docs/project-log.md`](docs/project-log.md) for a full chronological record of all implementation work.
