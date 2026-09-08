from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex import CodexCustomAgentDeployment
from scripts.install.common import DriftError, InstallerError, StateError


class CustomAgentDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka custom agents ")
        self.root = Path(self.temp.name)
        self.codex_home = self.root / ".codex"
        self.codex_home.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def deployment(
        self,
        name: str,
        *,
        force: bool = False,
    ) -> CodexCustomAgentDeployment:
        source = self.root / "{}.toml".format(name)
        if not source.exists():
            source.write_text(
                'name = "{}"\nsandbox_mode = "read-only"\n'.format(name),
                encoding="utf-8",
            )
        return CodexCustomAgentDeployment(
            name,
            source,
            self.codex_home,
            "1.2.3",
            enabled=True,
            force=force,
        )

    def deploy(self, deployment: CodexCustomAgentDeployment) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            deployment.deploy()

    def test_fresh_repeat_and_remove_preserve_surrounding_agents_text(self) -> None:
        agents = self.codex_home / "AGENTS.md"
        original = b"# User guidance\n\nKeep this byte-for-byte.\n"
        agents.write_bytes(original)
        deployment = self.deployment("sample-agent")

        self.deploy(deployment)
        installed = agents.read_bytes()
        self.assertEqual(original, installed)
        manifest = deployment.manifest_path.read_bytes()
        self.deploy(self.deployment("sample-agent"))

        self.assertEqual(installed, agents.read_bytes())
        self.assertEqual(manifest, deployment.manifest_path.read_bytes())
        self.assertEqual(
            4,
            json.loads(manifest.decode("utf-8"))["schemaVersion"],
        )
        self.deployment("sample-agent").uninstall()
        self.assertEqual(original, agents.read_bytes())
        self.assertFalse(deployment.target.exists())
        self.assertFalse(deployment.manifest_path.exists())

    def test_byte_identical_unmanaged_agent_is_adopted(self) -> None:
        deployment = self.deployment("sample-agent")
        deployment.target.parent.mkdir()
        deployment.target.write_bytes(deployment.source.read_bytes())

        self.deploy(deployment)

        self.assertTrue(deployment.manifest_path.is_file())
        self.assertEqual(deployment.source.read_bytes(), deployment.target.read_bytes())

    def test_different_unmanaged_agent_is_preserved_without_force(self) -> None:
        deployment = self.deployment("sample-agent")
        deployment.target.parent.mkdir()
        deployment.target.write_text("user-owned\n", encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "unmanaged sample-agent"):
            deployment.deploy()

        self.assertEqual("user-owned\n", deployment.target.read_text(encoding="utf-8"))
        self.assertFalse(deployment.manifest_path.exists())

    def test_two_agents_coexist_and_uninstall_independently(self) -> None:
        first = self.deployment("first-agent")
        second = self.deployment("second-agent")
        self.deploy(first)
        self.deploy(second)

        self.assertFalse(first.routing_target.exists())
        self.assertTrue(first.target.exists())
        self.assertTrue(second.target.exists())

        first.uninstall()

        self.assertFalse(first.target.exists())
        self.assertFalse(second.routing_target.exists())
        second.verify()

    def test_managed_drift_requires_force(self) -> None:
        deployment = self.deployment("sample-agent")
        self.deploy(deployment)
        deployment.target.write_text("drifted\n", encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "managed sample-agent"):
            self.deployment("sample-agent").deploy()
        self.deploy(self.deployment("sample-agent", force=True))

        self.assertEqual(
            deployment.source.read_bytes(),
            deployment.target.read_bytes(),
        )

    def test_symlink_agent_and_manifest_are_rejected(self) -> None:
        deployment = self.deployment("sample-agent")
        deployment.target.parent.mkdir()
        deployment.target.symlink_to(deployment.source)

        with self.assertRaisesRegex(StateError, "regular file"):
            deployment.deploy()

        deployment.target.unlink()
        deployment.manifest_path.symlink_to(deployment.source)
        with self.assertRaisesRegex(StateError, "invalid sample-agent manifest"):
            deployment.deploy()

    def test_validation_failure_rolls_back_all_agent_files(self) -> None:
        deployment = self.deployment("sample-agent")
        agents = deployment.routing_target
        original = b"# Sentinel\n"
        agents.write_bytes(original)

        with mock.patch.object(
            deployment.config,
            "verify",
            side_effect=InstallerError("doctor failed"),
        ), self.assertRaisesRegex(InstallerError, "doctor failed"):
            deployment.deploy()

        self.assertEqual(original, agents.read_bytes())
        self.assertFalse(deployment.target.exists())
        self.assertFalse(deployment.manifest_path.exists())
        self.assertFalse(deployment.config.path.exists())

    def test_agent_install_does_not_use_or_warn_about_guidance_override(self) -> None:
        deployment = self.deployment("sample-agent")
        override = self.codex_home / "AGENTS.override.md"
        override.write_text("# Override\n", encoding="utf-8")
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            self.deploy(deployment)

        self.assertEqual("", stderr.getvalue())
        self.assertEqual(
            "# Override\n", override.read_text(encoding="utf-8")
        )

    def seed_legacy(self, deployment, *, schema=1, resources=False):
        deployment.target.parent.mkdir(exist_ok=True)
        deployment.target.write_bytes(deployment.source.read_bytes())
        block = deployment.begin + b"\nLegacy routing.\n" + deployment.end
        original = b"# User guidance\r\nKeep exactly.\r\n"
        deployment.routing_target.write_bytes(original + b"\n" + block + b"\n")
        deployment.routing_target.chmod(0o640)
        manifest = {
            "schemaVersion": schema, "component": deployment.name, "version": "1.0.0",
            "agentTarget": "agents/{}.toml".format(deployment.name),
            "agentHash": hashlib.sha256(deployment.target.read_bytes()).hexdigest(),
            "routingTarget": "AGENTS.md", "routingHash": hashlib.sha256(block).hexdigest(),
            "prefix": "\n", "suffix": "\n",
        }
        if resources:
            manifest["resources"] = []
            for target, source in deployment.resource_sources.items():
                content = b"old helper\n"
                deployment.resource_targets[target].write_bytes(content)
                manifest["resources"].append({"target": target, "hash": hashlib.sha256(content).hexdigest()})
        deployment.manifest_path.write_text(json.dumps(manifest))
        return original

    def test_legacy_upgrade_removes_owned_block_preserves_bytes_mode_and_repeats(self):
        deployment = self.deployment("sample-agent")
        original = self.seed_legacy(deployment)
        self.deploy(deployment)
        deployment.verify()
        self.assertEqual(original, deployment.routing_target.read_bytes())
        self.assertEqual(0o640, deployment.routing_target.stat().st_mode & 0o777)
        self.assertNotIn("routingHash", json.loads(deployment.manifest_path.read_text()))
        self.deploy(deployment)
        deployment.uninstall()
        self.assertEqual(original, deployment.routing_target.read_bytes())

    def test_legacy_upgrade_with_resources_updates_owned_old_helper(self):
        deployment = self.deployment("sample-agent")
        source = self.root / "helper.py"
        source.write_bytes(b"new helper\n")
        deployment = CodexCustomAgentDeployment(
            "sample-agent", deployment.source, self.codex_home, "1.2.3", enabled=True,
            accepted_schemas=(1, 2, 4), resources=((source, "agents/helper.py"),),
        )
        original = self.seed_legacy(deployment, schema=2, resources=True)
        self.deploy(deployment)
        deployment.verify()
        self.assertEqual(source.read_bytes(), (self.codex_home / "agents/helper.py").read_bytes())
        self.assertEqual(original, deployment.routing_target.read_bytes())
        deployment.uninstall()
        self.assertFalse((self.codex_home / "agents/helper.py").exists())

    def test_legacy_edited_block_or_separator_rejects_without_writes(self):
        for edit in (lambda b: b.replace(b"Legacy routing", b"User edit"),
                     lambda b: b.replace(b"\n<!--", b"x<!--")):
            with self.subTest(edit=edit):
                deployment = self.deployment("sample-agent")
                self.seed_legacy(deployment)
                deployment.routing_target.write_bytes(edit(deployment.routing_target.read_bytes()))
                before = {p: p.read_bytes() for p in (deployment.target, deployment.manifest_path, deployment.routing_target)}
                with self.assertRaises(DriftError):
                    deployment.deploy()
                with self.assertRaises(DriftError):
                    deployment.uninstall()
                self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_legacy_dry_run_and_failed_upgrade_preserve_old_state(self):
        deployment = self.deployment("sample-agent")
        self.seed_legacy(deployment)
        before = {p: p.read_bytes() for p in (deployment.target, deployment.manifest_path, deployment.routing_target)}
        deployment.dry_run = True
        deployment.deploy()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        deployment.dry_run = False
        with mock.patch.object(deployment.config, "verify", side_effect=InstallerError("failed")), \
                self.assertRaises(InstallerError):
            deployment.deploy()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(deployment.config.path.exists())

    def test_agent_lifecycle_never_follows_unowned_guidance_symlink(self):
        deployment = self.deployment("sample-agent")
        external = self.root / "external.md"
        external.write_bytes(b"foreign text\xff")
        deployment.routing_target.symlink_to(external)
        self.deploy(deployment)
        deployment.verify()
        deployment.uninstall()
        self.assertTrue(deployment.routing_target.is_symlink())
        self.assertEqual(b"foreign text\xff", external.read_bytes())

    def test_legacy_uninstall_preserves_other_managed_blocks_and_user_guidance(self):
        first = self.deployment("first-agent")
        original = self.seed_legacy(first)
        first_bytes = first.routing_target.read_bytes()
        second = self.deployment("second-agent")
        self.seed_legacy(second)
        second_block = second.routing_target.read_bytes()[len(original):]
        first.routing_target.write_bytes(first_bytes + second_block)
        first.uninstall()
        self.assertEqual(original + second_block, second.routing_target.read_bytes())
        second.uninstall()
        self.assertEqual(original, second.routing_target.read_bytes())

    def test_legacy_missing_block_can_finish_upgrade_but_malformed_block_cannot(self):
        deployment = self.deployment("sample-agent")
        original = self.seed_legacy(deployment)
        deployment.routing_target.write_bytes(original)
        self.deploy(deployment)
        self.assertEqual(original, deployment.routing_target.read_bytes())
        self.seed_legacy(deployment)
        malformed = deployment.routing_target.read_bytes().replace(deployment.end, b"")
        deployment.routing_target.write_bytes(malformed)
        with self.assertRaises(StateError):
            deployment.deploy()
        self.assertEqual(malformed, deployment.routing_target.read_bytes())


if __name__ == "__main__":
    unittest.main()
