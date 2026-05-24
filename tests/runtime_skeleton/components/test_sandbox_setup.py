"""Tests for DefaultSandboxComponent.apply_setup."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_skeleton.components.sandbox import DefaultSandboxComponent
from runtime_skeleton.interfaces import SetupApplyRequest, SetupApplyResult


class ApplySetupTests(unittest.TestCase):
    def _req(self, **kwargs) -> SetupApplyRequest:
        defaults = dict(
            repo_root=Path("."),
            container_name="sandbox-1",
            sandbox_state={"packages": [{"name": "curl"}]},
            skip=False,
        )
        defaults.update(kwargs)
        return SetupApplyRequest(**defaults)

    def test_skip_requested(self) -> None:
        result = DefaultSandboxComponent().apply_setup(self._req(skip=True))
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "skip_requested")

    def test_missing_container(self) -> None:
        result = DefaultSandboxComponent().apply_setup(self._req(container_name=""))
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "missing_container")

    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_ansible_not_found(self, mock_which) -> None:
        mock_which.return_value = None
        result = DefaultSandboxComponent().apply_setup(self._req())
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "ansible_not_found")

    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_empty_state_skips_gracefully(self, mock_which) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        result = DefaultSandboxComponent().apply_setup(
            self._req(sandbox_state={})
        )
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_state")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_success_mapping(self, mock_which, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ansible-playbook"], returncode=0, stdout="ok", stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = DefaultSandboxComponent().apply_setup(
                self._req(repo_root=Path(tmp))
            )
        self.assertFalse(result.skipped)
        self.assertTrue(result.setup_applied)
        self.assertIsNone(result.error)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.source, "parsed_sandbox_state")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_failure_mapping(self, mock_which, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ansible-playbook"], returncode=2, stdout="", stderr="FAILED"
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = DefaultSandboxComponent().apply_setup(
                self._req(repo_root=Path(tmp))
            )
        self.assertFalse(result.skipped)
        self.assertFalse(result.setup_applied)
        self.assertEqual(result.error, "ansible_run_failed")
        self.assertEqual(result.returncode, 2)

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_exec_error_mapping(self, mock_which, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_run.side_effect = OSError("ansible missing")
        with tempfile.TemporaryDirectory() as tmp:
            result = DefaultSandboxComponent().apply_setup(
                self._req(repo_root=Path(tmp))
            )
        self.assertFalse(result.skipped)
        self.assertFalse(result.setup_applied)
        self.assertIn("ansible_exec_error", result.error or "")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_disk_state_file_used_when_present(self, mock_which, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ansible-playbook"], returncode=0, stdout="ok", stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            inputs = repo_root / "inputs"
            inputs.mkdir()
            (inputs / "sandbox_state.yml").write_text(
                "- name: disk state\n  hosts: sandbox\n  tasks: []\n"
            )
            result = DefaultSandboxComponent().apply_setup(
                self._req(repo_root=repo_root, sandbox_state={})
            )
        # disk file has content so resolve_state_yaml succeeds; source reflects it
        self.assertEqual(result.source, "inputs_sandbox_state_yml")
        self.assertTrue(result.setup_applied)

    def test_result_is_setuplresult_instance(self) -> None:
        result = DefaultSandboxComponent().apply_setup(self._req(skip=True))
        self.assertIsInstance(result, SetupApplyResult)


if __name__ == "__main__":
    unittest.main()
