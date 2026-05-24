"""Tests for diff-seeded context summary and patch intent injection."""
from __future__ import annotations

import unittest

from aegis_test_generator.planner.intent import PatchIntent
from aegis_test_generator.planner.llm_planner import _dspy_context_summary, _format_priority_targets


class FormatPriorityTargetsTests(unittest.TestCase):
    def test_empty_modified_returns_empty(self) -> None:
        self.assertEqual(_format_priority_targets([], []), "")

    def test_lists_each_modified_file(self) -> None:
        result = _format_priority_targets(["/etc/a.conf", "/etc/b.conf"], [])
        self.assertIn("/etc/a.conf", result)
        self.assertIn("/etc/b.conf", result)

    def test_high_sensitivity_files_marked(self) -> None:
        result = _format_priority_targets(
            ["/etc/nginx.conf"],
            [("/etc/nginx.conf", 0.9)],
        )
        self.assertIn("HIGH RISK", result)

    def test_low_sensitivity_files_not_marked(self) -> None:
        result = _format_priority_targets(
            ["/tmp/scratch"],
            [("/tmp/scratch", 0.1)],
        )
        self.assertNotIn("HIGH RISK", result)

    def test_files_ordered_by_score_descending(self) -> None:
        result = _format_priority_targets(
            ["/etc/low.conf", "/etc/high.conf"],
            [("/etc/low.conf", 0.2), ("/etc/high.conf", 0.9)],
        )
        high_pos = result.index("/etc/high.conf")
        low_pos = result.index("/etc/low.conf")
        self.assertLess(high_pos, low_pos)

    def test_includes_guidance_text(self) -> None:
        result = _format_priority_targets(["/etc/x"], [])
        self.assertIn("verify", result.lower())
        self.assertIn("guard", result.lower())


class DspyContextSummaryTests(unittest.TestCase):
    def _ctx(self, **kwargs) -> dict:
        base: dict = {
            "diff": {"modified": [], "added": [], "removed": []},
            "sensitivity_verdict": {"verdict": "safe", "scored_files": []},
            "predicted_impact": {"files": []},
        }
        base.update(kwargs)
        return base

    def test_intent_appears_at_top(self) -> None:
        summary = _dspy_context_summary(self._ctx(), patch_intent=PatchIntent.UPDATE)
        self.assertTrue(summary.startswith("PATCH INTENT: UPDATE"))

    def test_no_intent_omits_intent_line(self) -> None:
        summary = _dspy_context_summary(self._ctx(), patch_intent=None)
        self.assertNotIn("PATCH INTENT", summary)

    def test_modified_files_trigger_priority_section(self) -> None:
        ctx = self._ctx(diff={"modified": [{"path": "/etc/nginx.conf"}], "added": [], "removed": []})
        summary = _dspy_context_summary(ctx)
        self.assertIn("PRIORITY UPDATE TEST TARGETS", summary)
        self.assertIn("/etc/nginx.conf", summary)

    def test_no_modified_files_no_priority_section(self) -> None:
        ctx = self._ctx(diff={"modified": [], "added": [{"path": "/etc/new.conf"}], "removed": []})
        summary = _dspy_context_summary(ctx)
        self.assertNotIn("PRIORITY UPDATE TEST TARGETS", summary)

    def test_sensitivity_scores_surface_in_priority_section(self) -> None:
        ctx = self._ctx(
            diff={"modified": [{"path": "/etc/nginx.conf"}], "added": [], "removed": []},
            sensitivity_verdict={"verdict": "risky", "scored_files": [{"path": "/etc/nginx.conf", "score": 0.95}]},
        )
        summary = _dspy_context_summary(ctx)
        self.assertIn("HIGH RISK", summary)

    def test_description_field_included(self) -> None:
        ctx = self._ctx(description="Install security patches")
        summary = _dspy_context_summary(ctx)
        self.assertIn("Install security patches", summary)


if __name__ == "__main__":
    unittest.main()
