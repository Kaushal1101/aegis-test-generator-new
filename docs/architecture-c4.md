# Aegis Architecture — C4 Diagrams

Structural view of the system at three levels of zoom: context (what the system is),
containers (the two packages and their external dependencies), and components (what
lives inside each package).

---

## Level 1 — System Context

Who uses Aegis, and what external systems does it depend on.

```mermaid
C4Context
    title Aegis Test Generator — System Context

    Person(devops, "DevOps / Patch Author", "Provides Ansible patch playbooks and optional diff and sensitivity reports")

    System(aegis, "Aegis Test Generator", "Generates infrastructure tests, runs them against a sandboxed machine, and reports whether the patch worked and introduced regressions")

    System_Ext(openai, "OpenAI API", "LLM endpoint used for test plan generation and regression exception classification")
    System_Ext(docker, "Docker", "Container runtime — hosts the sandboxed machine under test")
    System_Ext(ansible, "Ansible", "Applies the setup state and the patch inside the container")

    Rel(devops, aegis, "Provides input JSON: playbook, sandbox state, diff, sensitivity scores")
    Rel(aegis, openai, "Two LLM calls per run: DSPy test planner and exception classifier")
    Rel(aegis, docker, "Creates containers; runs pytest via --hosts=docker://")
    Rel(aegis, ansible, "Runs setup and patch playbooks inside the container")
    Rel(aegis, devops, "Returns markdown report: verdict, test results, coverage summary, regression severity")
```

---

## Level 2 — Containers

The two Python packages and how they divide responsibility.

```mermaid
C4Container
    title Aegis Test Generator — Containers

    Person(devops, "DevOps / Patch Author")

    System_Boundary(aegis, "Aegis Test Generator") {
        Container(atg, "aegis_test_generator", "Python package", "LLM planning, schema validation, Testinfra rendering, coverage taxonomy, regression analysis, reporting")
        Container(rs, "runtime_skeleton", "Python package", "Pipeline orchestration, sandbox lifecycle, input parsing, pre/post evaluation")
    }

    System_Ext(openai, "OpenAI API")
    System_Ext(docker, "Docker Daemon")
    System_Ext(ansible, "Ansible")

    Rel(devops, rs, "Calls run_pipeline() with input JSON path or dict")
    Rel(rs, atg, "Delegates test generation, phase execution, and reporting")
    Rel(atg, openai, "DSPy structured prediction and exception classification")
    Rel(rs, docker, "docker run / docker exec for container lifecycle and bootstrap")
    Rel(rs, ansible, "ansible-playbook for setup state and patch application")
    Rel(atg, docker, "pytest --hosts=docker://<container> for pre and post phases")
    Rel(rs, devops, "Returns PipelineSnapshot with all stage results")
    Rel(atg, devops, "Writes per-run markdown report to output path")
```

---

## Level 3 — Components: `aegis_test_generator`

The internal modules of the test generator package.

```mermaid
C4Component
    title aegis_test_generator — Components

    Container_Boundary(atg, "aegis_test_generator") {
        Component(generate, "Generate Facade", "generate.py", "Entry point: orchestrates planner → validate → render → guard sufficiency check")
        Component(intent, "Intent Classifier", "planner/intent.py", "Deterministic. Reads Ansible modules to classify patch as install / update / remove / configure / mixed")
        Component(planner, "LLM Planner", "planner/llm_planner.py + dspy_planner.py", "DSPy two-pass generate+review. Injects patch intent and diff-seeded priority targets into prompt context")
        Component(schemas, "Schema Validator", "test_templates/schemas.py", "Pydantic. Validates TestCase / TestPlan; auto-assigns coverage_category from test_type")
        Component(renderer, "Testinfra Renderer", "test_templates/renderer.py", "Fixed-template Python generation. Produces pytest module with one function per TestCase")
        Component(runner, "Testinfra Runner", "runner/testinfra_runner.py", "Executes generated pytest module against a Docker container via --hosts=docker://")
        Component(coverage, "Coverage Analyser", "coverage.py", "Deterministic. Counts verify/guard per category; flags blind spots based on patch intent")
        Component(regression, "Regression Analyser", "regression.py", "Deterministic. Severity scoring, guard sufficiency check, six-tier verdict computation")
        Component(classifier, "Exception Classifier", "classifier/llm_classifier.py", "LLM call. Labels each regressed transition as APPLICABLE / ENV_ARTIFACT / FLAKY / OUT_OF_SCOPE")
        Component(reporter, "Report Writer", "reporter.py", "Assembles markdown report: verdict, test tables, annotation badges, coverage summary, severity score")
    }

    System_Ext(openai, "OpenAI API")
    Container_Ext(rs, "runtime_skeleton")

    Rel(generate, intent, "Classifies patch intent for prompt context")
    Rel(generate, planner, "Drives two-pass LLM test plan generation")
    Rel(generate, schemas, "Validates and enriches plan rows")
    Rel(generate, renderer, "Renders validated plan to Testinfra module")
    Rel(generate, regression, "Runs guard sufficiency check; appends warnings")
    Rel(planner, openai, "DSPy generate and review passes")
    Rel(classifier, openai, "JSON-object completion for annotation_type")
    Rel(runner, rs, "Called by TestSuite component for pre and post phases")
    Rel(reporter, coverage, "Computes per-category verify/guard counts and gaps")
    Rel(reporter, regression, "Scores severity and computes six-tier verdict")
    Rel(reporter, classifier, "Reads classified_transitions from PipelineSnapshot")
    Rel(reporter, schemas, "Looks up TestCase by index from test_plan")
```

---

## Level 3 — Components: `runtime_skeleton`

The internal modules of the pipeline and sandbox package.

```mermaid
C4Component
    title runtime_skeleton — Components

    Container_Boundary(rs, "runtime_skeleton") {
        Component(pipeline, "Pipeline Orchestrator", "orchestrator/pipeline.py", "Coordinates all stages in order. Wires components together and writes to PipelineSnapshot")
        Component(input_comp, "Input Component", "input/", "Parses input JSON/YAML. Extracts patch, sandbox_state, diff, sensitivity_verdict, predicted_impact sections")
        Component(sandbox_comp, "Sandbox Component", "components/sandbox/core.py", "Creates Docker container; runs bootstrap commands; applies setup-state and patch playbooks via Ansible")
        Component(state_gen, "State Generator", "sandbox/state.py", "Converts sandbox_state dict to an Ansible setup playbook YAML")
        Component(config, "Sandbox Config", "sandbox/config.py", "Resolves image profile (minimal / debian-full / ubuntu-lts / rhel-compat) from sandbox.json")
        Component(testsuite, "TestSuite Component", "components/testsuite/", "Normalises pre and post check records returned by the runner into a common format")
        Component(evaluation, "Evaluation Component", "components/evaluation/core.py", "Deterministic. Classifies each pre-post transition: verified, regressed, fixed, still_pass, etc.")
        Component(contracts, "Contracts", "interfaces/contracts.py", "Shared dataclasses: PipelineSnapshot, EvaluationResult, SandboxResult, DiffResult, etc.")
    }

    System_Ext(docker, "Docker Daemon")
    System_Ext(ansible, "Ansible")
    Container_Ext(atg, "aegis_test_generator")

    Rel(pipeline, input_comp, "parse(input_path)")
    Rel(pipeline, sandbox_comp, "create(), apply_setup(), apply_patch()")
    Rel(pipeline, testsuite, "run() for pre and post phases")
    Rel(pipeline, evaluation, "evaluate(pre_checks, post_checks)")
    Rel(pipeline, atg, "Calls classifier.classify() if classifier provided")
    Rel(sandbox_comp, state_gen, "Generates setup playbook YAML from sandbox_state")
    Rel(sandbox_comp, config, "Resolves image and bootstrap_commands from profile")
    Rel(sandbox_comp, docker, "docker run, docker exec bootstrap commands")
    Rel(sandbox_comp, ansible, "ansible-playbook setup.yml and patch.yml")
    Rel(testsuite, atg, "Calls TestinfraRunner.run_phase() for check collection")
    Rel(evaluation, contracts, "Returns EvaluationResult with transitions and counts")
    Rel(pipeline, contracts, "Reads and writes PipelineSnapshot throughout")
```
