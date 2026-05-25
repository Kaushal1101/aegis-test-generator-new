# Aegis Architecture — Flow Diagrams

Behavioral view of the system: how a pipeline run executes from start to finish,
and how a patch playbook becomes a typed test plan.

---

## Pipeline Execution Sequence

The full lifecycle of one `run_pipeline()` call, showing which component handles each
stage and the two optional LLM calls (test planning and exception classification).

```mermaid
sequenceDiagram
    actor Dev as DevOps Engineer
    participant PL as Pipeline Orchestrator
    participant IN as Input Component
    participant SB as Sandbox Component
    participant PL2 as LLM Planner
    participant OA as OpenAI API
    participant RN as Testinfra Runner
    participant EV as Evaluation Component
    participant CL as Exception Classifier
    participant RP as Report Writer

    Dev->>PL: run_pipeline(input_path, runner)

    PL->>IN: parse(input_path)
    IN-->>PL: ParsedInputResult

    PL->>SB: create(run_id)
    SB-->>PL: SandboxResult (container running)

    PL->>SB: apply_setup(sandbox_state)
    Note over SB: Runs Ansible setup playbook<br/>Pre-populates packages, files, services
    SB-->>PL: SetupApplyResult

    PL->>PL2: generate_tests(playbook, input_context)
    PL2->>OA: DSPy generate pass
    OA-->>PL2: raw test cases
    PL2->>OA: DSPy review pass
    OA-->>PL2: reviewed and validated plan
    PL2-->>PL: GenerateResult (TestPlan + warnings)

    PL->>RN: run_phase("pre", context)
    Note over RN: pytest --hosts=docker://<container>
    RN-->>PL: pre_checks

    PL->>SB: apply_patch(patch_section)
    Note over SB: Runs Ansible patch playbook<br/>Modifies machine state
    SB-->>PL: PatchApplyResult

    PL->>RN: run_phase("post", context)
    RN-->>PL: post_checks

    PL->>EV: evaluate(pre_checks, post_checks)
    Note over EV: Classifies each transition:<br/>verified / regressed / fixed / still_pass / etc.
    EV-->>PL: EvaluationResult

    opt classifier provided
        PL->>CL: classify(transitions, parsed_input)
        CL->>OA: annotation request per regression
        OA-->>CL: APPLICABLE / ENV_ARTIFACT / FLAKY / OUT_OF_SCOPE
        CL-->>PL: ClassifierResult (annotations)
    end

    PL-->>Dev: PipelineSnapshot

    Dev->>RP: write_run_report(snap, runner, output_path)
    Note over RP: Computes severity score,<br/>six-tier verdict, coverage summary
    RP-->>Dev: markdown report
```

---

## Test Generation Decision Flow

How a patch playbook becomes a validated, typed test plan. Deterministic stages are
marked; LLM calls are the two DSPy passes in the middle.

```mermaid
flowchart TD
    A([Input JSON\nplaybook + diff + sandbox_state]) --> B[Intent Classifier\ndeterministic]

    B --> C{Patch intent?}
    C -- install --> D1[Steer LLM toward\npackage_installed\nfile_exists\ndirectory_exists]
    C -- update --> D2[Steer LLM toward\ncontent_contains + content_not_contains\ncontent_changed\npackage_version_range]
    C -- configure --> D3[Steer LLM toward\ncontent_contains\nfile_mode\nfile_owner]
    C -- remove --> D4[Steer LLM toward\npackage_absent\nfile_absent]
    C -- mixed --> D5[Steer LLM toward\ncombination of all types]

    D1 & D2 & D3 & D4 & D5 --> E[Build DSPy context summary\ndeterministic\n— patch intent header\n— priority targets from diff.modified\n— HIGH RISK flag for sensitivity ≥ 0.5]

    E --> F[DSPy Generate Pass\nLLM call]
    F --> G[Raw test cases\nrole = verify or guard\ntest_type, target, expected, reason]

    G --> H[DSPy Review Pass\nLLM call]
    H --> I[Reviewed test cases\nDrops invalid types\nEnsures paired tests for update patches]

    I --> J[Schema Validation\nPydantic — deterministic]
    J --> K[Shape checks\ndeterministic]
    K -- missing expected,\nduplicate targets, etc. --> L[Drop row + emit warning]
    K -- valid --> M[TestPlan\nwith coverage_category auto-assigned]

    M --> N[Guard Sufficiency Check\ndeterministic]
    N -- high-sensitivity file\nhas no guard coverage --> O[Append warning\nto GenerateResult]
    N -- covered --> P[Testinfra Renderer\ndeterministic fixed templates]
    O --> P

    P --> Q([Generated pytest module\nready to run])
```
