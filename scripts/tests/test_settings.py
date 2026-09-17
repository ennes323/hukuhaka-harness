from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.settings import Settings, cli_literal, organize_config, read_profile
from scripts.install.settings_catalog import CATALOG, RECOMMENDED
from scripts.install.common import InstallerError, StateError


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.config = self.home / "config.toml"
        self.config.write_text('model = "personal"\nmodel_reasoning_effort = "medium"\n# keep\n[mcp_servers.personal]\ncommand = "private-tool"\n')
        self.settings = Settings(self.home)
        self.doctor = mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor")
        self.doctor.start()
        self.addCleanup(self.doctor.stop)

    def apply(self, plan):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.settings.apply(plan)

    def test_partial_profile_restore_preserves_later_unrelated_edits(self):
        profile = Path(self.temp.name) / "experiment.toml"
        profile.write_text('model_reasoning_effort = "high"\n[features.multi_agent_v2]\nmin_wait_timeout_ms = 120000\ndefault_wait_timeout_ms = 120000\n')
        identifier = self.apply(self.settings.plan(read_profile(profile)))
        self.config.write_text(self.config.read_text().replace('"personal"', '"new-personal"'))
        self.apply(self.settings.restore_plan(identifier))
        text = self.config.read_text()
        self.assertIn('model = "new-personal"', text)
        self.assertIn('model_reasoning_effort = "medium"', text)
        self.assertNotIn("wait_timeout_ms", text)
        self.assertIn('# keep\n[mcp_servers.personal]\ncommand = "private-tool"', text)

    def test_restore_conflict_and_stale_preview_are_read_only(self):
        plan = self.settings.plan({("model_reasoning_effort",): '"high"'})
        self.config.write_text(self.config.read_text() + "# manual\n")
        with self.assertRaisesRegex(StateError, "after preview"):
            self.apply(plan)
        identifier = self.apply(self.settings.plan({("model_reasoning_effort",): '"high"'}))
        self.config.write_text(self.config.read_text().replace('"high"', '"low"'))
        with self.assertRaisesRegex(StateError, "Restore conflict"):
            self.settings.restore_plan(identifier)

    def test_failed_validation_rolls_back_config_and_receipt(self):
        before = self.config.read_bytes()
        with mock.patch.object(self.settings.editor, "_doctor", side_effect=InstallerError("invalid")):
            with self.assertRaises(InstallerError):
                self.apply(self.settings.plan({("model",): '"candidate"'}))
        self.assertEqual(before, self.config.read_bytes())
        self.assertEqual([], self.settings.records())

    def test_dry_run_never_creates_home_or_lock(self):
        absent = Path(self.temp.name) / "absent"
        manager = Settings(absent, dry_run=True)
        with contextlib.redirect_stdout(io.StringIO()):
            manager.apply(manager.plan(RECOMMENDED))
        self.assertFalse(absent.exists())

    def test_wait_bounds_relations_and_unknown_defaults(self):
        prefix = ("features", "multi_agent_v2")
        self.settings.plan({prefix + ("max_wait_timeout_ms",): "3600000"})
        for values in ({prefix + ("min_wait_timeout_ms",): "3600001"},
                       {prefix + ("min_wait_timeout_ms",): "120000", prefix + ("default_wait_timeout_ms",): "10000"},
                       {prefix + ("max_wait_timeout_ms",): "-1"}):
            with self.assertRaises(StateError):
                self.settings.plan(values)
        self.assertEqual("not established", CATALOG["features.multi_agent_v2.default_wait_timeout_ms"].official_default)

    def test_profile_rejects_unknown_duplicate_and_ignored_syntax(self):
        profile = Path(self.temp.name) / "bad.toml"
        for text in ('model = "a"\nmodel = "b"\n', '[unknown]\n', 'nonsense\nmodel = "a"\n', 'features.context_management.experimental_mode = false\n', 'model = 2\n', 'model_context_window = true\n'):
            profile.write_text(text)
            with self.assertRaises(StateError, msg=text):
                read_profile(profile)

    def test_organize_preserves_multiline_values_unknown_tables_and_comments(self):
        text = 'web_search = "indexed"\n\n# model note\nmodel = "personal"\ncompact_prompt = """\nKeep this\n[not.a.table]\nline = value\n"""\n[plugins."z@x"]\nenabled = true\n[features]\nmemories = true\n[agents]\nenabled = false\n'
        result = organize_config(text)
        self.assertEqual(result, organize_config(result))
        self.assertIn('# model note\nmodel = "personal"', result)
        self.assertIn('"""\nKeep this\n[not.a.table]\nline = value\n"""', result)
        self.assertLess(result.index("[features]"), result.index('[plugins.'))
        self.config.write_text(text)
        identifier = self.apply(self.settings.plan(organize=True))
        self.assertEqual(text.encode(), (self.settings.history_root / (identifier + ".toml")).read_bytes())

    def test_export_multiline_profile_round_trip_and_never_overwrite(self):
        self.config.write_text('compact_prompt = """\nKeep exact paths.\nKeep evidence.\n"""\nmodel = "personal"\n')
        output = Path(self.temp.name) / "profile.toml"
        self.settings.export(output)
        values = read_profile(output)
        self.assertEqual('Keep exact paths.\nKeep evidence.\n', json.loads(values[("compact_prompt",)]))
        self.assertNotIn("mcp_servers", output.read_text())
        with self.assertRaises(StateError):
            self.settings.export(output)

    def test_unset_and_provenance(self):
        identifier = self.apply(self.settings.plan(remove=(("model_reasoning_effort",),)))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.settings.show(as_json=True)
        data = json.loads(output.getvalue())
        row = next(row for row in data["options"] if row["key"] == "model_reasoning_effort")
        self.assertIsNone(row["value"])
        self.assertIn(identifier, row["origin"])
        self.assertEqual("not observed", data["runtime"])

    def test_cli_strings_and_context_relation(self):
        self.assertEqual('"high"', cli_literal("model_reasoning_effort", "high"))
        with self.assertRaises(StateError):
            self.settings.plan({("model_context_window",): "100", ("model_auto_compact_token_limit",): "101"})

    def test_interactive_editor_plan_uses_same_relation_validation(self):
        plan = self.settings.editor.plan({("model_context_window",): "100", ("model_auto_compact_token_limit",): "101"})
        before = self.config.read_bytes()
        with self.assertRaises(StateError):
            self.apply(plan)
        self.assertEqual(before, self.config.read_bytes())


if __name__ == "__main__":
    unittest.main()
