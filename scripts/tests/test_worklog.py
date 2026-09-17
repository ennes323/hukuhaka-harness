from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "marketplace" / "hukuhaka-worklog"
SCRIPT = PLUGIN / "skills" / "worklog" / "scripts" / "worklog.py"
SPEC = importlib.util.spec_from_file_location("hukuhaka_worklog_script", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WORKLOG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WORKLOG
SPEC.loader.exec_module(WORKLOG)


def history_entry(day: int, title: str, body: str = "Recorded result.") -> str:
    return f"### 2026-07-{day:02d} — {title}\n\n{body}"


class WorklogScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka worklog ")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_setup_is_idempotent_and_preserves_unmanaged_instructions(self) -> None:
        instructions = self.root / "AGENTS.md"
        instructions.write_text("# Existing\n\nKeep this text.\n", encoding="utf-8")

        WORKLOG.setup(self.root)
        first = instructions.read_text(encoding="utf-8")
        WORKLOG.setup(self.root)

        self.assertEqual(first, instructions.read_text(encoding="utf-8"))
        self.assertIn("# Existing\n\nKeep this text.", first)
        self.assertEqual(1, first.count(WORKLOG.BEGIN_MARKER))
        self.assertTrue((self.root / ".hukuhaka" / "work.md").is_file())
        self.assertTrue((self.root / ".hukuhaka" / "changelog.md").is_file())
        self.assertTrue((self.root / ".hukuhaka" / "changelog").is_dir())

    def test_setup_targets_agents_for_codex(self) -> None:
        WORKLOG.setup(self.root)

        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("`$hukuhaka-worklog:worklog`", agents)
        self.assertIn("throughout project work", agents)
        self.assertIn("intermediate checkpoints", agents)
        self.assertIn("Only the primary agent changes Worklog state", agents)
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_setup_replaces_legacy_codex_managed_block_only(self) -> None:
        agents = self.root / "AGENTS.md"
        work = self.root / ".hukuhaka" / "work.md"
        changelog = self.root / ".hukuhaka" / "changelog.md"
        work.parent.mkdir()
        work.write_text("existing work\n", encoding="utf-8")
        changelog.write_text("existing history\n", encoding="utf-8")
        legacy = "\n".join(
            (
                WORKLOG.BEGIN_MARKER,
                "## Worklog",
                "",
                "- `.hukuhaka/work.md` contains current Planned, In Progress, and On Hold work.",
                "- Use the installed `$worklog` Skill when recording or changing work.",
                "- Completed and closed work belongs in `.hukuhaka/changelog.md`.",
                "- Read these files when current work state or prior decisions are relevant.",
                WORKLOG.END_MARKER,
            )
        )
        agents.write_text(f"# Existing\n\n{legacy}\n\nKeep this.\n", encoding="utf-8")

        WORKLOG.setup(self.root)
        updated = agents.read_text(encoding="utf-8")

        self.assertIn("# Existing", updated)
        self.assertIn("Keep this.", updated)
        self.assertIn(f"`{WORKLOG.CODEX_INVOCATION}`", updated)
        self.assertNotIn(f"`{WORKLOG.CODEX_LEGACY_INVOCATION}`", updated)
        self.assertEqual("existing work\n", work.read_text(encoding="utf-8"))
        self.assertEqual("existing history\n", changelog.read_text(encoding="utf-8"))

    def test_hook_runs_codex_setup_and_blocks_the_model(self) -> None:
        output = io.StringIO()
        payload = {
            "prompt": "$hukuhaka-worklog:worklog setup",
            "cwd": str(self.root),
        }

        WORKLOG.run_hook(io.StringIO(json.dumps(payload)), output, {"PLUGIN_DATA": "test"})
        response = json.loads(output.getvalue())

        self.assertEqual("block", response["decision"])
        self.assertIn("worklog setup (codex)", response["reason"])
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.root / "CLAUDE.md").exists())

        repeated = io.StringIO()
        WORKLOG.run_hook(io.StringIO(json.dumps(payload)), repeated, {"PLUGIN_DATA": "test"})
        self.assertIn("Created: none", json.loads(repeated.getvalue())["reason"])

    def test_hook_runs_all_codex_command_forms(self) -> None:
        forms = (
            "$hukuhaka-worklog:worklog {command}",
            "$hukuhaka-worklog:worklog {command}\n",
            "[$hukuhaka-worklog:worklog](/tmp/plugin/skills/worklog/SKILL.md) {command}",
            "[$hukuhaka-worklog:worklog](/tmp/plugin/skills/worklog/SKILL.md) {command}\r\n",
            "$worklog {command}",
        )
        expected_output = {
            "setup": "worklog setup",
            "status": "Worklog status",
            "archive": "worklog archive",
        }
        for command in WORKLOG.COMMANDS:
            for form in forms:
                with self.subTest(command=command, form=form), tempfile.TemporaryDirectory(
                    prefix="hukuhaka worklog command "
                ) as temp:
                    root = Path(temp)
                    if command != "setup":
                        WORKLOG.setup(root)
                    if command == "archive":
                        changelog = root / ".hukuhaka" / "changelog.md"
                        entries = [
                            history_entry(day, f"Entry {day}")
                            for day in range(20, 9, -1)
                        ]
                        changelog.write_text(
                            WORKLOG.CHANGELOG_TEMPLATE.rstrip()
                            + "\n\n"
                            + "\n\n".join(entries)
                            + "\n",
                            encoding="utf-8",
                        )

                    output = io.StringIO()
                    WORKLOG.run_hook(
                        io.StringIO(
                            json.dumps(
                                {
                                    "prompt": form.format(command=command),
                                    "cwd": str(root),
                                }
                            )
                        ),
                        output,
                        {"PLUGIN_DATA": ""},
                    )
                    response = json.loads(output.getvalue())

                    self.assertEqual("block", response["decision"])
                    self.assertIn(expected_output[command], response["reason"])
                    self.assertTrue((root / "AGENTS.md").is_file())
                    self.assertFalse((root / "CLAUDE.md").exists())

    def test_hook_status_and_archive_are_mechanical(self) -> None:
        WORKLOG.setup(self.root)
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(31, 4, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )

        status_output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "$hukuhaka-worklog:worklog status",
                        "cwd": str(self.root),
                    }
                )
            ),
            status_output,
            {"PLUGIN_DATA": ""},
        )
        self.assertIn("Worklog status", json.loads(status_output.getvalue())["reason"])

        archive_output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "$hukuhaka-worklog:worklog archive",
                        "cwd": str(self.root),
                    }
                )
            ),
            archive_output,
            {"PLUGIN_DATA": ""},
        )
        response = json.loads(archive_output.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("kept 25 in Recent; moved 2", response["reason"])
        self.assertTrue(
            (self.root / ".hukuhaka" / "changelog" / "2026-07.md").is_file()
        )

    def test_hook_passes_through_nonmechanical_requests(self) -> None:
        for prompt in (
            "$worklog record this as planned",
            "$worklog archive --keep 20",
            "$worklog status ",
            "$hukuhaka-worklog:worklog setup ",
            "$hukuhaka-worklog:worklog setup now",
            "/hukuhaka-worklog:worklog setup",
            "please $hukuhaka-worklog:worklog setup",
            "$hukuhaka-worklog:other setup",
            "[$hukuhaka-worklog:worklog]() setup",
            "[$hukuhaka-worklog:worklog](/tmp/SKILL.md)\nsetup",
            "[$worklog](/tmp/SKILL.md) setup",
            "please set up the worklog",
        ):
            with self.subTest(prompt=prompt):
                output = io.StringIO()
                WORKLOG.run_hook(
                    io.StringIO(json.dumps({"prompt": prompt, "cwd": str(self.root)})),
                    output,
                    {"PLUGIN_DATA": "test"},
                )
                self.assertEqual("", output.getvalue())
        self.assertFalse((self.root / ".hukuhaka").exists())

    def test_hook_fails_closed_for_recognized_command_errors(self) -> None:
        missing_cwd = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(json.dumps({"prompt": "$hukuhaka-worklog:worklog setup"})),
            missing_cwd,
            {"PLUGIN_DATA": "test"},
        )
        response = json.loads(missing_cwd.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("missing cwd", response["reason"])

        WORKLOG.setup(self.root)
        (self.root / ".hukuhaka" / "work.md").write_text(
            "# Work\n\n## Unexpected\n",
            encoding="utf-8",
        )
        malformed = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "$hukuhaka-worklog:worklog status",
                        "cwd": str(self.root),
                    }
                )
            ),
            malformed,
            {"PLUGIN_DATA": "test"},
        )
        response = json.loads(malformed.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("work.md must contain exactly", response["reason"])

    def test_malformed_markers_fail_before_creating_worklog_files(self) -> None:
        (self.root / "AGENTS.md").write_text(
            f"{WORKLOG.BEGIN_MARKER}\nmissing end\n",
            encoding="utf-8",
        )

        with self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.setup(self.root)

        self.assertFalse((self.root / ".hukuhaka").exists())

    def test_setup_ignores_legacy_backlog(self) -> None:
        legacy = self.root / ".claude" / "backlog.md"
        legacy.parent.mkdir()
        legacy.write_text("legacy content\n", encoding="utf-8")

        WORKLOG.setup(self.root)

        self.assertEqual("legacy content\n", legacy.read_text(encoding="utf-8"))

    def test_status_reports_structural_counts_without_rewriting(self) -> None:
        WORKLOG.setup(self.root)
        work = self.root / ".hukuhaka" / "work.md"
        work.write_text(
            """# Work

## In Progress

- **Active item.** Current state.
  - Next gate: run the fixture.

## Planned

- **Planned item.** Future state.

## On Hold

- **Held item.** Waiting.
  - Revisit when: the API ships.
""",
            encoding="utf-8",
        )
        before = work.read_bytes()
        output = io.StringIO()

        with redirect_stdout(output):
            WORKLOG.status(self.root)

        self.assertEqual(before, work.read_bytes())
        self.assertIn("In Progress (1)", output.getvalue())
        self.assertIn("Planned (1)", output.getvalue())
        self.assertIn("On Hold (1)", output.getvalue())
        self.assertIn("Recent history: 0/25", output.getvalue())

    def test_archive_keeps_default_limit_and_is_idempotent(self) -> None:
        WORKLOG.setup(self.root)
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(31, 4, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )

        WORKLOG.archive_history(self.root)
        first_main = changelog.read_text(encoding="utf-8")
        archive = self.root / ".hukuhaka" / "changelog" / "2026-07.md"
        first_archive = archive.read_text(encoding="utf-8")
        WORKLOG.archive_history(self.root)

        self.assertEqual(25, len(WORKLOG.parse_history(first_main, changelog)[1]))
        self.assertIn("Entry 6", first_archive)
        self.assertIn("Entry 5", first_archive)
        self.assertEqual(first_main, changelog.read_text(encoding="utf-8"))
        self.assertEqual(first_archive, archive.read_text(encoding="utf-8"))

    def test_archive_conflict_fails_before_recent_changes(self) -> None:
        WORKLOG.setup(self.root)
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(31, 5, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )
        archive = self.root / ".hukuhaka" / "changelog" / "2026-07.md"
        archive.write_text(
            "# Changelog — 2026-07\n\n"
            + history_entry(6, "Entry 6", "Conflicting result.")
            + "\n",
            encoding="utf-8",
        )
        before = changelog.read_bytes()

        with self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.archive_history(self.root)

        self.assertEqual(before, changelog.read_bytes())

        output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "$hukuhaka-worklog:worklog archive",
                        "cwd": str(self.root),
                    }
                )
            ),
            output,
            {"PLUGIN_DATA": ""},
        )
        response = json.loads(output.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("conflicting archive entry", response["reason"])
        self.assertEqual(before, changelog.read_bytes())

    def test_archive_refuses_symlinked_archive_directory(self) -> None:
        WORKLOG.setup(self.root)
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(31, 5, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip()
            + "\n\n"
            + "\n\n".join(entries)
            + "\n",
            encoding="utf-8",
        )
        archive = self.root / ".hukuhaka" / "changelog"
        archive.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        archive.symlink_to(outside, target_is_directory=True)
        before = changelog.read_bytes()

        with self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.archive_history(self.root)

        self.assertEqual(before, changelog.read_bytes())
        self.assertEqual([], list(outside.iterdir()))


class AutomaticArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="hukuhaka automatic worklog ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write_history(self, count: int = 26) -> Path:
        WORKLOG.setup(self.root)
        path = self.root / ".hukuhaka/changelog.md"
        path.write_text(WORKLOG.CHANGELOG_TEMPLATE + "\n" + "\n\n".join(
            history_entry(day, f"Entry {day}") for day in range(31, 31 - count, -1)
        ) + "\n")
        return path

    def event(self, event: str, call: str = "call-1", **overrides) -> str:
        payload = {
            "hook_event_name": event, "cwd": str(self.root),
            "session_id": "session-1", "tool_use_id": call,
            "tool_name": "apply_patch", "permission_mode": "default",
        }
        payload.update(overrides)
        output = io.StringIO()
        WORKLOG.run_hook(io.StringIO(json.dumps(payload)), output,
                         {"PLUGIN_DATA": str(self.root / "plugin-data")})
        return output.getvalue()

    def test_read_only_and_unpaired_events_preserve_overflow(self) -> None:
        path = self.write_history()
        before = path.read_bytes()
        self.assertEqual("", self.event("PostToolUse"))
        self.assertEqual("", self.event("PreToolUse"))
        self.assertEqual("", self.event("PostToolUse"))
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list((self.root / ".hukuhaka/changelog").iterdir()))

    def test_edit_archives_once_without_touching_progress(self) -> None:
        path = self.write_history()
        work = self.root / ".hukuhaka/work.md"
        work_before = work.read_bytes()
        self.event("PreToolUse")
        path.write_text(path.read_text().replace("Recorded result.", "Checkpoint.", 1))
        self.assertEqual("", self.event("PostToolUse"))
        archive = self.root / ".hukuhaka/changelog/2026-07.md"
        self.assertEqual(25, len(WORKLOG.parse_history(path.read_text(), path)[1]))
        self.assertIn("Entry 6", archive.read_text())
        before = (path.read_bytes(), archive.read_bytes())
        self.event("PostToolUse")
        self.assertEqual(before, (path.read_bytes(), archive.read_bytes()))
        self.assertEqual(work_before, work.read_bytes())
        self.assertEqual([], list((self.root / "plugin-data/worklog-pending").glob("*.json")))

    def test_overlapping_tool_pairs_have_independent_snapshots(self) -> None:
        path = self.write_history()
        self.event("PreToolUse", "a")
        self.event("PreToolUse", "b")
        path.write_text(path.read_text() + "\nCheckpoint detail.\n")
        self.event("PostToolUse", "b")
        self.event("PostToolUse", "a")
        archive = self.root / ".hukuhaka/changelog/2026-07.md"
        self.assertEqual(1, archive.read_text().count("### "))
        self.assertIn("Checkpoint detail.", archive.read_text())

    def test_plan_mode_missing_files_and_unknown_events_do_not_write(self) -> None:
        for event in ("PreToolUse", "PostToolUse", "Stop"):
            self.assertEqual("", self.event(event))
        self.assertFalse((self.root / ".hukuhaka").exists())
        path = self.write_history()
        before = path.read_bytes()
        self.event("PreToolUse", permission_mode="plan")
        path.write_text(path.read_text() + "\n")
        self.event("PostToolUse", permission_mode="plan")
        self.assertEqual(before + b"\n", path.read_bytes())
        self.assertEqual([], list((self.root / ".hukuhaka/changelog").iterdir()))

    def test_malformed_edit_warns_without_blocking_or_rewriting(self) -> None:
        path = self.write_history()
        self.event("PreToolUse")
        path.write_text("user content without a Recent section\n")
        response = json.loads(self.event("PostToolUse"))
        self.assertIn("systemMessage", response)
        self.assertNotIn("decision", response)
        self.assertEqual("user content without a Recent section\n", path.read_text())

    def test_subdirectory_lookup_stops_at_nested_repository(self) -> None:
        self.write_history()
        sub = self.root / "src"
        sub.mkdir()
        self.assertEqual(self.root, WORKLOG.project_root(sub))
        (sub / ".git").mkdir()
        self.assertIsNone(WORKLOG.project_root(sub))

    def test_archive_preserves_link_targets_and_code(self) -> None:
        path = self.write_history()
        body = '''[report](../docs/report.md#result) ![plot](images/plot.png)
[space](<../docs/a b.md>) [nested](../docs/a(b).md "Title")
[web](https://example.com/a) [root](/absolute/file) [local](#section)
[reference][report]
[report]: ../docs/report.md "Title"
- Task
  - Substep
    [nested note](../docs/report.md)
      - Detail [evidence](../docs/report.md)

Ordinary paragraph.

    [indented code](../leave.md)

`[example](../leave.md)`
```markdown
[example](../leave.md)
```
'''
        path.write_text(path.read_text().replace("### 2026-07-06 — Entry 6\n\nRecorded result.",
                                                "### 2026-07-06 — Entry 6\n\n" + body))
        WORKLOG.archive_history(self.root)
        text = (self.root / ".hukuhaka/changelog/2026-07.md").read_text()
        self.assertIn("[report](../../docs/report.md#result)", text)
        self.assertIn("![plot](../images/plot.png)", text)
        self.assertIn("(<../../docs/a b.md>)", text)
        self.assertIn('(../../docs/a(b).md "Title")', text)
        self.assertIn('[report]: ../../docs/report.md "Title"', text)
        self.assertIn('[nested note](../../docs/report.md)', text)
        self.assertIn('[evidence](../../docs/report.md)', text)
        self.assertIn('    [indented code](../leave.md)', text)
        for unchanged in ('https://example.com/a', '(/absolute/file)', '(#section)',
                          '`[example](../leave.md)`', '```markdown\n[example](../leave.md)\n```'):
            self.assertIn(unchanged, text)

    def test_interrupted_archive_retries_rebased_entry_without_duplicates(self) -> None:
        path = self.write_history()
        path.write_text(path.read_text() + "\n[report](../docs/report.md)\n")
        original = WORKLOG.atomic_write

        def interrupt(target, content):
            if target == path:
                raise OSError("interrupted before truncation")
            original(target, content)

        before = path.read_bytes()
        with patch.object(WORKLOG, "atomic_write", interrupt), self.assertRaises(OSError):
            WORKLOG.archive_history(self.root)
        self.assertEqual(before, path.read_bytes())
        WORKLOG.archive_history(self.root)
        text = (self.root / ".hukuhaka/changelog/2026-07.md").read_text()
        self.assertEqual(1, text.count("### "))
        self.assertEqual(1, text.count("../../docs/report.md"))

    def test_concurrent_edit_is_preserved_and_archive_is_serialized(self) -> None:
        path = self.write_history()
        with WORKLOG.archive_lock(self.root), self.assertRaises(OSError):
            WORKLOG.archive_history(self.root)
        original = WORKLOG.atomic_write

        def append_during_archive(target, content):
            original(target, content)
            if target != path:
                path.write_text(path.read_text().replace("## Recent", "## Recent\n\n" + history_entry(31, "New concurrent work")))

        with patch.object(WORKLOG, "atomic_write", append_during_archive), self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.archive_history(self.root)
        self.assertIn("New concurrent work", path.read_text())
        self.assertEqual(27, len(WORKLOG.parse_history(path.read_text(), path)[1]))
        WORKLOG.archive_history(self.root)
        self.assertIn("New concurrent work", path.read_text())
        self.assertEqual(25, len(WORKLOG.parse_history(path.read_text(), path)[1]))


class WorklogPackageTests(unittest.TestCase):
    def test_codex_manifest_exposes_identity_and_version(self) -> None:
        codex = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual("hukuhaka-worklog", codex["name"])
        self.assertEqual("0.5.0", codex["version"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertNotIn("hooks", codex)
        self.assertTrue((PLUGIN / "hooks" / "hooks.json").is_file())
        self.assertFalse((PLUGIN / ".claude-plugin").exists())
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        handler = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertEqual('python3 "${PLUGIN_ROOT}/skills/worklog/scripts/worklog.py" hook', handler["command"])
        self.assertNotIn("commandWindows", handler)

    def test_shared_skill_is_model_invokable_and_codex_native(self) -> None:
        skill = (PLUGIN / "skills" / "worklog" / "SKILL.md").read_text(encoding="utf-8")
        header = skill.split("---", 2)[1]
        self.assertNotIn("disable-model-invocation", header)
        self.assertNotIn("allowed-tools", header)
        self.assertIn(".hukuhaka/work.md", skill)
        self.assertIn("Use automatically throughout project work when these files exist", header)
        self.assertIn("when explicitly asked to update Worklog", header)
        self.assertNotIn("If either already has user changes", skill)
        self.assertIn("Only the primary agent updates these files", skill)
        self.assertNotIn("Claude Code", skill)
        self.assertNotIn("/hukuhaka-worklog:worklog", skill)
        self.assertNotIn("references/writing-guide.md", skill)
        self.assertFalse(
            (
                PLUGIN
                / "skills"
                / "worklog"
                / "references"
                / "writing-guide.md"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
