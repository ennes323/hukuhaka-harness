from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("plugin_contracts.py")
SPEC = importlib.util.spec_from_file_location("plugin_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
plugin_contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin_contracts)


class OpenAiYamlTests(unittest.TestCase):
    def validate(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "openai.yaml"
            path.write_text(text, encoding="utf-8")
            return plugin_contracts.validate_openai_yaml(path)

    def test_accepts_current_interface_subset(self) -> None:
        errors = self.validate(
            'interface:\n'
            '  display_name: "Planner"\n'
            '  short_description: "Ground plans"\n'
            '  default_prompt: "Use $engineering-plan."\n'
            'policy:\n'
            '  allow_implicit_invocation: true\n'
        )
        self.assertEqual([], errors)

    def test_rejects_duplicate_and_malformed_values(self) -> None:
        errors = self.validate(
            'interface:\n'
            '  display_name: "Planner"\n'
            '  display_name: broken\n'
            '  short_description: "Ground plans"\n'
        )
        self.assertTrue(errors)
        self.assertIn("duplicate key", errors[0])

    def test_rejects_unknown_interface_key(self) -> None:
        errors = self.validate(
            'interface:\n'
            '  display_name: "Planner"\n'
            '  short_description: "Ground plans"\n'
            '  mystery: "value"\n'
        )
        self.assertTrue(any("unsupported interface key" in error for error in errors))


class HookAndManifestPathTests(unittest.TestCase):
    def test_host_hook_events_and_root_variables_are_isolated(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as temp_name:
            plugin = Path(temp_name) / "plugin"
            hook = plugin / "hooks/claude.json"
            hook.parent.mkdir(parents=True)
            (plugin / "script.py").write_text("# helper", encoding="utf-8")
            hook.write_text(json.dumps({"hooks": {"PostToolUseFailure": [{"hooks": [{
                "type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/script.py"'
            }]}]}}), encoding="utf-8")
            errors: list[str] = []
            plugin_contracts.validate_hook_file(hook, {"claude"}, errors)
            self.assertEqual([], errors)
            plugin_contracts.validate_hook_file(hook, {"codex"}, errors)
            self.assertTrue(any("unsupported" in error for error in errors))
            self.assertTrue(any("another host" in error for error in errors))

    def test_rejects_unknown_event_invalid_timeout_and_missing_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            plugin = Path(temp_name) / "plugin"
            hooks = plugin / "hooks" / "hooks.json"
            hooks.parent.mkdir(parents=True)
            hooks.write_text(
                '{"hooks":{"UnknownEvent":[{"hooks":[{"type":"command",'
                '"command":"python3 ${PLUGIN_ROOT}/missing.py","timeout":0}]}]}}',
                encoding="utf-8",
            )
            errors: list[str] = []
            plugin_contracts.validate_hook_file(hooks, {"codex"}, errors)
        self.assertTrue(any("unsupported" in error for error in errors))
        self.assertTrue(any("timeout must be positive" in error for error in errors))
        self.assertTrue(any("referenced script does not exist" in error for error in errors))

    def test_rejects_manifest_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            plugin = Path(temp_name) / "plugin"
            plugin.mkdir()
            errors: list[str] = []
            resolved = plugin_contracts.resolve_plugin_path(
                plugin,
                "./../outside",
                "manifest skills",
                errors,
            )
        self.assertIsNone(resolved)
        self.assertTrue(any("escapes plugin root" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
