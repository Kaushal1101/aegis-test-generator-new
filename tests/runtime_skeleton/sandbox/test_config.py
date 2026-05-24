from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime_skeleton.sandbox.config import DEFAULT_SANDBOX, load_sandbox_config


class SandboxConfigTests(unittest.TestCase):
    def test_defaults_are_returned_when_config_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            cfg = load_sandbox_config(repo_root)

        self.assertEqual(cfg, DEFAULT_SANDBOX)

    def test_config_file_merges_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            config_dir = repo_root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "sandbox.json").write_text(
                json.dumps(
                    {
                        "image": "ubuntu:24.04",
                        "command": ["bash", "-lc", "sleep infinity"],
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_sandbox_config(repo_root)

        self.assertEqual(cfg["image"], "ubuntu:24.04")
        self.assertEqual(cfg["command"], ["bash", "-lc", "sleep infinity"])
        self.assertEqual(cfg["container_name_prefix"], DEFAULT_SANDBOX["container_name_prefix"])

    def test_non_object_json_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            config_dir = repo_root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "sandbox.json").write_text('["not", "an", "object"]', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                load_sandbox_config(repo_root)

    def test_invalid_command_type_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            config_dir = repo_root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "sandbox.json").write_text(
                json.dumps({"command": "sleep infinity"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "sandbox command must be a list\\[str\\]"):
                load_sandbox_config(repo_root)


if __name__ == "__main__":
    unittest.main()
