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


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class InstallCliTests(unittest.TestCase):
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

    def test_claude_host_is_rejected_through_shell_entrypoint(self) -> None:
        result = self._run(("claude", "install", "--recommended", "--yes"))

        self.assertEqual(2, result.returncode)
        self.assertIn("invalid choice: 'claude'", result.stderr)
        self.assertNotIn("Installation complete.", result.stdout)

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
        self.assertIn("plugin add hukuhaka-report-planner@hukuhaka-harness", dry_run.stdout)
        self.assertIn("plugin add hukuhaka-worklog@hukuhaka-harness", dry_run.stdout)
        self.assertNotIn("install evidence-scout", dry_run.stdout)
        self.assertNotIn("install result-runner", dry_run.stdout)
        self.assertFalse((state / "marketplace").exists())
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))

    def test_guidance_install_disables_subagents_and_preserves_other_config(self) -> None:
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
            self.assertEqual(original.replace("multi_agent = true", "multi_agent = false"),
                             config.read_text())
        self.assertEqual(original, (codex_home / "config.toml.hukuhaka-backup").read_text())
        self.assertNotIn("# Subagent Routing", (codex_home / "AGENTS.md").read_text())

    def test_fake_codex_project_docs_plugin_and_reader_are_independently_installable(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        plugin_only = self._run(
            (
                "codex",
                "install",
                "--components",
                "hukuhaka-project-docs",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, plugin_only.returncode, plugin_only.stderr)
        self.assertEqual(
            ["hukuhaka-project-docs"],
            (state / "plugins").read_text(encoding="utf-8").splitlines(),
        )
        self.assertFalse(
            (codex_home / ".hukuhaka-project-doc-reader-manifest.json").exists()
        )

        reader_only = self._run(
            (
                "codex",
                "install",
                "--components",
                "project-doc-reader",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, reader_only.returncode, reader_only.stderr)
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))
        self.assertTrue(
            (codex_home / ".hukuhaka-project-doc-reader-manifest.json").is_file()
        )
        self.assertTrue(
            (codex_home / "agents" / "project-doc-reader.toml").is_file()
        )
        helper = codex_home / "agents" / "project-doc-reader-tool.py"
        self.assertTrue(helper.is_file())
        reader_manifest = json.loads(
            (
                codex_home / ".hukuhaka-project-doc-reader-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(4, reader_manifest["schemaVersion"])
        self.assertEqual(
            ["agents/project-doc-reader-tool.py"],
            [item["target"] for item in reader_manifest["resources"]],
        )
        self.assertFalse((codex_home / "AGENTS.md").exists())

        paired = (
            "codex",
            "install",
            "--components",
            "hukuhaka-project-docs,project-doc-reader",
            "--yes",
        )
        first_pair = self._run(paired, environment=environment)
        second_pair = self._run(paired, environment=environment)
        self.assertEqual(0, first_pair.returncode, first_pair.stderr)
        self.assertEqual(0, second_pair.returncode, second_pair.stderr)
        self.assertEqual(
            ["hukuhaka-project-docs"],
            (state / "plugins").read_text(encoding="utf-8").splitlines(),
        )
        self.assertTrue(
            (codex_home / ".hukuhaka-project-doc-reader-manifest.json").is_file()
        )

        coexist = self._run(
            (
                "codex",
                "install",
                "--components",
                "astra_worker,project-doc-reader",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, coexist.returncode, coexist.stderr)
        self.assertFalse((codex_home / "AGENTS.md").exists())
        self.assertTrue((codex_home / "agents/astra_worker.toml").is_file())
        self.assertTrue((codex_home / "agents/project-doc-reader.toml").is_file())

        removed = self._run(
            ("codex", "uninstall", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertFalse(
            (codex_home / ".hukuhaka-project-doc-reader-manifest.json").exists()
        )
        self.assertFalse(
            (codex_home / "agents" / "project-doc-reader.toml").exists()
        )
        self.assertFalse(helper.exists())

        recommended = ("codex", "install", "--recommended", "--yes")
        first = self._run(recommended, environment=environment)
        second = self._run(recommended, environment=environment)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertRegex(
            first.stdout,
            r"hukuhaka-worklog +not installed → 0\.4\.1",
        )
        self.assertRegex(
            second.stdout,
            r"hukuhaka-worklog +0\.4\.1 \(same version\)",
        )
        self.assertRegex(
            first.stdout,
            r"hukuhaka-uiux-foundation +not installed → 0\.1\.0",
        )
        self.assertRegex(
            second.stdout,
            r"hukuhaka-uiux-foundation +0\.1\.0 \(same version\)",
        )
        self.assertEqual(
            {
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-uiux-foundation",
            },
            set((state / "plugins").read_text(encoding="utf-8").splitlines()),
        )
        self.assertTrue((codex_home / ".hukuhaka-guidance-manifest.json").is_file())
        self.assertFalse((codex_home / ".hukuhaka-evidence-scout-manifest.json").exists())
        self.assertFalse((codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((codex_home / "models-luna-v2.json").exists())
        self.assertNotIn(
            "hukuhaka-evidence-scout:begin",
            (codex_home / "AGENTS.md").read_text(encoding="utf-8"),
        )
        config = (codex_home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("multi_agent = false", config)
        self.assertNotIn("max_concurrent_threads_per_session", config)
        self.assertNotIn("max_depth", config)
        self.assertNotIn("model_catalog_json", config)

        reduced = self._run(
            (
                "codex",
                "install",
                "--components",
                "hukuhaka-report-planner",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, reduced.returncode, reduced.stderr)
        self.assertEqual(
            ["hukuhaka-report-planner"],
            (state / "plugins").read_text(encoding="utf-8").splitlines(),
        )
        self.assertFalse((codex_home / ".hukuhaka-guidance-manifest.json").exists())
        self.assertFalse((codex_home / ".hukuhaka-evidence-scout-manifest.json").exists())
        self.assertFalse((codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((codex_home / "models-luna-v2.json").exists())
        self.assertNotIn("model_catalog_json", (codex_home / "config.toml").read_text())

        first_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        second_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        self.assertEqual(0, first_remove.returncode, first_remove.stderr)
        self.assertEqual(0, second_remove.returncode, second_remove.stderr)
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))

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
        self.assertEqual(
            original.encode(),
            (codex_home / "config.toml.hukuhaka-backup").read_bytes(),
        )

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
        self.assertTrue((codex_home / ".hukuhaka-result-runner-manifest.json").exists())
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
        second = self._run(arguments, environment=environment)

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertFalse((codex_home / "AGENTS.md").exists())
        for name in ("astra_worker", "result-runner", "evidence-scout"):
            self.assertEqual(
                (ROOT / "agents" / (name + ".toml")).read_bytes(),
                (agents / (name + ".toml")).read_bytes(),
            )
            manifest = codex_home / (".hukuhaka-" + name + "-manifest.json")
            self.assertEqual(4, json.loads(manifest.read_text())["schemaVersion"])
        self.assertEqual("personal agent\n", personal.read_text(encoding="utf-8"))
        self.assertFalse((codex_home / "models-luna-v2.json").exists())

        recommended = self._run(
            ("codex", "install", "--recommended", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, recommended.returncode, recommended.stderr)
        for name in ("astra_worker", "result-runner", "evidence-scout"):
            self.assertFalse((agents / (name + ".toml")).exists())
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
            "Codex Worker, Runner, and Scout live install verified for v{}".format(VERSION),
            result.stdout,
        )

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
