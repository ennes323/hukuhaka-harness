from __future__ import annotations

import contextlib
import io
import json
import stat
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.claude import ClaudeDeployment, resolve_claude_config_dir
from scripts.install.codex import CodexGuidanceDeployment, CodexInstaller
from scripts.install.common import (
    DriftError,
    FileTransaction,
    InstallerError,
    InstallerLock,
    StateError,
    sha256_file,
)
from scripts.install.main import (
    HostComponentState,
    HostResult,
    Installer,
    build_parser,
)
from scripts.install.terminal import HostInstallPlan, prompt_install_plan


ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ["hukuhaka-report-planner", "hukuhaka-codex", "claude-md"]


class InstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka installer ")
        self.home = Path(self.temp.name)
        self.native_plugins = mock.patch.object(
            ClaudeDeployment,
            "_native_plugins",
            side_effect=self._registered_claude_plugins,
        )
        self.native_plugins.start()

    def tearDown(self) -> None:
        self.native_plugins.stop()
        self.temp.cleanup()

    def _registered_claude_plugins(self) -> list[dict]:
        installed_path = self.claude / "plugins" / "installed_plugins.json"
        settings_path = self.claude / "settings.json"
        installed = (
            json.loads(installed_path.read_text(encoding="utf-8"))
            if installed_path.is_file()
            else {"plugins": {}}
        )
        settings = (
            json.loads(settings_path.read_text(encoding="utf-8"))
            if settings_path.is_file()
            else {}
        )
        enabled = settings.get("enabledPlugins", {})
        result = []
        for plugin_id, entries in installed.get("plugins", {}).items():
            if not isinstance(entries, list) or not entries:
                continue
            entry = dict(entries[0])
            entry.update(
                {
                    "id": plugin_id,
                    "enabled": enabled.get(plugin_id) is True,
                }
            )
            result.append(entry)
        return result

    @property
    def claude(self) -> Path:
        return self.home / ".claude"

    @property
    def manifest(self) -> Path:
        return self.claude / ".hukuhaka-manifest.json"

    def deployment(self, *, force: bool = False, dry_run: bool = False) -> ClaudeDeployment:
        return ClaudeDeployment(ROOT, self.claude, COMPONENTS, force=force, dry_run=dry_run)

    def test_fresh_reinstall_and_uninstall_are_idempotent(self) -> None:
        self.deployment().deploy()
        first = json.loads(self.manifest.read_text())
        self.deployment().deploy()
        second = json.loads(self.manifest.read_text())
        self.assertEqual(first["files"], second["files"])
        self.assertEqual(first["hashes"], second["hashes"])
        self.assertEqual(2, second["schemaVersion"])
        self.deployment(force=True).uninstall(confirm=False)
        self.assertFalse(self.manifest.exists())
        self.deployment(force=True).uninstall(confirm=False)

    def test_legacy_partial_state_converges_when_dropped_dirs_are_absent(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(
            json.dumps(
                {
                    "version": "1.0.9",
                    "components": ["hukuhaka-ltm", "hukuhaka-project-mapper"],
                    "files": [],
                }
            )
        )
        self.deployment().deploy()
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(2, manifest["schemaVersion"])
        self.assertEqual(set(COMPONENTS), set(manifest["components"]))

    def test_malformed_registry_fails_before_file_mutation(self) -> None:
        self.claude.mkdir(parents=True)
        (self.claude / "settings.json").write_text("{broken")
        with self.assertRaises(StateError):
            self.deployment().deploy()
        self.assertFalse((self.claude / "CLAUDE.md").exists())
        self.assertEqual("{broken", (self.claude / "settings.json").read_text())

    def test_malformed_manifest_fields_fail_before_file_mutation(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(json.dumps({"schemaVersion": 2, "files": {}, "hashes": []}))
        with self.assertRaises(StateError):
            self.deployment().deploy()
        self.assertFalse((self.claude / "CLAUDE.md").exists())

    def test_managed_file_drift_requires_force(self) -> None:
        self.deployment().deploy()
        target = self.claude / "CLAUDE.md"
        target.write_text("user edit\n")
        with self.assertRaises(DriftError):
            self.deployment().deploy()
        self.assertEqual("user edit\n", target.read_text())
        self.deployment(force=True).deploy()
        self.assertNotEqual("user edit\n", target.read_text())

    def test_apply_failure_rolls_back_files_and_manifest(self) -> None:
        self.deployment().deploy()
        target = self.claude / "CLAUDE.md"
        target.write_text("pre-transaction edit\n")
        original_manifest = self.manifest.read_bytes()
        deployment = self.deployment(force=True)
        with mock.patch.object(
            deployment,
            "_write_registries",
            side_effect=InstallerError("injected registry failure"),
        ):
            with self.assertRaises(InstallerError):
                deployment.deploy()
        self.assertEqual("pre-transaction edit\n", target.read_text())
        self.assertEqual(original_manifest, self.manifest.read_bytes())

    def test_reset_install_failure_restores_the_previous_install(self) -> None:
        self.deployment().deploy()
        original_manifest = self.manifest.read_bytes()
        target = self.claude / "CLAUDE.md"
        original_target = target.read_bytes()
        deployment = self.deployment(force=True)
        with mock.patch.object(
            deployment,
            "_write_registries",
            side_effect=InstallerError("injected reset failure"),
        ):
            with self.assertRaises(InstallerError):
                deployment.deploy(reset=True, reset_template=True)
        self.assertEqual(original_manifest, self.manifest.read_bytes())
        self.assertEqual(original_target, target.read_bytes())

    def test_pending_transaction_is_recovered_on_next_run(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        self.assertEqual("new\n", target.read_text())
        self.assertEqual(1, FileTransaction.recover_pending(self.claude))
        self.assertEqual("old\n", target.read_text())

    def test_uninstall_recovers_before_manifest_noop_check(self) -> None:
        deployment = self.deployment(force=True)
        deployment.deploy()
        transaction = FileTransaction(deployment.claude_dir)
        transaction.__enter__()
        transaction.remove(deployment.manifest_path)

        deployment.uninstall(confirm=False)

        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.claude / "CLAUDE.md").exists())

    def test_snapshot_is_not_journaled_until_backup_exists(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        with mock.patch("shutil.copy2", side_effect=OSError("injected backup failure")):
            with self.assertRaises(OSError):
                transaction.snapshot(target)
        journal = json.loads(transaction.journal_path.read_text())
        self.assertEqual([], journal["entries"])
        transaction.__exit__(None, None, None)

    def test_failed_rollback_keeps_recovery_evidence(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        with mock.patch("shutil.copy2", side_effect=OSError("injected restore failure")):
            with self.assertRaises(StateError):
                transaction.__exit__(InstallerError, InstallerError("boom"), None)
        # The journal and its backups must survive a failed rollback, otherwise
        # the state root is left half-written with nothing left to replay.
        self.assertTrue(transaction.journal_path.is_file())
        self.assertEqual(1, FileTransaction.recover_pending(self.claude))
        self.assertEqual("old\n", target.read_text())

    def test_successful_rollback_removes_the_transaction_directory(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        transaction.__exit__(InstallerError, InstallerError("boom"), None)
        self.assertEqual("old\n", target.read_text())
        self.assertFalse(transaction.root.exists())

    def test_recovery_rejects_target_outside_state_root(self) -> None:
        self.claude.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.entries = [
            {"target": str(outside), "existed": False, "backup": "backups/000000"}
        ]
        transaction._write_journal("pending")
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.claude)
        self.assertEqual("keep\n", outside.read_text())
        transaction.__exit__(None, None, None)

    def test_transaction_refuses_targets_outside_its_own_state_root(self) -> None:
        self.claude.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        try:
            # remove() has to check before its existence test. A missing "../x"
            # used to return False silently, and reset_for_install() then drops
            # the entry from the rewritten manifest -- laundering the evidence.
            with self.assertRaises(StateError):
                transaction.remove(self.claude / ".." / "never-existed.txt")
            # Removing the state root itself would rmtree the live transaction.
            with self.assertRaises(StateError):
                transaction.remove(self.claude)
            with self.assertRaises(StateError):
                transaction.snapshot(outside)
            journal = json.loads(transaction.journal_path.read_text())
            self.assertEqual([], journal["entries"])
            self.assertEqual("keep\n", outside.read_text())
        finally:
            transaction.__exit__(None, None, None)

    def test_uninstall_rejects_a_manifest_entry_outside_the_state_root(self) -> None:
        self.claude.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        self.manifest.write_text(
            json.dumps({"schemaVersion": 2, "files": ["../outside.txt"], "hashes": {}})
        )
        with self.assertRaises(StateError):
            self.deployment(force=True).uninstall(confirm=False)
        self.assertEqual("keep\n", outside.read_text())
        self.assertTrue(self.manifest.exists())

    def test_reset_rejects_an_entry_that_escapes_the_prefix_filter(self) -> None:
        self.claude.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        # Satisfies startswith("plugins/hukuhaka-plugin/") yet resolves to $HOME.
        escaping = "plugins/hukuhaka-plugin/../../../outside.txt"
        self.manifest.write_text(
            json.dumps({"schemaVersion": 2, "files": [escaping], "hashes": {}})
        )
        with self.assertRaises(StateError):
            self.deployment(force=True).reset_for_install()
        self.assertEqual("keep\n", outside.read_text())
        self.assertIn(escaping, json.loads(self.manifest.read_text())["files"])

    def test_deploy_rejects_a_stale_manifest_entry_outside_the_state_root(self) -> None:
        self.deployment().deploy()
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        manifest = json.loads(self.manifest.read_text())
        manifest["files"].append("../outside.txt")
        self.manifest.write_text(json.dumps(manifest))
        # force=True on purpose: _check_drift() returns early under --force, so
        # this proves the gate is in build_plan() and not the drift check.
        with self.assertRaises(StateError):
            self.deployment(force=True).deploy()
        self.assertEqual("keep\n", outside.read_text())
        self.assertTrue((self.claude / "CLAUDE.md").exists())

    def test_deploy_rejects_a_registry_key_that_escapes_the_marketplace_root(self) -> None:
        plugins_dir = self.claude / "plugins"
        plugins_dir.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        (plugins_dir / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "../../../outside.txt@hukuhaka-plugin": [
                            {"scope": "user", "version": "0"}
                        ]
                    },
                }
            )
        )
        with self.assertRaises(StateError):
            self.deployment().deploy()
        self.assertEqual("keep\n", outside.read_text())

    def test_a_symlinked_directory_inside_the_state_root_is_not_an_escape(self) -> None:
        # Executable form of the reason containment stays lexical: swapping
        # os.path.abspath() for Path.resolve() in ensure_within() breaks this.
        shared = self.home / "plugins-shared"
        shared.mkdir()
        self.claude.mkdir(parents=True)
        (self.claude / "plugins").symlink_to(shared, target_is_directory=True)
        self.deployment().deploy()
        self.assertTrue(self.manifest.exists())
        self.assertTrue((self.claude / "CLAUDE.md").exists())

    def test_uninstall_does_not_create_missing_registries(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "version": "1.0.11",
                    "components": [],
                    "files": [],
                    "hashes": {},
                }
            )
        )
        self.deployment(force=True).uninstall(confirm=False)
        self.assertFalse((self.claude / "settings.json").exists())
        self.assertFalse((self.claude / "plugins" / "installed_plugins.json").exists())
        self.assertFalse((self.claude / "plugins" / "known_marketplaces.json").exists())

    def test_uninstall_preserves_optional_statusline(self) -> None:
        self.deployment().deploy()
        settings_path = self.claude / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["statusLine"] = {"command": "npx ccstatusline"}
        settings_path.write_text(json.dumps(settings))
        legacy = self.claude / "statusline.sh"
        legacy.write_text("user managed\n")
        self.deployment(force=True).uninstall(confirm=False)
        self.assertEqual({"command": "npx ccstatusline"}, json.loads(settings_path.read_text())["statusLine"])
        self.assertEqual("user managed\n", legacy.read_text())

    def test_ghost_registry_and_directory_are_removed(self) -> None:
        plugins = self.claude / "plugins"
        marketplace = plugins / "hukuhaka-plugin"
        removed_names = ("hukuhaka-ltm", "hukuhaka-project-mapper")
        for name in removed_names:
            ghost_dir = marketplace / name
            ghost_dir.mkdir(parents=True)
            (ghost_dir / "old.txt").write_text("old")
        registry = plugins / "installed_plugins.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "{}@hukuhaka-plugin".format(name): [
                            {
                                "scope": "user",
                                "installPath": str(marketplace / name),
                                "version": "0",
                            }
                        ]
                        for name in removed_names
                    },
                }
            )
        )
        self.deployment().deploy()
        installed = json.loads(registry.read_text())["plugins"]
        for name in removed_names:
            self.assertNotIn("{}@hukuhaka-plugin".format(name), installed)
            self.assertFalse((marketplace / name).exists())

    def test_dry_run_creates_no_state(self) -> None:
        self.deployment(dry_run=True).deploy()
        self.assertFalse(self.claude.exists())

    def test_dry_run_uninstall_does_not_contend_for_the_lock(self) -> None:
        # InstallerLock.__enter__ mkdir()s the state root and writes a pid, so a
        # dry run that takes it both creates state and dies against a real
        # install already holding it. Reporting what --dry-run would remove must
        # not need exclusive access to anything.
        self.deployment().deploy()
        with InstallerLock(self.claude):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.deployment(dry_run=True).uninstall(confirm=False)
        self.assertIn("Dry run", output.getvalue())

    def test_current_component_state_reads_plugin_versions(self) -> None:
        deployment = ClaudeDeployment(
            ROOT,
            self.claude,
            ["hukuhaka-worklog"],
        )
        deployment.deploy()

        components, versions = deployment.current_component_state()

        self.assertEqual({"hukuhaka-worklog"}, components)
        self.assertEqual("0.4.0", versions["hukuhaka-worklog"])

    def test_current_component_state_treats_missing_version_as_unknown(self) -> None:
        deployment = ClaudeDeployment(
            ROOT,
            self.claude,
            ["hukuhaka-worklog"],
        )
        deployment.deploy()
        registry = self.claude / "plugins" / "installed_plugins.json"
        data = json.loads(registry.read_text())
        del data["plugins"]["hukuhaka-worklog@hukuhaka-plugin"][0]["version"]
        registry.write_text(json.dumps(data))

        components, versions = deployment.current_component_state()

        self.assertEqual({"hukuhaka-worklog"}, components)
        self.assertNotIn("hukuhaka-worklog", versions)

    def test_claude_config_dir_overrides_default_home(self) -> None:
        configured = self.home / "custom claude"

        self.assertEqual(
            configured.resolve(),
            resolve_claude_config_dir(
                {"CLAUDE_CONFIG_DIR": str(configured)},
                fallback_home=self.home,
            ),
        )
        self.assertEqual(
            self.claude.resolve(),
            resolve_claude_config_dir({}, fallback_home=self.home),
        )

    def test_native_version_mismatch_rolls_back_the_whole_claude_update(self) -> None:
        self.deployment().deploy()
        plugin_relative = (
            "plugins/hukuhaka-plugin/hukuhaka-report-planner/"
            ".claude-plugin/plugin.json"
        )
        plugin_path = self.claude / plugin_relative
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        plugin["version"] = "0.5.0"
        plugin_path.write_text(json.dumps(plugin), encoding="utf-8")

        registry_path = self.claude / "plugins" / "installed_plugins.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["plugins"][
            "hukuhaka-report-planner@hukuhaka-plugin"
        ][0]["version"] = "0.5.0"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["version"] = "1.1.7"
        manifest["hashes"][plugin_relative] = sha256_file(plugin_path)
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        before = {
            path.relative_to(self.claude).as_posix(): path.read_bytes()
            for path in self.claude.rglob("*")
            if path.is_file()
        }

        def stale_native_state() -> list[dict]:
            plugins = self._registered_claude_plugins()
            for item in plugins:
                if item["id"] == "hukuhaka-report-planner@hukuhaka-plugin":
                    item["version"] = "0.5.0"
            return plugins

        deployment = self.deployment()
        with mock.patch.object(
            deployment, "_native_plugins", side_effect=stale_native_state
        ):
            with self.assertRaisesRegex(
                InstallerError, "version or enabled state does not match"
            ):
                deployment.deploy()

        after = {
            path.relative_to(self.claude).as_posix(): path.read_bytes()
            for path in self.claude.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
    def test_dry_run_reset_does_not_contend_for_the_lock(self) -> None:
        # Over-correction guard: reset already avoided this with nullcontext and
        # must keep avoiding it now that both paths share one manager.
        self.deployment().deploy()
        with InstallerLock(self.claude):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.deployment(dry_run=True).reset_for_install()
        self.assertIn("[dry-run] rm", output.getvalue())

    def leave_interrupted_transaction(self) -> None:
        # Against the deployment's own state root: containment is lexical, and
        # ClaudeDeployment resolves home, so a journal written through the
        # unresolved spelling of the same directory would not compare equal.
        state_root = self.deployment().claude_dir
        transaction = FileTransaction(state_root)
        transaction.__enter__()
        transaction.write_bytes(state_root / "settings.json", b"interrupted\n")

    def test_uninstall_reports_a_recovered_transaction(self) -> None:
        # The count was discarded here, so an interrupted transaction was
        # replayed with nothing said about it.
        self.deployment().deploy()
        self.leave_interrupted_transaction()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.deployment(force=True).uninstall(confirm=False)
        self.assertIn("[recovered] 1 interrupted transaction(s)", output.getvalue())

    def test_reset_reports_a_recovered_transaction(self) -> None:
        self.deployment().deploy()
        self.leave_interrupted_transaction()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.deployment(force=True).reset_for_install()
        self.assertIn("[recovered] 1 interrupted transaction(s)", output.getvalue())

    def test_reset_preserves_template_and_rejects_modified_plugin(self) -> None:
        self.deployment().deploy()
        plugin = (
            self.claude
            / "plugins"
            / "hukuhaka-plugin"
            / "hukuhaka-report-planner"
            / ".claude-plugin"
            / "plugin.json"
        )
        plugin.write_text("user edit\n")
        with self.assertRaises(DriftError):
            self.deployment().reset_for_install()
        self.assertTrue(plugin.exists())

        self.deployment(force=True).reset_for_install()
        self.assertFalse(plugin.exists())
        self.assertTrue((self.claude / "CLAUDE.md").exists())
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(["claude-md"], manifest["components"])

    def test_reset_can_include_managed_template(self) -> None:
        self.deployment().deploy()
        self.deployment().reset_for_install(reset_template=True)
        self.assertFalse((self.claude / "CLAUDE.md").exists())
        self.assertFalse(self.manifest.exists())


class ClaudeNativeCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka claude native ")
        self.config_dir = Path(self.temp.name) / "config"
        self.deployment = ClaudeDeployment(
            ROOT,
            self.config_dir,
            ["hukuhaka-engineering-plan"],
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_native_plugin_list_rejects_malformed_json(self) -> None:
        completed = subprocess.CompletedProcess(
            ("claude", "plugin", "list", "--json"),
            0,
            stdout="{broken",
            stderr="",
        )
        with mock.patch(
            "scripts.install.claude.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(InstallerError, "invalid JSON"):
                self.deployment._native_plugins()

    def test_native_plugin_list_reports_command_failure(self) -> None:
        failure = subprocess.CalledProcessError(
            1,
            ("claude", "plugin", "list", "--json"),
            stderr="injected native failure",
        )
        with mock.patch(
            "scripts.install.claude.subprocess.run", side_effect=failure
        ):
            with self.assertRaisesRegex(InstallerError, "injected native failure"):
                self.deployment._native_plugins()


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
            "claude",
            "install",
            "--recommended",
            "--yes",
        )
        self.assertEqual(
            [
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-codex",
                "claude-md",
            ],
            installer._automation_components("claude"),
        )

    def test_explicit_selection_is_the_complete_desired_state(self) -> None:
        installer = self.installer(
            "claude",
            "install",
            "--components",
            "hukuhaka-engineering-plan",
        )
        self.assertEqual(
            ["hukuhaka-engineering-plan"],
            installer._automation_components("claude"),
        )

    def test_removed_legacy_components_are_unknown(self) -> None:
        for name in ("hukuhaka-ltm", "hukuhaka-project-mapper"):
            installer = self.installer(
                "claude", "install", "--components", name
            )
            with self.assertRaisesRegex(
                InstallerError, "unknown .* component '{}'".format(name)
            ):
                installer._automation_components("claude")

    def test_declared_alias_resolves_to_current_component(self) -> None:
        installer = self.installer(
            "claude",
            "install",
            "--components",
            "old-report-planner",
        )
        installer.aliases["old-report-planner"] = "hukuhaka-report-planner"
        self.assertEqual(
            ["hukuhaka-report-planner"],
            installer._automation_components("claude"),
        )

    def test_version_summary_covers_install_change_same_and_unknown(self) -> None:
        installer = self.installer(
            "claude",
            "install",
            "--recommended",
            "--yes",
        )
        plan = HostInstallPlan(
            "claude",
            [
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-codex",
                "claude-md",
            ],
        )

        summary = dict(
            installer._version_summary(
                plan,
                {
                    "hukuhaka-engineering-plan",
                    "hukuhaka-worklog",
                    "hukuhaka-codex",
                },
                {
                    "hukuhaka-engineering-plan": "0.0.9",
                    "hukuhaka-worklog": "0.4.0",
                },
            )
        )

        self.assertEqual(
            "not installed → 0.6.0",
            summary["hukuhaka-report-planner"],
        )
        self.assertEqual(
            "0.0.9 → 0.2.2",
            summary["hukuhaka-engineering-plan"],
        )
        self.assertEqual(
            "0.4.0 (same version)",
            summary["hukuhaka-worklog"],
        )
        self.assertEqual(
            "unknown → 0.4.1",
            summary["hukuhaka-codex"],
        )
        self.assertNotIn("claude-md", summary)

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
                                    "claude": {"manifest": "plugin.json"}
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
                    "claude",
                    "install",
                    "--recommended",
                    "--yes",
                ]
            )
            installer = Installer(args)

            with self.assertRaisesRegex(
                StateError, "invalid plugin manifest for planner"
            ):
                installer._components("claude")

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
                                    "claude": {"manifest": "plugin.json"}
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
                    "claude",
                    "install",
                    "--recommended",
                    "--yes",
                ]
            )
            installer = Installer(args)

            with self.assertRaisesRegex(
                StateError, "invalid plugin manifest for planner"
            ):
                installer._components("claude")

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
                "claude",
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

    def test_interactive_continues_to_codex_after_claude_failure(self) -> None:
        installer = self.installer()
        plans = [
            HostInstallPlan("claude", ["claude-md"]),
            HostInstallPlan("codex", ["agents-md"]),
        ]
        with mock.patch.object(installer, "_tty_available", return_value=True), \
             mock.patch("scripts.install.main.shutil.which", return_value="/fake"), \
             mock.patch.object(
                 installer,
                 "_current_state",
                 return_value=HostComponentState(set(), {}),
             ), \
             mock.patch.object(installer, "_host_version", return_value="test"), \
             mock.patch("scripts.install.main.prompt_install_plan", return_value=plans), \
             mock.patch.object(installer, "_confirm", return_value=True), \
             mock.patch.object(
                 installer,
                 "_apply_host",
                 side_effect=[
                     HostResult("claude", "failed", "injected"),
                     HostResult("codex", "success"),
                 ],
             ) as apply_host:
            self.assertEqual(1, installer.interactive())

        self.assertEqual(2, apply_host.call_count)

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

    def test_only_detected_hosts_are_rendered_and_reset_is_explicit(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "claude",
                    "label": "Claude Code",
                    "available": True,
                    "version": "2.1",
                    "components": [{"name": "planner", "kind": "plugin"}],
                    "selected": {"planner"},
                },
            ],
            keys=("down", "down", "down", "toggle", "down", "down", "enter"),
        )

        self.assertEqual(1, len(plans))
        self.assertEqual("claude", plans[0].host)
        self.assertTrue(plans[0].reset)
        self.assertFalse(plans[0].include_template)
        rendered = output.getvalue()
        self.assertIn("Claude Code", rendered)
        self.assertNotIn("Codex", rendered)
        self.assertIn("Components", rendered)
        self.assertIn("Reset", rendered)
        self.assertNotIn("Settings", rendered)

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

    def test_enabled_host_with_no_components_is_an_exact_empty_state(self) -> None:
        plans = prompt_install_plan(
            io.StringIO(),
            io.StringIO(),
            sections=[
                {
                    "host": "claude",
                    "label": "Claude Code",
                    "components": [{"name": "planner", "kind": "plugin"}],
                    "selected": {"planner"},
                }
            ],
            keys=("down", "toggle", "down", "down", "down", "down", "enter"),
        )

        self.assertEqual(1, len(plans))
        self.assertEqual([], plans[0].components)


if __name__ == "__main__":
    unittest.main()
