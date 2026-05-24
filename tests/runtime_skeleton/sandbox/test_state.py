"""Tests for sandbox_state_to_playbook_yaml and resolve_state_yaml."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from runtime_skeleton.sandbox.state import resolve_state_yaml, sandbox_state_to_playbook_yaml


class SandboxStateToPlaybookYamlTests(unittest.TestCase):
    def _parse(self, state: dict) -> list:
        return yaml.safe_load(sandbox_state_to_playbook_yaml(state))

    def test_empty_state_raises(self) -> None:
        with self.assertRaises(ValueError):
            sandbox_state_to_playbook_yaml({})

    def test_empty_lists_raise(self) -> None:
        with self.assertRaises(ValueError):
            sandbox_state_to_playbook_yaml({"packages": [], "files": []})

    def test_package_without_version(self) -> None:
        plays = self._parse({"packages": [{"name": "curl"}]})
        tasks = plays[0]["tasks"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["apt"]["name"], "curl")
        self.assertEqual(tasks[0]["apt"]["state"], "present")

    def test_package_with_version(self) -> None:
        plays = self._parse({"packages": [{"name": "nginx", "version": "1.18.0"}]})
        tasks = plays[0]["tasks"]
        self.assertEqual(tasks[0]["apt"]["name"], "nginx=1.18.0")

    def test_package_as_bare_string(self) -> None:
        plays = self._parse({"packages": ["curl"]})
        tasks = plays[0]["tasks"]
        self.assertEqual(tasks[0]["apt"]["name"], "curl")

    def test_file_without_options(self) -> None:
        plays = self._parse({"files": [{"path": "/etc/app.conf", "content": "key=val"}]})
        tasks = plays[0]["tasks"]
        # directory task + file task
        paths = [t.get("file", {}).get("path") or t.get("copy", {}).get("dest") for t in tasks]
        self.assertIn("/etc", paths)
        self.assertIn("/etc/app.conf", paths)

    def test_file_with_mode_and_owner(self) -> None:
        plays = self._parse({
            "files": [{"path": "/tmp/x", "content": "hello", "mode": "0600", "owner": "root"}]
        })
        copy_task = next(t for t in plays[0]["tasks"] if "copy" in t)
        self.assertEqual(copy_task["copy"]["mode"], "0600")
        self.assertEqual(copy_task["copy"]["owner"], "root")

    def test_directory_task_deduplication(self) -> None:
        plays = self._parse({
            "files": [
                {"path": "/opt/app/a.conf", "content": "a"},
                {"path": "/opt/app/b.conf", "content": "b"},
            ]
        })
        dir_tasks = [t for t in plays[0]["tasks"] if t.get("file", {}).get("state") == "directory"]
        self.assertEqual(len(dir_tasks), 1)
        self.assertEqual(dir_tasks[0]["file"]["path"], "/opt/app")

    def test_service_task(self) -> None:
        plays = self._parse({"services": [{"name": "nginx", "state": "started", "enabled": True}]})
        task = plays[0]["tasks"][0]
        self.assertEqual(task["service"]["name"], "nginx")
        self.assertEqual(task["service"]["state"], "started")
        self.assertTrue(task["service"]["enabled"])

    def test_user_task(self) -> None:
        plays = self._parse({"users": [{"name": "appuser", "uid": 1001}]})
        task = plays[0]["tasks"][0]
        self.assertEqual(task["user"]["name"], "appuser")
        self.assertEqual(task["user"]["uid"], 1001)

    def test_play_metadata(self) -> None:
        plays = self._parse({"packages": [{"name": "curl"}]})
        self.assertEqual(plays[0]["hosts"], "sandbox")
        self.assertFalse(plays[0]["gather_facts"])

    def test_tasks_ordered_packages_then_dirs_then_files(self) -> None:
        plays = self._parse({
            "packages": [{"name": "curl"}],
            "files": [{"path": "/etc/app.conf", "content": "x"}],
        })
        tasks = plays[0]["tasks"]
        kinds = []
        for t in tasks:
            if "apt" in t:
                kinds.append("apt")
            elif "file" in t:
                kinds.append("file")
            elif "copy" in t:
                kinds.append("copy")
        self.assertEqual(kinds, ["apt", "file", "copy"])


class ResolveStateYamlTests(unittest.TestCase):
    def test_disk_file_takes_precedence(self) -> None:
        state = {"packages": [{"name": "curl"}]}
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            inputs_dir = repo_root / "inputs"
            inputs_dir.mkdir()
            disk = inputs_dir / "sandbox_state.yml"
            disk.write_text("# hand-crafted\n- name: override\n  hosts: sandbox\n  tasks: []\n")

            yaml_str, source = resolve_state_yaml(sandbox_state=state, repo_root=repo_root)

            self.assertEqual(source, "inputs_sandbox_state_yml")
            self.assertIn("hand-crafted", yaml_str)

    def test_falls_back_to_parsed_section(self) -> None:
        state = {"packages": [{"name": "curl"}]}
        with tempfile.TemporaryDirectory() as tmp:
            yaml_str, source = resolve_state_yaml(sandbox_state=state, repo_root=Path(tmp))

        self.assertEqual(source, "parsed_sandbox_state")
        plays = yaml.safe_load(yaml_str)
        self.assertEqual(plays[0]["hosts"], "sandbox")

    def test_empty_state_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_state_yaml(sandbox_state={}, repo_root=Path(tmp))


if __name__ == "__main__":
    unittest.main()
