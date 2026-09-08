from __future__ import annotations

import contextlib
import os
import io
import json
import stat
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex import CodexGuidanceDeployment, CodexInstaller
from scripts.install.common import (
    DriftError,
    FileTransaction,
    InstallerError,
    StateError,
)
from scripts.install.main import (
    HostComponentState,
    HostResult,
    Installer,
    build_parser,
)
from scripts.install.terminal import HostInstallPlan, prompt_install_plan


ROOT = Path(__file__).resolve().parents[2]


class FileTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka transaction ")
        self.state_root = Path(self.temp.name) / "state"
        self.state_root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pending_transaction_is_recovered_on_next_run(self) -> None:
        target = self.state_root / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        self.assertEqual("new\n", target.read_text())
        self.assertEqual(1, FileTransaction.recover_pending(self.state_root))
        self.assertEqual("old\n", target.read_text())

    def test_snapshot_is_not_journaled_until_backup_exists(self) -> None:
        target = self.state_root / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        with mock.patch("shutil.copy2", side_effect=OSError("injected backup failure")):
            with self.assertRaises(OSError):
                transaction.snapshot(target)
        journal = json.loads(transaction.journal_path.read_text())
        self.assertEqual([], journal["entries"])
        transaction.__exit__(None, None, None)

    def test_failed_rollback_keeps_recovery_evidence(self) -> None:
        target = self.state_root / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        with mock.patch("shutil.copy2", side_effect=OSError("injected restore failure")):
            with self.assertRaises(StateError):
                transaction.__exit__(InstallerError, InstallerError("boom"), None)
        self.assertTrue(transaction.journal_path.is_file())
        self.assertEqual(1, FileTransaction.recover_pending(self.state_root))
        self.assertEqual("old\n", target.read_text())

    def test_successful_rollback_removes_the_transaction_directory(self) -> None:
        target = self.state_root / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        transaction.__exit__(InstallerError, InstallerError("boom"), None)
        self.assertEqual("old\n", target.read_text())
        self.assertFalse(transaction.root.exists())

    def test_recovery_rejects_target_outside_state_root(self) -> None:
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("keep\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        transaction.entries = [
            {"target": str(outside), "existed": False, "backup": "backups/000000"}
        ]
        transaction._write_journal("pending")
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.state_root)
        self.assertEqual("keep\n", outside.read_text())
        transaction.__exit__(None, None, None)

    def test_transaction_refuses_targets_outside_its_own_state_root(self) -> None:
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("keep\n")
        transaction = FileTransaction(self.state_root)
        transaction.__enter__()
        try:
            with self.assertRaises(StateError):
                transaction.remove(self.state_root / ".." / "never-existed.txt")
            with self.assertRaises(StateError):
                transaction.remove(self.state_root)
            with self.assertRaises(StateError):
                transaction.snapshot(outside)
            journal = json.loads(transaction.journal_path.read_text())
            self.assertEqual([], journal["entries"])
            self.assertEqual("keep\n", outside.read_text())
        finally:
            transaction.__exit__(None, None, None)


class InstallerSelectionTests(unittest.TestCase):
    def installer(self, *arguments: str) -> Installer:
        arguments = [
            "--repo-root",
            str(ROOT),
            "--local-source",
            *arguments,
        ]
        args = build_parser().parse_args(arguments)
        return Installer(args)

    def test_recommended_selects_only_supported_catalog_defaults(self) -> None:
        installer = self.installer(
                    "codex",
                    "install",
            "--recommended",
            "--yes",
        )
        self.assertEqual(
            [
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-uiux-foundation",
                "agents-md",
            ],
            installer._automation_components("codex"),
        )

    def test_explicit_selection_is_the_complete_desired_state(self) -> None:
        installer = self.installer(
            "codex",
            "install",
            "--components",
            "hukuhaka-engineering-plan",
        )
        self.assertEqual(
            ["hukuhaka-engineering-plan"],
            installer._automation_components("codex"),
        )
        scout = self.installer(
            "codex", "install", "--components", "evidence-scout"
        )
        self.assertEqual(
            ["evidence-scout"], scout._automation_components("codex")
        )

    def test_removed_legacy_components_are_unknown(self) -> None:
        for name in ("hukuhaka-ltm", "hukuhaka-project-mapper"):
            installer = self.installer(
                "codex", "install", "--components", name
            )
            with self.assertRaisesRegex(
                InstallerError, "unknown .* component '{}'".format(name)
            ):
                installer._automation_components("codex")

    def test_declared_alias_resolves_to_current_component(self) -> None:
        installer = self.installer(
            "codex",
            "install",
            "--components",
            "old-report-planner",
        )
        installer.aliases["old-report-planner"] = "hukuhaka-report-planner"
        self.assertEqual(
            ["hukuhaka-report-planner"],
            installer._automation_components("codex"),
        )

    def test_version_summary_covers_install_change_same_and_unknown(self) -> None:
        installer = self.installer(
            "codex",
            "install",
            "--recommended",
            "--yes",
        )
        plan = HostInstallPlan(
            "codex",
            [
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-uiux-foundation",
                "agents-md",
                "astra_worker",
            ],
        )

        summary = dict(
            installer._version_summary(
                plan,
                {
                    "hukuhaka-engineering-plan",
                    "hukuhaka-worklog",
                    "hukuhaka-uiux-foundation",
                },
                {
                    "hukuhaka-engineering-plan": "0.0.9",
                    "hukuhaka-worklog": "0.4.1",
                },
            )
        )

        self.assertEqual(
            "not installed → 0.7.2",
            summary["hukuhaka-report-planner"],
        )
        self.assertEqual(
            "0.0.9 → 0.2.3",
            summary["hukuhaka-engineering-plan"],
        )
        self.assertEqual(
            "0.4.1 (same version)",
            summary["hukuhaka-worklog"],
        )
        self.assertEqual(
            "unknown → 0.1.0",
            summary["hukuhaka-uiux-foundation"],
        )
        self.assertNotIn("agents-md", summary)

    def test_target_version_rejects_invalid_plugin_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hukuhaka target version ") as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("1.0.0\n")
            (root / "plugin.json").write_text(
                json.dumps({"name": "wrong-name", "version": "1.2.3"})
            )
            (root / "components.json").write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "name": "planner",
                                "kind": "plugin",
                                "hosts": {
                                    "codex": {"manifest": "plugin.json"}
                                },
                            }
                        ]
                    }
                )
            )
            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(root),
                    "codex",
                    "install",
                    "--recommended",
                    "--yes",
                ]
            )
            installer = Installer(args)

            with self.assertRaisesRegex(
                StateError, "invalid plugin manifest for planner"
            ):
                installer._components("codex")

    def test_target_version_rejects_missing_plugin_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hukuhaka target version ") as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("1.0.0\n")
            (root / "plugin.json").write_text(json.dumps({"name": "planner"}))
            (root / "components.json").write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "name": "planner",
                                "kind": "plugin",
                                "hosts": {
                                    "codex": {"manifest": "plugin.json"}
                                },
                            }
                        ]
                    }
                )
            )
            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(root),
                    "codex",
                    "install",
                    "--recommended",
                    "--yes",
                ]
            )
            installer = Installer(args)

            with self.assertRaisesRegex(
                StateError, "invalid plugin manifest for planner"
            ):
                installer._components("codex")

    def test_codex_component_state_reads_versions_and_normalizes_alias(self) -> None:
        installer = self.installer(
            "codex",
            "install",
            "--recommended",
            "--yes",
        )
        with tempfile.TemporaryDirectory(prefix="hukuhaka codex state ") as tmp:
            with mock.patch.dict("os.environ", {"CODEX_HOME": tmp}):
                adapter = installer._codex()
                adapter.aliases["old-worklog"] = "hukuhaka-worklog"
                plugins = [
                    {
                        "name": "old-worklog",
                        "version": "0.1.0",
                        "marketplaceName": adapter.marketplace,
                    }
                ]

                with mock.patch.object(adapter, "_plugins", return_value=plugins):
                    components, versions = adapter.current_component_state()

        self.assertEqual({"hukuhaka-worklog"}, components)
        self.assertEqual("0.1.0", versions["hukuhaka-worklog"])

    def test_non_tty_without_a_host_command_is_rejected(self) -> None:
        installer = self.installer()
        with mock.patch.object(installer, "_tty_available", return_value=False):
            self.assertEqual(2, installer.interactive())

    def test_no_detected_host_exits_without_changes(self) -> None:
        installer = self.installer()
        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value=None):
            self.assertEqual(1, installer.interactive())

    def test_claude_host_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self.installer(
                "claude",
                "install",
                "--recommended",
                "--yes",
            )

    def test_legacy_selection_flags_are_removed(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(
                ["--repo-root", str(ROOT), "--host", "both", "--all"]
            )

    def test_bootstrap_options_are_accepted_after_the_host_action(self) -> None:
        args = build_parser().parse_args(
            [
                "--repo-root",
                str(ROOT),
                "codex",
            "install",
                "--recommended",
                "--version=1.2.3",
                "--source-dir=.",
            ]
        )
        self.assertEqual("1.2.3", args.version)
        self.assertEqual(".", args.source_dir)

    def test_context_set_parser_is_separate_from_global_configure(self) -> None:
        args = build_parser().parse_args(
            [
                "--repo-root",
                str(ROOT),
                "codex",
                "context",
                "set",
                "--window",
                "800000",
                "--compact-at",
                "720000",
                "--scope",
                "body_after_prefix",
                "--yes",
            ]
        )

        self.assertEqual("context", args.action)
        self.assertEqual("set", args.context_action)
        self.assertEqual(800000, args.window)
        self.assertEqual(720000, args.compact_at)
        self.assertEqual("body_after_prefix", args.scope)

    def test_interactive_applies_config_before_codex_components_and_verifies(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                reset=True,
                configure_codex=True,
            )
        ]
        config_plan = mock.Mock(changed=True)
        config_editor = mock.Mock()
        config_editor.inspect.return_value = {}
        config_editor.plan.return_value = config_plan
        events = []
        config_editor.apply.side_effect = lambda *args, **kwargs: events.append(
            "config"
        )
        config_editor.verify.side_effect = lambda *args, **kwargs: events.append(
            "verify"
        )

        def apply_host(*args, **kwargs):
            events.append("components")
            return HostResult("codex", "success")

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_settings", return_value={}), \
             mock.patch(
                 "scripts.install.main.CodexConfigEditor",
                 return_value=config_editor,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(installer, "_apply_host", side_effect=apply_host), \
             mock.patch.object(installer, "_print_results", return_value=0) as print_results:
            self.assertEqual(0, installer.interactive())

        self.assertEqual(["config", "components", "verify"], events)
        result = print_results.call_args.args[0][0]
        self.assertEqual("success", result.status)

    def test_interactive_applies_context_before_components_and_verifies(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                change_context_window=True,
            )
        ]
        context_plan = mock.Mock(action="set", changed=True)
        applied_context_plan = mock.Mock(action="set", changed=True)
        context_policy = mock.Mock()
        context_policy.status.return_value = "Codex default"
        context_policy.plan_set.return_value = context_plan
        context_policy.replan.return_value = applied_context_plan
        events = []
        context_policy.apply.side_effect = lambda *args: events.append("context")
        context_policy.verify.side_effect = lambda *args: events.append(
            "context-verify"
        )

        def apply_host(*args, **kwargs):
            events.append("components")
            return HostResult("codex", "success")

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_context_action", return_value="set"), \
             mock.patch(
                 "scripts.install.main.prompt_context_settings",
                 return_value=(800000, 720000, "total"),
             ), \
             mock.patch(
                 "scripts.install.main.CodexContextPolicy",
                 return_value=context_policy,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(installer, "_apply_host", side_effect=apply_host), \
             mock.patch.object(installer, "_print_results", return_value=0) as print_results:
            self.assertEqual(0, installer.interactive())

        self.assertEqual(["context", "components", "context-verify"], events)
        context_policy.plan_set.assert_called_once_with(
            context_window=800000,
            compact_at=720000,
            scope="total",
        )
        context_policy.replan.assert_called_once_with(context_plan)
        context_policy.apply.assert_called_once_with(applied_context_plan)
        context_policy.verify.assert_called_once_with(applied_context_plan)
        result = print_results.call_args.args[0][0]
        self.assertEqual("success", result.status)

    def test_interactive_applies_agent_policy_before_components_and_verifies(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                change_agent_policy=True,
            )
        ]
        agent_plan = mock.Mock(action="set", changed=True)
        applied_agent_plan = mock.Mock(action="set", changed=True)
        agent_policy = mock.Mock()
        agent_policy.state.return_value = mock.Mock(label="Codex defaults")
        agent_policy.plan_set.return_value = agent_plan
        agent_policy.replan.return_value = applied_agent_plan
        events = []
        agent_policy.apply.side_effect = lambda *args: events.append("agents")
        agent_policy.verify.side_effect = lambda *args: events.append(
            "agents-verify"
        )

        def apply_host(*args, **kwargs):
            events.append("components")
            return HostResult("codex", "success")

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_agent_action", return_value="set"), \
             mock.patch(
                 "scripts.install.main.prompt_agent_settings",
                 return_value=(8, 1),
             ), \
             mock.patch(
                 "scripts.install.main.CodexAgentPolicy",
                 return_value=agent_policy,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(installer, "_apply_host", side_effect=apply_host), \
             mock.patch.object(installer, "_print_results", return_value=0) as print_results:
            self.assertEqual(0, installer.interactive())

        self.assertEqual(["agents", "components", "agents-verify"], events)
        agent_policy.plan_set.assert_called_once_with(
            max_concurrent=8,
            max_depth=1,
        )
        agent_policy.replan.assert_called_once_with(agent_plan)
        agent_policy.apply.assert_called_once_with(applied_agent_plan)
        agent_policy.verify.assert_called_once_with(applied_agent_plan)
        result = print_results.call_args.args[0][0]
        self.assertEqual("success", result.status)

    def test_interactive_replans_context_after_global_config_update(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                configure_codex=True,
                change_context_window=True,
            )
        ]
        config_plan = mock.Mock(changed=True)
        config_editor = mock.Mock()
        config_editor.inspect.return_value = {}
        config_editor.plan.return_value = config_plan
        context_plan = mock.Mock(action="set", changed=True)
        applied_context_plan = mock.Mock(action="set", changed=True)
        context_policy = mock.Mock()
        context_policy.status.return_value = "Codex default"
        context_policy.plan_set.return_value = context_plan
        context_policy.replan.return_value = applied_context_plan
        events = []
        config_editor.apply.side_effect = lambda *args, **kwargs: events.append(
            "config"
        )
        config_editor.verify.side_effect = lambda *args, **kwargs: events.append(
            "config-verify"
        )
        context_policy.apply.side_effect = lambda *args: events.append("context")
        context_policy.verify.side_effect = lambda *args: events.append(
            "context-verify"
        )

        def apply_host(*args, **kwargs):
            events.append("components")
            return HostResult("codex", "success")

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_settings", return_value={}), \
             mock.patch("scripts.install.main.prompt_context_action", return_value="set"), \
             mock.patch(
                 "scripts.install.main.prompt_context_settings",
                 return_value=(800000, 720000, "total"),
             ), \
             mock.patch(
                 "scripts.install.main.CodexConfigEditor",
                 return_value=config_editor,
             ), \
             mock.patch(
                 "scripts.install.main.CodexContextPolicy",
                 return_value=context_policy,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(installer, "_apply_host", side_effect=apply_host), \
             mock.patch.object(installer, "_print_results", return_value=0):
            self.assertEqual(0, installer.interactive())

        self.assertEqual(
            ["config", "context", "components", "config-verify", "context-verify"],
            events,
        )
        context_policy.replan.assert_called_once_with(context_plan)

    def test_interactive_continues_components_after_config_failure(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                configure_codex=True,
            )
        ]
        config_plan = mock.Mock(changed=True)
        config_editor = mock.Mock()
        config_editor.inspect.return_value = {}
        config_editor.plan.return_value = config_plan
        config_editor.apply.side_effect = InstallerError("config failed")

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_settings", return_value={}), \
             mock.patch(
                 "scripts.install.main.CodexConfigEditor",
                 return_value=config_editor,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(
                 installer,
                 "_apply_host",
                 return_value=HostResult("codex", "success"),
             ) as apply_host, \
             mock.patch.object(installer, "_print_results", return_value=1) as print_results:
            self.assertEqual(1, installer.interactive())

        apply_host.assert_called_once()
        config_editor.verify.assert_not_called()
        result = print_results.call_args.args[0][0]
        self.assertEqual("partial", result.status)
        self.assertIn("config failed", result.detail)

    def test_interactive_keeps_config_when_codex_components_fail(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan(
                "codex",
                ["agents-md"],
                configure_codex=True,
            )
        ]
        config_plan = mock.Mock(changed=True)
        config_editor = mock.Mock()
        config_editor.inspect.return_value = {}
        config_editor.plan.return_value = config_plan

        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch("scripts.install.main.prompt_settings", return_value={}), \
             mock.patch(
                 "scripts.install.main.CodexConfigEditor",
                 return_value=config_editor,
             ), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(
                 installer,
                 "_apply_host",
                 return_value=HostResult("codex", "failed", "components failed"),
             ), \
             mock.patch.object(installer, "_print_results", return_value=1) as print_results:
            self.assertEqual(1, installer.interactive())

        config_editor.apply.assert_called_once_with(config_plan, show_diff=False)
        config_editor.verify.assert_called_once_with(config_plan)
        result = print_results.call_args.args[0][0]
        self.assertEqual("partial", result.status)
        self.assertIn("components failed", result.detail)

    def test_codex_result_reports_both_failures(self) -> None:
        result = Installer._combine_codex_result(
            HostResult("codex", "failed", "components failed"),
            config_requested=True,
            config_changed=True,
            config_applied=False,
            config_errors=["config failed"],
        )

        self.assertEqual("failed", result.status)
        self.assertEqual(
            "config failed\n    components failed",
            result.detail,
        )

    def test_codex_result_is_partial_when_applied_config_fails_final_verify(
        self,
    ) -> None:
        result = Installer._combine_codex_result(
            HostResult("codex", "failed", "components failed"),
            config_requested=True,
            config_changed=True,
            config_applied=True,
            config_errors=["config verify failed"],
        )

        self.assertEqual("partial", result.status)

    def test_installation_plan_groups_components_settings_and_reset(self) -> None:
        installer = self.installer(
            "codex",
            "install",
            "--recommended",
            "--yes",
        )
        config_plan = mock.Mock(changed=False)
        context_plan = mock.Mock(action="reset", changed=False)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            installer._print_plan(
                [
                    HostInstallPlan(
                        "codex",
                        ["agents-md"],
                        reset=True,
                        include_template=True,
                        configure_codex=True,
                        change_context_window=True,
                    )
                ],
                {"codex": {"agents-md"}},
                {"codex": {}},
                config_plan,
                context_plan,
                None,
            )

        rendered = output.getvalue()
        self.assertLess(rendered.index("  Components"), rendered.index("  Settings"))
        self.assertLess(rendered.index("  Settings"), rendered.index("  Reset"))
        self.assertIn("Global defaults: update", rendered)
        self.assertIn("Context window: reset to Codex defaults", rendered)
        self.assertIn("Managed components: yes", rendered)


class CodexPluginCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka codex cache ")
        self.codex_home = Path(self.temp.name) / "codex-home"
        self.codex_home.mkdir()
        catalog = json.loads((ROOT / "components.json").read_text(encoding="utf-8"))
        self.adapter = CodexInstaller(
            ROOT,
            catalog,
            "1.1.6",
            local_source=True,
        )
        self.adapter.codex_home = self.codex_home
        self.component = "hukuhaka-worklog"
        self.source = ROOT / "marketplace" / self.component
        self.version = json.loads(
            (self.source / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )["version"]
        self.cache = (
            self.codex_home
            / "plugins"
            / "cache"
            / self.adapter.marketplace
            / self.component
            / self.version
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def result(self) -> dict:
        return {
            "pluginId": "{}@{}".format(self.component, self.adapter.marketplace),
            "name": self.component,
            "marketplaceName": self.adapter.marketplace,
            "version": self.version,
            "installedPath": str(self.cache),
        }

    def populate_cache(self) -> None:
        if self.cache.exists():
            shutil.rmtree(self.cache)
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.source, self.cache)

    def installed_plugin(self) -> dict:
        return {
            "pluginId": "{}@{}".format(self.component, self.adapter.marketplace),
            "name": self.component,
            "marketplaceName": self.adapter.marketplace,
            "version": self.version,
        }

    def test_validates_versioned_cache_and_declared_payload(self) -> None:
        self.populate_cache()

        installed = self.adapter._validate_plugin_install(
            self.component, self.result()
        )

        self.assertEqual(self.cache.resolve(), installed)

    def test_invalid_cache_is_removed_and_reinstalled_once(self) -> None:
        self.populate_cache()
        script = self.cache / "skills" / "worklog" / "scripts" / "worklog.py"
        script.write_text("stale\n", encoding="utf-8")
        add_calls = 0

        def add(_component: str) -> dict:
            nonlocal add_calls
            add_calls += 1
            if add_calls == 2:
                self.populate_cache()
            return self.result()

        with mock.patch.object(
            self.adapter, "_run_plugin_add", side_effect=add
        ), mock.patch.object(
            self.adapter, "_plugins", return_value=[self.installed_plugin()]
        ), mock.patch.object(self.adapter, "_remove_plugin") as remove:
            result = self.adapter._install_plugin(self.component)

        self.assertEqual(self.result(), result)
        self.assertEqual(2, add_calls)
        remove.assert_called_once_with(
            self.installed_plugin(), stage="plugin-cache-repair"
        )

    def test_repeated_invalid_cache_fails_after_one_reinstall(self) -> None:
        with mock.patch.object(
            self.adapter, "_run_plugin_add", return_value=self.result()
        ) as add, mock.patch.object(
            self.adapter, "_plugins", return_value=[self.installed_plugin()]
        ), mock.patch.object(self.adapter, "_remove_plugin") as remove:
            with self.assertRaisesRegex(
                InstallerError, "plugin cache repair failed"
            ):
                self.adapter._install_plugin(self.component)

        self.assertEqual(2, add.call_count)
        remove.assert_called_once()

    def test_final_verify_rejects_registered_version_drift(self) -> None:
        self.populate_cache()
        self.adapter.install_results[self.component] = self.result()
        plugin = self.installed_plugin()
        plugin["version"] = "0.2.0"

        with mock.patch.object(self.adapter, "_plugins", return_value=[plugin]):
            with self.assertRaisesRegex(
                InstallerError, "post-install version does not match"
            ):
                self.adapter.verify({self.component})


class CodexGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka codex ")
        self.codex_home = Path(self.temp.name)
        self.source = self.codex_home / "source.md"
        self.source.write_text("# Managed\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def deployment(self, *, force: bool = False) -> CodexGuidanceDeployment:
        return CodexGuidanceDeployment(
            self.source,
            self.codex_home,
            "1.0.13",
            enabled=True,
            force=force,
        )

    def test_install_and_uninstall_preserve_user_text(self) -> None:
        target = self.codex_home / "AGENTS.md"
        target.write_text("# User\n")
        target.chmod(0o640)
        self.deployment().deploy()
        self.assertIn("# User", target.read_text())
        self.assertIn("# Managed", target.read_text())
        self.assertEqual(0o640, stat.S_IMODE(target.stat().st_mode))
        CodexGuidanceDeployment(
            self.source,
            self.codex_home,
            "1.0.13",
            enabled=False,
        ).uninstall()
        self.assertEqual("# User\n", target.read_text())
        self.assertEqual(0o640, stat.S_IMODE(target.stat().st_mode))

    def test_deploy_recovers_an_interrupted_codex_transaction(self) -> None:
        self.deployment().deploy()
        target = self.codex_home / "AGENTS.md"
        deployed = target.read_bytes()
        # Simulate a kill between the AGENTS.md write and the manifest write:
        # the journal stays "pending" and the managed block no longer matches
        # the recorded managedHash.
        transaction = FileTransaction(self.codex_home)
        transaction.__enter__()
        transaction.write_bytes(target, b"interrupted\n")
        self.deployment().deploy()
        self.assertEqual(deployed, target.read_bytes())

    def test_uninstall_recovers_before_guidance_manifest_noop_check(self) -> None:
        self.deployment().deploy()
        manifest = self.codex_home / ".hukuhaka-agents-manifest.json"
        transaction = FileTransaction(self.codex_home)
        transaction.__enter__()
        transaction.remove(manifest)

        self.deployment().uninstall()

        self.assertFalse(manifest.exists())
        target = self.codex_home / "AGENTS.md"
        self.assertTrue(
            not target.exists() or "# Managed" not in target.read_text()
        )

    def test_disabled_deploy_delegates_without_self_deadlock(self) -> None:
        self.deployment().deploy()
        target = self.codex_home / "AGENTS.md"
        self.assertTrue(target.exists())
        CodexGuidanceDeployment(
            self.source,
            self.codex_home,
            "1.0.13",
            enabled=False,
        ).deploy()
        self.assertFalse(target.exists())

    def test_modified_managed_block_requires_force(self) -> None:
        self.deployment().deploy()
        target = self.codex_home / "AGENTS.md"
        target.write_text(target.read_text().replace("# Managed", "# Changed"))
        with self.assertRaises(DriftError):
            self.deployment().deploy()
        self.deployment(force=True).deploy()
        self.assertIn("# Managed", target.read_text())


class PlainTerminalSelectionTests(unittest.TestCase):
    def test_plugin_rows_show_target_versions_only(self) -> None:
        output = io.StringIO()
        prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "version": "0.145.0",
                    "components": [
                        {
                            "name": "hukuhaka-worklog",
                            "kind": "plugin",
                            "version": "0.2.0",
                            "default": True,
                        },
                        {
                            "name": "agents-md",
                            "kind": "template",
                            "default": True,
                        },
                    ],
                    "selected": {"hukuhaka-worklog", "agents-md"},
                }
            ],
            keys=("exit",),
        )

        rendered = output.getvalue()
        self.assertIn("hukuhaka-worklog (plugin 0.2.0)", rendered)
        self.assertIn("agents-md (template)", rendered)
        self.assertNotIn("agents-md (template ", rendered)

    def test_codex_only_host_is_rendered_and_reset_is_explicit(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "available": True,
                    "version": "2.1",
                    "components": [{"name": "planner", "kind": "plugin"}],
                    "selected": {"planner"},
                },
            ],
            keys=("down", "down", "down", "down", "down", "down", "toggle", "down", "down", "enter"),
        )

        self.assertEqual(1, len(plans))
        self.assertEqual("codex", plans[0].host)
        self.assertTrue(plans[0].reset)
        self.assertFalse(plans[0].include_template)
        rendered = output.getvalue()
        self.assertIn("Codex", rendered)
        self.assertNotIn("Claude", rendered)
        self.assertIn("Components", rendered)
        self.assertIn("Settings", rendered)
        self.assertIn("Reset", rendered)

    def test_codex_global_config_is_opt_in(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "version": "0.145.0",
                    "components": [
                        {
                            "name": "hukuhaka-report-planner",
                            "kind": "plugin",
                            "default": True,
                            "lifecycle": "supported",
                        }
                    ],
                    "selected": {"hukuhaka-report-planner"},
                }
            ],
            keys=(
                "down",
                "down",
                "down",
                "toggle",
                "down",
                "down",
                "down",
                "down",
                "down",
                "enter",
            ),
        )

        self.assertEqual(1, len(plans))
        self.assertTrue(plans[0].configure_codex)
        rendered = output.getvalue()
        self.assertIn("Configure global Codex defaults", rendered)
        self.assertIn("Select recommended components", rendered)
        self.assertLess(rendered.index("Components"), rendered.index("Settings"))
        self.assertLess(rendered.index("Settings"), rendered.index("Reset"))

    def test_codex_context_window_is_opt_in_and_shows_its_status(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "version": "0.147.0",
                    "components": [
                        {
                            "name": "hukuhaka-report-planner",
                            "kind": "plugin",
                            "default": True,
                            "lifecycle": "supported",
                        }
                    ],
                    "selected": {"hukuhaka-report-planner"},
                    "context_status": "Codex/model defaults",
                }
            ],
            keys=(
                "down",
                "down",
                "down",
                "down",
                "toggle",
                "down",
                "down",
                "down",
                "down",
                "enter",
            ),
        )

        self.assertEqual(1, len(plans))
        self.assertTrue(plans[0].change_context_window)
        self.assertIn(
            "Configure context & auto-compaction (Codex/model defaults)",
            output.getvalue(),
        )

    def test_codex_agent_policy_is_opt_in_and_shows_its_status(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "version": "0.149.1",
                    "components": [
                        {
                            "name": "hukuhaka-report-planner",
                            "kind": "plugin",
                            "default": True,
                            "lifecycle": "supported",
                        }
                    ],
                    "selected": {"hukuhaka-report-planner"},
                    "agent_policy_status": "Codex defaults",
                }
            ],
            keys=(
                "down",
                "down",
                "down",
                "down",
                "down",
                "toggle",
                "down",
                "down",
                "down",
                "enter",
            ),
        )

        self.assertEqual(1, len(plans))
        self.assertTrue(plans[0].change_agent_policy)
        self.assertIn(
            "Configure agent concurrency & nesting (Codex defaults)",
            output.getvalue(),
        )

    def test_enabled_codex_with_no_components_is_an_exact_empty_state(self) -> None:
        plans = prompt_install_plan(
            io.StringIO(),
            io.StringIO(),
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "components": [{"name": "planner", "kind": "plugin"}],
                    "selected": {"planner"},
                }
            ],
            keys=("down", "toggle", "down", "down", "down", "down", "down", "down", "down", "enter"),
        )

        self.assertEqual(1, len(plans))
        self.assertEqual([], plans[0].components)


if __name__ == "__main__":
    unittest.main()
