Future Enhancements
===================

This file captures improvement ideas that have been identified but deferred. Each
entry notes the motivation, the rough implementation approach, and why it was not
prioritised yet.

-------------------------------------------------------------------------------

Functional verification tests (command_succeeds)
-------------------------------------------------

Motivation
  A package being installed does not prove the software works. The current pipeline
  mostly generates existence checks (file_exists, package_installed) but the
  test_type "command_succeeds" already exists in the schema and renderer. Tests like
  `curl --version` or `git --version` would prove the binary is on PATH and
  executable, not just that the package record exists.

Approach
  Update the LLM prompt in llm_planner.py to explicitly instruct the model:
    - For every package_installed test, also propose a command_succeeds test using
      the binary's canonical --version or --help invocation.
    - For every service_running test, also propose a command_succeeds test that
      exercises the service (e.g. nginx -t for config validation).
  No schema or renderer changes are needed. command_succeeds is already supported.

Why deferred
  The main risk is command hallucination: the LLM may propose commands that do not
  exist in the image or have different flags. This needs a guard — either a review
  pass (see Improvement 2 in the active plan) that can catch bad commands, or a
  whitelist of known-safe binary invocations. The review pass should be implemented
  first (it is part of the active plan), then this enhancement can be layered on top
  safely.

Effort estimate: Small prompt change. Medium risk without a review pass in place first.
