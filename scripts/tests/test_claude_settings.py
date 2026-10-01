from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts.install.claude_settings import CATALOG, ClaudeSettings, cli_value, read_profile, wizard
from scripts.install.common import FileTransaction, InstallerError, InstallerLock, StateError


class ClaudeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "claude"
        self.home.mkdir()
        self.path = self.home / "settings.json"
        self.secret = "do-not-display-unknown-content"
        self.original = {"model": "personal", "effortLevel": "medium",
                         "env": {"ANTHROPIC_API_KEY": self.secret},
                         "permissions": {"deny": ["Read(.env)"]},
                         "hooks": {"UserPromptSubmit": []}, "enabledPlugins": {"other@local": True},
                         "unknown": [None, 1.25, {"x": "keep"}]}
        self.write(self.original)
        self.manager = ClaudeSettings(self.home)

    def write(self, values):
        self.path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")

    def read(self):
        return json.loads(self.path.read_text())

    def apply(self, plan, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.manager.apply(plan, **kwargs)

    def test_partial_set_unset_restore_preserves_unrelated_later_edits(self):
        profile = self.root / "profile.json"
        profile.write_text('{"language":"Korean", "autoMemoryEnabled":false}')
        identifier = self.apply(self.manager.plan(read_profile(profile)), label="profile")
        current = self.read()
        self.assertEqual(self.original, {key: current[key] for key in self.original})
        current["model"] = "later-personal"
        current["unknown"].append("later")
        self.write(current)
        self.apply(self.manager.restore_plan(identifier), label="restore")
        restored = self.read()
        self.assertNotIn("language", restored)
        self.assertNotIn("autoMemoryEnabled", restored)
        self.assertEqual("later-personal", restored["model"])
        self.assertEqual("later", restored["unknown"][-1])
        identifier = self.apply(self.manager.plan(remove=("effortLevel",)), label="unset")
        self.assertNotIn("effortLevel", self.read())
        self.apply(self.manager.restore_plan(identifier))
        self.assertEqual("medium", self.read()["effortLevel"])

    def test_output_receipts_profiles_never_include_unknown_values(self):
        plan = self.manager.plan({"effortLevel": "high"})
        self.assertNotIn(self.secret, plan.diff())
        self.assertNotIn("permissions", plan.diff())
        identifier = self.apply(plan)
        receipt = self.manager.history_root / (identifier + ".json")
        self.assertNotIn(self.secret, receipt.read_text())
        self.assertEqual(0o600, stat.S_IMODE(receipt.stat().st_mode))
        self.assertEqual(["effortLevel"], list(self.manager.records()[0][1]["after"]))
        self.assertEqual([receipt], list(self.manager.history_root.iterdir()))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.manager.show(as_json=True)
        data = json.loads(output.getvalue())
        self.assertNotIn(self.secret, output.getvalue())
        self.assertEqual("not observed", data["runtime"])
        self.assertEqual(str(self.path), data["source"])
        row = next(row for row in data["options"] if row["key"] == "effortLevel")
        self.assertIn(identifier, row["origin"])
        self.assertIn("ignore", row["caveat"])
        exported = self.root / "export.json"
        self.manager.export(exported)
        self.assertNotIn(self.secret, exported.read_text())
        self.assertEqual({"model": "personal", "effortLevel": "high"}, read_profile(exported))
        self.assertEqual(0o600, stat.S_IMODE(exported.stat().st_mode))
        with self.assertRaises(StateError):
            self.manager.export(exported)

    def test_restore_refuses_intervening_selected_key_edits(self):
        identifier = self.apply(self.manager.plan({"model": "chosen", "language": "Korean"}))
        current = self.read()
        current["language"] = "English"
        self.write(current)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(StateError, "Restore conflict: language"):
            self.manager.restore_plan(identifier)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("chosen", self.read()["model"])

    def test_unset_restore_detects_null_and_missing_drift(self):
        identifier = self.apply(self.manager.plan(remove=("model",)))
        current = self.read()
        current["model"] = None
        self.write(current)
        with self.assertRaisesRegex(StateError, "Restore conflict"):
            self.manager.restore_plan(identifier)

    def test_stale_preview_and_forged_full_editor_plan_are_refused(self):
        plan = self.manager.plan({"model": "chosen"})
        self.path.write_bytes(self.path.read_bytes() + b" \n")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(StateError, "after preview"):
            self.apply(plan)
        self.assertEqual(before, self.path.read_bytes())
        plan = self.manager.plan({"model": "chosen"})
        bad = dict(self.original, env={})
        with self.assertRaisesRegex(StateError, "after preview"):
            self.apply(replace(plan, proposed=json.dumps(bad).encode()))
        with self.assertRaisesRegex(StateError, "Unsupported"):
            self.apply(replace(plan, after={"permissions": {}}))
        self.assertEqual(before, self.path.read_bytes())

    def test_dry_run_is_pure_even_when_home_absent_or_lock_held(self):
        absent = self.root / "absent"
        manager = ClaudeSettings(absent, dry_run=True)
        with contextlib.redirect_stdout(io.StringIO()):
            manager.apply(manager.plan({"language": "Korean"}))
        self.assertFalse(absent.exists())
        manager = ClaudeSettings(self.home, dry_run=True)
        before = self.path.read_bytes()
        with InstallerLock(self.home):
            locked = (self.home / ".hukuhaka-installer.lock").read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                manager.apply(manager.plan({"language": "Korean"}))
                manager.export(self.root / "never-written.json")
            self.assertEqual(locked, (self.home / ".hukuhaka-installer.lock").read_bytes())
        (self.home / ".hukuhaka-installer.lock").unlink()
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse((self.home / ".hukuhaka-installer.lock").exists())
        self.assertFalse(manager.history_root.exists())
        self.assertFalse((self.root / "never-written.json").exists())

    def test_real_apply_obeys_existing_installer_lock(self):
        before = self.path.read_bytes()
        with InstallerLock(self.home):
            with self.assertRaisesRegex(InstallerError, "already running"):
                self.apply(self.manager.plan({"language": "Korean"}))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], self.manager.records())

    def test_pending_transaction_recovery_requires_fresh_preview(self):
        before = self.path.read_bytes()
        transaction = FileTransaction(self.home)
        transaction.__enter__()
        transaction.write_bytes(self.path, json.dumps(dict(self.original, model="interrupted")).encode())
        stale = self.manager.plan({"model": "selected"})
        with self.assertRaisesRegex(StateError, "after preview"):
            self.apply(stale)
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(transaction.root.exists())
        self.assertEqual([], self.manager.records())
        self.apply(self.manager.plan({"model": "selected"}))
        self.assertEqual("selected", self.read()["model"])

    def test_failed_receipt_write_rolls_back_config_and_removes_receipt(self):
        before = self.path.read_bytes()
        original_write = FileTransaction.write_bytes

        def failing_write(transaction, target, content, mode=None):
            if target.parent == self.manager.history_root:
                raise OSError("simulated receipt failure")
            return original_write(transaction, target, content, mode)

        with mock.patch.object(FileTransaction, "write_bytes", failing_write):
            with self.assertRaisesRegex(OSError, "simulated"):
                self.apply(self.manager.plan({"model": "chosen"}))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], self.manager.records())
        self.assertFalse((self.home / ".hukuhaka-transactions").exists())

    def test_failed_verification_rolls_back_new_home_config(self):
        manager = ClaudeSettings(self.root / "new-home")
        original_decode = __import__("scripts.install.claude_settings", fromlist=["_decode"])._decode
        count = 0

        def fail_verification(raw, label):
            nonlocal count
            if manager.path.exists():
                count += 1
                raise StateError("simulated validation failure")
            return original_decode(raw, label)

        with mock.patch("scripts.install.claude_settings._decode", side_effect=fail_verification):
            with self.assertRaisesRegex(StateError, "simulated"):
                manager.apply(manager.plan({"autoMemoryEnabled": False}))
        self.assertEqual(1, count)
        self.assertFalse(manager.path.exists())
        self.assertEqual([], manager.records())

    def test_rejects_unknown_keys_types_and_effort_only_supported_choices(self):
        for key, value in (("permissions", {}), ("env", {}), ("model", 3),
                           ("language", []), ("effortLevel", "max"), ("effortLevel", "auto"),
                           ("autoMemoryEnabled", 1), ("autoMemoryEnabled", "false")):
            with self.assertRaises(StateError, msg=key):
                self.manager.plan({key: value})
        with self.assertRaises(StateError):
            self.manager.plan(remove=("permissions",))
        with self.assertRaises(StateError):
            self.manager.plan({"model": "a"}, remove=("model",))
        self.assertEqual("high", cli_value("effortLevel", "high"))
        self.assertEqual("Korean", cli_value("language", '"Korean"'))
        self.assertFalse(cli_value("autoMemoryEnabled", "false"))
        self.assertEqual(("low", "medium", "high", "xhigh"), CATALOG["effortLevel"].choices)

    def test_profiles_reject_duplicate_unknown_nonfinite_and_invalid_unicode(self):
        profile = self.root / "profile.json"
        for content in (b'{}', b'{"model":"a", "model":"b"}', b'{"model":2}',
                        b'{"env":{"TOKEN":"unknown"}}', b'[]', b'{"language":NaN}',
                        b'{"language":"\\ud800"}', b'{"language":"Korean",}', b'\xff'):
            profile.write_bytes(content)
            with self.assertRaises(StateError):
                read_profile(profile)

    def test_invalid_config_is_read_only_and_error_does_not_leak_raw_values(self):
        for content in (b'[]', b'{"private":"secret", "private":"secret"}',
                        b'{"private": NaN}', b'{"private": 1e999}', b'{"private":"\\ud800"}'):
            self.path.write_bytes(content)
            with self.assertRaises(StateError) as error:
                self.manager.plan({"language": "Korean"})
            self.assertNotIn("secret", str(error.exception))
            self.assertEqual(content, self.path.read_bytes())
        self.write(dict(self.original, language={"token": self.secret}))
        data = self.manager.snapshot()
        self.assertNotIn(self.secret, json.dumps(data))
        with self.assertRaises(StateError):
            self.manager.plan(remove=("language",))
        self.manager.plan({"autoMemoryEnabled": True})

    def test_corrupted_receipts_refuse_reads_and_writes(self):
        identifier = self.apply(self.manager.plan({"model": "chosen"}))
        path = self.manager.history_root / (identifier + ".json")
        valid = path.read_bytes()
        before = self.path.read_bytes()
        data = json.loads(valid)
        invalid = [dict(data, schemaVersion=True), dict(data, before={}),
                   dict(data, after={"model": False}), dict(data, label=self.secret),
                   dict(data, extra=self.secret), dict(data, before={"env": None}, after={"env": "bad"}),
                   dict(data, before=data["after"])]
        for item in invalid:
            path.write_text(json.dumps(item))
            with self.assertRaises(StateError):
                self.manager.records()
            with self.assertRaises(StateError):
                self.apply(self.manager.plan({"language": "Korean"}))
            self.assertEqual(before, self.path.read_bytes())
        path.write_bytes(valid)
        with self.assertRaises(StateError):
            self.manager.restore_plan("../../escaped")

    def test_symlink_settings_home_history_and_lock_are_refused(self):
        other = self.root / "other.json"
        other.write_text("{}")
        self.path.unlink()
        self.path.symlink_to(other)
        with self.assertRaises(StateError):
            self.manager.plan({"language": "Korean"})
        self.path.unlink()
        self.write(self.original)
        for target in (self.manager.history_root, self.home / ".hukuhaka-installer.lock"):
            target.symlink_to(other)
            with self.assertRaises(StateError):
                self.apply(self.manager.plan({"language": "Korean"}))
            target.unlink()
        linked = self.root / "linked"
        linked.symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(StateError):
            ClaudeSettings(linked).plan({"language": "Korean"})
        self.assertEqual("{}", other.read_text())

    def test_noop_preserves_original_bytes_and_file_mode(self):
        self.path.chmod(0o640)
        original = self.path.read_bytes()
        self.assertIsNone(self.apply(self.manager.plan({"model": "personal"})))
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse((self.home / ".hukuhaka-installer.lock").exists())
        self.apply(self.manager.plan({"model": "chosen"}))
        self.assertEqual(0o640, stat.S_IMODE(self.path.stat().st_mode))

    def test_wizard_accepts_explicit_selection_and_no_recommended_preset(self):
        with mock.patch("builtins.input", side_effect=["language", "Korean"]):
            with contextlib.redirect_stdout(io.StringIO()):
                plan = wizard(self.manager)
        self.assertEqual({"language": "Korean"}, plan.after)
        with mock.patch("builtins.input", return_value="recommended"):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(StateError):
                    wizard(self.manager)

    def test_public_python39_syntax(self):
        import scripts.install.claude_settings as module
        ast.parse(Path(module.__file__).read_text(), feature_version=(3, 9))


class SharedFilesystemSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()

    def test_lock_symlink_cannot_truncate_external_file(self):
        outside = self.root / "outside"
        outside.write_text("preserve external file")
        (self.home / ".hukuhaka-installer.lock").symlink_to(outside)
        with self.assertRaises(StateError):
            with InstallerLock(self.home):
                pass
        self.assertEqual("preserve external file", outside.read_text())

    def test_symlink_pending_transaction_directory_rejected_before_restore(self):
        outside = self.root / "outside-transaction"
        backup = outside / "backups" / "000000"
        backup.parent.mkdir(parents=True)
        backup.write_text("external snapshot")
        target = self.home / "target"
        target.write_text("preserve target")
        journal = outside / "journal.json"
        journal.write_text(json.dumps({"state": "pending", "entries": [
            {"target": str(target), "existed": True, "backup": "backups/000000"}]}))
        transactions = self.home / ".hukuhaka-transactions"
        transactions.mkdir()
        (transactions / "poisoned").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.home)
        self.assertEqual("preserve target", target.read_text())
        self.assertEqual("external snapshot", backup.read_text())
        self.assertTrue(journal.exists())

    def test_transaction_root_and_journal_symlinks_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        transactions = self.home / ".hukuhaka-transactions"
        transactions.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.home)
        with self.assertRaises(StateError):
            FileTransaction(self.home).__enter__()
        self.assertEqual([], list(outside.iterdir()))
        transactions.unlink()
        pending = transactions / "pending"
        pending.mkdir(parents=True)
        external_journal = outside / "journal.json"
        external_journal.write_text('{"state":"committed","entries":[]}')
        (pending / "journal.json").symlink_to(external_journal)
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.home)
        self.assertTrue(pending.exists())
        self.assertTrue(external_journal.exists())

    def test_symlinked_restore_parent_cannot_remove_external_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "target"
        target.write_text("preserve target")
        linked = self.home / "linked"
        linked.symlink_to(outside, target_is_directory=True)
        transaction = FileTransaction(self.home)
        transaction.__enter__()
        transaction.entries = [{"target": str(linked / "target"), "existed": False, "backup": "backups/000000"}]
        transaction._write_journal("pending")
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.home)
        self.assertEqual("preserve target", target.read_text())
        self.assertTrue(transaction.journal_path.exists())
        with self.assertRaises(StateError):
            transaction.snapshot(linked / "new-target")

    def test_backed_up_directory_symlink_is_restored_as_a_symlink(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "file").write_text("preserve outside")
        target = self.home / "linked"
        target.symlink_to(outside, target_is_directory=True)
        transaction = FileTransaction(self.home)
        transaction.__enter__()
        transaction.remove(target)
        target.mkdir()
        self.assertEqual(1, FileTransaction.recover_pending(self.home))
        self.assertTrue(target.is_symlink())
        self.assertEqual(outside.resolve(), target.resolve())
        self.assertEqual("preserve outside", (outside / "file").read_text())


class ClaudeSettingsCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka claude settings cli ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = Path(__file__).resolve().parents[2]
        self.home = self.root / "claude-home"
        self.home.mkdir()
        self.config = self.home / "settings.json"
        self.secret = "opaque-unknown-sentinel"
        self.original = {"model": "personal", "effortLevel": "medium", "env": {"PRIVATE_SENTINEL": self.secret}}
        self.config.write_text(json.dumps(self.original))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "unexpected-claude-call"
        fake = self.bin / "claude"
        fake.write_text('#!/bin/sh\nprintf "called\\n" >> "$UNEXPECTED_CLAUDE_LOG"\nexit 91\n')
        fake.chmod(0o755)
        self.env = {key: os.environ[key] for key in ("PATH", "LANG") if key in os.environ}
        self.env.update(HOME=str(self.root / "home"), CLAUDE_CONFIG_DIR=str(self.home),
                        CODEX_HOME=str(self.root / "codex-home"),
                        PATH=str(self.bin) + os.pathsep + self.env.get("PATH", os.defpath),
                        UNEXPECTED_CLAUDE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")

    def cli(self, *args):
        result = subprocess.run(("/bin/bash", str(self.source / "scripts/install.sh"),
                                 "--source-dir", str(self.source), "claude", "settings", *args),
                                cwd=str(self.source), env=self.env, capture_output=True, text=True, timeout=30)
        self.assertNotIn(self.secret, result.stdout + result.stderr)
        self.assertFalse(self.log.exists(), "settings commands must not invoke the Claude CLI")
        return result

    def success(self, *args):
        result = self.cli(*args)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def test_cli_partial_profile_diff_apply_export_and_restore(self):
        profile = self.root / "partial.json"
        profile.write_text('{"language":"Korean","autoMemoryEnabled":false}')
        before = self.config.read_bytes()
        self.success("diff", "--file", str(profile))
        self.assertEqual(before, self.config.read_bytes())
        self.assertFalse((self.home / ".hukuhaka-installer.lock").exists())
        self.success("apply", "--file", str(profile), "--yes")
        shown = json.loads(self.success("show", "--json").stdout)
        row = next(row for row in shown["options"] if row["key"] == "language")
        identifier = row["origin"].removeprefix("receipt ")
        self.assertEqual("Korean", row["value"])
        self.assertEqual("not observed", shown["runtime"])
        self.assertIn(identifier, self.success("history").stdout)
        exported = self.root / "exported.json"
        self.success("export", str(exported))
        self.assertEqual({"model": "personal", "effortLevel": "medium", "language": "Korean", "autoMemoryEnabled": False},
                         json.loads(exported.read_text()))
        current = json.loads(self.config.read_text())
        current["model"] = "later-personal"
        self.config.write_text(json.dumps(current))
        self.success("restore", identifier, "--yes")
        self.assertEqual(dict(self.original, model="later-personal"), json.loads(self.config.read_text()))

    def test_cli_set_unset_restore_and_dry_run_flags_at_both_levels(self):
        before = self.config.read_bytes()
        self.success("--dry-run", "set", "effortLevel", "high", "--yes")
        self.success("set", "effortLevel", "high", "--dry-run", "--yes")
        self.assertEqual(before, self.config.read_bytes())
        self.assertFalse((self.home / ".hukuhaka-claude-settings-history").exists())
        self.success("set", "effortLevel", "high", "--yes")
        self.assertEqual("high", json.loads(self.config.read_text())["effortLevel"])
        self.success("unset", "effortLevel", "--yes")
        self.assertNotIn("effortLevel", json.loads(self.config.read_text()))
        identifier = ClaudeSettings(self.home).records()[-1][0]
        self.success("restore", identifier, "--yes")
        self.assertEqual("high", json.loads(self.config.read_text())["effortLevel"])

    def test_cli_restore_conflict_and_unsupported_keys_are_read_only(self):
        self.success("set", "language", "Korean", "--yes")
        identifier = ClaudeSettings(self.home).records()[-1][0]
        current = json.loads(self.config.read_text())
        current["language"] = "English"
        self.config.write_text(json.dumps(current))
        before = self.config.read_bytes()
        result = self.cli("restore", identifier, "--yes")
        self.assertEqual(1, result.returncode)
        self.assertIn("Restore conflict", result.stderr)
        self.assertEqual(1, self.cli("set", "permissions", "{}", "--yes").returncode)
        self.assertEqual(1, self.cli("set", "effortLevel", "max", "--yes").returncode)
        self.assertEqual(2, self.cli("apply", "--recommended", "--yes").returncode)
        self.assertEqual(before, self.config.read_bytes())


class ClaudeRealE2EHarnessTests(unittest.TestCase):
    def test_missing_native_cli_fails_without_running_commands(self):
        from scripts.tests import claude_real_e2e
        with mock.patch.object(claude_real_e2e.shutil, "which", return_value=None):
            with mock.patch.object(claude_real_e2e.subprocess, "run") as runner:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = claude_real_e2e.main(["--source", str(Path(__file__).resolve().parents[2])])
        self.assertEqual(1, result)
        runner.assert_not_called()

    def test_environment_has_isolated_paths_and_no_ambient_auth(self):
        from scripts.tests.claude_real_e2e import isolated_environment
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret", "CLAUDE_CONFIG_DIR": "/ambient",
                                              "CODEX_HOME": "/ambient-codex", "PYTHONPATH": "/ambient-python"}):
                env = isolated_environment(root, Path(sys.executable))
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("PYTHONPATH", env)
            self.assertEqual(str(root / "claude-home"), env["CLAUDE_CONFIG_DIR"])
            self.assertEqual(str(root / "home"), env["HOME"])
            self.assertEqual(str(root / "codex-home"), env["CODEX_HOME"])
            self.assertTrue((root / "bin/claude").is_symlink())


if __name__ == "__main__":
    unittest.main()
