Improvement Plan — v1
=====================

Three improvements to test relevance and regression coverage, in implementation
order. All changes stay within existing components. No new components are introduced.


-------------------------------------------------------------------------------
CURRENT STATE
-------------------------------------------------------------------------------

Pipeline sequence:

    Input JSON
        │
        ▼
    parse_input()          ← produces ParsedInputResult (parsed, derived, warnings)
        │
        ▼
    TestSuite pre-phase    ← runner.run_phase("pre", {})
        │                     returns [] — nothing to run before patch
        ▼
    Sandbox: create container
        │
        ▼
    Sandbox: apply_patch
        │
        ▼
    TestSuite post-phase   ← runner.run_phase("post", { sandbox: SandboxResult })
        │                     calls generate_tests(playbook_path)
        │                         LLM sees: playbook YAML only
        │                     renders test module
        │                     runs pytest against container
        │                     returns CheckRecords
        ▼
    Evaluation             ← compare pre vs post check records
        │
        ▼
    PipelineSnapshot

The LLM only ever sees the raw Ansible YAML. It has no knowledge of which files
actually changed (diff), which files are high-risk (sensitivity_verdict), or which
files the system predicted would be affected (predicted_impact). These fields already
exist in the input JSON but are never forwarded to the planner.

The prompt does not ask for negative tests (tests that verify unchanged files were
not disturbed, or that removed items are truly gone).

There is no quality gate: the LLM's first response is used as-is.


-------------------------------------------------------------------------------
IMPROVEMENT 1 — Feed full input context to the planner
-------------------------------------------------------------------------------

Goal: The LLM should know what actually changed, at what risk level, and what files
were expected to be touched, so it generates tests that are targeted rather than
generic.

What is added to the prompt
  - diff.added:      list of file paths that should now exist
  - diff.modified:   list of file paths whose content changed
  - diff.removed:    list of file paths that should no longer exist
  - sensitivity_verdict.scored_files: path + risk score for each assessed file
  - predicted_impact.files: paths the system predicted the patch would affect

How data flows — before vs after:

  BEFORE

    orchestrator/pipeline.py
        run_pipeline()
            phase_context = { "sandbox": SandboxResult }
                │
                ▼
        TestinfraRunner.run_phase("post", phase_context)
            generate_tests(playbook_path)           ← no input context
                plan_from_playbook(playbook_path)   ← sees playbook YAML only
                    _build_messages(playbook_text)

  AFTER

    orchestrator/pipeline.py
        run_pipeline()
            phase_context = { "sandbox": SandboxResult,
                              "input":  parsed.parsed }    ← NEW: full input doc
                │
                ▼
        TestinfraRunner.run_phase("post", phase_context)
            input_context = phase_context.get("input")     ← NEW: extracted here
            generate_tests(playbook_path,
                           input_context=input_context)    ← NEW: passed through
                plan_from_playbook(playbook_path,
                                   input_context=...)      ← NEW: accepted here
                    _build_messages(playbook_text,
                                    input_context)         ← NEW: enriches prompt

Architecture diagram (after Improvement 1):

    Input JSON
        │
        ▼
    parse_input()
        │   parsed.parsed now forwarded into phase_context["input"]
        │
        ▼
    TestSuite pre-phase
        │   phase_context = { "input": parsed.parsed }
        │   runner.run_phase("pre", phase_context)  → []
        ▼
    Sandbox: create + apply_patch
        │
        ▼
    TestSuite post-phase
        │   phase_context = { "sandbox": SandboxResult,
        │                      "input":  parsed.parsed }
        │   runner.run_phase("post", phase_context)
        │       generate_tests(playbook_path, input_context=parsed.parsed)
        │           LLM sees: playbook YAML
        │                   + diff (added / modified / removed)
        │                   + sensitivity scores
        │                   + predicted impact files
        ▼
    Evaluation
        │
        ▼
    PipelineSnapshot

Files touched
  - src/runtime_skeleton/orchestrator/pipeline.py
      _normalize_phase(): already passes phase_context; add "input" key when
      calling the post phase.
      run_pipeline(): pass parsed.parsed into phase_context for both pre and
      post calls.

  - aegis_test_generator/runner/testinfra_runner.py
      run_phase(): extract context.get("input") and pass as input_context to
      _generate().
      _generate(): forward input_context to generate_tests().

  - aegis_test_generator/generate.py
      generate_tests(): add input_context parameter, forward to
      plan_from_playbook().

  - aegis_test_generator/planner/llm_planner.py
      plan_from_playbook(): add input_context parameter, forward to
      _build_messages().
      _build_messages(): add a new section to the prompt that summarises diff,
      sensitivity, and predicted impact.
      _summarise_input_context(): new helper that extracts the relevant fields
      into a compact text block for the prompt.

No contract changes needed. phase_context is already dict[str, Any].


-------------------------------------------------------------------------------
IMPROVEMENT 2 — Negative / regression guard tests
-------------------------------------------------------------------------------

Goal: The pipeline must verify that things the patch removed are truly gone, and
that high-sensitivity files outside the predicted impact set were not accidentally
touched. This is the core of regression detection.

This improvement builds directly on Improvement 1. The diff.removed list and
sensitivity_verdict.scored_files are only available to the prompt after Improvement 1
is implemented.

What changes in the prompt
  The prompt gains three explicit additional instructions:

    1. For each path in diff.removed: generate a file_absent or package_absent test
       to confirm it is gone after the patch.

    2. For each path in diff.added: confirm at least one presence check exists
       (file_exists, directory_exists, or package_installed as appropriate).

    3. For each file in sensitivity_verdict.scored_files that does NOT appear in
       predicted_impact.files: generate a content_not_contains or file_exists check
       to confirm the file was not unintentionally modified. These are the
       "bystander" files — high-risk and not supposed to change.

Example (complex_input.json run, after this improvement)
  diff.removed is empty in the complex example, so no absence tests fire.
  sensitivity_verdict.scored_files: /opt/aegis/config.conf (0.4), /usr/bin/git (0.2)
  predicted_impact.files: /opt/aegis/config.conf, /opt/aegis, /usr/bin/git, /usr/bin/curl
  Since both scored files appear in predicted_impact, no bystander tests fire here.
  A more interesting case is when scored_files contains paths NOT in predicted_impact.

Files touched
  - aegis_test_generator/planner/llm_planner.py
      _build_messages() / _summarise_input_context(): extend the prompt section
      added in Improvement 1 to include the three explicit guard instructions.

  No other files change for this improvement. It is purely a prompt extension.

Architecture impact: none. Same data path as Improvement 1.


-------------------------------------------------------------------------------
IMPROVEMENT 3 — Two-stage LLM self-review
-------------------------------------------------------------------------------

Goal: The LLM's first response sometimes includes hallucinated paths, redundant
checks, or tests for files that the playbook never touches. A second LLM call reviews
the initial plan and filters it before rendering.

This improvement is standalone — it does not depend on Improvements 1 or 2, but it
becomes more effective with the richer context those provide.

Flow — before vs after:

  BEFORE

    plan_from_playbook()
        _call_openai(messages)     ← one API call
        _extract_plan_rows(raw)
        return PlannerResult(tests=rows)

  AFTER

    plan_from_playbook(..., review=True)
        _call_openai(messages)               ← first API call: generate plan
        _extract_plan_rows(raw)
        _review_plan(rows, playbook_text,    ← second API call: filter plan
                     diff_summary, client, model)
        _extract_plan_rows(reviewed_raw)
        return PlannerResult(tests=reviewed_rows,
                             warnings=[...original warnings + review warnings...])

The review prompt is different from the generation prompt:

  System:
    "You are a test plan reviewer. You will be given an Ansible playbook, a diff
     summary, and a proposed list of Testinfra checks. Your job is to remove any
     checks that do not correspond to an actual action in the playbook or a file
     in the diff. You may also add missing checks for actions in the playbook that
     have no corresponding test. Return the filtered/extended list in the same JSON
     format: {\"tests\": [...]}."

  User:
    Playbook YAML (same as before)
    Diff summary (if available from input_context)
    Proposed tests (from the first call)

Architecture diagram (after all 3 improvements):

    Input JSON
        │
        ▼
    parse_input()
        │   parsed.parsed forwarded into phase_context["input"]
        │
        ▼
    TestSuite pre-phase
        │   runner.run_phase("pre", phase_context)  → []
        ▼
    Sandbox: create + apply_patch
        │
        ▼
    TestSuite post-phase
        │   runner.run_phase("post", phase_context)
        │       generate_tests(playbook_path, input_context=..., review=True)
        │           plan_from_playbook(...)
        │               [Call 1] LLM: playbook + diff + sensitivity → initial plan
        │               [Call 2] LLM: initial plan + playbook + diff → filtered plan
        │           validate_plan(filtered rows)
        │           render_plan(validated plan)
        │       pytest against container
        │       return CheckRecords
        ▼
    Evaluation
        │
        ▼
    PipelineSnapshot

Files touched
  - aegis_test_generator/planner/llm_planner.py
      plan_from_playbook(): add review: bool = True parameter.
      _review_plan(): new helper, second API call with reviewer prompt.
      _build_review_messages(): new helper, builds the reviewer prompt from
      the initial rows, playbook text, and optional diff summary.

  - aegis_test_generator/generate.py
      generate_tests(): forward review flag to plan_from_playbook().

  - aegis_test_generator/runner/testinfra_runner.py
      TestinfraRunner: add review: bool = True field, forward to generate_tests().

  No contract changes needed.


-------------------------------------------------------------------------------
COMPONENT MAP — what changes and what stays the same
-------------------------------------------------------------------------------

Component             Changes?   Why
--------------------  ---------  -----------------------------------------------
Input                 No         parse_input() output is unchanged; we only
                                 forward parsed.parsed downstream.
Sandbox               No         Unchanged.
TestSuite             No         Already passes phase_context as dict; no
                                 protocol change needed.
Evaluation            No         Compares check records; unaffected.
ThinOrchestrator      Small      pipeline.py adds "input" key to phase_context
                                 when calling post-phase normalization.
Contracts             No         phase_context is dict[str, Any]; no new fields
                                 on any dataclass.
--------------------  ---------  -----------------------------------------------
aegis_test_generator
  runner              Small      testinfra_runner.py reads input_context from
                                 phase_context and forwards it.
  generate.py         Small      New input_context and review parameters, forwarded.
  planner             Medium     Main work: enriched prompt, _summarise_input_context
                                 helper, _review_plan second call, review flag.
  test_templates      No         Renderer and schemas are unchanged.
--------------------  ---------  -----------------------------------------------


-------------------------------------------------------------------------------
IMPLEMENTATION ORDER
-------------------------------------------------------------------------------

Phase A: Context enrichment (Improvements 1 + 2 together)
  These are implemented in the same pass because Improvement 2's prompt changes are
  meaningless without the context data from Improvement 1. Both touch the same
  _build_messages() function.

  Deliverables:
    - llm_planner.py: input_context parameter, _summarise_input_context(), updated
      prompt with diff summary and guard instructions.
    - generate.py: input_context parameter.
    - testinfra_runner.py: extract input_context from phase_context, pass through.
    - orchestrator/pipeline.py: add "input": parsed.parsed to phase_context.
    - Updated tests for all four files.

Phase B: Self-review pass (Improvement 3)
  Standalone. Can be implemented after Phase A or independently.

  Deliverables:
    - llm_planner.py: review parameter, _review_plan(), _build_review_messages().
    - generate.py: review parameter forwarded.
    - testinfra_runner.py: review field, forwarded.
    - Updated tests (mock the second API call separately).


-------------------------------------------------------------------------------
RISKS AND NOTES
-------------------------------------------------------------------------------

- The review pass (Phase B) doubles API call cost for every pipeline run. Gate it
  behind review=True (default on) so callers can disable it when quota is tight.

- _summarise_input_context() should cap output size: if diff.added has hundreds of
  files, truncate to the top N by sensitivity score. Avoid blowing the context window.

- The prompt additions must be clearly delimited so the LLM does not confuse the
  diff summary with the playbook YAML. Use labelled sections:
    PLAYBOOK: ...
    DIFF SUMMARY: ...
    SENSITIVITY: ...

- Backward compatibility: all new parameters (input_context, review) have safe
  defaults (None, True). Callers that do not pass them get the same behaviour as
  today, minus the improvements.

- See docs/future-enhancements.md for the functional command_succeeds improvement
  that was deferred until the review pass is in place.
