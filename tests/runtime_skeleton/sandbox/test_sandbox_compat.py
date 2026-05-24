from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_skeleton.interfaces import PatchApplyResult, SandboxResult
from runtime_skeleton.sandbox import (
    apply_patch,
    create_sandbox,
    load_sandbox_config,
    resolve_playbook_yaml,
)
from runtime_skeleton.sandbox.config import load_sandbox_config as load_sandbox_config_module
from runtime_skeleton.sandbox.playbook import resolve_playbook_yaml as resolve_playbook_yaml_module


class SandboxCompatibilityTests(unittest.TestCase):
    def test_create_sandbox_signature_is_stable(self) -> None:
        signature = inspect.signature(create_sandbox)

        self.assertEqual(list(signature.parameters.keys()), ["repo_root", "run_id", "skip"])
        self.assertEqual(signature.parameters["repo_root"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["run_id"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["skip"].default, False)

    def test_apply_patch_signature_is_stable(self) -> None:
        signature = inspect.signature(apply_patch)

        self.assertEqual(
            list(signature.parameters.keys()),
            ["repo_root", "container_name", "patch_section", "skip"],
        )
        self.assertEqual(signature.parameters["repo_root"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["container_name"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["patch_section"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["skip"].default, False)

    def test_load_sandbox_config_public_entrypoint_is_stable(self) -> None:
        signature = inspect.signature(load_sandbox_config)

        self.assertEqual(list(signature.parameters.keys()), ["repo_root"])
        self.assertIs(load_sandbox_config, load_sandbox_config_module)

    def test_resolve_playbook_yaml_public_entrypoint_is_stable(self) -> None:
        signature = inspect.signature(resolve_playbook_yaml)

        self.assertEqual(list(signature.parameters.keys()), ["patch", "repo_root"])
        self.assertEqual(signature.parameters["patch"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["repo_root"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(resolve_playbook_yaml, resolve_playbook_yaml_module)

    @patch("runtime_skeleton.sandbox.create.create_sandbox_request")
    def test_create_sandbox_delegates_to_component_helper(self, mock_delegate) -> None:
        expected = SandboxResult(skipped=True, skip_reason="skip_requested")
        mock_delegate.return_value = expected

        result = create_sandbox(repo_root=Path("."), run_id="run-compat", skip=True)

        self.assertIs(result, expected)
        mock_delegate.assert_called_once_with(repo_root=Path("."), run_id="run-compat", skip=True)

    @patch("runtime_skeleton.sandbox.patch.apply_patch_request")
    def test_apply_patch_delegates_to_component_helper(self, mock_delegate) -> None:
        expected = PatchApplyResult(skipped=True, skip_reason="skip_requested")
        mock_delegate.return_value = expected

        result = apply_patch(
            repo_root=Path("."),
            container_name="sandbox-compat",
            patch_section={"plays": []},
            skip=True,
        )

        self.assertIs(result, expected)
        mock_delegate.assert_called_once_with(
            repo_root=Path("."),
            container_name="sandbox-compat",
            patch_section={"plays": []},
            skip=True,
        )


if __name__ == "__main__":
    unittest.main()
