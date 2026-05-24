# Context for `runtime_skeleton`

## What this is

`runtime_skeleton` is a stripped-down architecture scaffold extracted from the larger
`aegis-test-generator` project. It exists as a parallel package in the same repository.

## Why it exists

The main project includes runtime orchestration plus framework-specific execution paths.
That makes experimentation harder when you want to redesign architecture boundaries.

This skeleton provides a smaller base focused on:

- input parsing and derived signals
- sandbox creation and patch application
- generic pre/post diffing
- a thin orchestrator API

## What it is not

- It is not the production runtime path.
- It intentionally excludes framework/test execution systems (InSpec, testinfra, goss, LLM planning).
- It is not feature-complete.

## How to use it

Use `runtime_skeleton` as a starting point for architectural iterations:

1. evolve component boundaries and contracts under `src/runtime_skeleton/`
2. add extension components (for example a new `testing/` package) behind interfaces
3. keep orchestration thin and compose behavior from component APIs

Once stable, patterns from this skeleton can be ported into the main runtime implementation.
