"""Profile ownership counterexamples using an isolated native-config stand-in."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.install.common import FileTransaction, InstallerError
from scripts.install.paseo import PaseoInstaller, profile_hash


class NativeProfiles:
    def __init__(self, path):
        self.path = path
        self.calls = []
        self.invalid = {}
        self.applied = True
        self.on_prepare = None
        self.live = []

    def require_cli(self):
        return "0.10.2"

    def prepare(self):
        self.calls.append("prepare")
        if self.on_prepare:
            self.on_prepare()

    def read_profiles(self):
        return copy.deepcopy(self.live)

    def saved_profiles(self):
        return copy.deepcopy(json.loads(self.path.read_text())["daemon"]["agentProfiles"])

    def reload_profiles(self, expected):
        self.calls.append("reload")
        if self.applied:
            self.live = copy.deepcopy(self.saved_profiles())
        return {"saved": True, "applied": self.applied, "notices": []}

    def validate_profile(self, row):
        return self.invalid.get(row["name"])

    def apply_profiles(self, before, after):
        if self.read_profiles() != before:
            raise InstallerError("native input changed", host="paseo")
        self.calls.append("write")
        config = json.loads(self.path.read_text())
        config["daemon"]["agentProfiles"] = after
        self.path.write_text(json.dumps(config))
        if self.applied:
            self.live = copy.deepcopy(after)
        return {"saved": True, "applied": self.applied, "notices": ["Unrelated plugin restart not performed"]}


class PaseoInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.source = self.root / "source"
        self.source.mkdir()
        self.roles = ["advisor-gpt", "advisor-claude", "worker", "scouter"]
        self.catalog = {"components": []}
        self.values = {}
        for role in self.roles:
            data = {"name": role, "provider": "codex", "model": "model-one", "modeId": "auto",
                    "thinkingOptionId": "high", "notes": "Use for " + role}
            if role == "scouter":
                data["featureValues"] = {"fast_mode": True}
            self.values[role] = data
            (self.source / (role + ".json")).write_text(json.dumps(data))
            self.catalog["components"].append({"name": role, "kind": "profile", "path": role + ".json", "hosts": {"paseo": {}}})
        self.path = self.home / "config.json"
        self.path.write_text(json.dumps({"version": 1, "daemon": {"agentProfiles": [], "unchanged": {"setting": 7}},
                                         "agents": {"providers": {"personal": {"private": "not-for-output"}}}}))
        self.native = NativeProfiles(self.path)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"PASEO_HOME": str(self.home)}).start()
        patch("scripts.install.paseo.LocalPaseoTransport", return_value=self.native).start()
        self.out = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.out)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def installer(self, **kw):
        return PaseoInstaller(self.source, self.catalog, "1.4.0", **kw)

    def save_profiles(self, profiles):
        config = json.loads(self.path.read_text())
        config["daemon"]["agentProfiles"] = profiles
        self.path.write_text(json.dumps(config))
        self.native.live = copy.deepcopy(profiles)

    def existing(self, role="worker", identity="user-profile", **kw):
        row = dict(copy.deepcopy(self.values[role]), id=identity)
        row.update(kw)
        return row

    def update_source(self, role, **kw):
        self.values[role].update(kw)
        (self.source / (role + ".json")).write_text(json.dumps(self.values[role]))

    def test_fresh_then_repeat_is_one_write_and_preserves_unrelated_config(self):
        before = json.loads(self.path.read_text())
        first = self.installer()
        first.install(self.roles)
        installed = self.native.read_profiles()
        self.installer().install(self.roles)
        self.assertEqual(installed, self.native.read_profiles())
        self.assertEqual(1, self.native.calls.count("write"))
        after = json.loads(self.path.read_text())
        after["daemon"]["agentProfiles"] = []
        self.assertEqual(before, after)
        self.assertNotIn("not-for-output", self.out.getvalue())

    def test_adopt_preserves_bytes_and_uninstall_keeps_user_profiles(self):
        user = self.existing(model="custom-model", customField={"future": True})
        self.save_profiles([user])
        before = self.path.read_bytes()
        installer = self.installer(adopt={"worker": user["id"]})
        installer.install(["worker"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("local override", installer.status()["roles"][2]["status"])
        self.installer().uninstall()
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], self.installer().status()["components"])
        self.assertNotIn("write", self.native.calls)

    def test_advisor_migration_changes_only_name_and_notes(self):
        original = self.existing("advisor-gpt", name="advisor", notes="old note", model="personal-model")
        self.save_profiles([original])
        installer = self.installer(adopt={"advisor-gpt": original["id"]}, rename_adopted=["advisor-gpt"])
        preview = installer.preview(["advisor-gpt", "advisor-claude"])
        self.assertEqual("adopt + rename", preview.actions[0]["action"])
        installer.install(["advisor-gpt", "advisor-claude"])
        migrated = self.native.read_profiles()[0]
        self.assertEqual(dict(original, name="advisor-gpt", notes=self.values["advisor-gpt"]["notes"]), migrated)
        self.assertEqual(2, len(self.native.read_profiles()))
        self.installer().uninstall()
        self.assertEqual([migrated], self.native.read_profiles())

    def test_name_match_is_not_adoption_and_does_not_create_duplicate(self):
        user = self.existing()
        self.save_profiles([user])
        with self.assertRaisesRegex(InstallerError, "explicit|adopt"):
            self.installer().install(["worker", "scouter"])
        self.assertEqual(["worker", "scouter"], [p["name"] for p in self.native.read_profiles()])
        self.assertEqual({"scouter"}, self.installer().current_components())

    def test_local_override_prevents_source_upgrade_until_explicit_reset(self):
        self.installer().install(["scouter"])
        profiles = self.native.read_profiles()
        profiles[0]["thinkingOptionId"] = "xhigh"
        self.save_profiles(profiles)
        self.update_source("scouter", model="model-two", featureValues={"fast_mode": False})
        self.installer().install(["scouter"])
        self.assertEqual(profiles, self.native.read_profiles())
        self.installer().install(["scouter"], reset=True)
        row = self.native.read_profiles()[0]
        self.assertEqual("model-two", row["model"])
        self.assertEqual(profiles[0]["id"], row["id"])

    def test_unchanged_profile_updates_source_and_uninstall_removes_it(self):
        self.installer().install(["worker"])
        identity = self.native.read_profiles()[0]["id"]
        self.update_source("worker", model="model-two")
        self.installer().install(["worker"])
        self.assertEqual("model-two", self.native.read_profiles()[0]["model"])
        self.assertEqual(identity, self.native.read_profiles()[0]["id"])
        self.installer().uninstall()
        self.assertEqual([], self.native.read_profiles())

    def test_edited_created_profile_released_on_uninstall_even_with_force(self):
        self.installer().install(["worker"])
        rows = self.native.read_profiles()
        rows[0]["name"] = "My worker"
        self.save_profiles(rows)
        self.installer(force=True).uninstall()
        self.assertEqual(rows, self.native.read_profiles())
        self.assertEqual(set(), self.installer().current_components())

    def test_one_uuid_cannot_be_claimed_twice(self):
        self.save_profiles([self.existing()])
        with self.assertRaisesRegex(InstallerError, "multiple roles"):
            self.installer(adopt={"worker": "user-profile", "scouter": "user-profile"}).plan(["worker", "scouter"])
        self.installer(adopt={"worker": "user-profile"}).install(["worker"])
        with self.assertRaisesRegex(InstallerError, "another role"):
            self.installer(adopt={"scouter": "user-profile"}).plan(["scouter"])

    def test_missing_owned_profile_recreated_once(self):
        self.installer().install(["worker"])
        first_id = self.native.read_profiles()[0]["id"]
        self.save_profiles([])
        self.installer().install(["worker"])
        self.assertNotEqual(first_id, self.native.read_profiles()[0]["id"])
        self.assertEqual(1, len(self.native.read_profiles()))

    def test_dry_run_does_not_create_receipts_or_prepare_runtime(self):
        before = self.path.read_bytes()
        installer = self.installer(dry_run=True)
        installer.preview(self.roles)
        installer.install(self.roles)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], self.native.calls)
        self.assertFalse((self.home / "hk-config.toml").exists())
        self.assertFalse((self.home / "hk-operation.lock").exists())

    def test_edit_after_preview_aborts_before_any_native_setup(self):
        installer = self.installer()
        installer.preview(["worker"])
        self.save_profiles([self.existing(name="unrelated")])
        with self.assertRaisesRegex(InstallerError, "changed after preview"):
            installer.install(["worker"])
        self.assertEqual([], self.native.calls)

    def test_edit_during_setup_aborts_without_profile_write(self):
        self.native.on_prepare = lambda: self.save_profiles([self.existing(name="unrelated")])
        with self.assertRaisesRegex(InstallerError, "changed since preview"):
            self.installer().install(["worker"])
        self.assertNotIn("write", self.native.calls)

    def test_saved_not_applied_is_partial_and_never_rolled_back(self):
        self.native.applied = False
        installer = self.installer()
        with self.assertRaisesRegex(InstallerError, "saved but not confirmed"):
            installer.install(["worker"])
        self.assertEqual(1, len(self.native.saved_profiles()))
        record = installer.state.read()
        self.assertEqual("partial", record["operations"][-1]["status"])
        receipt = record["components"]["worker"]["receipt"]
        self.assertEqual("created", receipt["origin"])
        self.assertFalse(receipt["applied"])
        self.native.applied = True
        self.installer().install(["worker"])
        self.assertEqual(1, self.native.calls.count("write"))
        self.assertEqual(1, self.native.calls.count("reload"))
        self.assertTrue(self.installer()._receipts()["worker"]["applied"])
        self.installer().uninstall()
        self.assertEqual([], self.native.saved_profiles())

    def test_unsupported_profile_skipped_without_dropping_fast_flag(self):
        self.native.invalid["scouter"] = "fast_mode not supported"
        with self.assertRaisesRegex(InstallerError, "fast_mode"):
            self.installer().install(["scouter", "worker"])
        self.assertEqual(["worker"], [p["name"] for p in self.native.read_profiles()])
        self.assertEqual({"worker"}, self.installer().current_components())

    def test_desired_set_omissions_preview_release_and_removal(self):
        self.save_profiles([self.existing()])
        self.installer(adopt={"worker": "user-profile"}).install(["worker", "scouter"])
        plan = self.installer().preview(["advisor-claude"])
        self.assertEqual({("advisor-claude", "create"), ("worker", "release"), ("scouter", "remove")},
                         {(a["role"], a["action"]) for a in plan.actions})

    def test_profile_future_fields_count_as_override(self):
        self.installer().install(["worker"])
        profiles = self.native.read_profiles()
        profiles[0]["future"] = {"value": "preserve"}
        self.save_profiles(profiles)
        self.installer().install(["worker"])
        self.assertEqual(profiles, self.native.read_profiles())

    def test_config_and_state_symlinks_refused(self):
        target = self.home / "other.json"
        self.path.rename(target)
        self.path.symlink_to(target)
        with self.assertRaisesRegex(InstallerError, "symlink"):
            self.installer()

    def test_duplicate_ids_or_json_keys_refused(self):
        self.save_profiles([self.existing(), self.existing()])
        with self.assertRaisesRegex(InstallerError, "Duplicate"):
            self.installer().status()
        self.path.write_text('{"daemon":{},"daemon":{}}')
        with self.assertRaisesRegex(InstallerError, "strict"):
            self.installer().status()

    def test_recovery_never_restores_shared_config_snapshot(self):
        installer = self.installer()
        tx = FileTransaction(self.home)
        tx.__enter__()
        tx.snapshot(self.path)
        modified = [self.existing()]
        self.save_profiles(modified)
        with self.assertRaisesRegex(InstallerError, "non-receipt"):
            installer._recover_receipts()
        self.assertEqual(modified, self.native.read_profiles())

    def test_source_hash_ignores_uuid_but_not_unknown_fields(self):
        first = self.existing(identity="one")
        second = self.existing(identity="two")
        self.assertEqual(profile_hash(first), profile_hash(second))
        second["icon"] = "user-choice"
        self.assertNotEqual(profile_hash(first), profile_hash(second))

    def test_unknown_native_write_outcome_is_partial_without_rollback(self):
        from scripts.install.paseo_transport import PaseoTransportError
        original = self.native.apply_profiles
        def uncertain(before, after):
            original(before, after)
            raise PaseoTransportError("Connection lost after write", mutation_attempted=True)
        self.native.apply_profiles = uncertain
        installer = self.installer()
        with self.assertRaisesRegex(InstallerError, "Connection lost"):
            installer.install(["worker"])
        self.assertEqual(1, len(self.native.read_profiles()))
        self.assertEqual("partial", installer.state.read()["operations"][-1]["status"])
        self.assertFalse(installer._receipts()["worker"]["applied"])
        self.installer().install(["worker"])
        self.assertTrue(installer._receipts()["worker"]["applied"])

    def test_recover_missing_receipt_file_preserves_later_profile_edit(self):
        installer = self.installer()
        installer.install(["worker"])
        rows = self.native.read_profiles()
        rows[0]["name"] = "Edited after interruption"
        self.save_profiles(rows)
        before = self.path.read_bytes()
        installer.state.path.unlink()
        installer.recover()
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue(installer.state.path.is_file())

    def test_unsupported_existing_profile_keeps_order_during_deselection(self):
        self.installer().install(["advisor-gpt", "worker", "scouter"])
        original = self.native.read_profiles()
        self.native.invalid["worker"] = "provider unavailable"
        self.installer().install(["worker", "scouter"])
        self.assertEqual(original[1:], self.native.read_profiles())

    def test_pending_create_failed_before_save_reuses_intended_uuid(self):
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        installer = self.installer()
        with self.assertRaisesRegex(InstallerError, "save was not confirmed"):
            installer.install(["worker"])
        identity = installer._receipts()["worker"]["id"]
        self.assertEqual([], self.native.saved_profiles())
        self.native.apply_profiles = original
        self.installer().install(["worker"])
        self.assertEqual(identity, self.native.read_profiles()[0]["id"])

    def test_pending_update_before_save_retries_original_not_user_override(self):
        self.installer().install(["worker"])
        original = self.native.apply_profiles
        self.update_source("worker", model="model-two")
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        self.native.apply_profiles = original
        self.installer().install(["worker"])
        self.assertEqual("model-two", self.native.read_profiles()[0]["model"])

    def test_pending_update_preserves_third_value_user_edit(self):
        self.installer().install(["worker"])
        self.update_source("worker", model="model-two")
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        rows = self.native.saved_profiles()
        rows[0]["model"] = "user-model"
        self.save_profiles(rows)
        self.native.apply_profiles = original
        self.installer().install(["worker"])
        self.assertEqual(rows, self.native.read_profiles())
        receipt = self.installer()._receipts()["worker"]
        self.assertTrue(receipt["applied"])
        self.assertNotIn("previous_sha256", receipt)

    def test_reset_preserves_unknown_fields_and_source_match_refreshes_hash(self):
        self.installer().install(["worker"])
        self.update_source("worker", model="model-two")
        rows = self.native.read_profiles()
        rows[0]["model"] = "model-two"
        self.save_profiles(rows)
        self.installer().install(["worker"])
        self.assertEqual(profile_hash(self.values["worker"]), self.installer()._receipts()["worker"]["source_sha256"])
        rows[0]["futureField"] = True
        self.save_profiles(rows)
        self.installer().install(["worker"], reset=True)
        self.assertTrue(self.native.read_profiles()[0]["futureField"])

    def test_plain_adoption_does_not_require_available_model(self):
        row = self.existing(model="retired-model")
        self.save_profiles([row])
        self.native.invalid["worker"] = "model unavailable"
        self.installer(adopt={"worker": row["id"]}).install(["worker"])
        self.assertEqual(row, self.native.read_profiles()[0])
        self.assertNotIn("write", self.native.calls)

    def test_failed_batch_does_not_turn_untouched_override_into_update_intent(self):
        self.installer().install(["worker", "scouter"])
        rows = self.native.read_profiles()
        rows[1]["model"] = "personal-scouter"
        self.save_profiles(rows)
        self.update_source("worker", model="model-two")
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker", "scouter"])
        self.assertNotIn("pending_action", self.installer()._receipts()["scouter"])
        self.native.apply_profiles = original
        self.installer().install(["worker", "scouter"])
        self.assertEqual(rows[1], self.native.read_profiles()[1])
        self.assertEqual("model-two", self.native.read_profiles()[0]["model"])

    def test_failed_batch_preserves_plain_adoption_and_rename_scope_on_retry(self):
        advisor = self.existing("advisor-gpt", identity="advisor-id", name="advisor", model="personal-advisor")
        worker = self.existing("worker", identity="worker-id", model="personal-worker")
        self.save_profiles([advisor, worker])
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer(adopt={"advisor-gpt": "advisor-id", "worker": "worker-id"},
                           rename_adopted=["advisor-gpt"]).install(["advisor-gpt", "worker", "scouter"])
        self.native.apply_profiles = original
        self.installer().install(["advisor-gpt", "worker", "scouter"])
        rows = self.native.read_profiles()
        self.assertEqual(dict(advisor, name="advisor-gpt", notes=self.values["advisor-gpt"]["notes"]), rows[0])
        self.assertEqual(worker, rows[1])

    def test_unsaved_pending_update_can_remove_previous_unmodified_version(self):
        self.installer().install(["worker"])
        self.update_source("worker", model="model-two")
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        self.native.apply_profiles = original
        self.installer().uninstall()
        self.assertEqual([], self.native.saved_profiles())

    def test_dropped_pending_create_without_saved_row_discards_intent_only(self):
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        self.native.apply_profiles = original
        self.installer().uninstall()
        self.assertEqual([], self.native.saved_profiles())
        self.assertEqual({}, self.installer()._receipts())

    def test_saved_intermediate_source_remains_removable_after_later_retry_failure(self):
        self.installer().install(["worker"])
        self.update_source("worker", model="model-two")
        self.native.applied = False
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        self.native.applied = True
        self.update_source("worker", model="model-three")
        original = self.native.apply_profiles
        self.native.apply_profiles = lambda before, after: {"saved": False, "applied": False}
        with self.assertRaises(InstallerError):
            self.installer().install(["worker"])
        self.assertEqual("model-two", self.native.saved_profiles()[0]["model"])
        self.native.apply_profiles = original
        self.installer().uninstall()
        self.assertEqual([], self.native.saved_profiles())


if __name__ == "__main__":
    unittest.main()
