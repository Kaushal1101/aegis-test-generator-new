"""Tests for PatchIntent classifier."""
from __future__ import annotations

import unittest

from aegis_test_generator.planner.intent import PatchIntent, classify_patch_intent


def _play(tasks: list) -> str:
    import yaml
    return yaml.dump([{"name": "test play", "hosts": "all", "tasks": tasks}])


class ClassifyPatchIntentTests(unittest.TestCase):
    # ------------------------------------------------------------------ installs
    def test_apt_present_is_install(self) -> None:
        yaml_str = _play([{"name": "install curl", "apt": {"name": "curl", "state": "present"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.INSTALL)

    def test_yum_present_defaults_to_install(self) -> None:
        yaml_str = _play([{"name": "install nginx", "yum": {"name": "nginx"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.INSTALL)

    # ------------------------------------------------------------------ updates
    def test_lineinfile_is_update(self) -> None:
        yaml_str = _play([{"name": "edit line", "lineinfile": {"path": "/etc/x", "line": "val"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.UPDATE)

    def test_replace_is_update(self) -> None:
        yaml_str = _play([{"name": "replace", "replace": {"path": "/etc/x", "regexp": "old", "replace": "new"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.UPDATE)

    def test_blockinfile_is_update(self) -> None:
        yaml_str = _play([{"name": "block", "blockinfile": {"path": "/etc/x", "block": "stuff"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.UPDATE)

    def test_apt_latest_is_update(self) -> None:
        yaml_str = _play([{"name": "upgrade nginx", "apt": {"name": "nginx", "state": "latest"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.UPDATE)

    def test_copy_to_modified_path_is_update(self) -> None:
        yaml_str = _play([{"name": "copy config", "copy": {"dest": "/etc/app.conf", "content": "x"}}])
        result = classify_patch_intent(yaml_str, diff_modified=["/etc/app.conf"])
        self.assertEqual(result, PatchIntent.UPDATE)

    def test_template_to_modified_path_is_update(self) -> None:
        yaml_str = _play([{"name": "template", "template": {"src": "t.j2", "dest": "/etc/nginx.conf"}}])
        result = classify_patch_intent(yaml_str, diff_modified=["/etc/nginx.conf"])
        self.assertEqual(result, PatchIntent.UPDATE)

    # ------------------------------------------------------------------ removes
    def test_apt_absent_is_remove(self) -> None:
        yaml_str = _play([{"name": "remove curl", "apt": {"name": "curl", "state": "absent"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.REMOVE)

    def test_file_absent_is_remove(self) -> None:
        yaml_str = _play([{"name": "delete file", "file": {"path": "/tmp/x", "state": "absent"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.REMOVE)

    # ------------------------------------------------------------------ configure
    def test_copy_without_diff_is_configure(self) -> None:
        yaml_str = _play([{"name": "copy config", "copy": {"dest": "/etc/app.conf", "content": "x"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.CONFIGURE)

    def test_file_directory_is_configure(self) -> None:
        yaml_str = _play([{"name": "mkdir", "file": {"path": "/opt/app", "state": "directory"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.CONFIGURE)

    # ------------------------------------------------------------------ mixed
    def test_install_and_remove_is_mixed(self) -> None:
        yaml_str = _play([
            {"name": "install", "apt": {"name": "curl", "state": "present"}},
            {"name": "remove", "apt": {"name": "wget", "state": "absent"}},
        ])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.MIXED)

    def test_install_and_update_is_mixed(self) -> None:
        yaml_str = _play([
            {"name": "install", "apt": {"name": "curl", "state": "present"}},
            {"name": "edit", "lineinfile": {"path": "/etc/x", "line": "val"}},
        ])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.MIXED)

    def test_update_and_configure_collapses_to_update(self) -> None:
        yaml_str = _play([
            {"name": "edit", "lineinfile": {"path": "/etc/x", "line": "val"}},
            {"name": "copy", "copy": {"dest": "/etc/new.conf", "content": "x"}},
        ])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.UPDATE)

    # ------------------------------------------------------------------ edge cases
    def test_invalid_yaml_returns_mixed(self) -> None:
        self.assertEqual(classify_patch_intent("{{{{invalid"), PatchIntent.MIXED)

    def test_non_list_yaml_returns_mixed(self) -> None:
        self.assertEqual(classify_patch_intent("key: value"), PatchIntent.MIXED)

    def test_empty_playbook_returns_mixed(self) -> None:
        self.assertEqual(classify_patch_intent(""), PatchIntent.MIXED)

    def test_only_service_tasks_returns_mixed(self) -> None:
        yaml_str = _play([{"name": "start nginx", "service": {"name": "nginx", "state": "started"}}])
        self.assertEqual(classify_patch_intent(yaml_str), PatchIntent.MIXED)

    def test_diff_modified_none_safe(self) -> None:
        yaml_str = _play([{"name": "edit", "lineinfile": {"path": "/etc/x", "line": "val"}}])
        self.assertEqual(classify_patch_intent(yaml_str, diff_modified=None), PatchIntent.UPDATE)

    def test_intent_values_are_strings(self) -> None:
        for intent in PatchIntent:
            self.assertIsInstance(intent.value, str)


if __name__ == "__main__":
    unittest.main()
