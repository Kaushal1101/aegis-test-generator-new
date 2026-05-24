"""Tests for image profile resolution in load_sandbox_config."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime_skeleton.sandbox.config import IMAGE_PROFILES, load_sandbox_config


class ImageProfileTests(unittest.TestCase):
    def _write_config(self, tmp: str, data: dict) -> Path:
        cfg_dir = Path(tmp) / "config"
        cfg_dir.mkdir()
        cfg_path = cfg_dir / "sandbox.json"
        cfg_path.write_text(json.dumps(data))
        return Path(tmp)

    def test_all_named_profiles_are_valid(self) -> None:
        for name, profile in IMAGE_PROFILES.items():
            self.assertIn("image", profile, f"profile '{name}' missing image")
            self.assertIn("ansible_python_interpreter", profile, f"profile '{name}' missing interpreter")

    def test_profile_minimal_resolves_to_slim_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._write_config(tmp, {"profile": "minimal"})
            cfg = load_sandbox_config(repo_root)
        self.assertIn("slim", cfg["image"])

    def test_profile_ubuntu_lts_sets_correct_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._write_config(tmp, {"profile": "ubuntu-lts"})
            cfg = load_sandbox_config(repo_root)
        self.assertEqual(cfg["ansible_python_interpreter"], "/usr/bin/python3")
        self.assertIn("bootstrap_commands", cfg)

    def test_profile_rhel_compat_has_bootstrap_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._write_config(tmp, {"profile": "rhel-compat"})
            cfg = load_sandbox_config(repo_root)
        cmds = cfg.get("bootstrap_commands", [])
        self.assertTrue(len(cmds) > 0)
        self.assertTrue(any("python3" in c for c in cmds))

    def test_explicit_image_overrides_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._write_config(
                tmp, {"profile": "ubuntu-lts", "image": "ubuntu:20.04"}
            )
            cfg = load_sandbox_config(repo_root)
        self.assertEqual(cfg["image"], "ubuntu:20.04")

    def test_unknown_profile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._write_config(tmp, {"profile": "nonexistent"})
            with self.assertRaises(ValueError) as ctx:
                load_sandbox_config(repo_root)
        self.assertIn("nonexistent", str(ctx.exception))

    def test_no_profile_uses_default_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_sandbox_config(Path(tmp))
        self.assertIn("python", cfg["image"])


if __name__ == "__main__":
    unittest.main()
