from __future__ import annotations

import contextlib
import io
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex_config import (
    AGENT_POLICY_KEYS,
    AGENT_WAIT_SETTINGS,
    CONTEXT_POLICY_KEYS,
    RECOMMENDED_SETTINGS,
    CodexAgentPolicy,
    CodexContextPolicy,
    CodexConfigEditor,
    ContextPolicyState,
    current_values,
    prompt_context_action,
    prompt_context_settings,
    update_config,
)
from scripts.install.common import InstallerError, StateError


AGENT_SETTINGS = {
    ("agents", "max_concurrent_threads_per_session"): "8",
    ("agents", "max_depth"): "1",
}


class CodexConfigTextTests(unittest.TestCase):
    def test_agent_wait_update_preserves_other_settings_and_is_idempotent(self) -> None:
        original = (
            'model = "gpt-6-astra"\nmodel_reasoning_effort = "high"\n'
            '[features]\nmulti_agent = true\n'
            'multi_agent_v2.min_wait_timeout_ms = 10000 # local note\n'
            'multi_agent_v2.default_wait_timeout_ms = 30000\n'
            '[agents]\nmax_concurrent_threads_per_session = 8\n'
        )
        expected = original.replace('10000 # local note', '120000 # local note').replace(
            'default_wait_timeout_ms = 30000', 'default_wait_timeout_ms = 120000')
        updated = update_config(original, AGENT_WAIT_SETTINGS,
                                managed_keys=tuple(AGENT_WAIT_SETTINGS))
        self.assertEqual(expected, updated)
        self.assertEqual(updated, update_config(updated, AGENT_WAIT_SETTINGS,
                                               managed_keys=tuple(AGENT_WAIT_SETTINGS)))

    def test_recommended_settings_are_idempotent(self) -> None:
        first = update_config("", RECOMMENDED_SETTINGS)
        second = update_config(first, RECOMMENDED_SETTINGS)

        self.assertEqual(first, second)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(first))
        self.assertEqual("false", current_values(first)[("features", "multi_agent")])
        self.assertNotIn("\nmodel =", first)
        self.assertNotIn("max_concurrent_threads_per_session", first)
        self.assertNotIn("max_depth", first)

    def test_unmanaged_text_comments_and_tables_are_preserved(self) -> None:
        original = (
            "# personal note\n"
            'model = "gpt-user-choice"\n'
            'personality = "friendly" # replace this value\n'
            "\n"
            "[mcp_servers.example]\n"
            'command = "example"\n'
            "\n"
            "[agents]\n"
            "enabled = false\n"
            "custom_limit = 9\n"
        )

        updated = update_config(original, RECOMMENDED_SETTINGS)

        self.assertIn("# personal note\n", updated)
        self.assertIn("# replace this value", updated)
        self.assertIn('model = "gpt-user-choice"\n', updated)
        self.assertIn("[mcp_servers.example]\ncommand = \"example\"\n", updated)
        self.assertIn("custom_limit = 9\n", updated)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(updated))

    def test_quoted_plugin_table_ends_managed_agents_section(self) -> None:
        original = (
            "[agents]\n"
            "enabled = true\n"
            "max_concurrent_threads_per_session = 4\n"
            "\n"
            '[plugins."demo@marketplace"]\n'
            "enabled = true\n"
        )

        updated = update_config(original, RECOMMENDED_SETTINGS)

        self.assertEqual(RECOMMENDED_SETTINGS, current_values(updated))
        self.assertEqual(2, updated.count("enabled = true"))
        self.assertIn('[plugins."demo@marketplace"]\nenabled = true\n', updated)

    def test_dotted_managed_keys_remain_dotted(self) -> None:
        original = (
            "agents.enabled = false\n"
            "tui.notification_condition = \"always\"\n"
            "features.prevent_idle_sleep = false\n"
        )

        updated = update_config(original, RECOMMENDED_SETTINGS)

        self.assertNotIn("max_concurrent_threads_per_session", updated)
        self.assertIn("tui.status_line =", updated)
        self.assertNotIn("\n[agents]\n", updated)
        self.assertNotIn("\n[tui]\n", updated)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(updated))

    def test_legacy_agent_limit_is_migrated_in_place(self) -> None:
        original = (
            "[agents]\n"
            "max_threads = 7 # legacy limit\n"
            'default_subagent_model = "user-model"\n'
        )
        self.assertEqual(
            "7",
            current_values(
                original, managed_keys=AGENT_POLICY_KEYS, stage="agents"
            )[
                ("agents", "max_concurrent_threads_per_session")
            ],
        )

        updated = update_config(
            original,
            AGENT_SETTINGS,
            managed_keys=AGENT_POLICY_KEYS,
            stage="agents",
        )

        self.assertIn(
            "max_concurrent_threads_per_session = 8 # legacy limit\n",
            updated,
        )
        self.assertNotIn("\nmax_threads =", updated)
        self.assertIn('default_subagent_model = "user-model"\n', updated)
        self.assertEqual(
            AGENT_SETTINGS,
            current_values(
                updated, managed_keys=AGENT_POLICY_KEYS, stage="agents"
            ),
        )
        self.assertEqual(
            updated,
            update_config(
                updated,
                AGENT_SETTINGS,
                managed_keys=AGENT_POLICY_KEYS,
                stage="agents",
            ),
        )

    def test_dotted_legacy_agent_limit_is_migrated(self) -> None:
        updated = update_config(
            "agents.max_threads = 2\n",
            AGENT_SETTINGS,
            managed_keys=AGENT_POLICY_KEYS,
            stage="agents",
        )

        self.assertEqual(
            "agents.max_concurrent_threads_per_session = 8\n"
            "agents.max_depth = 1\n\n",
            updated,
        )

    def test_legacy_and_canonical_agent_limits_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            StateError,
            "duplicate managed Codex config key: "
            "agents.max_concurrent_threads_per_session",
        ):
            update_config(
                "[agents]\n"
                "max_threads = 4\n"
                "max_concurrent_threads_per_session = 4\n",
                AGENT_SETTINGS,
                managed_keys=AGENT_POLICY_KEYS,
                stage="agents",
            )

    def test_multiline_managed_array_is_replaced_as_one_value(self) -> None:
        original = (
            "[tui]\n"
            "status_line = [\n"
            '  "model",\n'
            '  "current-dir",\n'
            "]\n"
        )

        updated = update_config(
            original,
            {("tui", "status_line"): RECOMMENDED_SETTINGS[("tui", "status_line")]},
        )

        self.assertEqual(
            RECOMMENDED_SETTINGS[("tui", "status_line")],
            current_values(updated)[("tui", "status_line")],
        )
        self.assertNotIn('  "model",', updated)

    def test_duplicate_managed_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(StateError, "duplicate managed Codex config key"):
            update_config(
                'personality = "friendly"\npersonality = "pragmatic"\n',
                RECOMMENDED_SETTINGS,
            )

    def test_inline_managed_table_is_rejected(self) -> None:
        with self.assertRaisesRegex(StateError, "inline value"):
            update_config(
                "agents = { enabled = false }\n",
                RECOMMENDED_SETTINGS,
            )

    def test_managed_key_removal_preserves_comment_and_unmanaged_text(self) -> None:
        original = (
            '# keep\nmodel_catalog_json = "/managed/catalog.json" # why it existed\n'
            'model = "user-model"\n'
        )

        updated = update_config(
            original,
            {},
            remove=(("model_catalog_json",),),
        )

        self.assertEqual(
            '# keep\n# why it existed\nmodel = "user-model"\n',
            updated,
        )
        self.assertNotIn("model_catalog_json", updated)

    def test_key_cannot_be_set_and_removed_together(self) -> None:
        with self.assertRaisesRegex(StateError, "set and removed together"):
            update_config(
                "",
                {("model_catalog_json",): '"/managed/catalog.json"'},
                remove=(("model_catalog_json",),),
            )

    def test_context_keys_are_outside_the_general_config_scope(self) -> None:
        text = (
            "model_context_window = 800000\n"
            "model_auto_compact_token_limit = 720000\n"
            'model_auto_compact_token_limit_scope = "total"\n'
        )

        self.assertEqual({}, current_values(text))
        self.assertEqual(
            {
                ("model_context_window",): "800000",
                ("model_auto_compact_token_limit",): "720000",
                ("model_auto_compact_token_limit_scope",): '"total"',
            },
            current_values(text, managed_keys=CONTEXT_POLICY_KEYS, stage="context"),
        )


class CodexConfigApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka config ")
        self.codex_home = Path(self.temp.name) / ".codex"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def editor(self, *, dry_run: bool = False) -> CodexConfigEditor:
        return CodexConfigEditor(self.codex_home, dry_run=dry_run)

    def test_new_file_is_atomic_private_and_validated(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor") as doctor:
            self.assertTrue(editor.apply(plan, show_diff=False))

        doctor.assert_called_once_with()
        self.assertEqual(
            RECOMMENDED_SETTINGS,
            current_values(editor.path.read_text(encoding="utf-8")),
        )
        self.assertEqual(0o600, stat.S_IMODE(editor.path.stat().st_mode))
        self.assertFalse(editor.backup.exists())

    def test_existing_file_mode_and_unmanaged_text_are_preserved_with_backup(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        original = b'# keep\nmodel = "user-model"\npersonality = "friendly"\n'
        path.write_bytes(original)
        path.chmod(0o640)
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)

        self.assertEqual(original, editor.backup.read_bytes())
        self.assertEqual(0o640, stat.S_IMODE(editor.path.stat().st_mode))
        self.assertIn('model = "user-model"', editor.path.read_text(encoding="utf-8"))

    def test_apply_and_verify_remove_managed_key(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        path.write_text(
            'model_catalog_json = "/managed/catalog.json"\nmodel = "user-model"\n',
            encoding="utf-8",
        )
        editor = self.editor()
        plan = editor.plan({}, remove=(("model_catalog_json",),))

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)
            editor.verify(plan)

        updated = path.read_text(encoding="utf-8")
        self.assertNotIn("model_catalog_json", updated)
        self.assertIn('model = "user-model"', updated)

    def test_doctor_failure_restores_the_original(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        original = b'personality = "friendly"\n'
        path.write_bytes(original)
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(
            editor,
            "_doctor",
            side_effect=InstallerError("doctor rejected config"),
        ):
            with self.assertRaisesRegex(InstallerError, "doctor rejected"):
                editor.apply(plan, show_diff=False)

        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original, editor.backup.read_bytes())

    def test_legacy_migration_failure_restores_the_original(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        original = b"[agents]\nmax_threads = 6 # keep on rollback\n"
        path.write_bytes(original)
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(
            editor,
            "_doctor",
            side_effect=InstallerError("doctor rejected migrated config"),
        ):
            with self.assertRaisesRegex(InstallerError, "doctor rejected migrated"):
                editor.apply(plan, show_diff=False)

        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original, editor.backup.read_bytes())

    def test_dry_run_creates_no_directory_or_file(self) -> None:
        editor = self.editor(dry_run=True)
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor") as doctor:
            self.assertFalse(editor.apply(plan, show_diff=False))

        doctor.assert_not_called()
        self.assertFalse(self.codex_home.exists())

    def test_change_after_diff_is_refused(self) -> None:
        self.codex_home.mkdir()
        editor = self.editor()
        editor.path.write_text('personality = "friendly"\n', encoding="utf-8")
        plan = editor.plan(RECOMMENDED_SETTINGS)
        editor.path.write_text('personality = "none"\n', encoding="utf-8")

        with self.assertRaisesRegex(StateError, "changed after the diff"):
            editor.apply(plan, show_diff=False)

        self.assertEqual(
            'personality = "none"\n',
            editor.path.read_text(encoding="utf-8"),
        )

    def test_verify_allows_plugin_sections_added_after_apply(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)

        with editor.path.open("a", encoding="utf-8") as config:
            config.write(
                '\n[plugins."hukuhaka-report-planner@hukuhaka-harness"]\n'
                "enabled = true\n"
            )

        with mock.patch.object(editor, "_doctor") as doctor:
            editor.verify(plan)

        doctor.assert_called_once_with()
        self.assertEqual(
            RECOMMENDED_SETTINGS,
            current_values(editor.path.read_text(encoding="utf-8")),
        )
        self.assertIn(
            '[plugins."hukuhaka-report-planner@hukuhaka-harness"]',
            editor.path.read_text(encoding="utf-8"),
        )

    def test_verify_rejects_managed_value_changed_by_component_install(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)
        editor.path.write_text(
            editor.path.read_text(encoding="utf-8").replace(
                'model_reasoning_effort = "medium"',
                'model_reasoning_effort = "high"',
            ),
            encoding="utf-8",
        )

        with mock.patch.object(editor, "_doctor") as doctor:
            with self.assertRaisesRegex(
                StateError, "managed Codex config changed"
            ):
                editor.verify(plan)

        doctor.assert_not_called()

    def test_doctor_accepts_config_ok_when_other_checks_make_exit_nonzero(self) -> None:
        editor = self.editor()
        report = (
            '{"checks":{"config.load":{"status":"ok","summary":"config loaded"},'
            '"auth.credentials":{"status":"fail"}}}'
        )
        completed = subprocess.CompletedProcess(
            ["codex", "doctor", "--json"],
            1,
            stdout=report,
            stderr="",
        )

        with mock.patch(
            "scripts.install.codex_config.shutil.which", return_value="/fake/codex"
        ), mock.patch(
            "scripts.install.codex_config.subprocess.run", return_value=completed
        ):
            editor._doctor()


class CodexAgentPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka agent policy ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.codex_home.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def policy(self, *, dry_run: bool = False) -> CodexAgentPolicy:
        return CodexAgentPolicy(self.codex_home, dry_run=dry_run)

    def test_set_and_reset_preserve_unrelated_config(self) -> None:
        config = self.codex_home / "config.toml"
        config.write_text(
            'model = "user-model"\n[agents]\ndefault_subagent_model = "user-agent"\n',
            encoding="utf-8",
        )
        policy = self.policy()
        plan = policy.plan_set(max_concurrent=8, max_depth=1)

        with mock.patch.object(policy.config, "_doctor"):
            self.assertTrue(policy.apply(plan))

        configured = config.read_text(encoding="utf-8")
        self.assertIn("max_concurrent_threads_per_session = 8", configured)
        self.assertIn("max_depth = 1", configured)
        self.assertIn('model = "user-model"', configured)
        self.assertIn('default_subagent_model = "user-agent"', configured)
        self.assertEqual("managed", policy.state().kind)
        self.assertTrue(policy.manifest_path.is_file())

        reset = policy.plan_reset()
        with mock.patch.object(policy.config, "_doctor"):
            self.assertTrue(policy.apply(reset))

        restored = config.read_text(encoding="utf-8")
        self.assertNotIn("max_concurrent_threads_per_session", restored)
        self.assertNotIn("max_depth", restored)
        self.assertIn('model = "user-model"', restored)
        self.assertIn('default_subagent_model = "user-agent"', restored)
        self.assertFalse(policy.manifest_path.exists())

    def test_set_adopts_exact_legacy_scout_limit(self) -> None:
        config = self.codex_home / "config.toml"
        config.write_text(
            "[agents]\nmax_threads = 4 # legacy\n",
            encoding="utf-8",
        )
        (self.codex_home / ".hukuhaka-evidence-scout-manifest.json").write_text(
            '{"schemaVersion": 3, "component": "evidence-scout"}\n',
            encoding="utf-8",
        )
        policy = self.policy()
        state = policy.state()
        self.assertEqual("legacy", state.kind)
        self.assertTrue(state.actionable)
        plan = policy.plan_set(max_concurrent=8, max_depth=1)
        with mock.patch.object(policy.config, "_doctor"):
            policy.apply(plan)

        updated = config.read_text(encoding="utf-8")
        self.assertNotIn("max_threads", updated)
        self.assertIn("max_concurrent_threads_per_session = 8 # legacy", updated)
        self.assertIn("max_depth = 1", updated)

    def test_unmanaged_override_is_preserved(self) -> None:
        config = self.codex_home / "config.toml"
        original = "[agents]\nmax_depth = 2\n"
        config.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(StateError, "not owned by Hukuhaka"):
            self.policy().plan_reset()

        self.assertEqual(original, config.read_text(encoding="utf-8"))

    def test_managed_drift_is_rejected(self) -> None:
        policy = self.policy()
        plan = policy.plan_set(max_concurrent=8, max_depth=1)
        with mock.patch.object(policy.config, "_doctor"):
            policy.apply(plan)
        config = self.codex_home / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "max_concurrent_threads_per_session = 8",
                "max_concurrent_threads_per_session = 6",
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(StateError, "agent policy drifted"):
            policy.plan_reset()

    def test_doctor_failure_rolls_back_config_and_manifest(self) -> None:
        config = self.codex_home / "config.toml"
        original = b'model = "user-model"\n'
        config.write_bytes(original)
        policy = self.policy()
        plan = policy.plan_set(max_concurrent=8, max_depth=1)

        with mock.patch.object(
            policy.config,
            "_doctor",
            side_effect=InstallerError("doctor rejected agent policy"),
        ):
            with self.assertRaisesRegex(InstallerError, "doctor rejected"):
                policy.apply(plan)

        self.assertEqual(original, config.read_bytes())
        self.assertFalse(policy.manifest_path.exists())

    def test_limits_must_be_positive(self) -> None:
        with self.assertRaisesRegex(StateError, "positive integer"):
            self.policy().plan_set(max_concurrent=0, max_depth=1)
        with self.assertRaisesRegex(StateError, "positive integer"):
            self.policy().plan_set(max_concurrent=8, max_depth=0)


class ContextPolicyPromptTests(unittest.TestCase):
    def test_current_policy_lists_window_compaction_and_scope(self) -> None:
        state = ContextPolicyState(
            "managed",
            {
                ("model_context_window",): "800000",
                ("model_auto_compact_token_limit",): "720000",
                ("model_auto_compact_token_limit_scope",): '"total"',
            },
            "gpt-5.6-sol",
            1_050_000,
        )
        output = io.StringIO()

        with mock.patch("builtins.input", return_value="q"), contextlib.redirect_stdout(
            output
        ):
            self.assertIsNone(prompt_context_action(state))

        rendered = output.getvalue()
        self.assertIn("Current configuration: custom (Hukuhaka managed)", rendered)
        self.assertIn("Configured model: gpt-5.6-sol (config.toml)", rendered)
        self.assertIn("Documented model capacity: 1,050,000 tokens", rendered)
        self.assertIn("Context window: 800000", rendered)
        self.assertIn("Auto-compact at: 720000", rendered)
        self.assertIn("Threshold scope: total", rendered)

    def test_custom_policy_input_explains_all_three_settings(self) -> None:
        output = io.StringIO()

        with mock.patch(
            "builtins.input", side_effect=("800000", "720000", "")
        ), contextlib.redirect_stdout(output):
            self.assertEqual(
                (800000, 720000, "total"),
                prompt_context_settings(
                    ContextPolicyState(
                        "default", {}, "gpt-5.6-sol", 1_050_000
                    )
                ),
            )

        rendered = output.getvalue()
        self.assertIn("window, auto-compaction threshold, and threshold scope", rendered)
        self.assertIn("must be lower than the context window", rendered)
        self.assertIn("Documented model capacity: 1,050,000 tokens", rendered)
        self.assertIn("Current context window: Codex/model default", rendered)
        self.assertIn("numeric threshold not exposed", rendered)
        self.assertIn("Current threshold scope: total (Codex default", rendered)

    def test_unmanaged_policy_does_not_offer_mutation(self) -> None:
        state = ContextPolicyState(
            "unmanaged", {("model_context_window",): "700000"}
        )
        output = io.StringIO()

        with mock.patch(
            "builtins.input", side_effect=("1", "q")
        ), contextlib.redirect_stdout(output):
            self.assertIsNone(prompt_context_action(state))

        rendered = output.getvalue()
        self.assertIn("will not be changed", rendered)
        self.assertNotIn("1. Set custom policy", rendered)


class CodexContextPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka context policy ")
        self.codex_home = Path(self.temp.name) / ".codex"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def policy(self, *, dry_run: bool = False) -> CodexContextPolicy:
        return CodexContextPolicy(self.codex_home, dry_run=dry_run)

    def test_state_reports_only_observed_overrides(self) -> None:
        self.assertEqual("default", self.policy().state().kind)
        self.assertEqual({}, self.policy().state().settings)

        self.codex_home.mkdir()
        config = self.codex_home / "config.toml"
        config.write_text(
            'model = "gpt-5.6-sol"\n'
            "model_context_window = 800000\n"
            "model_auto_compact_token_limit = 720000\n"
            'model_auto_compact_token_limit_scope = "total"\n',
            encoding="utf-8",
        )

        state = self.policy().state()
        self.assertEqual("unmanaged", state.kind)
        self.assertEqual("gpt-5.6-sol", state.model)
        self.assertEqual(1_050_000, state.documented_context_capacity)
        self.assertEqual("800000", state.settings[("model_context_window",)])
        self.assertEqual(
            "720000", state.settings[("model_auto_compact_token_limit",)]
        )
        self.assertEqual(
            '"total"',
            state.settings[("model_auto_compact_token_limit_scope",)],
        )

    def test_state_shows_documented_capacity_for_configured_model(self) -> None:
        self.codex_home.mkdir()
        config = self.codex_home / "config.toml"

        for model in (
            "gpt-5.6",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        ):
            config.write_text('model = "{}"\n'.format(model), encoding="utf-8")
            state = self.policy().state()

            self.assertEqual("default", state.kind)
            self.assertEqual(model, state.model)
            self.assertEqual(1_050_000, state.documented_context_capacity)

    def test_set_then_reset_preserves_all_unrelated_config(self) -> None:
        self.codex_home.mkdir()
        config = self.codex_home / "config.toml"
        original = b'model = "user-model"\npersonality = "friendly"\n'
        config.write_bytes(original)
        policy = self.policy()

        set_plan = policy.plan_set(
            context_window=800000,
            compact_at=720000,
            scope="total",
        )
        with mock.patch.object(policy.config, "_doctor"):
            self.assertTrue(policy.apply(set_plan))

        updated = config.read_text(encoding="utf-8")
        self.assertIn('model = "user-model"', updated)
        self.assertIn('personality = "friendly"', updated)
        self.assertEqual(
            {
                ("model_context_window",): "800000",
                ("model_auto_compact_token_limit",): "720000",
                ("model_auto_compact_token_limit_scope",): '"total"',
            },
            current_values(
                updated,
                managed_keys=CONTEXT_POLICY_KEYS,
                stage="context",
            ),
        )
        self.assertTrue((self.codex_home / ".hukuhaka-context-policy.json").is_file())

        reset_plan = policy.plan_reset()
        with mock.patch.object(policy.config, "_doctor"):
            self.assertTrue(policy.apply(reset_plan))

        self.assertEqual(
            original.decode("utf-8").strip(),
            config.read_text(encoding="utf-8").strip(),
        )
        self.assertFalse((self.codex_home / ".hukuhaka-context-policy.json").exists())

    def test_existing_unmanaged_context_override_is_preserved(self) -> None:
        self.codex_home.mkdir()
        config = self.codex_home / "config.toml"
        original = b"model_context_window = 700000\n"
        config.write_bytes(original)

        with self.assertRaisesRegex(StateError, "not owned by Hukuhaka"):
            self.policy().plan_reset()

        self.assertEqual(original, config.read_bytes())

    def test_managed_context_drift_is_rejected_without_mutation(self) -> None:
        self.codex_home.mkdir()
        policy = self.policy()
        first_plan = policy.plan_set(
            context_window=800000,
            compact_at=720000,
            scope="total",
        )
        with mock.patch.object(policy.config, "_doctor"):
            policy.apply(first_plan)
        config = self.codex_home / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("720000", "710000"),
            encoding="utf-8",
        )
        drifted = config.read_bytes()

        with self.assertRaisesRegex(StateError, "context policy drifted"):
            policy.plan_reset()

        self.assertEqual(drifted, config.read_bytes())

    def test_verify_detects_component_changes_to_managed_context(self) -> None:
        self.codex_home.mkdir()
        policy = self.policy()
        plan = policy.plan_set(
            context_window=800000,
            compact_at=720000,
            scope="total",
        )
        with mock.patch.object(policy.config, "_doctor"):
            policy.apply(plan)
        config = self.codex_home / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("720000", "710000"),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(StateError, "context policy drifted"):
            policy.verify(plan)

    def test_doctor_failure_rolls_back_config_and_context_manifest(self) -> None:
        self.codex_home.mkdir()
        config = self.codex_home / "config.toml"
        original = b'model = "user-model"\n'
        config.write_bytes(original)
        policy = self.policy()
        plan = policy.plan_set(
            context_window=800000,
            compact_at=720000,
            scope="total",
        )

        with mock.patch.object(
            policy.config,
            "_doctor",
            side_effect=InstallerError("doctor rejected context policy"),
        ):
            with self.assertRaisesRegex(InstallerError, "doctor rejected context policy"):
                policy.apply(plan)

        self.assertEqual(original, config.read_bytes())
        self.assertFalse((self.codex_home / ".hukuhaka-context-policy.json").exists())
        self.assertFalse((self.codex_home / "config.toml.hukuhaka-backup").exists())

    def test_compaction_threshold_must_be_lower_than_window(self) -> None:
        with self.assertRaisesRegex(StateError, "must be lower"):
            self.policy().plan_set(
                context_window=800000,
                compact_at=800000,
                scope="total",
            )


if __name__ == "__main__":
    unittest.main()
