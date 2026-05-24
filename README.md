# Runtime Skeleton

Barebones foundation extracted from `aegis-test-generator` to support a cleaner architecture rebuild.

## Project Context

`runtime_skeleton` belongs to the `aegis-test-generator` repository.
The main repository currently contains a larger runtime pipeline with framework-specific integrations.
This folder is a parallel, intentionally minimal baseline that keeps only core pipeline concerns:
input parsing, sandbox lifecycle, patch apply flow, and pre/post diffing.

If you are new to this repo, think of `runtime_skeleton` as a clean reference architecture you can
extend safely, without inheriting the full complexity of the production runtime path.

## Included Components

- `input/`: parse and validate analyzer input, derive compact signals.
- `sandbox/`: Docker sandbox creation and patch application surface.
- `diff/`: generic pre/post check comparison engine.
- `orchestrator/`: thin flow that wires `parse -> sandbox -> patch -> diff`.
- `interfaces/`: minimal contracts for component boundaries.
- `io/`: optional artifact writing helpers.

## Explicitly Excluded

This skeleton intentionally excludes framework-specific and test-execution subsystems:

- InSpec adapters and runners
- testinfra generation/validation/execution
- goss code paths
- LLM planning/integration
- retrieval/index/scraper subsystems

## Folder Layout

```text
runtime_skeleton/
  README.md
  pyproject.toml
  src/runtime_skeleton/
    interfaces/
    input/
    sandbox/
    diff/
    io/
    orchestrator/
  examples/
    sample_input.json
    patch.yml
```

## Quick Start

```python
from pathlib import Path
from runtime_skeleton import run_pipeline

snapshot = run_pipeline(
    repo_root=Path(".").resolve(),
    input_path="runtime_skeleton/examples/sample_input.json",
    pre_checks=[{"suite_id": "svc", "check_id": "nginx", "status": "pass"}],
    post_checks=[{"suite_id": "svc", "check_id": "nginx", "status": "fail"}],
    skip_sandbox=True,
    skip_patch_apply=True,
)
print(snapshot.diff.regression_detected)
```

## Extension Seams

- Add framework runners behind `interfaces/contracts.py`.
- Replace patch executor in `sandbox/patch.py` without changing orchestrator flow.
- Plug a richer orchestrator engine (graph/workflow) into `orchestrator/pipeline.py`.
- Expand diff severity/metadata logic in `diff/compare.py`.

See `runtime_skeleton/CONTEXT.md` for a short explanation of where this fits in the wider project.
