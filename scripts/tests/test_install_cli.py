from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from scripts.install.common import FileTransaction
from scripts.install.state import InstallState, encode_state

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class InstallCliTests(unittest.TestCase):
    def test_unified_settings_cli_profile_receipt_and_restore(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state), FAKE_SOURCE_ROOT=str(ROOT))
        original = 'model = "personal"\nmodel_verbosity = "low"\n'
        config = codex_home / "config.toml"
        config.write_text(original)
        profile = self.temp / "experiment.toml"
        profile.write_text('model_verbosity = "high"\n')
        root_flag = self._run(("codex", "settings", "--dry-run", "set", "model_verbosity", "high", "--yes"), environment=environment)
        self.assertEqual(0, root_flag.returncode, root_flag.stderr)
        self.assertEqual(original, config.read_text())
        self.assertFalse((codex_home / ".hukuhaka-settings-history").exists())
        diff = self._run(("codex", "settings", "diff", "--file", str(profile)), environment=environment)
        self.assertEqual(0, diff.returncode, diff.stderr)
        self.assertEqual(original, config.read_text())
        self.assertFalse((codex_home / ".hukuhaka-settings-history").exists())
        applied = self._run(("codex", "settings", "apply", "--file", str(profile), "--yes"), environment=environment)
        self.assertEqual(0, applied.returncode, applied.stderr)
        shown = self._run(("codex", "settings", "show", "--json"), environment=environment)
        self.assertEqual(0, shown.returncode, shown.stderr)
        payload = json.loads(shown.stdout)
        row = next(row for row in payload["options"] if row["key"] == "model_verbosity")
        self.assertEqual('"high"', row["value"])
        identifier = row["origin"].removeprefix("receipt ")
        restored = self._run(("codex", "settings", "restore", identifier, "--yes"), environment=environment)
        self.assertEqual(0, restored.returncode, restored.stderr)
        self.assertEqual(original, config.read_text())

    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory(prefix="hukuhaka install cli ")
        self.temp = Path(self.temp_context.name)
        self.bin_dir = self.temp / "bin"
        self.bin_dir.mkdir()
        self.home = self.temp / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self.temp_context.cleanup()

    def _write_executable(self, name: str, content: str) -> Path:
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def _environment(self, **extra: str) -> Dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "PATH": "{}:{}".format(self.bin_dir, environment.get("PATH", "")),
            }
        )
        environment.update(extra)
        return environment

    def _run(
        self,
        arguments: Sequence[str],
        *,
        environment: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("/bin/bash", str(INSTALL), "--source-dir", str(ROOT), "--version", VERSION)
            + tuple(arguments),
            cwd=ROOT,
            env=environment or self._environment(),
            text=True,
            capture_output=True,
        )

    def _install_fake_codex(self) -> Tuple[Path, Path]:
        state = self.temp / "codex-state"
        codex_home = self.temp / "codex-home"
        state.mkdir()
        codex_home.mkdir()
        (codex_home / "models_cache.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "slug": "gpt-5.6-luna",
                            "multi_agent_version": "v1",
                            "display_name": "GPT-5.6-Luna",
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self._write_executable(
            "codex",
            """#!/bin/bash
set -eu
state_dir="${FAKE_CODEX_STATE:?}"
marketplace="$state_dir/marketplace"
plugins="$state_dir/plugins"
touch "$plugins"
if [ "${1:-}" = "--version" ]; then
    printf 'codex fake 0.145.0\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "add" ]; then
    if [ -f "$marketplace" ]; then
        printf '{"alreadyAdded":true}\n'
    else
        : > "$marketplace"
        printf '{"alreadyAdded":false}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "list" ]; then
    if [ -f "$marketplace" ]; then
        printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"local","source":"%s"}}]}\n' "$FAKE_SOURCE_ROOT" "$FAKE_SOURCE_ROOT"
    else
        printf '{"marketplaces":[]}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "remove" ]; then
    rm -f "$marketplace"
    printf '{}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ]; then
    first=1
    printf '{"installed":['
    while IFS= read -r name; do
        [ -n "$name" ] || continue
        [ "$first" -eq 1 ] || printf ','
        first=0
        version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")"
        printf '{"name":"%s","marketplaceName":"hukuhaka-harness","pluginId":"%s@hukuhaka-harness","version":"%s"}' "$name" "$name" "$version"
    done < "$plugins"
    printf ']}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "add" ]; then
    name="${3%%@*}"
    version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")"
    cache_root="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    installed="$cache_root/$version"
    rm -rf "$cache_root"
    mkdir -p "$cache_root"
    cp -R "$FAKE_SOURCE_ROOT/marketplace/$name" "$installed"
    if ! grep -Fxq "$name" "$plugins"; then
        printf '%s\n' "$name" >> "$plugins"
    fi
    printf '{"pluginId":"%s@hukuhaka-harness","name":"%s","marketplaceName":"hukuhaka-harness","version":"%s","installedPath":"%s"}\n' "$name" "$name" "$version" "$installed"
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "remove" ]; then
    name="${3%%@*}"
    next="$plugins.next"
    grep -Fxv "$name" "$plugins" > "$next" || true
    mv "$next" "$plugins"
    rm -rf "$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    printf '{}\n'
elif [ "${1:-}" = "doctor" ] && [ "${2:-}" = "--json" ]; then
    config="$CODEX_HOME/config.toml"
    if grep -Eq '^[[:space:]]*(agents\.)?max_threads[[:space:]]*=' "$config" && \
       grep -Eq '^[[:space:]]*(agents\.)?max_concurrent_threads_per_session[[:space:]]*=' "$config"; then
        printf '{"checks":{"config.load":{"status":"warning","summary":"config loaded","details":{"startup warning":"Ignoring malformed agent role definition: duplicate field `max_concurrent_threads_per_session`"}}}}\n'
    else
        printf '{"checks":{"config.load":{"status":"ok","summary":"config loaded"}}}\n'
    fi
else
    printf 'unexpected fake codex args: %s\n' "$*" >&2
    exit 2
fi
""",
        )
        return state, codex_home

    def test_claude_host_rejects_old_cli_without_installing(self) -> None:
        self._write_executable("claude", '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "2.1.100 (Claude Code)"; else echo "[]"; fi\n')
        result = self._run(("claude", "install", "--recommended", "--dry-run"))

        self.assertEqual(1, result.returncode)
        self.assertIn("2.1.281 or later", result.stdout + result.stderr)
        self.assertNotIn("Installation complete.", result.stdout)
        self.assertFalse((self.home / ".claude").exists())

    def test_fake_codex_desired_state_dry_run_and_lifecycle(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        dry_run = self._run(
            ("codex", "install", "--recommended", "--dry-run", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, dry_run.returncode, dry_run.stderr)
        self.assertNotIn("plugin add hukuhaka-report-planner@hukuhaka-harness", dry_run.stdout)
        self.assertIn("plugin add hukuhaka-worklog@hukuhaka-harness", dry_run.stdout)
        self.assertNotIn("install evidence-scout", dry_run.stdout)
        self.assertNotIn("install result-runner", dry_run.stdout)
        self.assertIn("Agent runtime:  existing settings preserved (V1/V2 state not inferred)", dry_run.stdout)
        self.assertNotIn("multi-agent enabled", dry_run.stdout)
        self.assertFalse((state / "marketplace").exists())
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))
        self.assertFalse((codex_home / "hk-config.toml").exists())

    def test_guidance_install_preserves_all_config(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )
        config = codex_home / "config.toml"
        original = 'model = "user-model"\n[features]\nmulti_agent = true # user note\n'
        config.write_text(original)
        args = ("codex", "install", "--components", "agents-md", "--yes")
        dry = self._run(args + ("--dry-run",), environment=environment)
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertEqual(original, config.read_text())
        self.assertFalse((codex_home / "config.toml.hukuhaka-backup").exists())
        for _ in range(2):
            result = self._run(args, environment=environment)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(original, config.read_text())
        self.assertFalse((codex_home / "config.toml.hukuhaka-backup").exists())
        self.assertNotIn("# Subagent Routing", (codex_home / "AGENTS.md").read_text())

    def test_installer_state_cli_recovery_preserves_payload_and_allows_retry(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )
        config = codex_home / "config.toml"
        config.write_text('model = "personal-model"\n', encoding="utf-8")
        install = ("codex", "install", "--components", "result-runner", "--yes")
        applied = self._run(install, environment=environment)
        self.assertEqual(0, applied.returncode, applied.stderr)
        shown = self._run(("codex", "state", "show", "--json"), environment=environment)
        self.assertEqual(0, shown.returncode, shown.stderr)
        recorded = json.loads(shown.stdout)
        self.assertEqual("success", recorded["operations"][-1]["status"])
        self.assertIn("result-runner", recorded["components"])
        payload = {
            path: path.read_bytes()
            for path in (config, codex_home / "agents/result-runner.toml")
        }
        record_path = codex_home / "hk-config.toml"
        backup_path = codex_home / "hk-config.toml.bak"
        self.assertTrue(backup_path.is_file())
        backup = backup_path.read_bytes()
        corrupt = b"[unfinished\n"
        record_path.write_bytes(corrupt)
        broken = self._run(("codex", "state", "show", "--json"), environment=environment)
        self.assertNotEqual(0, broken.returncode)
        dry = self._run(
            ("codex", "state", "recover", "--dry-run", "--yes"), environment=environment,
        )
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertEqual(corrupt, record_path.read_bytes())
        self.assertEqual(backup, backup_path.read_bytes())
        self.assertEqual(payload, {path: path.read_bytes() for path in payload})
        recovered = self._run(
            ("codex", "state", "recover", "--yes"), environment=environment,
        )
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        restored = InstallState(codex_home).read()
        self.assertEqual(recorded["components"], restored["components"])
        self.assertEqual("recover", restored["operations"][-1]["action"])
        self.assertEqual("success", restored["operations"][-1]["status"])
        self.assertTrue(any(path.read_bytes() == corrupt for path in (codex_home / "hk-backups").rglob("*.toml")))
        self.assertEqual(payload, {path: path.read_bytes() for path in payload})
        retried = self._run(install, environment=environment)
        self.assertEqual(0, retried.returncode, retried.stderr)
        self.assertEqual("success", InstallState(codex_home).read()["operations"][-1]["status"])
        self.assertEqual(payload, {path: path.read_bytes() for path in payload})

    def test_uninstall_reconciles_record_when_native_plugin_was_removed(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )
        result = self._run(
            ("codex", "install", "--components", "hukuhaka-worklog", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        before = InstallState(codex_home).read()
        self.assertIn("hukuhaka-worklog", before["components"])
        externally_removed = subprocess.run(
            (str(self.bin_dir / "codex"), "plugin", "remove", "hukuhaka-worklog@hukuhaka-harness"),
            env=environment, capture_output=True, text=True,
        )
        self.assertEqual(0, externally_removed.returncode, externally_removed.stderr)
        self.assertEqual("", (state / "plugins").read_text())
        result = self._run(("codex", "uninstall", "--yes"), environment=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        after = InstallState(codex_home).read()
        self.assertNotIn("hukuhaka-worklog", after["components"])
        self.assertEqual(len(before["operations"]) + 1, len(after["operations"]))
        self.assertEqual("success", after["operations"][-1]["status"])

    def test_state_recover_replays_pending_transaction_without_older_backup(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )
        result = self._run(
            ("codex", "install", "--components", "result-runner", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        before = InstallState(codex_home).read()
        agent = codex_home / "agents/result-runner.toml"
        original_agent = agent.read_bytes()
        (codex_home / "hk-config.toml.bak").write_bytes(encode_state({
            "schema_version": 1, "components": {}, "operations": [],
        }))
        transaction = FileTransaction(codex_home)
        transaction.__enter__()
        transaction.write_bytes(codex_home / "hk-config.toml", b"[interrupted\n")
        transaction.write_bytes(agent, b"incomplete payload\n")
        self.assertTrue(transaction.journal_path.is_file())
        dry = self._run(
            ("codex", "state", "recover", "--dry-run", "--yes"), environment=environment,
        )
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertEqual(b"[interrupted\n", (codex_home / "hk-config.toml").read_bytes())
        self.assertEqual(b"incomplete payload\n", agent.read_bytes())
        self.assertTrue(transaction.journal_path.is_file())
        recovered = self._run(
            ("codex", "state", "recover", "--yes"), environment=environment,
        )
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        after = InstallState(codex_home).read()
        self.assertEqual(before["components"], after["components"])
        self.assertEqual(original_agent, agent.read_bytes())
        self.assertFalse(transaction.journal_path.exists())
        self.assertEqual("recover", after["operations"][-1]["action"])
        self.assertEqual("success", after["operations"][-1]["status"])

    def test_project_docs_plugin_retires_historical_reader(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )
        rejected = self._run(
            ("codex", "install", "--components", "project-doc-reader", "--yes"),
            environment=environment,
        )
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("unknown Codex component 'project-doc-reader'", rejected.stderr)

        fixture = ROOT / "scripts/tests/fixtures/installer-v1.2.0-reader/codex-home"
        shutil.copytree(fixture, codex_home, dirs_exist_ok=True)
        unowned = codex_home / "agents/project-doc-reader-protocol.py"
        unowned.write_bytes(b"personal helper\n")
        selected = ("codex", "install", "--components", "hukuhaka-project-docs", "--yes")
        first = self._run(selected, environment=environment)
        second = self._run(selected, environment=environment)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            ["hukuhaka-project-docs"],
            (state / "plugins").read_text(encoding="utf-8").splitlines(),
        )
        self.assertNotIn("project-doc-reader", InstallState(codex_home).read()["components"])
        self.assertFalse((codex_home / "agents/project-doc-reader.toml").exists())
        self.assertFalse((codex_home / "agents/project-doc-reader-tool.py").exists())
        self.assertFalse((codex_home / ".hukuhaka-project-doc-reader-manifest.json").exists())
        self.assertEqual(b"personal helper\n", unowned.read_bytes())

        removed = self._run(("codex", "uninstall", "--yes"), environment=environment)
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertEqual(b"personal helper\n", unowned.read_bytes())

    def test_fake_codex_context_policy_is_scoped_and_reversible(self) -> None:
        state, codex_home = self._install_fake_codex()
        config_path = codex_home / "config.toml"
        config_path.write_text(
            'model = "user-model"\npersonality = "friendly"\n',
            encoding="utf-8",
        )
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        set_policy = self._run(
            (
                "codex",
                "context",
                "set",
                "--window",
                "800000",
                "--compact-at",
                "720000",
                "--scope",
                "total",
                "--yes",
            ),
            environment=environment,
        )

        self.assertEqual(0, set_policy.returncode, set_policy.stderr)
        self.assertIn("model_context_window = 800000", config_path.read_text())
        self.assertIn(
            "model_auto_compact_token_limit = 720000", config_path.read_text()
        )
        self.assertIn('model = "user-model"', config_path.read_text())
        self.assertTrue((codex_home / ".hukuhaka-context-policy.json").is_file())

        install = self._run(
            ("codex", "install", "--recommended", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, install.returncode, install.stderr)
        after_install = config_path.read_text(encoding="utf-8")
        self.assertIn("model_context_window = 800000", after_install)
        self.assertIn("model_auto_compact_token_limit = 720000", after_install)
        self.assertIn('model = "user-model"', after_install)

        reset_policy = self._run(
            ("codex", "context", "reset", "--yes"),
            environment=environment,
        )

        self.assertEqual(0, reset_policy.returncode, reset_policy.stderr)
        reset = config_path.read_text(encoding="utf-8")
        self.assertNotIn("model_context_window", reset)
        self.assertNotIn("model_auto_compact_token_limit", reset)
        self.assertIn('model = "user-model"', reset)
        self.assertIn('personality = "friendly"', reset)
        self.assertFalse((codex_home / ".hukuhaka-context-policy.json").exists())

    def test_fake_codex_context_reset_refuses_unmanaged_override(self) -> None:
        state, codex_home = self._install_fake_codex()
        config_path = codex_home / "config.toml"
        original = "model_context_window = 700000\n"
        config_path.write_text(original, encoding="utf-8")
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        result = self._run(
            ("codex", "context", "reset", "--yes"),
            environment=environment,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not owned by Hukuhaka", result.stderr)
        self.assertEqual(original, config_path.read_text(encoding="utf-8"))

    def test_fake_codex_agent_policy_is_scoped_and_reversible(self) -> None:
        state, codex_home = self._install_fake_codex()
        config_path = codex_home / "config.toml"
        config_path.write_text('model = "user-model"\n', encoding="utf-8")
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        set_policy = self._run(
            (
                "codex",
                "agents",
                "set",
                "--max-concurrent",
                "8",
                "--max-depth",
                "1",
                "--yes",
            ),
            environment=environment,
        )

        self.assertEqual(0, set_policy.returncode, set_policy.stderr)
        configured = config_path.read_text(encoding="utf-8")
        self.assertIn("max_concurrent_threads_per_session = 8", configured)
        self.assertIn("max_depth = 1", configured)
        self.assertIn('model = "user-model"', configured)
        self.assertTrue((codex_home / ".hukuhaka-agent-policy.json").is_file())
        self.assertIn("max_depth is V1-only", set_policy.stdout)

        install = self._run(
            ("codex", "install", "--recommended", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, install.returncode, install.stderr)
        after_install = config_path.read_text(encoding="utf-8")
        self.assertIn("max_concurrent_threads_per_session = 8", after_install)
        self.assertIn("max_depth = 1", after_install)

        reset_policy = self._run(
            ("codex", "agents", "reset", "--yes"),
            environment=environment,
        )

        self.assertEqual(0, reset_policy.returncode, reset_policy.stderr)
        reset = config_path.read_text(encoding="utf-8")
        self.assertNotIn("max_concurrent_threads_per_session", reset)
        self.assertNotIn("max_depth", reset)
        self.assertIn('model = "user-model"', reset)
        self.assertFalse((codex_home / ".hukuhaka-agent-policy.json").exists())

    def test_fake_codex_agent_policy_refuses_unmanaged_override(self) -> None:
        state, codex_home = self._install_fake_codex()
        config_path = codex_home / "config.toml"
        original = "[agents]\nmax_depth = 2\n"
        config_path.write_text(original, encoding="utf-8")
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        result = self._run(
            (
                "codex",
                "agents",
                "set",
                "--max-concurrent",
                "8",
                "--max-depth",
                "1",
                "--yes",
            ),
            environment=environment,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not owned by Hukuhaka", result.stderr)
        self.assertEqual(original, config_path.read_text(encoding="utf-8"))

    def test_fake_codex_install_preserves_legacy_agent_limit(self) -> None:
        state, codex_home = self._install_fake_codex()
        config_path = codex_home / "config.toml"
        original = (
            "[agents]\n"
            "max_threads = 4 # legacy alias\n"
            'default_subagent_model = "user-model"\n'
            'default_subagent_reasoning_effort = "high"\n'
        )
        config_path.write_text(original, encoding="utf-8")
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        result = self._run(
            ("codex", "install", "--components", "agents-md,astra_worker", "--yes"),
            environment=environment,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout, r"  Codex: +success")
        config = config_path.read_text(encoding="utf-8")
        self.assertIn("max_threads = 4 # legacy alias", config)
        self.assertNotIn("max_concurrent_threads_per_session", config)
        self.assertNotIn("max_depth", config)
        self.assertIn('default_subagent_model = "user-model"', config)
        self.assertIn('default_subagent_reasoning_effort = "high"', config)
        self.assertEqual(original, config)
        self.assertFalse((codex_home / "config.toml.hukuhaka-backup").exists())

        # Legacy capacity adoption is authorized by the old Scout manifest,
        # not by installing a new Worker. Seed that historical ownership.
        from scripts.install.codex import CodexEvidenceScoutDeployment
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            CodexEvidenceScoutDeployment(
                ROOT / "scripts/tests/fixtures/archived-agents/evidence-scout.toml",
                codex_home, VERSION, enabled=True,
            ).deploy()
        adopted = self._run(
            (
                "codex",
                "agents",
                "set",
                "--max-concurrent",
                "8",
                "--max-depth",
                "1",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, adopted.returncode, adopted.stderr)
        migrated = config_path.read_text(encoding="utf-8")
        self.assertNotIn("max_threads", migrated)
        self.assertIn("max_concurrent_threads_per_session = 8", migrated)
        self.assertIn("max_depth = 1", migrated)

    def test_child_model_cli_inspect_dry_run_inherit_and_repeat(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state), FAKE_SOURCE_ROOT=str(ROOT),
        )
        original = (
            'model = "parent"\n[agents]\nmax_depth = 2\n'
            'default_subagent_model = "small"\ndefault_subagent_reasoning_effort = "max"\n'
        )
        config = codex_home / "config.toml"
        config.write_text(original)
        inspected = self._run(("codex", "agents", "model", "inspect"), environment=environment)
        self.assertEqual(0, inspected.returncode, inspected.stderr)
        # The shell bootstrap prints its source banner before the JSON report.
        report = json.loads(inspected.stdout[inspected.stdout.index("{"):])
        self.assertEqual('"parent"', report["parent"]["model"])
        dry = self._run(("codex", "agents", "model", "inherit", "--dry-run"), environment=environment)
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertIn('-default_subagent_model = "small"', dry.stdout)
        self.assertEqual(original, config.read_text())
        self.assertFalse((codex_home / "config.toml.hukuhaka-backup").exists())
        denied = self._run(("codex", "agents", "model", "inherit"), environment=environment)
        self.assertNotEqual(0, denied.returncode)
        self.assertEqual(original, config.read_text())
        for _ in range(2):
            result = self._run(("codex", "agents", "model", "inherit", "--yes"), environment=environment)
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('model = "parent"\n[agents]\nmax_depth = 2\n', config.read_text())
        self.assertEqual(original, (codex_home / "config.toml.hukuhaka-backup").read_text())

    def test_optional_runner_adoption_and_recommended_removal(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state), FAKE_SOURCE_ROOT=str(ROOT),
        )
        role = codex_home / "agents/result-runner.toml"
        role.parent.mkdir()
        role.write_text("personal runner")
        before = role.read_bytes()
        arguments = ("codex", "install", "--components", "result-runner", "--yes")
        conflict = self._run(arguments, environment=environment)
        self.assertNotEqual(0, conflict.returncode)
        self.assertEqual(before, role.read_bytes())
        role.write_bytes((ROOT / "agents/result-runner.toml").read_bytes())
        result = self._run(arguments, environment=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("result-runner", InstallState(codex_home).read()["components"])
        self.assertFalse((codex_home / ".hukuhaka-result-runner-manifest.json").exists())
        result = self._run(("codex", "install", "--recommended", "--yes"), environment=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(role.exists())
        self.assertNotIn("hukuhaka-result-runner:begin", (codex_home / "AGENTS.md").read_text())

    def test_optional_scout_repeat_coexistence_and_recommended_removal(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home), FAKE_CODEX_STATE=str(state), FAKE_SOURCE_ROOT=str(ROOT),
        )
        agents = codex_home / "agents"
        agents.mkdir()
        personal = agents / "personal-agent.toml"
        personal.write_text("personal agent\n", encoding="utf-8")
        arguments = (
            "codex",
            "install",
            "--components",
            "astra_worker,result-runner,evidence-scout",
            "--yes",
        )

        first = self._run(arguments, environment=environment)
        self.assertEqual(0, first.returncode, first.stderr)
        first_state = InstallState(codex_home).read()
        second = self._run(arguments, environment=environment)

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        second_state = InstallState(codex_home).read()
        self.assertEqual(set(first_state["components"]), set(second_state["components"]))
        for name, component in first_state["components"].items():
            self.assertEqual(component["receipt"], second_state["components"][name]["receipt"])
        self.assertEqual(len(first_state["operations"]) + 1, len(second_state["operations"]))
        first_operation = first_state["operations"][-1]
        second_operation = second_state["operations"][-1]
        self.assertNotEqual(first_operation["id"], second_operation["id"])
        for operation in (first_operation, second_operation):
            self.assertEqual("success", operation["status"])
            self.assertEqual(VERSION, operation["installer_version"])
            self.assertTrue(operation["started_at"])
            self.assertTrue(operation["finished_at"])
        self.assertFalse((codex_home / "AGENTS.md").exists())
        for name in ("astra_worker", "result-runner", "evidence-scout"):
            self.assertEqual(
                (ROOT / "agents" / (name + ".toml")).read_bytes(),
                (agents / (name + ".toml")).read_bytes(),
            )
            receipt = InstallState(codex_home).read()["components"][name]["receipt"]
            self.assertEqual(4, receipt["schemaVersion"])
            self.assertFalse((codex_home / (".hukuhaka-" + name + "-manifest.json")).exists())
        self.assertEqual("personal agent\n", personal.read_text(encoding="utf-8"))
        self.assertFalse((codex_home / "models-luna-v2.json").exists())

        recommended = self._run(
            ("codex", "install", "--recommended", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, recommended.returncode, recommended.stderr)
        for name in ("astra_worker", "result-runner", "evidence-scout"):
            self.assertFalse((agents / (name + ".toml")).exists())
            self.assertNotIn(name, InstallState(codex_home).read()["components"])
            self.assertFalse(
                (codex_home / (".hukuhaka-" + name + "-manifest.json")).exists()
            )
        self.assertEqual("personal agent\n", personal.read_text(encoding="utf-8"))
        routing = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("hukuhaka-evidence-scout:begin", routing)

    def test_codex_live_install_smoke_with_local_source(self) -> None:
        result = subprocess.run(
            (
                "/bin/bash",
                str(ROOT / "scripts" / "tests" / "live-install-codex.sh"),
                VERSION,
                str(ROOT),
            ),
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            "Public bootstrap and component lifecycle verified with fake Codex CLI for v{}".format(VERSION),
            result.stdout,
        )

    @unittest.skipUnless(os.environ.get("HUKUHAKA_RUN_LIVE_CLI") == "1", "explicit scripts/validate.sh --live-cli check")
    def test_installed_codex_cli_settings_round_trip(self) -> None:
        self.assertTrue(shutil.which("codex"), "--live-cli requires an installed Codex CLI")
        codex_home = self.temp / "real-settings-home"
        codex_home.mkdir()
        config = codex_home / "config.toml"
        original = 'model_verbosity = "low"\n[features]\nmulti_agent = false\n'
        config.write_text(original)
        environment = self._environment(CODEX_HOME=str(codex_home))
        profile = self.temp / "real-profile.toml"
        profile.write_text('model_verbosity = "high"\n[features.multi_agent_v2]\nmin_wait_timeout_ms = 120000\ndefault_wait_timeout_ms = 120000\nmax_wait_timeout_ms = 3600000\n')
        changed = self._run(("codex", "settings", "apply", "--file", str(profile), "--yes"), environment=environment)
        self.assertEqual(0, changed.returncode, changed.stderr + changed.stdout)
        receipt = next((codex_home / ".hukuhaka-settings-history").glob("*.json")).stem
        restored = self._run(("codex", "settings", "restore", receipt, "--yes"), environment=environment)
        self.assertEqual(0, restored.returncode, restored.stderr + restored.stdout)
        self.assertIn('model_verbosity = "low"', config.read_text())
        self.assertNotIn("wait_timeout_ms", config.read_text())
        organized = self._run(("codex", "settings", "organize", "--yes"), environment=environment)
        self.assertEqual(0, organized.returncode, organized.stderr + organized.stdout)

    @unittest.skipUnless(os.environ.get("HUKUHAKA_RUN_LIVE_CLI") == "1", "explicit scripts/validate.sh --live-cli check")
    def test_installed_codex_cli_temp_home_lifecycle(self) -> None:
        self.assertTrue(shutil.which("codex"), "--live-cli requires an installed Codex CLI")
        live_cache = Path.home() / ".codex" / "models_cache.json"
        self.assertTrue(live_cache.is_file(), "--live-cli requires a local Codex model cache")
        codex_home = self.temp / "real-codex-home"
        codex_home.mkdir()
        shutil.copy2(live_cache, codex_home / "models_cache.json")
        (codex_home / "config.toml").write_text(
            "[agents]\n"
            "max_threads = 4 # legacy alias\n"
            'default_subagent_model = "user-model"\n',
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment.update({"HOME": str(self.home), "CODEX_HOME": str(codex_home)})
        arguments = ("codex", "install", "--recommended", "--yes")

        first = self._run(arguments, environment=environment)
        second = self._run(arguments, environment=environment)
        roles = ("codex", "install", "--components",
                 "agents-md,astra_worker,result-runner,evidence-scout", "--yes")
        roles_first = self._run(roles, environment=environment)
        installed_roles = {
            name: (codex_home / "agents" / (name + ".toml")).read_bytes()
            for name in ("astra_worker", "result-runner", "evidence-scout")
        } if roles_first.returncode == 0 else {}
        roles_second = self._run(roles, environment=environment)
        first_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        second_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(0, roles_first.returncode, roles_first.stderr)
        self.assertEqual(0, roles_second.returncode, roles_second.stderr)
        for name, content in installed_roles.items():
            self.assertEqual((ROOT / "agents" / (name + ".toml")).read_bytes(), content)
        self.assertEqual(0, first_remove.returncode, first_remove.stderr)
        self.assertEqual(0, second_remove.returncode, second_remove.stderr)
        config = (codex_home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("max_threads = 4 # legacy alias", config)
        self.assertNotIn("max_concurrent_threads_per_session", config)
        self.assertNotIn("max_depth", config)
        self.assertIn('default_subagent_model = "user-model"', config)


if __name__ == "__main__":
    unittest.main()
