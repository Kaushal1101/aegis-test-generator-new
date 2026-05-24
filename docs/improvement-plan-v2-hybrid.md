Improvement Plan — v2 (Hybrid Pre/Post + Explicit Exception Reporting)
=======================================================================

Goal
----

Upgrade regression evidence quality by running generated Testinfra checks in both
pre and post phases, then explicitly annotate non-applicable transitions (instead
of silently dropping them) using a dedicated LLM classifier step.

Design principles
-----------------

- Keep canonical ordering: pre evidence -> patch apply -> post evidence -> evaluation.
- Do not move patch ownership out of Sandbox.
- Keep Evaluation deterministic and unchanged for base transition math.
- Explicitly report exception annotations; do not hide raw transitions.

Target architecture
-------------------

    Input parse
      -> Sandbox create (before pre runner)
      -> TestSuite pre (runner executes generated checks on clean container)
      -> Sandbox apply_patch
      -> TestSuite post (runner executes same generated checks on patched container)
      -> Evaluation compare(pre, post)
      -> Exception classifier annotate transitions (optional)
      -> PipelineSnapshot(raw transitions + annotated transitions)

Key implementation decision
---------------------------

Generate once, run twice:

- TestinfraRunner will generate/render tests in pre (or lazily on first phase call),
  cache the generated file path on the runner instance, and reuse the exact same
  test module in post.
- This stabilizes pytest nodeids/check_ids across phases and improves diff quality.

Phase 1 scope (pipeline + runner)
---------------------------------

1) Reorder orchestration in `src/runtime_skeleton/orchestrator/pipeline.py`:
   - Create sandbox before pre normalization when parsed input is valid.
   - Pass `{"sandbox": sandbox, "input": parsed.parsed}` to both pre and post
     in-process phases.
   - Keep parse-error branch non-destructive.

2) Update `aegis_test_generator/runner/testinfra_runner.py`:
   - Pre phase now executes pytest (not `[]`).
   - Cache generated module path to reuse in post.
   - Keep all failure handling and status mapping behavior.

Phase 2 scope (exception classifier)
------------------------------------

1) Add classifier package:
   - `aegis_test_generator/classifier/__init__.py`
   - `aegis_test_generator/classifier/llm_classifier.py`

2) Classifier contract/result:
   - Add `ExceptionClassifier` protocol in contracts.
   - Add `ClassifierResult` dataclass in contracts.
   - Add `PipelineSnapshot.classified_transitions: list[dict[str, Any]]`.

3) Orchestrator wiring:
   - Add optional `classifier: ExceptionClassifier | None = None` parameter to
     `run_pipeline`.
   - After Evaluation, call classifier (if provided) and populate
     `snapshot.classified_transitions`.
   - Keep `snapshot.diff.transitions` intact as raw baseline output.

Classifier behavior
-------------------

Inputs:
- evaluation transitions
- playbook text (from parsed input)
- parsed input context (diff/sensitivity/predicted impact)

Output:
- one annotation per transition/check_id:
  - `applicable: bool`
  - `reason: str`

Important:
- Annotation is additive, never destructive.
- If classifier fails, pipeline still returns raw diff transitions.

Testing strategy
----------------

- Runner tests:
  - pre phase executes and returns mapped rows.
  - generate called once across pre+post reuse.
- Pipeline tests:
  - pre phase sees sandbox in context for in-process runs.
  - ordering remains pre -> apply_patch -> post.
  - classifier path fills `classified_transitions`.
  - classifier failures emit warnings and preserve raw diff output.
- Classifier tests:
  - JSON parsing, malformed response handling, row-level warning behavior.

