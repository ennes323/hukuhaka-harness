from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import verification as v


class VerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / "tree"
        self.tree.mkdir()
        (self.tree / "input").write_text("original")
        self.cache = self.root / "receipts"
        self.environment = "environment-one"
        self.action = mock.Mock(return_value="check output")
        self.clean_env = mock.patch.dict(os.environ, {v.FRESH_ENV: "0"})
        self.clean_env.start()
        self.addCleanup(self.clean_env.stop)

    def check(self, action=None):
        return v.run_verified(
            "test", lambda: {"tree": v.tree_digest(self.tree), "environment": self.environment},
            action or self.action, cache=self.cache,
        )

    def receipt(self) -> Path:
        return next(self.cache.glob("*.json"))

    def test_identical_success_reuses_without_executing_or_storing_output(self) -> None:
        self.assertFalse(self.check().reused)
        result = self.check()
        self.assertTrue(result.reused)
        self.action.assert_called_once()
        self.assertNotIn("check output", self.receipt().read_text())

    def test_content_mode_path_and_environment_changes_each_run_again(self) -> None:
        self.check()
        (self.tree / "input").write_text("different")
        self.assertFalse(self.check().reused)
        (self.tree / "input").chmod(0o755)
        self.assertFalse(self.check().reused)
        (self.tree / "input").rename(self.tree / "renamed")
        self.assertFalse(self.check().reused)
        (self.tree / "empty-directory").mkdir()
        self.assertFalse(self.check().reused)
        self.environment = "environment-two"
        self.assertFalse(self.check().reused)
        (self.tree / "renamed").unlink()
        self.assertFalse(self.check().reused)
        self.assertEqual(7, self.action.call_count)

    def test_root_git_metadata_does_not_change_payload_identity(self) -> None:
        before = v.tree_digest(self.tree)
        (self.tree / ".git").mkdir()
        (self.tree / ".git/config").write_text("metadata")
        self.assertEqual(before, v.tree_digest(self.tree))

    def test_validation_children_do_not_inherit_hook_repository_or_live_cli_selectors(self) -> None:
        with mock.patch.dict(os.environ, {"GIT_DIR": "/caller/git", "GIT_WORK_TREE": "/caller/tree",
                                          "GIT_INDEX_FILE": "/caller/index", "HUKUHAKA_RUN_LIVE_CLI": "1"}):
            values = v.validation_environment(self.cache)
        self.assertNotIn("GIT_DIR", values)
        self.assertNotIn("GIT_WORK_TREE", values)
        self.assertNotIn("GIT_INDEX_FILE", values)
        self.assertEqual("0", values["HUKUHAKA_RUN_LIVE_CLI"])
        self.assertEqual(os.devnull, values["GIT_CONFIG_GLOBAL"])
        self.assertEqual("1", values["GIT_CONFIG_NOSYSTEM"])
        self.assertEqual("1", values["PYTHONNOUSERSITE"])

    def test_expired_future_corrupt_failed_and_wrong_schema_records_miss(self) -> None:
        for change in (
            {"completed_at": 0}, {"completed_at": 999999999999},
            {"status": "running"}, {"status": "failed"}, {"schema": -1},
            {"exit_code": 1}, {"key": "other"}, {"elapsed_seconds": float("nan")},
            {"schema": True}, {"exit_code": False}, {"elapsed_seconds": True},
            {"completed_at": True}, {"check": "different check"},
        ):
            with self.subTest(change=change):
                self.check()
                path = self.receipt()
                payload = json.loads(path.read_text())
                payload.update(change)
                path.write_text(json.dumps(payload))
                self.assertFalse(self.check().reused)
        self.receipt().write_text("{")
        self.assertFalse(self.check().reused)

    def test_receipt_age_boundary(self) -> None:
        with mock.patch.object(v.time, "time", return_value=100000):
            self.check()
        with mock.patch.object(v.time, "time", return_value=100000 + v.MAX_AGE_SECONDS):
            self.assertTrue(self.check().reused)
        with mock.patch.object(v.time, "time", return_value=100001 + v.MAX_AGE_SECONDS):
            self.assertFalse(self.check().reused)

    def test_failed_forced_refresh_invalidates_previous_success(self) -> None:
        self.check()
        with mock.patch.dict(os.environ, {v.FRESH_ENV: "1"}):
            with self.assertRaises(subprocess.CalledProcessError):
                self.check(mock.Mock(side_effect=subprocess.CalledProcessError(1, "test")))
        self.assertFalse(self.check().reused)

    def test_changed_inputs_and_interruption_never_leave_a_success(self) -> None:
        def mutate():
            (self.tree / "input").write_text("mutated")
            return ""
        with self.assertRaisesRegex(v.VerificationError, "inputs changed"):
            self.check(mutate)
        self.assertFalse(self.check().reused)
        with mock.patch.dict(os.environ, {v.FRESH_ENV: "1"}):
            with self.assertRaises(KeyboardInterrupt):
                self.check(mock.Mock(side_effect=KeyboardInterrupt))
        self.assertFalse(self.check().reused)

    def test_unwritable_cache_runs_check_without_claiming_reuse(self) -> None:
        self.cache.write_text("not a directory")
        self.assertFalse(self.check().reused)
        self.assertFalse(self.check().reused)
        self.assertEqual(2, self.action.call_count)

    def test_receipt_symlink_is_not_followed(self) -> None:
        self.check()
        path = self.receipt()
        target = self.root / "user-file"
        target.write_text(path.read_text())
        original = target.read_bytes()
        path.unlink()
        path.symlink_to(target)
        self.assertFalse(self.check().reused)
        self.assertEqual(original, target.read_bytes())

    def test_unknown_inputs_run_fresh_and_raw_values_never_enter_receipts(self) -> None:
        result = v.run_verified(
            "probe", mock.Mock(side_effect=OSError("probe unavailable")), self.action, cache=self.cache,
        )
        self.assertFalse(result.reused)
        self.assertFalse(self.cache.exists())
        secret = "synthetic-sensitive-environment-value"
        v.run_verified("secret", lambda: {"environment": secret}, self.action, cache=self.cache)
        self.assertNotIn(secret, self.receipt().read_text())

    def test_unknown_values_cannot_become_reusable_identities(self) -> None:
        for inputs in (None, {}, {"probe": None}, {"probe": ""}, {"tools": ["known", None]}):
            with self.subTest(inputs=inputs):
                result = v.run_verified("probe", lambda: inputs, self.action, cache=self.cache)
                self.assertFalse(result.reused)
                self.assertFalse(self.cache.exists())

    def test_tool_bytes_changing_with_the_same_size_and_mtime_change_identity(self) -> None:
        tool = self.root / "tool"
        tool.write_text("#!/bin/sh\necho version\n# one\n")
        tool.chmod(0o755)
        original = tool.stat()
        with mock.patch.object(v.shutil, "which", return_value=str(tool)):
            first = v.tool_identity("tool")
            tool.write_text(tool.read_text().replace("# one", "# two"))
            os.utime(tool, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertNotEqual(first, v.tool_identity("tool"))


if __name__ == "__main__":
    unittest.main()
