# Input Component Extraction

## What changed
- Added Input contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `InputRequest`
  - `InputResult`
  - `InputComponent`
- Exported Input contracts from `src/runtime_skeleton/interfaces/__init__.py`.
- Added a new deterministic Input component:
  - `src/runtime_skeleton/components/input/core.py`
  - `src/runtime_skeleton/components/input/__init__.py`
- Kept backward compatibility in `src/runtime_skeleton/input/parser.py` by delegating `parse_input(...)` to the new Input component and returning `ParsedInputResult`.
- Added focused Input and compatibility tests:
  - `tests/runtime_skeleton/components/test_input.py`
  - `tests/runtime_skeleton/input/test_parse_input_compat.py`

## Compatibility guarantees
- `runtime_skeleton.input.parse_input` remains available and callable with the same signature.
- `runtime_skeleton.input.__all__` remains unchanged.
- `parse_input` still returns `ParsedInputResult` with existing fields:
  - `parsed`, `derived`, `warnings`, `error`.
- Existing parse behavior is preserved:
  - `input_json` precedence over `input_path`
  - schema validation and unsupported `schema_version` checks
  - `meta.sections_present` warning behavior
  - derived signal computation for sensitivity and predicted/materialized deltas

## Files changed
- `src/runtime_skeleton/interfaces/contracts.py`
- `src/runtime_skeleton/interfaces/__init__.py`
- `src/runtime_skeleton/components/input/core.py`
- `src/runtime_skeleton/components/input/__init__.py`
- `src/runtime_skeleton/input/parser.py`
- `tests/runtime_skeleton/components/test_input.py`
- `tests/runtime_skeleton/input/test_parse_input_compat.py`

## Follow-up tasks
- Optionally wire orchestrator/pipeline to an `InputComponent` instance directly once broader component extraction is staged.
- Decide whether to converge `ParsedInputResult` and `InputResult` into a single public type after downstream callers migrate.
- Add broader integration tests that exercise input file loading via pipeline entrypoints.
