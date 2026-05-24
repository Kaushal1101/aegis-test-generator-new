# Evaluation Component Extraction

## What changed
- Added Evaluation contracts in `src/runtime_skeleton/interfaces/contracts.py`:
  - `EvaluationInput`
  - `EvaluationResult`
  - `EvaluationComponent`
- Added a new pure Evaluation component:
  - `src/runtime_skeleton/components/evaluation/core.py`
  - `src/runtime_skeleton/components/evaluation/__init__.py`
- Added `src/runtime_skeleton/components/__init__.py` to establish the components package.
- Kept backward compatibility in `src/runtime_skeleton/diff/compare.py` by delegating `compare_results(...)` to the new Evaluation component and returning `DiffResult`.
- Added transition and compatibility tests:
  - `tests/runtime_skeleton/components/test_evaluation.py`
  - `tests/runtime_skeleton/diff/test_compare_compat.py`

## Compatibility guarantees
- `runtime_skeleton.diff.compare_results` remains available and callable with the same signature.
- `runtime_skeleton.diff.__all__` remains unchanged.
- `compare_results` still returns `DiffResult` with existing fields:
  - `skipped`, `skip_reason`, `counts`, `net_change`, `regression_detected`,
    `regressed_count`, `fixed_count`, `transitions`.
- Transition naming and aggregate formulas are preserved.

## Files changed
- `src/runtime_skeleton/interfaces/contracts.py`
- `src/runtime_skeleton/interfaces/__init__.py`
- `src/runtime_skeleton/components/__init__.py`
- `src/runtime_skeleton/components/evaluation/core.py`
- `src/runtime_skeleton/components/evaluation/__init__.py`
- `src/runtime_skeleton/diff/compare.py`
- `tests/__init__.py`
- `tests/runtime_skeleton/components/test_evaluation.py`
- `tests/runtime_skeleton/diff/test_compare_compat.py`

## Follow-up tasks
- Optionally wire orchestrator/pipeline to a concrete `EvaluationComponent` instance directly (instead of `compare_results`) once broader component extraction is ready.
- Decide whether to gradually rename `DiffResult` usage sites to `EvaluationResult` where it improves readability.
- Add CI test invocation for the new tests if not already present.

