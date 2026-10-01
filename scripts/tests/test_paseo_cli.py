"""Profile-target selection and approval boundaries independent of transport."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.common import InstallerError
from scripts.install.main import Installer, build_parser
from scripts.install.terminal import (
    CLEAR, SECTION_LABELS, _HostState, _render, _rows, prompt_install_plan,
)


ROOT = Path(__file__).resolve().parents[2]
ROLES = ["advisor-gpt", "advisor-claude", "worker", "scouter", "designer", "writer", "vision"]


class PaseoCliTests(unittest.TestCase):
    def installer(self, *args):
        return Installer(build_parser().parse_args(["--repo-root", str(ROOT), "paseo", *args]))

    def test_profile_recommendations_and_complete_selection_are_independent(self):
        self.assertEqual(ROLES, self.installer("install", "--recommended")._automation_components("paseo"))
        selected = self.installer("install", "--components", "worker,scouter,worker")
        self.assertEqual(["worker", "scouter"], selected._automation_components("paseo"))
        for name in ("agents-md", "claude-md", "hukuhaka-paseo"):
            with self.assertRaises(InstallerError):
                self.installer("install", "--components", name)._automation_components("paseo")

    def test_adoption_mapping_never_uses_names_and_rejects_duplicates(self):
        args = ("install", "--recommended")
        self.assertEqual({"advisor-gpt": "exact-id"}, self.installer(*args, "--adopt", "advisor-gpt=exact-id")._paseo_adoptions())
        for values in (("worker=id", "scouter=id"), ("worker=id", "worker=other"), ("worker",)):
            flags = [flag for value in values for flag in ("--adopt", value)]
            with self.assertRaises(InstallerError):
                self.installer(*args, *flags)._paseo_adoptions()
        with self.assertRaises(InstallerError):
            self.installer(*args, "--rename-adopted", "advisor-gpt")._paseo_adoptions()

    def test_profile_target_has_no_template_or_settings_actions(self):
        for args in (("reset", "--recommended", "--include-template"), ("settings",)):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.installer(*args)

    def test_offline_receipt_recovery_has_its_own_preview_and_confirmation(self):
        installer = self.installer("state", "recover", "--yes")
        adapter = mock.Mock()
        installer._paseo_adapter = adapter
        with mock.patch("scripts.install.main.shutil.which", side_effect=AssertionError("receipt recovery is offline")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, installer.automation())
        adapter.recover.assert_called_once_with()
        self.assertIn("config.json are not restored or changed", output.getvalue())
        adapter.install.assert_not_called()
        adapter.uninstall.assert_not_called()

    def test_tty_adoption_confirmation_does_not_replace_install_confirmation(self):
        installer = self.installer("status")
        adapter = mock.Mock()
        adapter.status.return_value = {"home": "/isolated", "profiles": [], "roles": []}
        with mock.patch.object(installer, "_adapter", return_value=adapter), mock.patch.object(installer, "_confirm", return_value=False), mock.patch("scripts.install.main.shutil.which", return_value="fixture-cli"), mock.patch("builtins.input", side_effect=["advisor-gpt=exact-id", "advisor-gpt", "y"]), contextlib.redirect_stdout(io.StringIO()):
            adapter.current_component_state.return_value = (set(), {})
            self.assertEqual(0, installer._paseo_adoption_wizard(ROLES))
        self.assertEqual({"advisor-gpt": "exact-id"}, installer._paseo_adoptions())
        self.assertEqual(["advisor-gpt"], installer.args.rename_adopted)
        self.assertEqual([mock.call(ROLES), mock.call(ROLES, reset=False)], adapter.preview.call_args_list)
        adapter.install.assert_not_called()

    def test_declining_separate_adoption_confirmation_never_applies(self):
        installer = self.installer("status")
        adapter = mock.Mock()
        adapter.status.return_value = {"home": "/isolated", "profiles": [], "roles": []}
        with mock.patch.object(installer, "_adapter", return_value=adapter), mock.patch.object(installer, "automation", side_effect=AssertionError("adoption declined")), mock.patch("builtins.input", side_effect=["worker=exact-id", "", "n"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, installer._paseo_adoption_wizard(["worker"]))
        adapter.install.assert_not_called()

    def test_offline_status_reads_snapshot_without_cli_detection(self):
        installer = self.installer("status", "--json")
        adapter = mock.Mock()
        adapter.status.return_value = {"home": "/isolated", "profiles": [], "roles": [], "managed": {}, "components": []}
        installer._paseo_adapter = adapter
        with mock.patch("scripts.install.main.shutil.which", side_effect=AssertionError("status must be offline")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, installer.automation())
        self.assertIn('"profiles": []', output.getvalue())
        adapter.require_cli.assert_not_called()

    def test_offline_dry_run_keeps_same_adapter_from_preview_through_apply(self):
        installer = self.installer("install", "--components", "worker", "--dry-run")
        adapter = mock.Mock()
        adapter.current_component_state.return_value = ({"worker", "scouter"}, {})
        installer._paseo_adapter = adapter
        with mock.patch("scripts.install.main.shutil.which", return_value=None), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, installer.automation())
        adapter.preview.assert_called_once_with(["worker"], reset=False)
        adapter.install.assert_called_once_with(["worker"], reset=False, include_template=False)
        self.assertIn("Remove/release: scouter", output.getvalue())

    def test_missing_cli_blocks_mutation_before_profile_adapter(self):
        installer = self.installer("install", "--recommended", "--yes")
        with mock.patch("scripts.install.main.shutil.which", return_value=None), mock.patch.object(installer, "_adapter", side_effect=AssertionError("must not mutate")), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, installer.automation())

    def test_absent_and_malformed_saved_status_do_not_create_or_repair_files(self):
        with tempfile.TemporaryDirectory(prefix="paseo-cli-status-") as directory:
            home = Path(directory) / "missing-home"
            with mock.patch.dict(os.environ, {"PASEO_HOME": str(home)}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, self.installer("status").automation())
                self.assertFalse(home.exists())
                home.mkdir()
                config = home / "config.json"
                config.write_text('{"daemon":{"agentProfiles":null}}')
                before = config.read_bytes()
                with self.assertRaisesRegex(InstallerError, "agentProfiles must be an array"):
                    self.installer("status").automation()
                self.assertEqual(before, config.read_bytes())
                self.assertEqual([config], list(home.iterdir()))


class PaseoTerminalTests(unittest.TestCase):
    def state(self):
        installer = PaseoCliTests().installer("status")
        return _HostState("paseo", "Paseo", "0.10.2", False, installer._components("paseo"), set(ROLES),
                          profile_status=[{"role": "scouter", "status": "local override", "id": "saved-id", "profile": {"provider": "codex", "model": "custom-model", "thinkingOptionId": "high", "featureValues": {"fast_mode": False}}},
                                          {"role": "advisor-gpt", "status": "existing, unmanaged", "candidate_ids": ["personal-id"]}])

    def test_paseo_controls_are_separate_and_show_saved_metadata(self):
        state = self.state()
        rows = _rows([state])
        kinds = [row[0] for row in rows]
        self.assertIn("adopt", kinds)
        for excluded in ("template", "configure", "settings"):
            self.assertNotIn(excluded, kinds)
        output = io.StringIO()
        _render(output, [state], rows, kinds.index("host"))
        text = output.getvalue()
        for expected in ("[ ] Install/update", "Fast=true: priority processing, increased usage", "local override", "custom-model", "Fast=False", "candidate UUIDs=personal-id"):
            self.assertIn(expected, text)

    def test_scrolling_keeps_profile_controls_visible_at_two_terminal_sizes(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True
            def fileno(self):
                return 1
        state = self.state()
        rows = _rows([state])
        for size in ((80, 24), (45, 16)):
            for index, row in enumerate(rows):
                if row[0] == "header" or row[0] in SECTION_LABELS:
                    continue
                output = Terminal()
                with mock.patch("scripts.install.terminal.os.get_terminal_size", return_value=size):
                    _render(output, [state], rows, index)
                lines = output.getvalue().removeprefix(CLEAR).splitlines()
                self.assertLess(len(lines), size[1])
                self.assertTrue(all(len(line) < size[0] for line in lines))
                self.assertEqual(1, sum(line.startswith("> ") for line in lines))

    def test_enabling_paseo_selects_defaults_without_native_hosts(self):
        state = self.state()
        section = {"host": "paseo", "label": "Paseo", "enabled": False, "components": state.components, "selected": state.selected}
        self.assertEqual([], prompt_install_plan(io.StringIO(), io.StringIO(), sections=[section], keys=("up", "up", "enter")))
        plans = prompt_install_plan(io.StringIO(), io.StringIO(), sections=[section], keys=("toggle", "up", "up", "enter"))
        self.assertEqual(["paseo"], [plan.host for plan in plans])
        self.assertEqual(ROLES, plans[0].components)
        self.assertFalse(plans[0].include_template)

    def test_adoption_action_carries_the_explicit_picker_set(self):
        state = self.state()
        state.selected = {"worker", "scouter"}
        section = {"host": "paseo", "label": "Paseo", "enabled": False, "components": state.components, "selected": state.selected, "profile_status": state.profile_status}
        rows = _rows([state])
        selectable = [row for row in rows if row[0] != "header" and row[0] not in SECTION_LABELS]
        position = [row[0] for row in selectable].index("adopt")
        plans = prompt_install_plan(io.StringIO(), io.StringIO(), sections=[section], keys=(*(["down"] * position), "enter"))
        self.assertEqual("adopt", plans[0].action)
        self.assertEqual(["worker", "scouter"], plans[0].components)


if __name__ == "__main__":
    unittest.main()
