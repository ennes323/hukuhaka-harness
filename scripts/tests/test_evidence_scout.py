from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest import mock

from scripts.install.codex import (
    EVIDENCE_SCOUT_MANIFEST,
    CodexEvidenceScoutDeployment,
    CodexInstaller,
)
from scripts.install.codex_config import (
    EVIDENCE_SCOUT_SETTINGS,
    current_values,
    update_config,
)
from scripts.install.common import DriftError, InstallerError
from scripts.install.terminal import prompt_install_plan


ROOT = Path(__file__).resolve().parents[2]


class EvidenceScoutDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka evidence scout ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.source = ROOT / "scripts/tests/fixtures/archived-agents/evidence-scout.toml"
        self.codex_home.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def deployment(self, *, force: bool = False) -> CodexEvidenceScoutDeployment:
        return CodexEvidenceScoutDeployment(
            self.source,
            self.codex_home,
            "1.2.3",
            enabled=True,
            force=force,
        )

    def seed_legacy_v2(
        self,
        *,
        pointer: Optional[str] = None,
        catalog: bytes = b'{"legacy":"luna-v2"}\n',
    ) -> None:
        agent = self.codex_home / "agents" / "evidence-scout.toml"
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(self.source.read_bytes())
        block = b"<!-- hukuhaka-evidence-scout:begin -->\nLegacy dynamic routing.\n<!-- hukuhaka-evidence-scout:end -->"
        (self.codex_home / "AGENTS.md").write_bytes(block + b"\n")
        if catalog:
            (self.codex_home / "models-luna-v2.json").write_bytes(catalog)
        owned_pointer = json.dumps(str(self.codex_home / "models-luna-v2.json"))
        config = update_config(
            "",
            {
                **EVIDENCE_SCOUT_SETTINGS,
                ("model_catalog_json",): pointer or owned_pointer,
            },
        )
        (self.codex_home / "config.toml").write_text(config, encoding="utf-8")
        manifest = {
            "schemaVersion": 2,
            "component": "evidence-scout",
            "version": "1.1.10",
            "agentTarget": "agents/evidence-scout.toml",
            "agentHash": hashlib.sha256(self.source.read_bytes()).hexdigest(),
            "routingTarget": "AGENTS.md",
            "routingHash": hashlib.sha256(block).hexdigest(),
            "catalogSource": "models_cache.json",
            "catalogSourceHash": "legacy-source-hash",
            "catalogTarget": "models-luna-v2.json",
            "catalogHash": hashlib.sha256(catalog).hexdigest(),
            "prefix": "",
            "suffix": "\n",
        }
        (self.codex_home / EVIDENCE_SCOUT_MANIFEST).write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def test_install_is_complete_and_idempotent(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
            self.assertFalse((self.codex_home / "AGENTS.md").exists())
            first_manifest = (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_bytes()
            self.deployment().deploy()

        self.assertEqual(
            self.source.read_bytes(),
            (self.codex_home / "agents" / "evidence-scout.toml").read_bytes(),
        )
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertEqual(
            first_manifest,
            (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_bytes(),
        )
        values = current_values(
            (self.codex_home / "config.toml").read_text(encoding="utf-8")
        )
        for key, expected in EVIDENCE_SCOUT_SETTINGS.items():
            self.assertEqual(expected, values[key])
        self.assertNotIn(("model_catalog_json",), values)
        manifest = json.loads(
            (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_text(encoding="utf-8")
        )
        self.assertEqual(4, manifest["schemaVersion"])
        self.assertNotIn("routingHash", manifest)
        self.assertNotIn("catalogTarget", manifest)

    def test_fresh_install_does_not_require_or_create_model_catalog(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertFalse((self.codex_home / "models_cache.json").exists())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())

    def test_install_preserves_user_agent_limit(self) -> None:
        config = self.codex_home / "config.toml"
        original = (
            "[agents]\n"
            "max_threads = 9 # legacy alias\n"
            'default_subagent_model = "user-model"\n'
        )
        config.write_text(original, encoding="utf-8")

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        migrated = config.read_text(encoding="utf-8")
        self.assertIn("max_threads = 9 # legacy alias\n", migrated)
        self.assertNotIn("max_concurrent_threads_per_session", migrated)
        self.assertIn('default_subagent_model = "user-model"\n', migrated)
        self.assertEqual(
            original.encode(),
            self.deployment().config.backup.read_bytes(),
        )

    def test_legacy_v2_install_migrates_to_native_luna_support(self) -> None:
        self.seed_legacy_v2()
        config = self.codex_home / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8")
            + '\n[agents.custom]\nvalue = "keep"\n',
            encoding="utf-8",
        )

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        values = current_values(config.read_text(encoding="utf-8"))
        self.assertNotIn(("model_catalog_json",), values)
        self.assertIn(
            '[agents.custom]\nvalue = "keep"', config.read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_text(encoding="utf-8")
        )
        self.assertEqual(4, manifest["schemaVersion"])
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_legacy_v2_migration_preserves_foreign_catalog_pointer(self) -> None:
        self.seed_legacy_v2(pointer='"/user/catalog.json"')

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        self.assertIn(
            'model_catalog_json = "/user/catalog.json"',
            (self.codex_home / "config.toml").read_text(encoding="utf-8"),
        )

    def test_legacy_v3_removes_routing_without_requiring_catalog(self) -> None:
        self.seed_legacy_v2(catalog=b"")
        path = self.codex_home / EVIDENCE_SCOUT_MANIFEST
        manifest = json.loads(path.read_text())
        manifest = {key: value for key, value in manifest.items() if not key.startswith("catalog")}
        manifest["schemaVersion"] = 3
        path.write_text(json.dumps(manifest))
        (self.codex_home / "config.toml").write_text("[features]\nmulti_agent = true\n")
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertEqual(4, json.loads(path.read_text())["schemaVersion"])

    def test_agent_install_leaves_override_unchanged_without_warning(self) -> None:
        override = self.codex_home / "AGENTS.override.md"
        override.write_text("# User override\n", encoding="utf-8")
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor"
        ):
            self.deployment().deploy()

        self.assertEqual("", stderr.getvalue())
        self.assertEqual("# User override\n", override.read_text(encoding="utf-8"))

    def test_legacy_catalog_drift_requires_force_and_force_removes_it(self) -> None:
        self.seed_legacy_v2()
        catalog = self.codex_home / "models-luna-v2.json"
        catalog.write_text('{"user":"change"}\n', encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            self.deployment().deploy()
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment(force=True).deploy()

        self.assertFalse(catalog.exists())
        self.assertNotIn(
            "model_catalog_json",
            (self.codex_home / "config.toml").read_text(encoding="utf-8"),
        )

    def test_missing_legacy_catalog_requires_force_to_remove_owned_pointer(self) -> None:
        self.seed_legacy_v2(catalog=b"")

        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            self.deployment().deploy()
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment(force=True).deploy()

        self.assertNotIn(
            "model_catalog_json",
            (self.codex_home / "config.toml").read_text(encoding="utf-8"),
        )

    def test_exact_manual_agent_is_adopted(self) -> None:
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.source.read_bytes())

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).is_file())
        self.assertEqual(self.source.read_bytes(), target.read_bytes())

    def test_conflicting_manual_agent_is_preserved_without_force(self) -> None:
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.parent.mkdir(parents=True)
        target.write_text("user agent\n", encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "unmanaged evidence-scout"):
            self.deployment().deploy()

        self.assertEqual("user agent\n", target.read_text(encoding="utf-8"))
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())

    def test_force_repairs_managed_agent_and_routing_drift(self) -> None:
        self.seed_legacy_v2()
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.write_text("changed\n", encoding="utf-8")
        agents = self.codex_home / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"dynamic", b"altered", 1))

        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            self.deployment().deploy()
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment(force=True).deploy()

        self.assertEqual(self.source.read_bytes(), target.read_bytes())
        self.assertFalse(agents.exists())

    def test_validation_failure_rolls_back_agent_routing_and_config(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        agents = self.codex_home / "AGENTS.md"
        config = self.codex_home / "config.toml"
        agents.write_text("# User guidance\n", encoding="utf-8")
        config.write_text('model = "user-model"\n', encoding="utf-8")
        original_agents = agents.read_bytes()
        original_config = config.read_bytes()

        with mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor",
            side_effect=InstallerError("injected doctor failure"),
        ):
            with self.assertRaisesRegex(InstallerError, "injected doctor failure"):
                self.deployment().deploy()

        self.assertEqual(original_agents, agents.read_bytes())
        self.assertEqual(original_config, config.read_bytes())
        self.assertFalse((self.codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())

    def test_uninstall_removes_only_managed_agent_and_routing(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        agents = self.codex_home / "AGENTS.md"
        agents.write_text("# User guidance\n", encoding="utf-8")
        agents.chmod(0o640)
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
        configured = (self.codex_home / "config.toml").read_bytes()

        CodexEvidenceScoutDeployment(
            self.source,
            self.codex_home,
            "1.2.3",
            enabled=False,
        ).uninstall()

        self.assertEqual("# User guidance\n", agents.read_text(encoding="utf-8"))
        self.assertEqual(0o640, stat.S_IMODE(agents.stat().st_mode))
        self.assertFalse((self.codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())
        self.assertEqual(configured, (self.codex_home / "config.toml").read_bytes())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())

    def test_uninstall_cleans_owned_legacy_catalog_and_pointer(self) -> None:
        self.seed_legacy_v2()

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            CodexEvidenceScoutDeployment(
                self.source,
                self.codex_home,
                "1.2.3",
                enabled=False,
            ).uninstall()

        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        self.assertNotIn(
            "model_catalog_json",
            (self.codex_home / "config.toml").read_text(encoding="utf-8"),
        )

    def test_uninstall_refuses_drifted_legacy_catalog_without_force(self) -> None:
        self.seed_legacy_v2()
        catalog = self.codex_home / "models-luna-v2.json"
        catalog.write_text('{"user":"change"}\n', encoding="utf-8")

        deployment = CodexEvidenceScoutDeployment(
            self.source,
            self.codex_home,
            "1.2.3",
            enabled=False,
        )
        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            deployment.uninstall()

        self.assertTrue(catalog.exists())
        self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())


class EvidenceScoutInstallerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka evidence integration ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.catalog = json.loads((ROOT / "components.json").read_text(encoding="utf-8"))
        self.environment = mock.patch.dict(
            os.environ, {"CODEX_HOME": str(self.codex_home)}
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_installer_tracks_and_removes_evidence_scout_component(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        with mock.patch("scripts.install.codex.shutil.which", return_value="/fake/codex"), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.seed_archived_scout()
            self.assertEqual({"evidence-scout"}, installer.current_components())
            installer.uninstall()
            self.assertEqual(set(), installer.current_components())

    def seed_archived_scout(self) -> None:
        CodexEvidenceScoutDeployment(
            ROOT / "scripts/tests/fixtures/archived-agents/evidence-scout.toml",
            self.codex_home, "1.2.3", enabled=True,
        ).deploy()

    def test_reset_replaces_archived_scout_with_worker_without_model_catalog(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        with mock.patch(
            "scripts.install.codex.shutil.which", return_value="/fake/codex"
        ), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor"
        ):
            self.seed_archived_scout()
            configured = (self.codex_home / "config.toml").read_bytes()
            installer.install(["astra_worker"], reset=True)

        self.assertTrue((self.codex_home / "agents" / "astra_worker.toml").is_file())
        self.assertFalse((self.codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())
        self.assertFalse((self.codex_home / "models_cache.json").exists())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        self.assertEqual(configured, (self.codex_home / "config.toml").read_bytes())

    def test_active_scout_installs_and_reinstalls_from_catalog_source(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        with mock.patch("scripts.install.codex.shutil.which", return_value="/fake/codex"), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            installer.install(["evidence-scout"])
            first = (self.codex_home / "agents/evidence-scout.toml").read_bytes()
            installer.install(["evidence-scout"])

        self.assertEqual((ROOT / "agents/evidence-scout.toml").read_bytes(), first)
        self.assertEqual(first, (self.codex_home / "agents/evidence-scout.toml").read_bytes())
        manifest = json.loads(
            (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_text(encoding="utf-8")
        )
        self.assertEqual(4, manifest.get("schemaVersion"))
        self.assertFalse(any(key.startswith("routing") for key in manifest))

    def test_replacement_preserves_modified_scout_as_conflict(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        with mock.patch("scripts.install.codex.shutil.which", return_value="/fake/codex"), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.seed_archived_scout()
            scout = self.codex_home / "agents/evidence-scout.toml"
            changed = scout.read_bytes() + b"\n# user change\n"
            scout.write_bytes(changed)
            with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
                installer.install(["astra_worker", "result-runner"])
            self.assertEqual(changed, scout.read_bytes())
            self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).is_file())
            self.assertTrue((self.codex_home / "agents/astra_worker.toml").is_file())

    def test_interactive_row_names_the_runtime_contract(self) -> None:
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
                            "name": "astra_worker",
                            "kind": "agent",
                            "description": "Astra low bounded implementation and review",
                            "default": False,
                            "lifecycle": "supported",
                        }
                    ],
                    "selected": {"astra_worker"},
                }
            ],
            keys=["exit"],
        )

        self.assertEqual([], plans)
        rendered = output.getvalue()
        self.assertIn("[x] astra_worker", rendered)
        self.assertIn("agent: Astra low bounded implementation and review", rendered)


if __name__ == "__main__":
    unittest.main()
