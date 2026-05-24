from __future__ import annotations

import unittest
from typing import Any

from runtime_skeleton.components.input import parse_input_request
from runtime_skeleton.input import parse_input


def _valid_input_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "meta": {
            "run_id": "run-compat",
            "sections_present": [
                "patch",
                "diff",
                "sensitivity_verdict",
                "predicted_impact",
                "apply",
            ],
        },
        "patch": {"raw_yaml": "---", "plays": []},
        "diff": {
            "added": [{"path": "added.py"}],
            "modified": [{"path": "modified.py"}],
            "removed": [{"path": "removed.py"}],
            "errors": [],
        },
        "sensitivity_verdict": {
            "verdict": "medium",
            "scored_files": [{"path": "modified.py", "score": 0.8}],
        },
        "predicted_impact": {"files": [{"path": "modified.py"}]},
        "apply": {},
    }


class ParseInputCompatibilityTests(unittest.TestCase):
    def test_parse_input_matches_component_output(self) -> None:
        payload = _valid_input_document()

        legacy_result = parse_input(input_json=payload)
        component_result = parse_input_request(input_json=payload)

        self.assertEqual(legacy_result.parsed, component_result.parsed)
        self.assertEqual(legacy_result.derived, component_result.derived)
        self.assertEqual(legacy_result.warnings, component_result.warnings)
        self.assertEqual(legacy_result.error, component_result.error)


if __name__ == "__main__":
    unittest.main()
