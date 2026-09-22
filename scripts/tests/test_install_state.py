from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.common import FileTransaction, StateError, installer_state
from scripts.install.state import InstallState, decode_state, encode_state


class InstallStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"
        self.store = InstallState(self.home)
        self.legacy = self.home / ".hukuhaka-reader-manifest.json"
        self.receipt = {"schemaVersion": 4, "component": "reader", "version": "0.2.0",
                        "agentTarget": "agents/reader.toml", "agentHash": "a" * 64,
                        "resources": [{"target": "reader/tool.py", "hash": "b" * 64}]}

    def put(self, receipt=None):
        with installer_state(self.home, dry_run=False), FileTransaction(self.home) as tx:
            self.store.put_receipt(tx, "reader", receipt or self.receipt, "agent", "1.2.0", self.legacy)
            tx.commit()

    def legacy_receipt(self):
        self.home.mkdir(exist_ok=True)
        self.legacy.write_text(json.dumps(self.receipt))
        return self.legacy.read_bytes()

    def test_absent_and_legacy_reads_are_pure(self):
        self.assertEqual({"schema_version": 1, "components": {}, "operations": []}, self.store.read())
        self.assertIsNone(self.store.receipt("reader", self.legacy))
        self.assertFalse(self.home.exists())
        original = self.legacy_receipt()
        self.assertEqual(self.receipt, self.store.receipt("reader", self.legacy))
        self.assertEqual(original, self.legacy.read_bytes())
        self.assertEqual([self.legacy], list(self.home.iterdir()))

    def test_migration_preserves_receipt_and_unknown_install_time_with_backup(self):
        original = self.legacy_receipt()
        updated = dict(self.receipt, version="0.3.0")
        self.put(updated)
        record = self.store.read()["components"]["reader"]
        self.assertEqual(updated, record["receipt"])
        self.assertEqual("0.3.0", record["version"])
        self.assertEqual("unknown", record["installed_at"])
        self.assertEqual("legacy", record["provenance"])
        self.assertEqual("0.2.0", record["migrated_from_version"])
        self.assertFalse(self.legacy.exists())
        backups = list((self.home / "hk-backups/legacy").iterdir())
        self.assertEqual([original], [path.read_bytes() for path in backups])
        self.assertEqual([backups[0].relative_to(self.home).as_posix()], record["backups"])
        self.put(dict(updated, version="0.4.0"))
        self.assertEqual("unknown", self.store.read()["components"]["reader"]["installed_at"])
        self.assertEqual("0.2.0", self.store.read()["components"]["reader"]["migrated_from_version"])
        self.assertEqual(record["backups"], self.store.read()["components"]["reader"]["backups"])
        self.assertEqual("0.3.0", decode_state(self.store.backup_path.read_bytes())["components"]["reader"]["version"])

    def test_state_and_legacy_backup_roll_back_with_payload_transaction(self):
        original = self.legacy_receipt()
        payload = self.home / "agent.toml"
        payload.write_bytes(b"old")
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with installer_state(self.home, dry_run=False), FileTransaction(self.home) as tx:
                tx.write_bytes(payload, b"new")
                self.store.put_receipt(tx, "reader", self.receipt, "agent", "1.2.0", self.legacy)
                raise RuntimeError("failure after receipt migration")
        self.assertEqual(b"old", payload.read_bytes())
        self.assertEqual(original, self.legacy.read_bytes())
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.store.backup_path.exists())
        self.assertFalse(list((self.home / "hk-backups").rglob("*.json")))

    def test_conflicting_or_symlinked_legacy_is_not_masked_by_central(self):
        self.put()
        before = self.store.path.read_bytes()
        self.legacy.write_text(json.dumps(dict(self.receipt, version="different")))
        with self.assertRaises(StateError):
            self.store.receipt("reader", self.legacy)
        self.legacy.unlink()
        self.legacy.symlink_to(self.home / "missing")
        with self.assertRaises(StateError):
            self.store.receipt("reader", self.legacy)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_remove_migrates_legacy_backup_without_touching_other_records(self):
        original = self.legacy_receipt()
        self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        with installer_state(self.home, dry_run=False), FileTransaction(self.home) as tx:
            self.store.remove_receipt(tx, "reader", self.legacy)
            tx.commit()
        self.assertEqual({"worklog"}, set(self.store.read()["components"]))
        self.assertEqual([original], [path.read_bytes() for path in (self.home / "hk-backups/legacy").iterdir()])
        self.assertFalse(self.legacy.exists())
        self.store.remove_plugin("worklog")
        self.assertEqual({}, self.store.read()["components"])

    def test_toml_round_trip_and_standard_parser_agree(self):
        self.put()
        identity = self.store.begin_operation("install", "1.2.0", ["reader"])
        self.store.update_operation(identity, "agent", ["reader"])
        self.store.finish_operation(identity, "failed", ["reader"], {"stage": "agent", "type": "StateError", "message": "secret"})
        data = self.store.read()
        data["components"]["reader"]["receipt"]["prefix"] = '한글 🙂\nquote " slash \\ tab\t\x7f' + "".join(chr(value) for value in range(32))
        raw = encode_state(data)
        self.assertEqual(data, decode_state(raw))
        self.assertIn(b'[["components"."reader"."receipt"."resources"]]', raw)
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return  # Optional independent parser; never a runtime dependency.
        self.assertEqual(data, tomllib.loads(raw.decode()))

    def test_unrepresentable_nested_receipts_are_rejected_without_loss(self):
        self.put()
        original = self.store.path.read_bytes(), self.store.backup_path.read_bytes()
        for value in (None, 1.5, ["mixed", {"target": "x"}], [1, 2], 2 ** 63, "\ud800"):
            with self.subTest(value=repr(value)):
                receipt = dict(self.receipt, nested={"entries": [{"unsupported": value}]})
                with self.assertRaises(StateError):
                    self.put(receipt)
                self.assertEqual(original, (self.store.path.read_bytes(), self.store.backup_path.read_bytes()))

    def test_invalid_state_and_unsupported_toml_never_repair_on_read(self):
        self.home.mkdir()
        valid = encode_state(self.store.read())
        invalids = [valid + b'"schema_version" = 1\n', b'schema_version = 2\ncomponents = []\noperations = []\n',
                    b'schema_version = true\n[components]\n', valid + b'["components"]\n',
                    b'schema_version = 1.5\n', b'\xff', valid.replace(b'"schema_version" = 1', b'"schema_version" = null'),
                    valid + b'[["operations"]]\n']
        for raw in invalids:
            with self.subTest(raw=raw):
                self.store.path.write_bytes(raw)
                with self.assertRaises(StateError):
                    self.store.read()
                self.assertEqual(raw, self.store.path.read_bytes())
                self.assertFalse(self.store.backup_path.exists())

    def test_corrupt_restore_requires_valid_backup_and_preserves_original(self):
        self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        backup = self.store.backup_path.read_bytes()
        corrupt = b"broken TOML\n"
        self.store.path.write_bytes(corrupt)
        reference = self.store.restore_backup()
        self.assertEqual(backup, self.store.path.read_bytes())
        self.assertEqual(corrupt, (self.home / reference).read_bytes())
        self.assertEqual([corrupt], [path.read_bytes() for path in (self.home / "hk-backups").glob("state-*.toml")])
        self.store.path.write_bytes(corrupt)
        self.store.backup_path.write_bytes(b"also broken")
        with self.assertRaises(StateError):
            self.store.restore_backup()
        self.assertEqual(corrupt, self.store.path.read_bytes())

    def test_missing_primary_preserves_backup_until_explicit_recovery(self):
        self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        identity = self.store.begin_operation("install", "1.2.0", ["worklog"])
        self.store.finish_operation(identity, "success", ["worklog"])
        backup = self.store.backup_path.read_bytes()
        expected = decode_state(backup)
        self.store.path.unlink()
        with self.assertRaisesRegex(StateError, "state recover"):
            self.store.read()
        with self.assertRaisesRegex(StateError, "state recover"):
            self.store.begin_operation("install", "1.3.0", ["reader"])
        self.assertFalse(self.store.path.exists())
        self.assertEqual(backup, self.store.backup_path.read_bytes())
        self.assertIsNone(self.store.restore_backup())
        self.assertEqual(expected, self.store.read())
        self.assertEqual("0.5.0", self.store.read()["components"]["worklog"]["version"])
        self.assertEqual(identity, self.store.read()["operations"][-1]["id"])

    def test_explicit_transaction_recovery_precedes_older_record_backup(self):
        self.assertFalse(self.store.has_pending_transactions())
        self.assertFalse(self.home.exists())
        self.put()
        self.put(dict(self.receipt, version="0.3.0"))
        expected = self.store.read()
        older_backup = self.store.backup_path.read_bytes()
        self.assertEqual("0.2.0", decode_state(older_backup)["components"]["reader"]["version"])
        payload = self.home / "agent.toml"
        payload.write_bytes(b"original")
        tx = FileTransaction(self.home)
        tx.__enter__()
        tx.write_bytes(payload, b"uncommitted")
        tx.remove(self.store.path)
        journal_before = tx.journal_path.read_bytes()
        self.assertTrue(self.store.has_pending_transactions())
        with self.assertRaisesRegex(StateError, "pending transaction recovery"):
            self.store.read()
        with self.assertRaisesRegex(StateError, "pending file transactions"):
            self.store.restore_backup()
        self.assertFalse(self.store.path.exists())
        self.assertEqual(journal_before, tx.journal_path.read_bytes())
        self.assertEqual(b"uncommitted", payload.read_bytes())
        self.assertEqual(1, self.store.recover_transactions())
        self.assertEqual(expected, self.store.read())
        self.assertEqual(older_backup, self.store.backup_path.read_bytes())
        self.assertEqual(b"original", payload.read_bytes())
        self.assertFalse(self.store.has_pending_transactions())

    def test_pending_detection_rejects_unsafe_or_malformed_journals(self):
        self.home.mkdir()
        root = self.home / ".hukuhaka-transactions"
        root.symlink_to(self.home / "missing")
        with self.assertRaises(StateError):
            self.store.has_pending_transactions()
        root.unlink()
        transaction = root / "interrupted"
        transaction.mkdir(parents=True)
        journal = transaction / "journal.json"
        journal.write_text('{"state": "unknown", "entries": []}')
        before = journal.read_bytes()
        with self.assertRaises(StateError):
            self.store.recover_transactions()
        self.assertEqual(before, journal.read_bytes())

    def test_unsafe_state_and_backup_paths_are_rejected(self):
        self.home.mkdir()
        self.store.path.symlink_to(self.home / "missing")
        with self.assertRaises(StateError):
            self.store.read()
        self.store.path.unlink()
        self.store.path.mkdir()
        with self.assertRaises(StateError):
            self.store.read()
        self.store.path.rmdir()
        self.store.backup_path.symlink_to(self.home / "outside")
        with self.assertRaises(StateError):
            self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        self.assertFalse(self.store.path.exists())

    def test_pending_operations_become_interrupted_and_errors_are_structural(self):
        first = self.store.begin_operation("reset", "1.2.0", ["reader"])
        self.store.update_operation(first, "remove-reader", ["worklog"])
        second = self.store.begin_operation("install", "1.3.0", ["reader"])
        old, current = self.store.read()["operations"]
        self.assertEqual("interrupted", old["status"])
        self.assertEqual(["worklog"], old["completed"])
        self.assertEqual("remove-reader", old["stage"])
        self.assertEqual("running", current["status"])
        self.store.finish_operation(second, "partial", [], {"stage": "reader", "type": "StateError", "message": "SECRET"})
        self.assertNotIn("SECRET", self.store.path.read_text())
        self.assertEqual({"stage": "reader", "type": "StateError"}, self.store.read()["operations"][-1]["error"])
        with self.assertRaises(StateError):
            self.store.update_operation(first, "overwrite-finished", [])

    def test_history_keeps_last_fifty_terminal_records_and_active_operation(self):
        first = self.store.begin_operation("install", "1", [])
        data = self.store.read()
        template = data["operations"][0]
        data["operations"] = [dict(template, id=str(index), status="success", finished_at="observed") for index in range(55)]
        data["operations"].append(dict(template, id=first))
        self.store.path.write_bytes(encode_state(data))
        latest = self.store.begin_operation("install", "2", [])
        records = self.store.read()["operations"]
        self.assertEqual(51, len(records))
        self.assertEqual(latest, records[-1]["id"])
        self.assertEqual(first, records[-2]["id"])
        self.assertEqual("interrupted", records[-2]["status"])

    def test_failed_state_write_restores_previous_backup_and_state(self):
        self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        before = self.store.path.read_bytes(), self.store.backup_path.read_bytes()
        original = FileTransaction.write_bytes
        def fail_state(tx, target, content, mode=None):
            if target == self.store.path:
                raise OSError("failed state publication")
            original(tx, target, content, mode)
        with mock.patch.object(FileTransaction, "write_bytes", fail_state), self.assertRaises(OSError):
            self.store.set_plugin("worklog", "0.6.0", "1.3.0")
        self.assertEqual(before, (self.store.path.read_bytes(), self.store.backup_path.read_bytes()))

    def test_next_writer_recovers_interrupted_receipt_and_payload_together(self):
        self.put()
        payload = self.home / "agent.toml"
        payload.write_bytes(b"old")
        tx = FileTransaction(self.home)
        tx.__enter__()
        tx.write_bytes(payload, b"uncommitted")
        self.store.put_receipt(tx, "reader", dict(self.receipt, version="0.3.0"), "agent", "1.3.0", self.legacy)
        # Simulate process exit: leave its journal intact and release no transaction.
        self.assertEqual("0.3.0", self.store.read()["components"]["reader"]["version"])
        self.store.set_plugin("worklog", "0.5.0", "1.3.0")
        self.assertEqual(b"old", payload.read_bytes())
        self.assertEqual("0.2.0", self.store.read()["components"]["reader"]["version"])
        self.assertEqual("0.5.0", self.store.read()["components"]["worklog"]["version"])
        self.assertFalse(tx.root.exists())

    def test_operation_versions_and_backup_references_survive_upgrade_and_removal(self):
        original = self.legacy_receipt()
        self.store.set_plugin("worklog", "0.5.0", "1.2.0")
        identity = self.store.begin_operation("install", "1.3.0", ["reader", "worklog"])
        self.put(dict(self.receipt, version="0.3.0"))
        self.store.set_plugin("worklog", "0.6.0", "1.3.0")
        self.store.finish_operation(identity, "success", ["reader", "worklog"])
        operation = self.store.read()["operations"][-1]
        self.assertEqual({"reader": "0.2.0", "worklog": "0.5.0"}, operation["components_before"])
        self.assertEqual({"reader": "0.3.0", "worklog": "0.6.0"}, operation["components_after"])
        self.assertEqual([original], [(self.home / reference).read_bytes() for reference in operation["backups"]])
        removal = self.store.begin_operation("remove", "1.3.0", ["reader"])
        with installer_state(self.home, dry_run=False), FileTransaction(self.home) as tx:
            self.store.remove_receipt(tx, "reader", self.legacy)
            tx.commit()
        self.store.finish_operation(removal, "success", ["reader"])
        after = self.store.read()
        self.assertEqual(operation, after["operations"][-2])
        self.assertEqual({"worklog": "0.6.0"}, after["operations"][-1]["components_after"])
        self.assertEqual(operation["backups"], after["operations"][-1]["backups"])

    def test_legacy_removal_records_previous_version_and_backup(self):
        original = self.legacy_receipt()
        identity = self.store.begin_operation("remove", "1.3.0", ["reader"])
        with installer_state(self.home, dry_run=False), FileTransaction(self.home) as tx:
            self.store.remove_receipt(tx, "reader", self.legacy)
            tx.commit()
        self.store.finish_operation(identity, "success", ["reader"])
        operation = self.store.read()["operations"][-1]
        self.assertEqual({"reader": "0.2.0"}, operation["components_before"])
        self.assertEqual({}, operation["components_after"])
        self.assertEqual([original], [(self.home / reference).read_bytes() for reference in operation["backups"]])

    def test_unknown_kind_and_status_fail_without_rewriting_state(self):
        self.put()
        original = self.store.path.read_bytes()
        data = self.store.read()
        data["components"]["reader"]["kind"] = "arbitrary"
        with self.assertRaises(StateError):
            encode_state(data)
        identity = self.store.begin_operation("install", "1.3.0", [])
        original = self.store.path.read_bytes()
        with self.assertRaises(StateError):
            self.store.finish_operation(identity, "arbitrary", [])
        self.assertEqual(original, self.store.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
