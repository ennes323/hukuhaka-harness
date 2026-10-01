"""Claude lifecycle counterexamples using a persistent native-CLI stand-in.

The fake implements CLI inventory and mutation boundaries, not installer methods.
All installer inputs, native state, homes, and source checkouts are temporary.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.install.claude import ClaudeInstaller, SOURCE_RECORD
from scripts.install.common import DriftError, FileTransaction, InstallerError
from scripts.install.state import InstallState


FAKE_CLI = r'''#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
state_path = Path(os.environ["FAKE_CLAUDE_STATE"])
state = json.loads(state_path.read_text())
with Path(os.environ["FAKE_CLAUDE_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\n")
key = " ".join(args[:3])
failure = state.get("failure")
fail = failure and key == failure["command"]
if fail and not failure.get("after_mutation"):
    state.pop("failure")
    state_path.write_text(json.dumps(state))
    print("secret-cli-output-must-not-be-promoted", file=sys.stderr)
    sys.exit(17)

result = None
if args == ["--version"]:
    result = state.get("version", "2.1.286 (Claude Code)")
elif args[:3] == ["plugin", "list", "--json"]:
    result = state["plugins"]
elif args[:4] == ["plugin", "marketplace", "list", "--json"]:
    result = state["marketplaces"]
elif args[:3] == ["plugin", "validate", "--strict"]:
    manifest = Path(args[3]) / ".claude-plugin/plugin.json"
    assert manifest.is_file(), str(manifest)
    metadata = json.loads(manifest.read_text())
    assert metadata["name"] and metadata["version"]
    result = "valid"
elif args[:3] == ["plugin", "marketplace", "add"]:
    source = Path(args[3])
    market = json.loads((source / ".claude-plugin/marketplace.json").read_text())
    state["marketplaces"].append({"name": market["name"], "source": "directory", "path": str(source), "installLocation": str(source)})
    result = "added"
elif args[:3] == ["plugin", "marketplace", "update"]:
    assert any(row["name"] == args[3] for row in state["marketplaces"])
    result = "updated"
elif args[:3] == ["plugin", "marketplace", "remove"]:
    state["marketplaces"] = [row for row in state["marketplaces"] if row["name"] != args[3]]
    result = "removed"
elif args[:2] in (["plugin", "install"], ["plugin", "update"]):
    identity = args[2]
    name, marketplace = identity.split("@")
    registered = next(row for row in state["marketplaces"] if row["name"] == marketplace)
    source = Path(registered["path"]) / name
    metadata = json.loads((source / ".claude-plugin/plugin.json").read_text())
    cache = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "plugins/cache" / marketplace / name / metadata["version"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, cache, dirs_exist_ok=True)
    previous = next((row for row in state["plugins"] if row["id"] == identity and row["scope"] == "user"), None)
    enabled = previous["enabled"] if args[1] == "update" and previous else True
    row = {"id": identity, "scope": "user", "version": metadata["version"], "enabled": enabled, "installPath": str(cache)}
    state["plugins"] = [p for p in state["plugins"] if not (p["id"] == identity and p["scope"] == "user")] + [row]
    result = {"success": True}
elif args[:2] == ["plugin", "enable"]:
    for row in state["plugins"]:
        if row["id"] == args[2] and row["scope"] == "user":
            row["enabled"] = True
    result = {"success": True}
elif args[:2] == ["plugin", "uninstall"]:
    assert "--scope" in args and args[args.index("--scope") + 1] == "user"
    assert "--keep-data" in args
    state["plugins"] = [p for p in state["plugins"] if not (p["id"] == args[2] and p["scope"] == "user")]
    result = {"success": True}
else:
    raise RuntimeError("unexpected fake CLI command: " + str(args))
if fail:
    state.pop("failure")
state_path.write_text(json.dumps(state))
if fail:
    print("secret-cli-output-must-not-be-promoted", file=sys.stderr)
    sys.exit(17)
if state.get("malformed_inventory") and args[:2] == ["plugin", "list"]:
    print('{"plugins": "not-an-array"}')
else:
    print(json.dumps(result) if isinstance(result, (list, dict)) else result)
'''


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ClaudeInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="harness claude lifecycle ")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.repo = self.base / "bootstrap checkout"
        self.home = self.base / "claude home"
        self.codex = self.base / "codex home"
        self.bin = self.base / "bin"
        for directory in (self.repo, self.home, self.codex, self.bin):
            directory.mkdir()
        self.native_path = self.base / "native.json"
        self.log = self.base / "commands.jsonl"
        self.native_path.write_text(json.dumps({"plugins": [], "marketplaces": []}))
        executable = self.bin / "claude"
        executable.write_text(FAKE_CLI)
        executable.chmod(0o755)
        env = patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "CLAUDE_CONFIG_DIR": str(self.home),
            "CODEX_HOME": str(self.codex),
            "FAKE_CLAUDE_STATE": str(self.native_path),
            "FAKE_CLAUDE_LOG": str(self.log),
        })
        env.start()
        self.addCleanup(env.stop)
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        (self.repo / "templates").mkdir()
        (self.repo / "templates/CLAUDE.md").write_text("# Common guidance\nPreserve project contracts.\n")
        self.names = ["hukuhaka-alpha", "hukuhaka-beta"]
        components = []
        for name in self.names:
            plugin = self.repo / "marketplace" / name
            (plugin / ".claude-plugin").mkdir(parents=True)
            manifest = plugin / ".claude-plugin/plugin.json"
            manifest.write_text(json.dumps({"name": name, "version": "1.0.1", "description": "Fixture plugin", "skills": "./skills/"}))
            (plugin / "skills/fixture").mkdir(parents=True)
            (plugin / "skills/fixture/SKILL.md").write_text("---\nname: fixture\ndescription: Fixture\n---\nShared instructions.\n")
            components.append({"name": name, "kind": "plugin", "hosts": {"claude": {"manifest": manifest.relative_to(self.repo).as_posix()}}})
        components.append({"name": "claude-md", "kind": "template", "hosts": {"claude": {}}})
        components.append({"name": "codex-only-worker", "kind": "agent", "hosts": {"codex": {}}})
        self.catalog = {"marketplaces": {"claude": "hukuhaka-plugin"}, "components": components}
        self.settings = b'{"model":"custom-model","effortLevel":"high","permissions":{"deny":["Bash(rm *)"]},"enabledPlugins":{"other@unrelated":true}}\n'
        (self.home / "settings.json").write_bytes(self.settings)
        (self.home / "agents").mkdir()
        (self.home / "agents/unmanaged.md").write_text("Keep unmanaged agent.\n")
        (self.codex / "config.toml").write_text('model = "preserve-codex"\n')

    def installer(self, **options) -> ClaudeInstaller:
        return ClaudeInstaller(self.repo, self.catalog, "9.0.0", local_source=False, **options)

    def native(self) -> dict:
        return json.loads(self.native_path.read_text())

    def change_native(self, **values) -> None:
        state = self.native()
        state.update(values)
        self.native_path.write_text(json.dumps(state))

    def commands(self) -> list:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def mutations(self) -> list:
        return [cmd for cmd in self.commands() if cmd[:2] in (["plugin", "install"], ["plugin", "update"], ["plugin", "enable"], ["plugin", "uninstall"])
                or cmd[:3] in (["plugin", "marketplace", "add"], ["plugin", "marketplace", "update"], ["plugin", "marketplace", "remove"])]

    def snapshot(self, root: Path) -> dict:
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.is_symlink()}

    def protected_snapshot(self) -> dict:
        # Failed preflights may append truthful installer operation records.
        # They must not change user inputs, native source, or legacy receipts.
        records = {"hk-config.toml", "hk-config.toml.bak", "hk-operation.lock", ".hukuhaka-installer.lock"}
        return {p: content for p, content in self.snapshot(self.home).items() if p not in records}

    def installed(self) -> set:
        return {row["id"].split("@")[0] for row in self.native()["plugins"] if row["scope"] == "user"}

    def assert_preserved(self) -> None:
        self.assertEqual(self.settings, (self.home / "settings.json").read_bytes())
        self.assertEqual("Keep unmanaged agent.\n", (self.home / "agents/unmanaged.md").read_text())
        self.assertEqual('model = "preserve-codex"\n', (self.codex / "config.toml").read_text())

    def seed_legacy(self) -> tuple[dict, dict]:
        files = {"CLAUDE.md": b"# Legacy whole-file guidance\nObsolete legacy route.\n"}
        bridge = "plugins/hukuhaka-plugin/hukuhaka-codex/"
        files[bridge + ".claude-plugin/plugin.json"] = b'{"name":"hukuhaka-codex","version":"1.0.6"}\n'
        for index in range(104):
            files[bridge + f"legacy-{index}.md"] = f"Legacy bridge input {index}\n".encode()
        for relative, content in files.items():
            target = self.home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        receipt = {"schemaVersion": 2, "version": "1.0.6", "components": ["hukuhaka-codex", "claude-md"],
                   "files": list(files), "hashes": {p: digest(content) for p, content in files.items()}}
        (self.home / ".hukuhaka-manifest.json").write_text(json.dumps(receipt))
        self.change_native(plugins=[{"id": "hukuhaka-codex@hukuhaka-plugin", "scope": "user", "version": "1.0.6", "enabled": True, "installPath": "/legacy/cache"}],
                           marketplaces=[{"name": "hukuhaka-plugin", "source": "directory", "path": str(self.home / "plugins/hukuhaka-plugin"), "installLocation": str(self.home / "plugins/marketplaces/hukuhaka-plugin")}])
        return receipt, files

    def test_complete_selection_idempotence_reset_and_uninstall_preserve_other_surfaces(self) -> None:
        user_guidance = b"# Personal instructions\nPreserve this exact text.\n"
        (self.home / "CLAUDE.md").write_bytes(user_guidance)
        first = self.installer()
        first.install([*self.names, "claude-md"])
        guidance = (self.home / "CLAUDE.md").read_bytes()
        source = self.snapshot(first.source)
        self.installer().install([*self.names, "claude-md"])
        self.assertEqual(guidance, (self.home / "CLAUDE.md").read_bytes())
        self.assertEqual(source, self.snapshot(first.source))
        self.assertEqual(set(self.names), self.installed())
        self.installer().install([self.names[1], "claude-md"], reset=True)
        self.assertEqual({self.names[1]}, self.installed())
        self.assertEqual(1, len(self.native()["marketplaces"]))
        self.assertTrue(any(cmd[:2] == ["plugin", "uninstall"] and cmd[2].startswith(self.names[1]) for cmd in self.commands()))
        self.installer().uninstall()
        self.assertEqual(set(), self.installed())
        self.assertEqual([], self.native()["marketplaces"])
        self.assertEqual(user_guidance, (self.home / "CLAUDE.md").read_bytes())
        self.assertEqual({}, InstallState(self.home).read()["components"])
        self.assert_preserved()

    def test_dry_run_fresh_install_and_existing_reset_uninstall_are_read_only(self) -> None:
        for action in ("fresh", "reset", "uninstall"):
            with self.subTest(action=action):
                if action == "reset":
                    self.installer().install([*self.names, "claude-md"])
                before = self.snapshot(self.home)
                native_before = self.native()
                mutation_count = len(self.mutations())
                adapter = self.installer(dry_run=True)
                if action == "uninstall":
                    adapter.uninstall()
                else:
                    adapter.install([*self.names, "claude-md"], reset=action == "reset")
                self.assertEqual(before, self.snapshot(self.home))
                self.assertEqual(native_before, self.native())
                self.assertEqual(mutation_count, len(self.mutations()))

    def test_durable_registered_source_survives_deleted_bootstrap_checkout(self) -> None:
        adapter = self.installer()
        adapter.install([self.names[0]])
        registered = Path(self.native()["marketplaces"][0]["path"])
        shutil.rmtree(self.repo)
        self.assertEqual(adapter.source, registered)
        self.assertTrue((registered / self.names[0] / ".claude-plugin/plugin.json").is_file())
        self.assertTrue((registered / ".claude-plugin/marketplace.json").is_file())
        self.assert_preserved()

    def test_legacy_106_hash_receipt_becomes_managed_block_and_retains_bridge(self) -> None:
        receipt, files = self.seed_legacy()
        self.assertEqual(106, len(receipt["files"]))
        self.installer().install([self.names[0], "claude-md"])
        self.assertFalse((self.home / ".hukuhaka-manifest.json").exists())
        guidance = (self.home / "CLAUDE.md").read_bytes()
        self.assertIn(b"<!-- hukuhaka-harness:begin -->", guidance)
        self.assertNotIn(b"Obsolete legacy route", guidance)
        backup = self.home / "hk-backups/legacy" / ("CLAUDE-" + digest(files["CLAUDE.md"]) + ".md")
        self.assertEqual(files["CLAUDE.md"], backup.read_bytes())
        state = InstallState(self.home).read()
        self.assertEqual("legacy", state["components"][SOURCE_RECORD]["provenance"])
        self.assertIn("hukuhaka-codex", self.installed())
        for relative, content in files.items():
            if relative != "CLAUDE.md":
                self.assertEqual(content, (self.home / relative).read_bytes())
        self.installer().uninstall()
        self.assertEqual({"hukuhaka-codex"}, self.installed())
        self.assertEqual(1, len(self.native()["marketplaces"]))
        self.assertIn(SOURCE_RECORD, InstallState(self.home).read()["components"])
        self.assertFalse((self.home / "CLAUDE.md").exists())
        self.assert_preserved()

    def test_edited_legacy_guidance_blocks_migration_without_mutations(self) -> None:
        self.seed_legacy()
        (self.home / "CLAUDE.md").write_text("User edited legacy instructions.\n")
        before = self.protected_snapshot()
        with self.assertRaises(DriftError):
            self.installer().install([self.names[0], "claude-md"])
        self.assertEqual(before, self.protected_snapshot())
        self.assertEqual("failed", InstallState(self.home).read()["operations"][-1]["status"])
        self.assertEqual([], self.mutations())

    def test_edited_source_and_managed_guidance_require_force_but_unmanaged_content_survives(self) -> None:
        personal = b"# User-owned prose\n"
        (self.home / "CLAUDE.md").write_bytes(personal)
        adapter = self.installer()
        adapter.install([self.names[0], "claude-md"])
        skill = adapter.source / self.names[0] / "skills/fixture/SKILL.md"
        skill.write_text("User edit of managed source.\n")
        mutations = len(self.mutations())
        with self.assertRaises(DriftError):
            self.installer().install([self.names[0], "claude-md"])
        self.assertEqual(mutations, len(self.mutations()))
        self.installer(force=True).install([self.names[0], "claude-md"])
        guidance = self.home / "CLAUDE.md"
        guidance.write_bytes(guidance.read_bytes().replace(b"Preserve project contracts.", b"User changed managed sentence."))
        with self.assertRaises(DriftError):
            self.installer().uninstall()
        self.installer(force=True).uninstall()
        self.assertEqual(personal, guidance.read_bytes())
        self.assert_preserved()

    def test_unmanaged_collision_is_never_replaced_even_with_force(self) -> None:
        target = self.home / "plugins/hukuhaka-plugin" / self.names[0] / ".claude-plugin/plugin.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"Unmanaged collision.\n")
        before = self.protected_snapshot()
        with self.assertRaisesRegex(InstallerError, "unmanaged source file conflicts"):
            self.installer(force=True).install([self.names[0]])
        self.assertEqual(before, self.protected_snapshot())
        self.assertEqual([], self.mutations())

    def test_unmanaged_source_file_survives_removal(self) -> None:
        adapter = self.installer()
        adapter.install([self.names[0]])
        note = adapter.source / "personal-note.md"
        note.write_text("Not owned by installer.\n")
        self.installer().uninstall()
        self.assertEqual("Not owned by installer.\n", note.read_text())
        self.assertEqual([], self.native()["marketplaces"])

    def test_other_scope_plugin_keeps_source_and_registration(self) -> None:
        adapter = self.installer()
        adapter.install([self.names[0]])
        row = dict(self.native()["plugins"][0], scope="project")
        self.change_native(plugins=[*self.native()["plugins"], row])
        before = self.snapshot(adapter.source)
        self.installer().uninstall()
        self.assertEqual([row], self.native()["plugins"])
        self.assertEqual(before, self.snapshot(adapter.source))
        self.assertEqual(1, len(self.native()["marketplaces"]))

    def test_plugin_install_partial_side_effect_is_recorded_and_retry_reconciles(self) -> None:
        self.change_native(failure={"command": "plugin install " + self.names[0] + "@hukuhaka-plugin", "after_mutation": True})
        with self.assertRaises(InstallerError) as failed:
            self.installer().install(self.names)
        self.assertNotIn("secret-cli-output", str(failed.exception))
        self.assertEqual({self.names[0]}, self.installed())
        state = InstallState(self.home).read()
        self.assertEqual("partial", state["operations"][-1]["status"])
        self.assertEqual("plugin-install", state["operations"][-1]["error"]["stage"])
        self.assertIn(SOURCE_RECORD, state["components"])
        self.assertNotIn(self.names[0], state["components"])
        self.installer().install(self.names)
        self.assertEqual(set(self.names), self.installed())
        state = InstallState(self.home).read()
        self.assertEqual("success", state["operations"][-1]["status"])
        self.assertTrue(set(self.names) <= set(state["components"]))

    def test_disabled_desired_plugin_is_enabled_without_replacing_independent_settings(self) -> None:
        self.installer().install([self.names[0]])
        rows = self.native()["plugins"]
        rows[0]["enabled"] = False
        self.change_native(plugins=rows)
        self.installer().install([self.names[0]])
        self.assertTrue(self.native()["plugins"][0]["enabled"])
        self.assert_preserved()

    def test_uninstall_recovers_owned_pending_file_transaction_before_hash_preflight(self) -> None:
        adapter = self.installer()
        adapter.install([self.names[0]])
        owned = adapter.source / self.names[0] / "skills/fixture/SKILL.md"
        transaction = FileTransaction(self.home)
        transaction.__enter__()
        transaction.write_bytes(owned, b"Partially staged installer bytes.\n")
        # Simulate a killed installer: no __exit__, journal remains pending.
        self.assertTrue(InstallState(self.home).has_pending_transactions())
        self.installer().uninstall()
        self.assertFalse(InstallState(self.home).has_pending_transactions())
        self.assertEqual(set(), self.installed())
        self.assertEqual({}, InstallState(self.home).read()["components"])
        self.assert_preserved()

    def test_partial_uninstall_can_be_retried_without_discarding_settings_or_source(self) -> None:
        adapter = self.installer()
        adapter.install(self.names)
        self.change_native(failure={"command": "plugin uninstall " + self.names[0] + "@hukuhaka-plugin", "after_mutation": True})
        with self.assertRaises(InstallerError):
            self.installer().uninstall()
        self.assertEqual({self.names[1]}, self.installed())
        self.assertTrue((adapter.source / ".claude-plugin/marketplace.json").exists())
        self.installer().uninstall()
        self.assertEqual(set(), self.installed())
        self.assertEqual({}, InstallState(self.home).read()["components"])
        self.assert_preserved()

    def test_native_validation_failure_rolls_back_file_staging_and_records_failure(self) -> None:
        self.change_native(failure={"command": "plugin validate --strict"})
        with self.assertRaises(InstallerError):
            self.installer().install([self.names[0]])
        self.assertEqual([], self.mutations())
        self.assertFalse((self.home / "plugins/hukuhaka-plugin/.claude-plugin/marketplace.json").exists())
        self.assertEqual("failed", InstallState(self.home).read()["operations"][-1]["status"])
        self.installer().install([self.names[0]])
        self.assertEqual({self.names[0]}, self.installed())

    def test_version_floor_malformed_inventory_and_foreign_marketplace_block_mutation(self) -> None:
        for change, action in (
            ({"version": "2.1.280 (Claude Code)"}, lambda adapter: adapter.install([self.names[0]])),
            ({"version": "2.1.286 (Claude Code)", "malformed_inventory": True}, lambda adapter: adapter.current_component_state()),
            ({"malformed_inventory": False, "marketplaces": [{"name": "hukuhaka-plugin", "source": "github", "path": "foreign/source"}]}, lambda adapter: adapter.install([self.names[0]])),
        ):
            with self.subTest(change=change):
                self.change_native(**change)
                before = self.protected_snapshot()
                with self.assertRaises(InstallerError):
                    action(self.installer())
                self.assertEqual(before, self.protected_snapshot())
                self.assertEqual([], self.mutations())

    def test_symlinked_home_source_parent_is_rejected_without_touching_external_files(self) -> None:
        external = self.base / "external"
        external.mkdir()
        (external / "sentinel").write_text("Never modify.\n")
        (self.home / "plugins").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(InstallerError, "symlink"):
            self.installer().install([self.names[0]])
        self.assertEqual({"sentinel": b"Never modify.\n"}, self.snapshot(external))
        self.assertEqual([], self.mutations())

    def test_symlinked_config_home_is_rejected_before_lock_writes_follow_it(self) -> None:
        external = self.base / "external configured home"
        self.home.rename(external)
        self.home.symlink_to(external, target_is_directory=True)
        before = self.snapshot(external)
        with self.assertRaises(InstallerError):
            self.installer().install([self.names[0]])
        self.assertEqual(before, self.snapshot(external))
        self.assertEqual([], self.mutations())

    def test_legacy_receipt_traversal_is_rejected_even_with_force(self) -> None:
        outside = self.base / "outside.md"
        outside.write_text("Preserve external file.\n")
        receipt = {"schemaVersion": 2, "version": "1.0.6", "components": ["hukuhaka-codex"],
                   "files": ["plugins/hukuhaka-plugin/../../../outside.md"],
                   "hashes": {"plugins/hukuhaka-plugin/../../../outside.md": digest(outside.read_bytes())}}
        (self.home / ".hukuhaka-manifest.json").write_text(json.dumps(receipt))
        with self.assertRaises(InstallerError):
            self.installer(force=True).install([self.names[0]])
        self.assertEqual("Preserve external file.\n", outside.read_text())
        self.assertTrue((self.home / ".hukuhaka-manifest.json").exists())
        self.assertEqual([], self.mutations())


if __name__ == "__main__":
    unittest.main()
