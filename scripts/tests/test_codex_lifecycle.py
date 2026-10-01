from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from unittest import mock

from scripts.install.codex import REMOTE_MARKETPLACE_SOURCE, CodexInstaller
from scripts.install.common import DriftError, InstallerError, InstallerLock, StateError
from scripts.install.state import InstallState, encode_state


ROOT = Path(__file__).resolve().parents[2]


class FakeCodex:
    def __init__(self) -> None:
        self.plugins = []  # type: List[Dict[str, str]]
        self.marketplace = False
        self.marketplace_source_type = ""
        self.marketplace_source = ""
        self.marketplace_root = ""
        self.marketplace_commit = ""
        self.marketplace_refs = {}  # type: Dict[str, str]
        self.fail_marketplace_refs = set()  # type: set[str]
        self.calls = []  # type: List[Sequence[str]]
        self.fail_add = ""

    def remote_marketplace(self, commit: str, *, ref: str = "v1.1.6") -> None:
        self.marketplace = True
        self.marketplace_source_type = "git"
        self.marketplace_source = REMOTE_MARKETPLACE_SOURCE
        self.marketplace_root = "/tmp/fake-marketplace"
        self.marketplace_commit = commit
        self.marketplace_refs[ref] = commit

    def git_commit(self, _root: Path, ref: str) -> Optional[str]:
        if not self.marketplace:
            return None
        if ref == "HEAD":
            return self.marketplace_commit or None
        suffix = "^{commit}"
        return self.marketplace_refs.get(
            ref[: -len(suffix)] if ref.endswith(suffix) else ref
        )

    def installed(self, name: str) -> None:
        self.plugins.append(
            {
                "name": name,
                "marketplaceName": "hukuhaka-harness",
                "pluginId": "{}@hukuhaka-harness".format(name),
            }
        )

    def run_json(self, command: Sequence[str], *, stage: str) -> Dict[str, Any]:
        self.calls.append(tuple(command))
        words = tuple(command[1:-1])
        if words == ("plugin", "list"):
            return {"installed": copy.deepcopy(self.plugins)}
        if words[:3] == ("plugin", "marketplace", "add"):
            ref = words[words.index("--ref") + 1] if "--ref" in words else ""
            if ref in self.fail_marketplace_refs:
                raise InstallerError("injected marketplace add failure for {}".format(ref))
            self.marketplace = True
            source = words[3]
            if source.startswith("/"):
                self.marketplace_source_type = "local"
                self.marketplace_source = source
                self.marketplace_root = source
            else:
                self.marketplace_source_type = "git"
                self.marketplace_source = REMOTE_MARKETPLACE_SOURCE
                self.marketplace_root = "/tmp/fake-marketplace"
                self.marketplace_commit = ref
                self.marketplace_refs[ref] = ref
            return {"alreadyAdded": False}
        if words == ("plugin", "marketplace", "list"):
            return {
                "marketplaces": (
                    [
                        {
                            "name": "hukuhaka-harness",
                            "marketplaceSource": {
                                "sourceType": self.marketplace_source_type,
                                "source": self.marketplace_source,
                            },
                            "root": self.marketplace_root,
                        }
                    ]
                    if self.marketplace
                    else []
                )
            }
        if words[:2] == ("plugin", "add"):
            name = words[2].split("@", 1)[0]
            if name == self.fail_add:
                raise InstallerError("injected plugin add failure")
            source = ROOT / "marketplace" / name
            metadata = json.loads(
                (source / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            version = str(metadata["version"])
            cache_root = (
                Path(os.environ["CODEX_HOME"])
                / "plugins"
                / "cache"
                / "hukuhaka-harness"
                / name
            )
            shutil.rmtree(cache_root, ignore_errors=True)
            installed_path = cache_root / version
            shutil.copytree(source, installed_path)
            self.plugins = [plugin for plugin in self.plugins if plugin["name"] != name]
            result = {
                "name": name,
                "marketplaceName": "hukuhaka-harness",
                "pluginId": "{}@hukuhaka-harness".format(name),
                "version": version,
                "installedPath": str(installed_path),
            }
            self.plugins.append(dict(result))
            return result
        if words[:2] == ("plugin", "remove"):
            plugin_id = words[2]
            name = plugin_id.split("@", 1)[0]
            self.plugins = [
                plugin for plugin in self.plugins if plugin["pluginId"] != plugin_id
            ]
            shutil.rmtree(
                Path(os.environ["CODEX_HOME"])
                / "plugins"
                / "cache"
                / "hukuhaka-harness"
                / name,
                ignore_errors=True,
            )
            return {}
        if words[:3] == ("plugin", "marketplace", "remove"):
            self.marketplace = False
            return {}
        raise AssertionError("unexpected command at {}: {}".format(stage, command))


class CodexLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka codex lifecycle ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.catalog = json.loads((ROOT / "components.json").read_text(encoding="utf-8"))
        self.catalog["components"][0]["aliases"] = ["old-report-planner"]
        self.fake = FakeCodex()
        self.environment = mock.patch.dict(
            os.environ, {"CODEX_HOME": str(self.codex_home)}
        )
        self.environment.start()
        self.which = mock.patch(
            "scripts.install.codex.shutil.which", return_value="/fake/codex"
        )
        self.which.start()
        self.runner = mock.patch(
            "scripts.install.codex.run_json", side_effect=self.fake.run_json
        )
        self.runner.start()
        self.doctor = mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor")
        self.doctor.start()

    def tearDown(self) -> None:
        self.doctor.stop()
        self.runner.stop()
        self.which.stop()
        self.environment.stop()
        self.temp.cleanup()

    def installer(self, *, local_source: bool = True) -> CodexInstaller:
        return CodexInstaller(
            ROOT,
            self.catalog,
            "1.2.3",
            local_source=local_source,
        )

    def test_native_removal_is_reconciled_without_treating_receipt_as_installed(self) -> None:
        state = InstallState(self.codex_home)
        for action in ("install", "reset", "uninstall"):
            with self.subTest(action=action):
                state.set_plugin("hukuhaka-worklog", "0.5.0", "1.2.3")
                installer = self.installer()
                before = state.path.read_bytes()
                self.assertEqual(set(), installer.current_components())
                self.assertEqual(before, state.path.read_bytes())
                installer.dry_run = True
                if action == "install":
                    installer.install([])
                elif action == "reset":
                    installer.reset(include_template=True)
                else:
                    installer.uninstall()
                self.assertEqual(before, state.path.read_bytes())
                installer.dry_run = False
                self.fake.calls.clear()
                if action == "install":
                    installer.install([])
                elif action == "reset":
                    installer.reset(include_template=True)
                else:
                    installer.uninstall()
                self.assertNotIn("hukuhaka-worklog", state.read()["components"])
                self.assertEqual("success", state.read()["operations"][-1]["status"])
                self.assertFalse(any(c[1:3] == ("plugin", "remove") for c in self.fake.calls))

    def test_exact_desired_state_adds_canonical_before_removing_alias_and_omitted(self) -> None:
        self.fake.installed("old-report-planner")
        self.fake.installed("hukuhaka-engineering-plan")

        self.installer().install(["hukuhaka-report-planner", "agents-md"])

        names = {plugin["name"] for plugin in self.fake.plugins}
        self.assertEqual({"hukuhaka-report-planner"}, names)
        add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "add")
        )
        remove_indices = [
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "remove")
        ]
        self.assertTrue(remove_indices)
        self.assertLess(add_index, min(remove_indices))
        agents_path = self.codex_home / "AGENTS.md"
        self.assertTrue(agents_path.is_file())
        self.assertIn(
            (ROOT / "templates" / "AGENTS.md").read_text().strip(),
            agents_path.read_text(),
        )

    def test_first_agent_failure_reports_no_completed_operation(self) -> None:
        agent = next(
            item
            for item in self.catalog["components"]
            if item.get("name") == "astra_worker"
        )
        agent["path"] = "agents/missing-astra-worker.toml"
        installer = self.installer()

        with self.assertRaisesRegex(InstallerError, "source is missing"):
            installer.install(["astra_worker"])

        self.assertEqual([], installer.completed)
        self.assertFalse(
            (self.codex_home / ".hukuhaka-astra_worker-manifest.json").exists()
        )

    def test_current_agent_resources_are_owned_and_drift_protected(self) -> None:
        self.catalog["components"].append({
            "name": "resource-probe",
            "kind": "agent",
            "lifecycle": "supported",
            "default": False,
            "path": "agents/astra_worker.toml",
            "resources": [{
                "source": "templates/AGENTS.md",
                "target": "agents/resource-probe.txt",
            }],
            "hosts": {"codex": {}},
        })
        resource = self.codex_home / "agents/resource-probe.txt"
        self.installer().install(["resource-probe"])
        self.assertEqual((ROOT / "templates/AGENTS.md").read_bytes(), resource.read_bytes())
        self.assertEqual(
            ["agents/resource-probe.txt"],
            [item["target"] for item in self.receipt("resource-probe")["resources"]],
        )
        self.installer().install(["resource-probe"])
        resource.write_text("edited\n", encoding="utf-8")
        with self.assertRaisesRegex(DriftError, "managed resource-probe files changed"):
            self.installer().install([])
        self.assertEqual("edited\n", resource.read_text(encoding="utf-8"))
        forced = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True, force=True)
        forced.install([])
        self.assertFalse(resource.exists())
        self.assertIsNone(self.receipt("resource-probe"))

    def test_current_agent_resource_source_failure_and_symlink_guard(self) -> None:
        component = {
            "name": "resource-probe",
            "kind": "agent",
            "lifecycle": "supported",
            "default": False,
            "path": "agents/astra_worker.toml",
            "resources": [{
                "source": "agents/missing-resource.txt",
                "target": "agents/resource-probe.txt",
            }],
            "hosts": {"codex": {}},
        }
        self.catalog["components"].append(component)
        with self.assertRaisesRegex(InstallerError, "resource.*source is missing"):
            self.installer().install(["resource-probe"])
        self.assertIsNone(self.receipt("resource-probe"))
        component["resources"][0]["source"] = "templates/AGENTS.md"
        self.installer().install(["resource-probe"])
        resource = self.codex_home / "agents/resource-probe.txt"
        resource.unlink()
        resource.symlink_to(ROOT / "README.md")
        with self.assertRaisesRegex(InstallerError, "must be a regular file"):
            self.installer().install([])

    def test_current_agent_resource_doctor_failure_rolls_back_payload_and_receipt(self) -> None:
        self.catalog["components"].append({
            "name": "resource-probe",
            "kind": "agent",
            "lifecycle": "supported",
            "default": False,
            "path": "agents/astra_worker.toml",
            "resources": [{
                "source": "templates/AGENTS.md",
                "target": "agents/resource-probe.txt",
            }],
            "hosts": {"codex": {}},
        })
        with mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor",
            side_effect=InstallerError("injected config doctor failure"),
        ), self.assertRaisesRegex(InstallerError, "injected config doctor failure"):
            self.installer().install(["resource-probe"])

        for target in (
            "agents/resource-probe.toml",
            "agents/resource-probe.txt",
            ".hukuhaka-resource-probe-manifest.json",
        ):
            self.assertFalse((self.codex_home / target).exists(), target)
        self.assertIsNone(self.receipt("resource-probe"))

    def test_later_agent_failure_preserves_earlier_success_for_partial_result(self) -> None:
        installer = self.installer()

        with mock.patch(
            "scripts.install.codex_config.CodexConfigEditor.verify",
            side_effect=[None, InstallerError("injected second agent validation failure")],
        ), self.assertRaisesRegex(InstallerError, "second agent validation failure"):
            installer.install(["astra_worker", "result-runner"])

        self.assertEqual(["installed astra_worker"], installer.completed)
        self.assertTrue(
            self.receipt("astra_worker") is not None
        )
        self.assertFalse(
            (self.codex_home / ".hukuhaka-result-runner-manifest.json").exists()
        )
        state = installer.state.read()
        operation = state["operations"][-1]
        self.assertEqual("partial", operation["status"])
        self.assertEqual("install:result-runner", operation["error"]["stage"])
        self.assertEqual({"astra_worker"}, set(state["components"]))

    def test_interrupted_operation_is_retained_and_nested_reset_is_one_attempt(self) -> None:
        state = InstallState(self.codex_home)
        interrupted = state.begin_operation("install", "1.2.0", ["astra_worker"])
        self.installer().install(["agents-md"], reset=True, include_template=True)
        operations = state.read()["operations"]
        self.assertEqual(2, len(operations))
        self.assertEqual(interrupted, operations[0]["id"])
        self.assertEqual("interrupted", operations[0]["status"])
        self.assertEqual("1.2.0", operations[0]["installer_version"])
        self.assertEqual("reset", operations[1]["action"])
        self.assertEqual(["agents-md"], operations[1]["requested"])
        self.assertEqual("success", operations[1]["status"])

    def test_concurrent_host_operation_cannot_mark_running_attempt_interrupted(self) -> None:
        state = InstallState(self.codex_home)
        with InstallerLock(self.codex_home, name="hk-operation.lock"):
            active = state.begin_operation("install", "1.2.0", ["agents-md"])
            before = state.path.read_bytes()
            with self.assertRaisesRegex(InstallerError, "already running"):
                self.installer().install(["agents-md"])
            self.assertEqual(before, state.path.read_bytes())
            self.assertEqual("running", state.read()["operations"][-1]["status"])
            self.assertEqual(active, state.read()["operations"][-1]["id"])

    def receipt(self, name="project-doc-reader"):
        return InstallState(self.codex_home).read()["components"].get(name, {}).get("receipt")

    def seed_released_reader(self) -> Path:
        fixture = ROOT / "scripts/tests/fixtures/installer-v1.2.0-reader/codex-home"
        shutil.copytree(fixture, self.codex_home, dirs_exist_ok=True)
        return self.codex_home / ".hukuhaka-project-doc-reader-manifest.json"

    def test_released_reader_is_removed_on_desired_state_install(self) -> None:
        manifest_path = self.seed_released_reader()
        self.assertEqual(1, len(json.loads(manifest_path.read_text())["resources"]))
        sentinel = self.codex_home / "agents/personal.toml"
        sentinel.write_bytes(b"personal\n")
        self.installer().install(["hukuhaka-project-docs"])
        self.assertFalse(manifest_path.exists())
        self.assertIsNone(self.receipt())
        self.assertEqual(b"personal\n", sentinel.read_bytes())
        for entry in ("agents/project-doc-reader.toml", "agents/project-doc-reader-tool.py"):
            self.assertFalse((self.codex_home / entry).exists())
        self.installer().install(["hukuhaka-project-docs"])
        self.assertIsNone(self.receipt())

    def test_retired_reader_central_v2_resources_are_removed(self) -> None:
        legacy_path = self.seed_released_reader()
        manifest = json.loads(legacy_path.read_text())
        for target in (
            "agents/project-doc-reader-protocol.py",
            "agents/project-doc-reader/reader-request-v2.schema.json",
            "agents/project-doc-reader/reader-response-v2.schema.json",
        ):
            path = self.codex_home / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(target.encode("utf-8"))
            manifest["resources"].append({"target": target, "hash": hashlib.sha256(path.read_bytes()).hexdigest()})
        state = InstallState(self.codex_home)
        data = state.read()
        data["components"]["project-doc-reader"] = {
            "kind": "agent", "version": "1.2.0", "installer_version": "1.2.0",
            "installed_at": "unknown", "provenance": "legacy", "receipt": manifest,
        }
        state.path.write_bytes(encode_state(data))
        legacy_path.unlink()
        self.installer().install(["hukuhaka-project-docs"])
        self.assertIsNone(self.receipt())
        for entry in manifest["resources"]:
            self.assertFalse((self.codex_home / entry["target"]).exists())
        self.assertFalse((self.codex_home / manifest["agentTarget"]).exists())

    def test_released_reader_deselection_preserves_unowned_new_resource(self) -> None:
        manifest_path = self.seed_released_reader()
        unowned = self.codex_home / "agents/project-doc-reader-protocol.py"
        unowned.write_bytes(b"personal helper\n")
        self.installer().install([])
        self.assertFalse(manifest_path.exists())
        self.assertIsNone(self.receipt())
        self.assertFalse((self.codex_home / "agents/project-doc-reader-tool.py").exists())
        self.assertEqual(b"personal helper\n", unowned.read_bytes())

    def test_retired_reader_legacy_routing_removal_preserves_user_text(self) -> None:
        manifest_path = self.seed_released_reader()
        manifest = json.loads(manifest_path.read_text())
        block = (
            b"<!-- hukuhaka-project-doc-reader:begin -->\n"
            b"Historical routing.\n"
            b"<!-- hukuhaka-project-doc-reader:end -->"
        )
        guidance = self.codex_home / "AGENTS.md"
        guidance.write_bytes(b"# User guidance\n\n" + block + b"\n")
        manifest.update({
            "schemaVersion": 1, "routingTarget": "AGENTS.md",
            "routingHash": hashlib.sha256(block).hexdigest(),
            "prefix": "\n\n", "suffix": "\n",
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.installer().install(["hukuhaka-project-docs"])
        self.assertEqual(b"# User guidance", guidance.read_bytes())
        self.assertIsNone(self.receipt())
        self.assertFalse((self.codex_home / "agents/project-doc-reader-tool.py").exists())

    def test_retired_reader_drift_fails_before_plugin_mutation(self) -> None:
        manifest = self.seed_released_reader()
        owned = self.codex_home / "agents/project-doc-reader-tool.py"
        before = manifest.read_bytes()
        self.fake.installed("hukuhaka-worklog")
        for content in (b"edited helper\n", b""):
            with self.subTest(content=content):
                owned.write_bytes(content)
                with self.assertRaisesRegex(DriftError, "managed project-doc-reader files changed"):
                    self.installer().install(["hukuhaka-engineering-plan"])
                self.assertEqual(["hukuhaka-worklog"], [p["name"] for p in self.fake.plugins])
                self.assertFalse(any(c[1:3] in (("plugin", "add"), ("plugin", "remove")) for c in self.fake.calls))
                self.assertEqual(before, manifest.read_bytes())
                self.assertEqual(content, owned.read_bytes())

    def test_resource_manifest_rejects_duplicate_and_unknown_owned_paths(self) -> None:
        manifest_path = self.seed_released_reader()
        original = json.loads(manifest_path.read_text())
        recorded = original["resources"][0]
        for resources in (
            [recorded, recorded],
            [{"target": "agents/personal.toml", "hash": recorded["hash"]}],
            [{"target": "../outside.py", "hash": recorded["hash"]}],
        ):
            with self.subTest(resources=resources):
                manifest_path.write_text(json.dumps(dict(original, resources=resources)))
                before = manifest_path.read_bytes()
                with self.assertRaisesRegex(StateError, "invalid project-doc-reader manifest"):
                    self.installer().install([])
                self.assertEqual(before, manifest_path.read_bytes())
                self.assertTrue((self.codex_home / "agents/project-doc-reader-tool.py").is_file())

    def test_reset_and_uninstall_preflight_preserve_state_then_retry(self) -> None:
        for action in ("install", "reset", "uninstall"):
            with self.subTest(action=action):
                manifest = self.seed_released_reader()
                original = manifest.read_bytes()
                manifest.write_text("{}")
                self.fake.plugins = []
                self.fake.installed("hukuhaka-worklog")
                self.fake.marketplace = True
                self.fake.calls.clear()
                installer = self.installer()
                def apply():
                    if action == "install":
                        installer.install(["hukuhaka-engineering-plan"], reset=True)
                    elif action == "reset":
                        installer.reset(include_template=True)
                    else:
                        installer.uninstall()
                with self.assertRaisesRegex(StateError, "invalid project-doc-reader manifest"):
                    apply()
                self.assertEqual(["hukuhaka-worklog"], [p["name"] for p in self.fake.plugins])
                self.assertTrue(self.fake.marketplace)
                self.assertEqual([], installer.completed)
                self.assertEqual("failed", InstallState(self.codex_home).read()["operations"][-1]["status"])
                self.assertEqual("{}", manifest.read_text())
                self.assertFalse(any(c[1:3] in (("plugin", "remove"), ("plugin", "add")) or c[1:4] == ("plugin", "marketplace", "remove") for c in self.fake.calls))
                manifest.write_bytes(original)
                apply()
                self.assertFalse(manifest.exists())
                self.assertIsNone(self.receipt())
                expected = ["hukuhaka-engineering-plan"] if action == "install" else []
                self.assertEqual(expected, [p["name"] for p in self.fake.plugins])

    def test_missing_guidance_is_restored_and_invalid_guidance_prevents_plugin_changes(self) -> None:
        self.installer().install(["agents-md"])
        guidance = self.codex_home / "AGENTS.md"
        guidance.write_bytes(b"# Personal guidance\n")
        self.installer().install(["agents-md", "hukuhaka-worklog"])
        self.assertTrue(guidance.read_bytes().startswith(b"# Personal guidance\n"))
        guidance.write_bytes(b"# Personal guidance\n<!-- hukuhaka-harness:begin -->\n")
        before = guidance.read_bytes()
        self.fake.calls.clear()
        with self.assertRaises(StateError):
            self.installer().install(["agents-md", "hukuhaka-engineering-plan"], reset=True, include_template=True)
        self.assertEqual(before, guidance.read_bytes())
        self.assertEqual(["hukuhaka-worklog"], [p["name"] for p in self.fake.plugins])
        self.assertFalse(any(c[1:3] in (("plugin", "add"), ("plugin", "remove")) for c in self.fake.calls))

    def test_remote_marketplace_is_pinned_to_the_resolved_release(self) -> None:
        with mock.patch("scripts.install.codex.git_commit", return_value="target"):
            self.installer(local_source=False).install(["hukuhaka-report-planner"])

        add = next(
            command
            for command in self.fake.calls
            if command[1:4] == ("plugin", "marketplace", "add")
        )
        self.assertEqual(("--ref", "v1.2.3"), add[-3:-1])

    def test_local_clone_replaces_official_remote_before_plugin_install(self) -> None:
        self.fake.remote_marketplace("old-commit")
        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            self.installer().install(["hukuhaka-worklog"])

        self.assertEqual("local", self.fake.marketplace_source_type)
        self.assertEqual(str(ROOT), self.fake.marketplace_source)
        mutations = [
            command[1:4]
            for command in self.fake.calls
            if command[1:4] in (
                ("plugin", "marketplace", "remove"),
                ("plugin", "marketplace", "add"),
            ) or command[1:3] == ("plugin", "add")
        ]
        self.assertEqual([
            ("plugin", "marketplace", "remove"),
            ("plugin", "marketplace", "add"),
            ("plugin", "add", "hukuhaka-worklog@hukuhaka-harness"),
        ], mutations)
        self.assertEqual("success", InstallState(self.codex_home).read()["operations"][-1]["status"])

    def test_local_clone_replaces_another_local_checkout(self) -> None:
        old_root = Path(self.temp.name) / "old clone"
        manifest = old_root / ".agents/plugins/marketplace.json"
        manifest.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / ".agents/plugins/marketplace.json", manifest)
        self.fake.marketplace = True
        self.fake.marketplace_source_type = "local"
        self.fake.marketplace_source = str(old_root)
        self.fake.marketplace_root = str(old_root)

        self.installer().install(["hukuhaka-worklog"])

        self.assertEqual(str(ROOT), self.fake.marketplace_source)
        self.assertTrue(manifest.is_file())
        self.assertEqual(["hukuhaka-worklog"], [p["name"] for p in self.fake.plugins])

    def test_local_clone_reuses_same_local_checkout_without_registration_mutation(self) -> None:
        self.fake.marketplace = True
        self.fake.marketplace_source_type = "local"
        self.fake.marketplace_source = str(ROOT)
        self.fake.marketplace_root = str(ROOT)

        self.installer().install(["hukuhaka-worklog"])

        self.assertFalse(any(
            command[1:4] in (
                ("plugin", "marketplace", "remove"),
                ("plugin", "marketplace", "add"),
            ) for command in self.fake.calls
        ))
        self.assertEqual(["hukuhaka-worklog"], [p["name"] for p in self.fake.plugins])

    def test_local_clone_preserves_foreign_remote(self) -> None:
        self.fake.remote_marketplace("foreign-commit")
        self.fake.marketplace_source = "https://github.com/example/fork.git"

        with self.assertRaisesRegex(InstallerError, "different source"):
            self.installer().install(["hukuhaka-worklog"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("https://github.com/example/fork.git", self.fake.marketplace_source)
        self.assertEqual("foreign-commit", self.fake.marketplace_commit)
        self.assertFalse(any(
            command[1:4] in (
                ("plugin", "marketplace", "remove"),
                ("plugin", "marketplace", "add"),
            ) or command[1:3] == ("plugin", "add")
            for command in self.fake.calls
        ))

    def test_failed_local_clone_registration_restores_exact_remote_head(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.add("")
        installer = self.installer()
        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            with self.assertRaisesRegex(InstallerError, "restored previous"):
                installer.install(["hukuhaka-worklog"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("git", self.fake.marketplace_source_type)
        self.assertEqual(REMOTE_MARKETPLACE_SOURCE, self.fake.marketplace_source)
        self.assertEqual("old-commit", self.fake.marketplace_commit)
        self.assertEqual([], self.fake.plugins)
        self.assertEqual([], installer.completed)
        operation = InstallState(self.codex_home).read()["operations"][-1]
        self.assertEqual("failed", operation["status"])

    def test_local_clone_rollback_failure_records_partial_operation(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.update(("", "old-commit"))
        installer = self.installer()
        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            with self.assertRaisesRegex(InstallerError, "rollback failed"):
                installer.install(["hukuhaka-worklog"])

        self.assertFalse(self.fake.marketplace)
        self.assertEqual([], self.fake.plugins)
        self.assertTrue(installer.completed)
        operation = InstallState(self.codex_home).read()["operations"][-1]
        self.assertEqual("partial", operation["status"])

    def test_failed_local_clone_registration_restores_old_local_checkout(self) -> None:
        old_root = Path(self.temp.name) / "old clone"
        old_root.mkdir()
        self.fake.marketplace = True
        self.fake.marketplace_source_type = "local"
        self.fake.marketplace_source = str(old_root)
        self.fake.marketplace_root = str(old_root)

        def fail_target(command: Sequence[str], *, stage: str) -> Dict[str, Any]:
            if tuple(command[1:5]) == ("plugin", "marketplace", "add", str(ROOT)):
                self.fake.calls.append(tuple(command))
                raise InstallerError("injected target checkout registration failure")
            return self.fake.run_json(command, stage=stage)

        with mock.patch("scripts.install.codex.run_json", side_effect=fail_target):
            with self.assertRaisesRegex(InstallerError, "restored previous source"):
                self.installer().install(["hukuhaka-worklog"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("local", self.fake.marketplace_source_type)
        self.assertEqual(old_root.resolve(), Path(self.fake.marketplace_source).resolve())
        self.assertFalse(any(command[1:3] == ("plugin", "add") for command in self.fake.calls))
        self.assertEqual("failed", InstallState(self.codex_home).read()["operations"][-1]["status"])

    def test_local_clone_rejects_empty_registered_source_without_mutation(self) -> None:
        self.fake.marketplace = True
        self.fake.marketplace_source_type = "local"
        self.fake.marketplace_source = ""
        self.fake.marketplace_root = str(ROOT)

        with self.assertRaisesRegex(InstallerError, "source is missing"):
            self.installer().install(["hukuhaka-worklog"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("", self.fake.marketplace_source)
        self.assertFalse(any(
            command[1:4] in (
                ("plugin", "marketplace", "remove"),
                ("plugin", "marketplace", "add"),
            ) or command[1:3] == ("plugin", "add")
            for command in self.fake.calls
        ))

    def test_remote_marketplace_old_ref_is_replaced_before_plugin_install(self) -> None:
        self.fake.remote_marketplace("old-commit")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            installer.install(["hukuhaka-report-planner"])

        self.assertEqual("v1.2.3", self.fake.marketplace_commit)
        remove_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:4] == ("plugin", "marketplace", "remove")
        )
        marketplace_add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:4] == ("plugin", "marketplace", "add")
        )
        plugin_add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "add")
        )
        self.assertLess(remove_index, marketplace_add_index)
        self.assertLess(marketplace_add_index, plugin_add_index)
        self.assertIn("updated marketplace to v1.2.3", installer.completed)

    def test_remote_marketplace_target_ref_is_reused(self) -> None:
        self.fake.remote_marketplace("target-commit", ref="v1.2.3")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            self.installer(local_source=False).install(["hukuhaka-report-planner"])

        marketplace_mutations = [
            command
            for command in self.fake.calls
            if command[1:4]
            in (
                ("plugin", "marketplace", "add"),
                ("plugin", "marketplace", "remove"),
            )
        ]
        self.assertEqual([], marketplace_mutations)

    def test_remote_marketplace_update_failure_restores_old_commit(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.add("v1.2.3")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            with self.assertRaisesRegex(InstallerError, "restored previous revision"):
                installer.install(["hukuhaka-report-planner"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("old-commit", self.fake.marketplace_commit)
        self.assertEqual([], installer.completed)

    def test_remote_marketplace_rollback_failure_is_partial(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.update(("v1.2.3", "old-commit"))

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            with self.assertRaisesRegex(InstallerError, "rollback failed"):
                installer.install(["hukuhaka-report-planner"])

        self.assertFalse(self.fake.marketplace)
        self.assertIn("marketplace update incomplete", installer.completed)

    def test_remote_marketplace_foreign_source_is_preserved(self) -> None:
        self.fake.remote_marketplace("foreign-commit")
        self.fake.marketplace_source = "https://github.com/example/fork.git"

        installer = self.installer(local_source=False)
        with self.assertRaisesRegex(InstallerError, "different source"):
            installer.install(["hukuhaka-report-planner"])

        self.assertTrue(self.fake.marketplace)
        self.assertFalse(
            any(
                command[1:4] == ("plugin", "marketplace", "remove")
                for command in self.fake.calls
            )
        )

    def test_remote_marketplace_without_head_is_preserved(self) -> None:
        self.fake.remote_marketplace("")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            with self.assertRaisesRegex(InstallerError, "cannot snapshot"):
                self.installer(local_source=False).install(
                    ["hukuhaka-report-planner"]
                )

        self.assertTrue(self.fake.marketplace)
        self.assertFalse(
            any(
                command[1:4] == ("plugin", "marketplace", "remove")
                for command in self.fake.calls
            )
        )

    def test_canonical_add_failure_preserves_existing_alias(self) -> None:
        self.fake.installed("old-report-planner")
        self.fake.fail_add = "hukuhaka-report-planner"

        with self.assertRaisesRegex(InstallerError, "injected plugin add failure"):
            self.installer().install(["hukuhaka-report-planner"])

        self.assertEqual(["old-report-planner"], [p["name"] for p in self.fake.plugins])
        self.assertFalse(
            any(command[1:3] == ("plugin", "remove") for command in self.fake.calls)
        )

    def test_missing_codex_cli_is_a_failure(self) -> None:
        with mock.patch("scripts.install.codex.shutil.which", return_value=None):
            with self.assertRaisesRegex(InstallerError, "codex CLI is required"):
                self.installer().uninstall()

    def test_reset_and_uninstall_do_not_touch_global_config(self) -> None:
        self.codex_home.mkdir(parents=True)
        config = self.codex_home / "config.toml"
        config.write_text('model = "user-choice"\n', encoding="utf-8")
        original = config.read_bytes()
        self.fake.installed("hukuhaka-report-planner")
        self.fake.marketplace = True

        self.installer().install(
            ["hukuhaka-engineering-plan"],
            reset=True,
            include_template=True,
        )
        self.assertEqual(original, config.read_bytes())
        installed = config.read_bytes()
        self.installer().reset(include_template=True)
        self.assertEqual(installed, config.read_bytes())
        self.installer().uninstall()
        self.assertEqual(installed, config.read_bytes())


if __name__ == "__main__":
    unittest.main()
