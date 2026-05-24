# Aegis Test Generator — Phased Improvement Plan

## Context Summary

The system currently:
- Runs a clean `python:3.12-slim-bookworm` container as its sandbox — no pre-existing state
- Generates tests skewed toward install-type assertions (`package_installed`, `file_exists`, `directory_exists`)
- Classifies tests in two roles: `verify` (did the patch do what it claims?) and `guard` (did it break anything?)
- Regression detection is purely binary — any guard `pass→fail` transition is a regression, with no severity weighting, exception handling, or coverage analysis

Three gaps to close:
1. Sandboxes need pre-existing state for update/maintenance scenarios
2. No coverage taxonomy or documentation exists
3. Regression component is incomplete (no severity, no exception handling, no coverage sufficiency)

---

## Phase 1 — Pre-State Sandbox Infrastructure

**Goal:** Make sandboxes simulate real enterprise machines — with files, packages, and configs already in place — so update patches are tested against a realistic "before" state.

### 1.1 Sandbox State Descriptor

Introduce a `sandbox_state` section in the input document (alongside the existing `patch` section). This declares what should be pre-installed before the pre-phase runs.

```yaml
# inputs/sandbox_state.yml  (or inline in input JSON)
packages:
  - name: nginx
    version: "1.18.0"
  - name: curl
files:
  - path: /etc/nginx/nginx.conf
    content: |
      worker_processes 1;
      ...
  - path: /opt/app/config.json
    content: '{"debug": false, "port": 8080}'
    mode: "0644"
    owner: root
services:
  - name: nginx
    state: started
    enabled: true
users:
  - name: appuser
    uid: 1001
```

This gets converted into an Ansible `setup_playbook.yml` that runs in the sandbox *before* the pre-phase tests execute — analogous to how `patch.yml` already works but for initialization.

### 1.2 Pipeline Extension

Add a `setup` step between sandbox creation and the pre-phase:

```
CREATE SANDBOX
    ↓
APPLY SETUP STATE  ← new
    ↓
PRE-PHASE TESTS
    ↓
APPLY PATCH
    ↓
POST-PHASE TESTS
    ↓
EVALUATE
```

In `pipeline.py`, this means calling `sandbox.apply_setup(context)` in addition to the existing `sandbox.apply_patch(context)`. The `apply_setup` method mirrors `apply_patch` — it writes a playbook, creates an inventory, and runs `ansible-playbook`.

### 1.3 Docker Image Variants

The current `python:3.12-slim-bookworm` is a minimal Debian image with no `systemd`, no service manager, and no `apt` pre-populated package index. Add configurable image variants:

| Profile | Image | When to Use |
|---|---|---|
| `minimal` | `python:3.12-slim-bookworm` (current) | Install-only patches |
| `debian-full` | `debian:bookworm` | File/config update patches |
| `ubuntu-lts` | `ubuntu:22.04` | Ubuntu enterprise machines |
| `rhel-compat` | `rockylinux:9` | RHEL/CentOS enterprise machines |

The `sandbox.json` config already accepts `image` — this just adds documented presets and a `profile` shorthand in the input document.

### 1.4 LLM Prompt Updates

The DSPy role rules in `dspy_planner.py` currently read:
> "Writes content to a file → verify, test_type=content_contains"

Update these to explicitly handle update scenarios:

```
- Modifies an existing file's content → verify, test_type=content_contains (new value)
  AND guard, test_type=content_not_contains (value that should have been removed)
- Changes a file's permissions → verify, test_type=file_mode
- Changes a file's owner → verify, test_type=file_owner
- Updates a package version → verify, test_type=package_version
- Restarts or reconfigures a service → verify, test_type=service_running
  AND guard, test_type=content_contains (existing unrelated config preserved)
```

The key shift: for update patches, the LLM should generate **paired tests** — one asserting the new state exists, one asserting the old state is gone.

**Deliverables:** `sandbox_state` input schema, `apply_setup()` in `DefaultSandboxComponent`, pipeline step, image profiles in `sandbox.json`, updated DSPy role rules.

---

## Phase 2 — Update-Focused Test Generation

**Goal:** Shift the test generation logic to produce higher-quality tests for edit/update patches specifically, rather than treat all patches as installation operations.

### 2.1 Patch Intent Classification

Before planning tests, classify the patch's intent. Add a lightweight pre-planning step that categorizes the playbook:

```python
class PatchIntent(str, Enum):
    INSTALL = "install"        # Net-new packages/files
    UPDATE = "update"          # Modifying existing files/packages
    REMOVE = "remove"          # Deleting packages/files
    CONFIGURE = "configure"    # Changing config files only
    MIXED = "mixed"            # Combination of above
```

This classification gets passed to the LLM planner as part of the prompt context, steering it toward the right test type distribution. A simple heuristic works for v1: if the playbook has `lineinfile`, `replace`, `blockinfile`, `template` with existing-file targets, or `copy` to paths that appear in the `diff.modified` list — classify as `update` or `configure`.

### 2.2 Update-Specific Test Type Additions

Add three new test types to `schemas.py` and `renderer.py`:

| New Type | Assertion | Use Case |
|---|---|---|
| `content_changed` | File content differs from `expected` baseline | Verify a file was actually modified |
| `file_mode_changed` | Mode differs from `expected_before`, matches `expected_after` | Permissions update |
| `package_version_range` | Version satisfies semver constraint (e.g., `>=2.0,<3.0`) | Version bump patches |

`content_changed` in particular is useful for update patches: the pre-phase captures the original content hash, and the post-phase verifies it changed. This is a structural difference from `content_contains`, which only checks a substring exists.

### 2.3 Diff-Seeded Test Generation

When `diff.modified` paths are present in the input document, seed the LLM with specific file paths and their change context so it generates targeted assertions rather than generic ones. Pass the sensitivity scores from `sensitivity_verdict` to weight which files to prioritize for test generation.

**Deliverables:** `PatchIntent` classifier, three new test types with schemas + renderers, diff-seeded prompt context, updated `GeneratePlanSignature` in `dspy_planner.py`.

---

## Phase 3 — Coverage Taxonomy and Documentation

**Goal:** Give every generated test a coverage category, produce a per-run coverage report, and document the system's known strengths and weaknesses.

### 3.1 Coverage Taxonomy

Define a fixed set of coverage categories:

| Category | Test Types Included | What It Covers |
|---|---|---|
| `package_integrity` | `package_installed`, `package_absent`, `package_version`, `package_version_range` | Software inventory |
| `file_integrity` | `file_exists`, `file_absent`, `file_mode`, `file_owner`, `symlink_exists`, `binary_executable` | File system state |
| `file_content` | `content_contains`, `content_not_contains`, `content_changed`, `command_output_contains` | Configuration correctness |
| `service_state` | `service_running`, `service_enabled` | Daemon/process lifecycle |
| `network_posture` | `port_listening` | Exposed ports |
| `identity` | `user_exists`, `group_exists` | Users and groups |
| `command_behavior` | `command_succeeds`, `command_output_contains` | Script/binary execution |

### 3.2 Schema Extension

Add `coverage_category` to `TestCase`:

```python
class TestCase(BaseModel):
    test_type: str
    target: str
    expected: str | int | bool | None = None
    reason: str | None = None
    role: Literal["guard", "verify"] = "guard"
    coverage_category: CoverageCategory | None = None  # auto-assigned if None
```

Auto-assign from `test_type` in `validate_plan()` — the mapping is deterministic so the LLM doesn't need to set it. The LLM can optionally override for edge cases (e.g., a `command_succeeds` test that's really checking service state).

### 3.3 Coverage Report

Add a coverage summary block to the existing markdown report:

```markdown
## Coverage Summary

| Category | Verify Tests | Guard Tests | Total |
|---|---|---|---|
| file_content | 3 | 1 | 4 |
| package_integrity | 1 | 2 | 3 |
| service_state | 1 | 0 | 1 |
| network_posture | 0 | 0 | 0 ⚠️ |
| identity | 0 | 0 | 0 ⚠️ |

⚠️ Categories with no coverage may indicate blind spots for this patch type.
```

The `⚠️` flag appears when a category relevant to the patch's intent has zero tests. The relevance mapping (e.g., "configure patches should always have file_content tests") is a small static table.

### 3.4 System-Level Coverage Documentation

Produce a `docs/coverage-reference.md` that documents:

- **Strengths:** What the system tests well (package management, file existence, config content)
- **Known gaps:** What it cannot currently test (network connectivity between containers, database state, application-level behavior, Windows targets)
- **Test type reference:** Each of the 19 (+ 3 new) types with description, typical use case, and example
- **Coverage category matrix:** Which enterprise patch scenarios each category addresses

**Deliverables:** `CoverageCategory` enum, auto-assignment in `validate_plan()`, coverage block in `reporter.py`, `docs/coverage-reference.md`.

---

## Phase 4 — Complete the Regression Component

**Goal:** Move from binary pass/fail regression detection to severity-weighted, exception-aware, coverage-informed regression analysis.

### 4.1 Exception Classification (planned v2 feature)

After evaluation, an LLM classifier reviews each `regressed` or `new_fail` transition and annotates it as:

```python
class TransitionAnnotation(str, Enum):
    APPLICABLE = "applicable"            # Real regression, counts against score
    ENV_ARTIFACT = "env_artifact"        # Docker environment limitation, not a real regression
    FLAKY = "flaky"                      # Known unstable test
    OUT_OF_SCOPE = "out_of_scope"        # Unrelated to this patch's risk surface
```

Only `APPLICABLE` transitions increment `regressed_count`. The others are preserved in the report but don't affect the verdict.

The LLM receives: the transition details, the patch's `predicted_impact` and `sensitivity_verdict`, and the sandbox environment descriptor — enough context to make a reasonable call.

### 4.2 Severity-Weighted Regression Scoring

Currently `regression_detected = regressed_count > 0` — one low-risk regression and one critical regression are treated identically.

Add a `regression_severity_score` to `EvaluationResult`:

```python
@dataclass
class EvaluationResult:
    ...
    regression_severity_score: float   # 0.0–1.0, weighted sum
    regression_severity: Literal["none", "low", "medium", "high", "critical"]
```

Score is computed as:
- Each applicable regression contributes its `sensitivity_score` (from `sensitivity_verdict.scored_files`) if the test's target maps to a scored file
- Tests with no sensitivity score contribute a flat 0.3
- Sum is normalized and bucketed into severity tiers

This means a regression in `/etc/nginx/nginx.conf` (high sensitivity) triggers `high` severity, while a regression in `/tmp/scratch` (low sensitivity) stays `low`.

### 4.3 Guard Coverage Sufficiency Check

For each file in `diff.modified` with a sensitivity score above 0.5, verify that at least one guard test covers a file or package that file depends on or interacts with (using the `predicted_impact` list as a proxy for the dependency surface).

If a high-sensitivity modified file has zero guard tests covering its neighborhood, emit a `CoverageWarning` in the `GenerateResult.warnings` list. This surfaces in the report as:

```
⚠️ Coverage Warning: /etc/app/settings.conf (sensitivity: 0.87) has no guard tests
   covering its dependency surface. Consider adding guard tests for: nginx, port 443.
```

### 4.4 Verdict Expansion

Current verdicts: `PASS`, `FAIL`, `PARTIAL`. Expand to carry severity:

| Verdict | Condition |
|---|---|
| `PASS` | All verify tests pass, zero applicable regressions |
| `PASS_WITH_WARNINGS` | All verify tests pass, zero applicable regressions, but coverage gaps exist |
| `PARTIAL_LOW` | Verify pass, low-severity regressions only |
| `PARTIAL_HIGH` | Verify pass, medium/high/critical regressions |
| `FAIL_VERIFY` | One or more verify tests failed, no regressions |
| `FAIL_BOTH` | Verify failures AND regressions |

**Deliverables:** LLM exception classifier in `evaluation/core.py`, `regression_severity_score` in `EvaluationResult`, coverage sufficiency check in `generate.py`, expanded verdict table in `reporter.py`.

---

## Dependency Order

```
Phase 1 (sandbox pre-state)
    ↓
Phase 2 (update-focused generation) — depends on Phase 1 image profiles and intent classifier
    ↓
Phase 3 (coverage taxonomy) — independent, can start in parallel with Phase 2
    ↓
Phase 4 (regression completion) — depends on Phase 3 categories for sufficiency check,
                                   and Phase 2 test types for accurate severity mapping
```

Phases 2 and 3 can run in parallel once Phase 1 is done.
