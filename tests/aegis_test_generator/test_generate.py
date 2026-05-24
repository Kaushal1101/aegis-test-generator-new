"""Smoke tests for aegis_test_generator.generate (no OpenAI/network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from aegis_test_generator.generate import generate_tests
from aegis_test_generator.planner.llm_planner import PlannerResult


def test_generate_tests_wires_planner_validate_render(tmp_path) -> None:
    yaml_path = Path(__file__).resolve().parents[1] / "fixtures" / "example_patch.yml"
    rows = [
        {"test_type": "file_exists", "target": "/tmp/aegis_gen_smoke"},
    ]
    result = PlannerResult(
        tests=rows,
        raw='{"tests": []}',
        warnings=[],
        model="gpt-4o-mini",
    )
    out_file = tmp_path / "generated_tests.py"
    with patch("aegis_test_generator.generate.plan_from_playbook", return_value=result) as mocked:
        gen = generate_tests(yaml_path, output_path=out_file, client=None, model=None)
    mocked.assert_called_once()
    _, kwargs = mocked.call_args
    assert kwargs.get("input_context") is None
    assert kwargs.get("review") is True
    assert kwargs["model"] is None
    assert gen.path == out_file
    text = out_file.read_text(encoding="utf-8")
    assert "def test_" in text
    assert gen.path.exists()
