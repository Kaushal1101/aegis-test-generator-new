# Sandbox Component Extraction

## What changed
- Added Sandbox contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `SandboxCreateRequest`
  - `PatchApplyRequest`
  - `SandboxComponent`
- Exported Sandbox contracts from `src/runtime_skeleton/interfaces/__init__.py`.
- Added a new Sandbox component:
  - `src/runtime_skeleton/components/sandbox/core.py`
  - `src/runtime_skeleton/components/sandbox/__init__.py`
- Kept backward compatibility in legacy sandbox APIs by delegating:
  - `src/runtime_skeleton/sandbox/create.py` delegates `create_sandbox(...)` to component helper.
  - `src/runtime_skeleton/sandbox/patch.py` delegates `apply_patch(...)` to component helper.
- Added focused Sandbox and compatibility tests:
  - `tests/runtime_skeleton/components/test_sandbox.py`
  - `tests/runtime_skeleton/sandbox/test_sandbox_compat.py`
- Added direct utility tests for sandbox legacy helpers:
  - `tests/runtime_skeleton/sandbox/test_config.py`
  - `tests/runtime_skeleton/sandbox/test_playbook.py`
  - Expanded `tests/runtime_skeleton/sandbox/test_sandbox_compat.py` to cover public `load_sandbox_config` and `resolve_playbook_yaml` entrypoint stability.

## Compatibility guarantees
- `runtime_skeleton.sandbox.create_sandbox` remains available and callable with the same signature.
- `runtime_skeleton.sandbox.apply_patch` remains available and callable with the same signature.
- Existing output dataclasses remain unchanged:
  - `SandboxResult`
  - `PatchApplyResult`
- Existing behavior semantics are preserved:
  - skip handling and skip reasons
  - docker/ansible error mapping
  - container-name sanitization
  - patch source precedence (`inputs/patch.yml` over parsed patch section)
  - deterministic patch artifacts under `runtime_skeleton/artifacts/patch/`

## Files changed
- `src/runtime_skeleton/interfaces/contracts.py`
- `src/runtime_skeleton/interfaces/__init__.py`
- `src/runtime_skeleton/components/sandbox/core.py`
- `src/runtime_skeleton/components/sandbox/__init__.py`
- `src/runtime_skeleton/sandbox/create.py`
- `src/runtime_skeleton/sandbox/patch.py`
- `tests/runtime_skeleton/components/test_sandbox.py`
- `tests/runtime_skeleton/sandbox/test_sandbox_compat.py`

## Follow-up tasks
- Optionally inject a `SandboxComponent` instance into orchestrator pipeline wiring to reduce direct function-level coupling in future extractions.
- Add pipeline-level sandbox wiring tests once TestSuite component extraction is staged.
