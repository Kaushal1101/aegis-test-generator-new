from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime_skeleton.sandbox.playbook import resolve_playbook_yaml


class SandboxPlaybookTests(unittest.TestCase):
    def test_disk_patch_file_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            inputs_dir = repo_root / "inputs"
            inputs_dir.mkdir(parents=True, exist_ok=True)
            (inputs_dir / "patch.yml").write_text("- hosts: all\n  tasks: []\n", encoding="utf-8")

            yaml_text, source = resolve_playbook_yaml(
                patch={"raw_yaml": "- hosts: ignored\n"},
                repo_root=repo_root,
            )

        self.assertEqual(source, "inputs_patch_yml")
        self.assertEqual(yaml_text, "- hosts: all\n  tasks: []\n")

    def test_fallback_to_parsed_patch_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            yaml_text, source = resolve_playbook_yaml(
                patch={"raw_yaml": "- hosts: all\n  tasks: []\n"},
                repo_root=repo_root,
            )

        self.assertEqual(source, "parsed_patch_section")
        self.assertEqual(yaml_text, "- hosts: all\n  tasks: []\n")

    def test_error_when_patch_has_no_usable_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            with self.assertRaisesRegex(ValueError, "neither non-empty plays nor raw_yaml"):
                resolve_playbook_yaml(patch={}, repo_root=repo_root)


if __name__ == "__main__":
    unittest.main()
