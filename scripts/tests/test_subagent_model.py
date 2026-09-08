from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex_config import CodexSubagentModel
from scripts.install.common import FileTransaction, InstallerError, StateError


class SubagentModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.path = self.home / "config.toml"
        self.original = (
            '# personal\nmodel = "parent"\nmodel_reasoning_effort = "high"\n'
            '[agents]\nmax_depth = 2\nmax_concurrent_threads_per_session = 8\n'
            'default_subagent_model = "small"\n'
            'default_subagent_reasoning_effort = "max"\n'
            '[profiles.work]\nmodel = "profile"\n'
        )
        self.path.write_text(self.original)
        self.path.chmod(0o600)
        (self.home / "agents").mkdir()
        self.role = self.home / "agents/scout.toml"
        self.role.write_text('model = "pinned"\nmodel_reasoning_effort = "low"\n')

    def test_inspect_separates_saved_sources_and_does_not_write(self):
        state = CodexSubagentModel(self.home).inspect()
        self.assertEqual('"parent"', state["parent"]["model"])
        self.assertEqual('"small"', state["global_child_overrides"]["agents.default_subagent_model"])
        self.assertEqual('"pinned"', state["role_file_pins"]["scout"]["model"])
        self.assertEqual(self.original, self.path.read_text())
        self.assertFalse((self.home / "config.toml.hukuhaka-backup").exists())

    def test_inherit_preserves_every_other_byte_and_role_pin(self):
        policy = CodexSubagentModel(self.home)
        plan = policy.plan_inherit()
        with mock.patch.object(policy.config, "_doctor"):
            self.assertTrue(policy.apply(plan))
            self.assertFalse(policy.apply(policy.plan_inherit()))
        expected = self.original.replace('default_subagent_model = "small"\n', '').replace(
            'default_subagent_reasoning_effort = "max"\n', '')
        self.assertEqual(expected, self.path.read_text())
        self.assertEqual(self.original, policy.config.backup.read_text())
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)
        self.assertEqual('model = "pinned"\nmodel_reasoning_effort = "low"\n', self.role.read_text())

    def test_dry_run_writes_nothing_and_never_calls_doctor(self):
        policy = CodexSubagentModel(self.home, dry_run=True)
        before = sorted(str(path.relative_to(self.home)) for path in self.home.rglob("*"))
        with mock.patch.object(policy.config, "_doctor") as doctor:
            self.assertFalse(policy.apply(policy.plan_inherit()))
        doctor.assert_not_called()
        self.assertEqual(self.original, self.path.read_text())
        self.assertEqual(before, sorted(str(path.relative_to(self.home)) for path in self.home.rglob("*")))

    def test_doctor_failure_rolls_back_config_and_backup(self):
        policy = CodexSubagentModel(self.home)
        policy.config.backup.write_bytes(b"previous backup")
        with mock.patch.object(policy.config, "_doctor", side_effect=InstallerError("invalid")):
            with self.assertRaises(InstallerError):
                policy.apply(policy.plan_inherit())
        self.assertEqual(self.original, self.path.read_text())
        self.assertEqual(b"previous backup", policy.config.backup.read_bytes())

    def test_concurrent_edit_is_preserved(self):
        policy = CodexSubagentModel(self.home)
        plan = policy.plan_inherit()
        self.path.write_text(self.original + "# new note\n")
        with self.assertRaisesRegex(StateError, "changed after"):
            policy.apply(plan)
        self.assertEqual(self.original + "# new note\n", self.path.read_text())

    def test_dotted_keys_and_absent_config(self):
        self.path.write_text('agents.default_subagent_model = "small"\nmodel = "parent"\n')
        policy = CodexSubagentModel(self.home)
        self.assertEqual(b'model = "parent"\n', policy.plan_inherit().proposed)
        self.path.unlink()
        self.assertFalse(policy.plan_inherit().changed)
        self.assertIsNone(policy.inspect()["parent"]["model"])

    def test_duplicate_and_symlink_configs_fail_closed(self):
        policy = CodexSubagentModel(self.home)
        self.path.write_text(self.original + '[agents]\ndefault_subagent_model = "second"\n')
        with self.assertRaises(StateError):
            policy.plan_inherit()
        self.path.unlink()
        self.path.symlink_to(self.role)
        with self.assertRaises(StateError):
            policy.plan_inherit()

    def test_quoted_keys_and_multiline_instruction_text(self):
        self.path.write_text(
            '["agents"]\n"default_subagent_model" = "small" # retain note\n'
            "'default_subagent_reasoning_effort' = 'max'\nmax_depth = 2\n"
            '[plugins."example@market"]\nenabled = true\n'
        )
        policy = CodexSubagentModel(self.home)
        self.assertEqual(
            b'["agents"]\n# retain note\nmax_depth = 2\n[plugins."example@market"]\nenabled = true\n',
            policy.plan_inherit().proposed,
        )
        self.role.write_text(
            'model = "pinned"\ndeveloper_instructions = """\n'
            'model = "example-only"\n[agents]\n'
            'default_subagent_model = "example-only"\n"""\n'
        )
        self.assertEqual({"model": '"pinned"'}, policy.inspect()["role_file_pins"]["scout"])

    def test_missing_home_noop_does_not_create_state(self):
        home = self.home / "absent"
        policy = CodexSubagentModel(home)
        self.assertFalse(policy.apply(policy.plan_inherit()))
        self.assertFalse(home.exists())

    def test_interrupted_removal_is_recovered_before_noop_acceptance(self):
        policy = CodexSubagentModel(self.home)
        proposed = policy.plan_inherit().proposed
        interrupted = FileTransaction(self.home)
        interrupted.__enter__()
        interrupted.write_bytes(self.path, proposed, 0o600)
        plan = policy.plan_inherit()
        self.assertFalse(plan.changed)
        with self.assertRaisesRegex(StateError, "changed after"):
            policy.apply(plan)
        self.assertEqual(self.original, self.path.read_text())
        self.assertFalse(interrupted.journal_path.exists())

    def test_inspect_rejects_non_directory_and_invalid_role_encoding(self):
        self.role.unlink()
        (self.home / "agents").rmdir()
        (self.home / "agents").write_text("not a directory")
        with self.assertRaisesRegex(StateError, "directory"):
            CodexSubagentModel(self.home).inspect()
        (self.home / "agents").unlink()
        (self.home / "agents").mkdir()
        self.role.write_bytes(b"\xff")
        with self.assertRaisesRegex(StateError, "UTF-8"):
            CodexSubagentModel(self.home).inspect()


if __name__ == "__main__":
    unittest.main()
