from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_skeleton.components.sandbox import DefaultSandboxComponent
from runtime_skeleton.interfaces import PatchApplyRequest, PatchApplyResult, SandboxCreateRequest


class SandboxComponentTests(unittest.TestCase):
    def test_create_skip_requested(self) -> None:
        component = DefaultSandboxComponent()
        result = component.create(
            SandboxCreateRequest(repo_root=Path("."), run_id="run-1", skip=True)
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "skip_requested")

    @patch("runtime_skeleton.components.sandbox.core.load_sandbox_config")
    def test_create_config_error(self, mock_load_config) -> None:
        mock_load_config.side_effect = ValueError("bad config")
        component = DefaultSandboxComponent()

        result = component.create(SandboxCreateRequest(repo_root=Path("."), run_id="run-2"))

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "config_error")
        self.assertEqual(result.error, "bad config")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.load_sandbox_config")
    def test_create_docker_unavailable(self, mock_load_config, mock_run) -> None:
        mock_load_config.return_value = {
            "image": "ubuntu:22.04",
            "container_name_prefix": "runtime-skeleton-sandbox",
            "command": ["sleep", "infinity"],
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=["docker", "info"],
            returncode=1,
            stdout="",
            stderr="docker daemon not running",
        )
        component = DefaultSandboxComponent()

        result = component.create(SandboxCreateRequest(repo_root=Path("."), run_id="run-3"))

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "docker_unavailable")
        self.assertIn("docker daemon not running", result.error or "")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.load_sandbox_config")
    def test_create_docker_run_failure(self, mock_load_config, mock_run) -> None:
        mock_load_config.return_value = {
            "image": "ubuntu:22.04",
            "container_name_prefix": "runtime-skeleton-sandbox",
            "command": ["sleep", "infinity"],
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["docker", "info"], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(args=["docker", "rm"], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                args=["docker", "run"], returncode=125, stdout="", stderr="pull failed"
            ),
        ]
        component = DefaultSandboxComponent()

        result = component.create(SandboxCreateRequest(repo_root=Path("."), run_id="run-4"))

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "docker_run_failed")
        self.assertEqual(result.error, "pull failed")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.load_sandbox_config")
    def test_create_success_mapping(self, mock_load_config, mock_run) -> None:
        mock_load_config.return_value = {
            "image": "ubuntu:22.04",
            "container_name_prefix": "runtime-skeleton-sandbox",
            "command": ["sleep", "infinity"],
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["docker", "info"], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(args=["docker", "rm"], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                args=["docker", "run"], returncode=0, stdout="abc123\n", stderr=""
            ),
        ]
        component = DefaultSandboxComponent()

        result = component.create(
            SandboxCreateRequest(repo_root=Path("."), run_id="run id with spaces")
        )

        self.assertFalse(result.skipped)
        self.assertEqual(result.image, "ubuntu:22.04")
        self.assertEqual(result.container_id, "abc123")
        self.assertTrue(result.container_name.startswith("runtime-skeleton-sandbox-"))

    def test_apply_patch_skip_requested(self) -> None:
        component = DefaultSandboxComponent()

        result = component.apply_patch(
            PatchApplyRequest(
                repo_root=Path("."),
                container_name="sandbox-1",
                patch_section={},
                skip=True,
            )
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "skip_requested")

    def test_apply_patch_missing_container(self) -> None:
        component = DefaultSandboxComponent()

        result = component.apply_patch(
            PatchApplyRequest(
                repo_root=Path("."),
                container_name="",
                patch_section={},
                skip=False,
            )
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "missing_container")

    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_apply_patch_ansible_not_found(self, mock_which) -> None:
        mock_which.return_value = None
        component = DefaultSandboxComponent()

        result = component.apply_patch(
            PatchApplyRequest(
                repo_root=Path("."),
                container_name="sandbox-1",
                patch_section={},
            )
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "ansible_not_found")

    @patch("runtime_skeleton.components.sandbox.core.resolve_playbook_yaml")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_apply_patch_playbook_resolve_failure(self, mock_which, mock_resolve) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_resolve.side_effect = ValueError("no patch data")
        component = DefaultSandboxComponent()

        result = component.apply_patch(
            PatchApplyRequest(
                repo_root=Path("."),
                container_name="sandbox-1",
                patch_section={},
            )
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "playbook_resolve_failed")
        self.assertEqual(result.error, "no patch data")

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.resolve_playbook_yaml")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_apply_patch_success_mapping(self, mock_which, mock_resolve, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_resolve.return_value = ("- hosts: all\n  tasks: []\n", "parsed_patch_section")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ansible-playbook"], returncode=0, stdout="ok", stderr=""
        )
        component = DefaultSandboxComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            result = component.apply_patch(
                PatchApplyRequest(
                    repo_root=repo_root,
                    container_name="sandbox-1",
                    patch_section={},
                )
            )

            self.assertFalse(result.skipped)
            self.assertTrue(result.patch_applied)
            self.assertEqual(result.error, None)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "ok")
            self.assertEqual(result.source, "parsed_patch_section")
            self.assertTrue(Path(result.log_path).is_file())

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.resolve_playbook_yaml")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_apply_patch_failure_mapping(self, mock_which, mock_resolve, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_resolve.return_value = ("- hosts: all\n  tasks: []\n", "inputs_patch_yml")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ansible-playbook"], returncode=2, stdout="changes", stderr="failed"
        )
        component = DefaultSandboxComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            result = component.apply_patch(
                PatchApplyRequest(
                    repo_root=repo_root,
                    container_name="sandbox-1",
                    patch_section={},
                )
            )

            self.assertFalse(result.skipped)
            self.assertFalse(result.patch_applied)
            self.assertEqual(result.error, "ansible_run_failed")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "changes")
            self.assertEqual(result.stderr, "failed")
            self.assertEqual(result.source, "inputs_patch_yml")
            self.assertTrue(Path(result.log_path).is_file())

    @patch("runtime_skeleton.components.sandbox.core.subprocess.run")
    @patch("runtime_skeleton.components.sandbox.core.resolve_playbook_yaml")
    @patch("runtime_skeleton.components.sandbox.core.shutil.which")
    def test_apply_patch_exec_error_mapping(self, mock_which, mock_resolve, mock_run) -> None:
        mock_which.return_value = "/usr/bin/ansible-playbook"
        mock_resolve.return_value = ("- hosts: all\n  tasks: []\n", "parsed_patch_section")
        mock_run.side_effect = OSError("ansible not executable")
        component = DefaultSandboxComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            result = component.apply_patch(
                PatchApplyRequest(
                    repo_root=repo_root,
                    container_name="sandbox-1",
                    patch_section={},
                )
            )

            self.assertFalse(result.skipped)
            self.assertFalse(result.patch_applied)
            self.assertIn("ansible_exec_error:", result.error or "")
            self.assertEqual(result.source, "parsed_patch_section")
            self.assertTrue(result.log_path.endswith("ansible.log"))
            self.assertIsInstance(result, PatchApplyResult)


if __name__ == "__main__":
    unittest.main()
