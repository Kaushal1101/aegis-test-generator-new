from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from runtime_skeleton.components.input import DefaultInputComponent, parse_input_request
from runtime_skeleton.interfaces import InputRequest, InputResult


def _valid_input_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "meta": {
            "run_id": "run-1",
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
            "added": [{"path": "new_file.py"}],
            "modified": [{"path": "changed_file.py"}],
            "removed": [{"path": "old_file.py"}],
            "errors": [{"path": "broken_file.py"}],
        },
        "sensitivity_verdict": {
            "verdict": "high",
            "scored_files": [
                {"path": "changed_file.py", "score": 0.8},
                {"path": "new_file.py", "score": 0.74},
            ],
        },
        "predicted_impact": {
            "files": [
                {"path": "changed_file.py"},
                {"path": "predicted_only.py"},
            ]
        },
        "apply": {"candidate": True},
    }


class InputComponentTests(unittest.TestCase):
    def test_input_json_success_path(self) -> None:
        result = parse_input_request(input_json=_valid_input_document())

        self.assertIsInstance(result, InputResult)
        self.assertIsNone(result.error)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.parsed["schema_version"], "1.0")

    def test_input_path_file_not_found(self) -> None:
        component = DefaultInputComponent()

        result = component.parse(InputRequest(input_path="/tmp/does-not-exist-input.json"))

        self.assertEqual(result.parsed, {})
        self.assertEqual(result.derived, {})
        self.assertIn("Input file not found:", result.error or "")

    def test_invalid_json_path_returns_error(self) -> None:
        component = DefaultInputComponent()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "invalid.json"
            input_path.write_text("{not-valid-json", encoding="utf-8")

            result = component.parse(InputRequest(input_path=str(input_path)))

        self.assertEqual(result.parsed, {})
        self.assertEqual(result.derived, {})
        self.assertIsNotNone(result.error)

    def test_invalid_schema_returns_error(self) -> None:
        invalid_payload = _valid_input_document()
        invalid_payload.pop("meta")

        result = parse_input_request(input_json=invalid_payload)

        self.assertEqual(result.parsed, {})
        self.assertEqual(result.derived, {})
        self.assertIsNotNone(result.error)

    def test_unsupported_schema_version_returns_error(self) -> None:
        payload = _valid_input_document()
        payload["schema_version"] = "2.0"

        result = parse_input_request(input_json=payload)

        self.assertEqual(result.parsed, {})
        self.assertEqual(result.derived, {})
        self.assertEqual(result.warnings, [])
        self.assertIn("Unsupported schema_version: 2.0", result.error or "")

    def test_sections_present_warnings(self) -> None:
        payload = _valid_input_document()
        payload["meta"]["sections_present"] = ["patch", "diff", "unexpected_section"]

        result = parse_input_request(input_json=payload)

        self.assertIsNone(result.error)
        self.assertEqual(len(result.warnings), 2)
        self.assertIn("missing entries", result.warnings[0])
        self.assertIn("unexpected entries", result.warnings[1])

    def test_derived_field_behavior(self) -> None:
        result = parse_input_request(input_json=_valid_input_document())

        self.assertIsNone(result.error)
        self.assertEqual(result.derived["high_sensitivity_paths"], ["changed_file.py"])
        self.assertEqual(result.derived["predicted_not_materialized"], ["predicted_only.py"])
        self.assertEqual(
            result.derived["materialized_not_predicted"],
            ["new_file.py", "old_file.py"],
        )


if __name__ == "__main__":
    unittest.main()
