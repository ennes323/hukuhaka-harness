"""Safe global Codex config.toml editor."""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .common import (
    FileTransaction,
    InstallerError,
    StateError,
    atomic_write_bytes,
    installer_state,
)


Key = Tuple[str, ...]

SUBAGENT_SETTINGS = {
    ("features", "multi_agent"): "false",
}  # type: Dict[Key, str]

AGENT_WAIT_SETTINGS = {
    ("features", "multi_agent_v2", "min_wait_timeout_ms"): "120000",
    ("features", "multi_agent_v2", "default_wait_timeout_ms"): "120000",
}  # type: Dict[Key, str]


RECOMMENDED_SETTINGS = {
    **AGENT_WAIT_SETTINGS,
    **SUBAGENT_SETTINGS,
    ("personality",): '"pragmatic"',
    ("model_reasoning_effort",): '"medium"',
    ("model_reasoning_summary",): '"concise"',
    ("model_verbosity",): '"low"',
    ("agents", "enabled"): "true",
    (
        "tui",
        "status_line",
    ): '["model-with-reasoning", "context-remaining", "used-tokens", '
    '"five-hour-limit", "weekly-limit", "git-branch", "current-dir"]',
    ("tui", "notifications"): '["agent-turn-complete", "approval-requested"]',
    ("tui", "notification_condition"): '"unfocused"',
    ("features", "prevent_idle_sleep"): "true",
}  # type: Dict[Key, str]

# Preserve optional role files without re-enabling subagent execution.
EVIDENCE_SCOUT_SETTINGS = {
    **SUBAGENT_SETTINGS,
    ("agents", "enabled"): "true",
}  # type: Dict[Key, str]

# Agent execution capacity is an explicit user policy, separate from component
# installation and the general Codex defaults wizard. The policy owns only
# these two settings and records that ownership in its own manifest.
AGENT_POLICY_KEYS = (
    ("agents", "max_concurrent_threads_per_session"),
    ("agents", "max_depth"),
)
AGENT_POLICY_MANIFEST = ".hukuhaka-agent-policy.json"

# Explicit one-shot migration, never part of ordinary install or capacity policy.
SUBAGENT_MODEL_KEYS = (
    ("agents", "default_subagent_model"),
    ("agents", "default_subagent_reasoning_effort"),
)

# Legacy Evidence Scout installs owned this top-level key. Keep it in the
# managed set only so schema-v2 manifests can remove their exact pointer.
EVIDENCE_SCOUT_DYNAMIC_KEYS = {("model_catalog_json",)}

# Context policy is intentionally outside the general recommended settings.
# Its command owns only these explicit top-level overrides and must never make
# an install, reset, or full config-wizard operation responsible for them.
CONTEXT_POLICY_KEYS = (
    ("model_context_window",),
    ("model_auto_compact_token_limit",),
    ("model_auto_compact_token_limit_scope",),
)
CONTEXT_POLICY_SCOPES = ("total", "body_after_prefix")
CONTEXT_POLICY_MANIFEST = ".hukuhaka-context-policy.json"
MODEL_KEY = ("model",)

# These are documented model capacities, not Codex runtime defaults. Keep an
# unknown model unknown instead of guessing from a name or silently applying a
# capacity intended for a different model/provider.
DOCUMENTED_MODEL_CONTEXT_CAPACITIES = {
    "gpt-5.6": 1_050_000,
    "gpt-5.6-sol": 1_050_000,
    "gpt-5.6-terra": 1_050_000,
    "gpt-5.6-luna": 1_050_000,
}  # type: Dict[str, int]

# Codex still accepts agents.max_threads as a legacy alias for the canonical
# concurrency key. Treat both spellings as one managed identity so an existing
# legacy setting is replaced instead of leaving Codex to load both fields.
LEGACY_KEY_ALIASES = {
    ("agents", "max_threads"): (
        "agents",
        "max_concurrent_threads_per_session",
    ),
}  # type: Dict[Key, Key]


def _managed_keys() -> set[Key]:
    return set(RECOMMENDED_SETTINGS) | EVIDENCE_SCOUT_DYNAMIC_KEYS


def _canonical_key(key: Key) -> Key:
    return LEGACY_KEY_ALIASES.get(key, key)


def _resolved_managed_keys(managed_keys: Optional[Sequence[Key]]) -> set[Key]:
    keys = _managed_keys() if managed_keys is None else set(managed_keys)
    return {_canonical_key(key) for key in keys}


def _canonical_key_text(assignment: "_Assignment", key: Key) -> str:
    if assignment.path == key:
        return assignment.key_text
    if len(_key_parts(assignment.key_text)) == 1:
        return key[-1]
    return ".".join(key)


_KEY_SEGMENT = r"""(?:[A-Za-z0-9_-]+|"(?:[^"\\]|\\.)*"|'[^']*')"""
_KEY_PATH = _KEY_SEGMENT + r"(?:\s*\.\s*" + _KEY_SEGMENT + r")*"
_SECTION_RE = re.compile(r"^\s*\[(" + _KEY_PATH + r")\]\s*(?:#.*)?$")
_ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>\s*)(?P<key>" + _KEY_PATH + r")\s*="
)


def _key_parts(text: str) -> Key:
    parts = []
    for match in re.finditer(_KEY_SEGMENT, text):
        token = match.group()
        if token.startswith('"'):
            try:
                token = json.loads(token)
            except ValueError as exc:
                raise StateError("unsupported quoted TOML key escape",
                                 operation="parse-config") from exc
        elif token.startswith("'"):
            token = token[1:-1]
        parts.append(token)
    return tuple(parts)


@dataclass(frozen=True)
class ConfigPlan:
    path: Path
    original: bytes
    proposed: bytes
    existed: bool
    mode: int
    removed: Tuple[Key, ...] = ()
    managed_keys: Tuple[Key, ...] = ()
    stage: str = "configure"

    @property
    def changed(self) -> bool:
        return self.original != self.proposed

    def diff(self) -> str:
        before = self.original.decode("utf-8").splitlines(keepends=True)
        after = self.proposed.decode("utf-8").splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=str(self.path),
                tofile=str(self.path) + " (proposed)",
            )
        )


@dataclass(frozen=True)
class _Assignment:
    path: Key
    start: int
    end: int
    indent: str
    key_text: str
    value: str


def _balance(value: str) -> int:
    """Return unmatched []/{} depth while ignoring strings and comments."""
    depth = 0
    quote = ""
    escaped = False
    for character in value:
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "#":
            break
        elif character in "[{":
            depth += 1
        elif character in "]}":
            depth -= 1
    return depth


def _comment_offset(line: str) -> int:
    quote = ""
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "#":
            return index
    return -1


def _trailing_comment(line: str) -> str:
    offset = _comment_offset(line)
    return line[offset:].rstrip("\r\n") if offset >= 0 else ""


def _without_comment(line: str) -> str:
    offset = _comment_offset(line)
    return line[:offset] if offset >= 0 else line


def _assignment_value(lines: Sequence[str], start: int, value_offset: int) -> Tuple[int, str]:
    first = lines[start][value_offset:]
    delimiter = first.lstrip()[:3]
    if delimiter in ('"""', "'''"):
        remainder = first.lstrip()[3:]
        end = start
        while True:
            for match in re.finditer(re.escape(delimiter), remainder):
                prefix = remainder[:match.start()]
                slashes = len(prefix) - len(prefix.rstrip("\\"))
                if delimiter == "'''" or slashes % 2 == 0:
                    return end + 1, (first + "".join(lines[start + 1:end + 1])).strip()
            end += 1
            if end >= len(lines):
                raise StateError("unterminated TOML string", operation="parse-config")
            remainder = lines[end]
    values = [_without_comment(first)]
    depth = _balance(first)
    end = start + 1
    while depth > 0 and end < len(lines):
        values.append(_without_comment(lines[end]))
        depth += _balance(lines[end])
        end += 1
    if depth != 0:
        raise StateError(
            "unterminated TOML value",
            host="codex",
            stage="configure",
            operation="parse-config",
        )
    return end, "".join(values).strip()


def _parse_assignments(text: str) -> Tuple[List[str], List[_Assignment], Dict[Key, int]]:
    lines = text.splitlines(keepends=True)
    assignments = []  # type: List[_Assignment]
    sections = {}  # type: Dict[Key, int]
    section = ()  # type: Key
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("[["):
            section = ("<array-table>",)
            index += 1
            continue
        section_match = _SECTION_RE.match(lines[index])
        if section_match:
            section = _key_parts(section_match.group(1))
            sections.setdefault(section, index)
            index += 1
            continue
        if stripped.startswith("["):
            # Codex owns tables with quoted segments such as
            # [plugins."name@marketplace"]. They are outside this editor's
            # managed surface, but they still end the preceding table. Do not
            # misclassify their assignments as members of [agents] or another
            # supported section.
            section = ("<unsupported-table>",)
            index += 1
            continue
        match = _ASSIGNMENT_RE.match(lines[index])
        if not match:
            index += 1
            continue
        key_parts = _key_parts(match.group("key"))
        path = section + key_parts
        end, value = _assignment_value(lines, index, match.end())
        assignments.append(
            _Assignment(
                path=path,
                start=index,
                end=end,
                indent=match.group("indent"),
                key_text=match.group("key"),
                value=value,
            )
        )
        index = end
    return lines, assignments, sections


def current_values(
    text: str,
    *,
    managed_keys: Optional[Sequence[Key]] = None,
    stage: str = "configure",
) -> Dict[Key, str]:
    managed = _resolved_managed_keys(managed_keys)
    _, assignments, _ = _parse_assignments(text)
    found = {}  # type: Dict[Key, str]
    for assignment in assignments:
        key = _canonical_key(assignment.path)
        if key in managed:
            if key in found:
                raise StateError(
                    "duplicate managed Codex config key: {}".format(
                        ".".join(key)
                    ),
                    host="codex",
                    stage=stage,
                    operation="parse-config",
                )
            found[key] = assignment.value
        elif any(
            key[: len(assignment.path)] == assignment.path
            for key in managed
        ):
            raise StateError(
                "managed Codex config table uses an inline value: {}".format(
                    ".".join(assignment.path)
                ),
                host="codex",
                stage=stage,
                operation="parse-config",
            )
    return found


def _section_end(lines: Sequence[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("["):
            return index
    return len(lines)


def update_config(
    text: str,
    settings: Mapping[Key, str],
    *,
    remove: Sequence[Key] = (),
    managed_keys: Optional[Sequence[Key]] = None,
    stage: str = "configure",
) -> str:
    managed = _resolved_managed_keys(managed_keys)
    remove_keys = {_canonical_key(key) for key in remove}
    unknown = [
        key for key in tuple(settings) + tuple(remove_keys) if key not in managed
    ]
    if unknown:
        raise StateError(
            "unsupported managed Codex config key: {}".format(".".join(unknown[0])),
            host="codex",
            stage=stage,
            operation="update-config",
        )
    overlap = set(settings) & remove_keys
    if overlap:
        raise StateError(
            "Codex config key cannot be set and removed together: {}".format(
                ".".join(next(iter(overlap)))
            ),
            host="codex",
            stage=stage,
            operation="update-config",
        )

    lines, assignments, sections = _parse_assignments(text)
    current_values(
        text, managed_keys=tuple(managed), stage=stage
    )  # Validate duplicate and inline managed shapes.
    replacements = {}  # type: Dict[int, Tuple[int, str]]
    present = set()  # type: set[Key]
    for assignment in assignments:
        key = _canonical_key(assignment.path)
        if key in remove_keys:
            original_lines = lines[assignment.start:assignment.end]
            comments = [
                comment
                for comment in (_trailing_comment(line) for line in original_lines)
                if comment
            ]
            newline = "\r\n" if original_lines[0].endswith("\r\n") else "\n"
            replacements[assignment.start] = (
                assignment.end,
                "".join(
                    "{}{}{}".format(assignment.indent, comment, newline)
                    for comment in comments
                ),
            )
            continue
        if key not in settings:
            continue
        present.add(key)
        original_lines = lines[assignment.start:assignment.end]
        comments = [
            comment
            for comment in (_trailing_comment(line) for line in original_lines)
            if comment
        ]
        newline = "\r\n" if original_lines[0].endswith("\r\n") else "\n"
        prefix = ""
        suffix = ""
        if len(original_lines) == 1 and comments:
            suffix = " " + comments[0]
        elif comments:
            prefix = "".join(
                "{}{}{}".format(assignment.indent, comment, newline)
                for comment in comments
            )
        replacements[assignment.start] = (
            assignment.end,
            "{}{}{} = {}{}{}".format(
                prefix,
                assignment.indent,
                _canonical_key_text(assignment, key),
                settings[key],
                suffix,
                newline,
            ),
        )

    rewritten = []  # type: List[str]
    index = 0
    while index < len(lines):
        replacement = replacements.get(index)
        if replacement is None:
            rewritten.append(lines[index])
            index += 1
        else:
            end, content = replacement
            rewritten.append(content)
            index = end

    missing = [key for key in settings if key not in present]
    if not missing:
        return "".join(rewritten)

    # Re-parse after replacements so insertion indices match the rewritten text.
    lines, _, sections = _parse_assignments("".join(rewritten))
    dotted_tables = {
        assignment.path[:-1]
        for assignment in assignments
        if len(assignment.path) > 1
        and assignment.key_text == ".".join(assignment.path)
    }
    top_level = [
        key
        for key in missing
        if len(key) == 1 or key[:-1] in dotted_tables
    ]
    tables = list(
        dict.fromkeys(
            key[:-1]
            for key in missing
            if len(key) > 1 and key[:-1] not in dotted_tables
        )
    )

    if top_level:
        first_section = next(
            (index for index, line in enumerate(lines) if line.strip().startswith("[")),
            len(lines),
        )
        additions = [
            "{} = {}\n".format(".".join(key), settings[key]) for key in top_level
        ]
        if first_section and lines[first_section - 1].strip():
            additions.append("\n")
        lines[first_section:first_section] = additions

    for table in tables:
        # Earlier insertions can move sections, so find the table each time.
        _, _, current_sections = _parse_assignments("".join(lines))
        keys = [key for key in missing if key[:-1] == table]
        if table in current_sections:
            insertion = _section_end(lines, current_sections[table])
            additions = ["{} = {}\n".format(key[-1], settings[key]) for key in keys]
            if insertion and lines[insertion - 1].strip():
                additions.append("\n")
            lines[insertion:insertion] = additions
        else:
            if lines and lines[-1].strip():
                lines.append("\n")
            lines.append("[{}]\n".format(".".join(table)))
            lines.extend("{} = {}\n".format(key[-1], settings[key]) for key in keys)

    return "".join(lines)


def _prompt_choice(label: str, current: str, allowed: Sequence[str]) -> str:
    default = current if current in allowed else allowed[0]
    while True:
        value = input("{} [{}]: ".format(label, default)).strip() or default
        if value in allowed:
            return value
        print("Choose one of: {}".format(", ".join(allowed)))


def _prompt_bool(label: str, current: bool) -> bool:
    prompt = "Y/n" if current else "y/N"
    while True:
        value = input("{} [{}]: ".format(label, prompt)).strip().lower()
        if not value:
            return current
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False


def _decode_string(value: str, fallback: str) -> str:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return fallback
    return decoded if isinstance(decoded, str) else fallback


def prompt_settings(current: Mapping[Key, str]) -> Dict[Key, str]:
    """Ask only about the supported global defaults."""
    recommended = RECOMMENDED_SETTINGS
    personality = _prompt_choice(
        "Personality",
        _decode_string(current.get(("personality",), ""), "pragmatic"),
        ("pragmatic", "friendly", "none"),
    )
    effort = _prompt_choice(
        "Reasoning effort",
        _decode_string(current.get(("model_reasoning_effort",), ""), "medium"),
        ("medium", "low", "high", "xhigh", "minimal"),
    )
    summary = _prompt_choice(
        "Reasoning summary",
        _decode_string(current.get(("model_reasoning_summary",), ""), "concise"),
        ("concise", "auto", "detailed", "none"),
    )
    verbosity = _prompt_choice(
        "Response verbosity",
        _decode_string(current.get(("model_verbosity",), ""), "low"),
        ("low", "medium", "high"),
    )
    agents_enabled = _prompt_bool(
        "Enable multi-agent",
        current.get(("agents", "enabled"), "true").lower() != "false",
    )
    notifications = _prompt_bool(
        "Enable TUI notifications",
        current.get(("tui", "notifications"), "true").lower() != "false",
    )
    idle_sleep = _prompt_bool(
        "Prevent idle sleep during a turn",
        current.get(("features", "prevent_idle_sleep"), "true").lower() != "false",
    )
    return {
        ("personality",): json.dumps(personality),
        ("model_reasoning_effort",): json.dumps(effort),
        ("model_reasoning_summary",): json.dumps(summary),
        ("model_verbosity",): json.dumps(verbosity),
        ("agents", "enabled"): str(agents_enabled).lower(),
        ("tui", "status_line"): current.get(
            ("tui", "status_line"), recommended[("tui", "status_line")]
        ),
        ("tui", "notifications"): (
            recommended[("tui", "notifications")] if notifications else "false"
        ),
        ("tui", "notification_condition"): current.get(
            ("tui", "notification_condition"),
            recommended[("tui", "notification_condition")],
        ),
        ("features", "prevent_idle_sleep"): str(idle_sleep).lower(),
    }


def prompt_agent_action(state: "AgentPolicyState") -> Optional[str]:
    print("Codex agent execution policy")
    print("  Current configuration: {}".format(state.label))
    print(
        "  Concurrent spawned threads: {}".format(
            state.display(("agents", "max_concurrent_threads_per_session"))
        )
    )
    print(
        "  V1 nesting depth: {}".format(
            state.display(("agents", "max_depth"))
        )
    )
    print("  Note: max_depth is V1-only and is ignored by V2.")
    if not state.actionable:
        print("  This policy is not managed by Hukuhaka and will not be changed.")
        print("  q. Exit")
        while True:
            choice = input("Choose an action [q]: ").strip().lower() or "q"
            if choice in ("q", "quit", "exit"):
                return None
            print("Choose q.")
    print("  1. Set custom policy")
    print("  2. Reset to Codex defaults")
    print("  q. Exit")
    while True:
        choice = input("Choose an action [q]: ").strip().lower() or "q"
        if choice in ("1", "set"):
            return "set"
        if choice in ("2", "reset"):
            return "reset"
        if choice in ("q", "quit", "exit"):
            return None
        print("Choose 1, 2, or q.")


def prompt_agent_settings(state: "AgentPolicyState") -> Tuple[int, int]:
    print("Set custom agent execution policy")
    print("  max_depth is V1-only and is ignored by V2.")
    threads = state.integer(
        ("agents", "max_concurrent_threads_per_session"), fallback=8
    )
    depth = state.integer(("agents", "max_depth"), fallback=1)
    while True:
        entered = (
            input("Concurrent spawned threads [{}]: ".format(threads)).strip()
            or str(threads)
        )
        if entered.isdigit() and int(entered) > 0:
            threads = int(entered)
            break
        print("Enter a positive integer.")
    while True:
        entered = input("V1 nesting depth [{}]: ".format(depth)).strip() or str(depth)
        if entered.isdigit() and int(entered) > 0:
            depth = int(entered)
            break
        print("Enter a positive integer.")
    return threads, depth


def _prompt_positive_integer(label: str) -> int:
    while True:
        entered = input("{}: ".format(label)).strip()
        if entered.isdigit() and int(entered) > 0:
            return int(entered)
        print("Enter a positive integer.")


def _context_setting_display(state: "ContextPolicyState", key: Key) -> str:
    value = state.settings.get(key)
    if value is None:
        if key == ("model_context_window",):
            return "Codex/model default (no override; numeric limit not exposed)"
        if key == ("model_auto_compact_token_limit",):
            return (
                "Codex model default (no override; numeric threshold "
                "not exposed)"
            )
        if key == ("model_auto_compact_token_limit_scope",):
            return "total (Codex default; no override)"
        return "Codex/model default (no override)"
    if key == ("model_auto_compact_token_limit_scope",):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return "{} ({})".format(value, state.source)


def prompt_context_action(state: "ContextPolicyState") -> Optional[str]:
    print("Codex context policy")
    print("  Current configuration: {}".format(state.label))
    if state.model is None:
        print("  Configured model: Codex default (not set in config.toml)")
    else:
        print("  Configured model: {} (config.toml)".format(state.model))
    if state.documented_context_capacity is not None:
        print(
            "  Documented model capacity: {:,} tokens (not the Codex default)".format(
                state.documented_context_capacity
            )
        )
    print(
        "  Context window: {}".format(
            _context_setting_display(
                state, ("model_context_window",)
            )
        )
    )
    print(
        "  Auto-compact at: {}".format(
            _context_setting_display(
                state, ("model_auto_compact_token_limit",)
            )
        )
    )
    print(
        "  Threshold scope: {}".format(
            _context_setting_display(
                state,
                ("model_auto_compact_token_limit_scope",),
            )
        )
    )
    if not state.actionable:
        print("  This policy is not managed by Hukuhaka and will not be changed.")
        print("  q. Exit")
        while True:
            choice = input("Choose an action [q]: ").strip().lower() or "q"
            if choice in ("q", "quit", "exit"):
                return None
            print("Choose q.")
    print("  1. Set custom policy")
    print("  2. Reset to Codex defaults")
    print("  q. Exit")
    while True:
        choice = input("Choose an action [q]: ").strip().lower() or "q"
        if choice in ("1", "set"):
            return "set"
        if choice in ("2", "reset"):
            return "reset"
        if choice in ("q", "quit", "exit"):
            return None
        print("Choose 1, 2, or q.")


def prompt_context_settings(state: "ContextPolicyState") -> Tuple[int, int, str]:
    print("Set custom context policy")
    print("  Set the window, auto-compaction threshold, and threshold scope.")
    print("  Auto-compact at must be lower than the context window.")
    if state.model is None:
        print("  Configured model: Codex default (not set in config.toml)")
    else:
        print("  Configured model: {} (config.toml)".format(state.model))
    if state.documented_context_capacity is not None:
        print(
            "  Documented model capacity: {:,} tokens (not the Codex default)".format(
                state.documented_context_capacity
            )
        )
    print(
        "  Current context window: {}".format(
            _context_setting_display(state, ("model_context_window",))
        )
    )
    print(
        "  Current auto-compact at: {}".format(
            _context_setting_display(state, ("model_auto_compact_token_limit",))
        )
    )
    print(
        "  Current threshold scope: {}".format(
            _context_setting_display(
                state, ("model_auto_compact_token_limit_scope",)
            )
        )
    )
    context_window = _prompt_positive_integer("Context window tokens")
    compact_at = _prompt_positive_integer("Auto-compact at tokens")
    scope = _prompt_choice(
        "Auto-compaction threshold scope",
        "total",
        CONTEXT_POLICY_SCOPES,
    )
    return context_window, compact_at, scope


class CodexConfigEditor:
    def __init__(
        self,
        codex_home: Path,
        *,
        dry_run: bool = False,
        managed_keys: Optional[Sequence[Key]] = None,
        stage: str = "configure",
    ) -> None:
        self.codex_home = codex_home.expanduser()
        self.path = self.codex_home / "config.toml"
        self.backup = self.codex_home / "config.toml.hukuhaka-backup"
        self.dry_run = dry_run
        self.managed_keys = tuple(sorted(_resolved_managed_keys(managed_keys)))
        self.stage = stage

    def _read(self) -> Tuple[bytes, bool, int]:
        if not self.path.exists() and not self.path.is_symlink():
            return b"", False, 0o600
        if self.path.is_symlink() or not self.path.is_file():
            raise StateError(
                "Codex config.toml must be a regular file",
                host="codex",
                stage=self.stage,
                path=str(self.path),
            )
        content = self.path.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "Codex config.toml must be UTF-8",
                host="codex",
                stage=self.stage,
                path=str(self.path),
            ) from exc
        return content, True, stat.S_IMODE(self.path.stat().st_mode)

    def inspect(self) -> Dict[Key, str]:
        original, _, _ = self._read()
        return current_values(
            original.decode("utf-8"),
            managed_keys=self.managed_keys,
            stage=self.stage,
        )

    def plan(
        self,
        settings: Mapping[Key, str],
        *,
        remove: Sequence[Key] = (),
    ) -> ConfigPlan:
        original, existed, mode = self._read()
        proposed = update_config(
            original.decode("utf-8"),
            settings,
            remove=remove,
            managed_keys=self.managed_keys,
            stage=self.stage,
        ).encode("utf-8")
        return ConfigPlan(
            self.path,
            original,
            proposed,
            existed,
            mode,
            tuple(_canonical_key(key) for key in remove),
            self.managed_keys,
            self.stage,
        )

    def _doctor(self) -> None:
        command = shutil.which("codex")
        if command is None:
            raise InstallerError(
                "codex CLI is required to validate global config",
                host="codex",
                stage=self.stage,
                operation="doctor",
            )
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        result = subprocess.run(
            (command, "doctor", "--json"),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
            timeout=30,
        )
        try:
            payload = json.loads(result.stdout)
            check = payload["checks"]["config.load"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            detail = (result.stderr or result.stdout).strip()
            raise InstallerError(
                "codex doctor returned an unexpected JSON report{}".format(
                    ": " + detail if detail else ""
                ),
                host="codex",
                stage=self.stage,
                operation="doctor",
            ) from exc
        if check.get("status") != "ok":
            raise InstallerError(
                "codex config validation failed: {}".format(
                    check.get("summary", "config.load was not ok")
                ),
                host="codex",
                stage=self.stage,
                operation="doctor",
            )

    def apply(self, plan: ConfigPlan, *, show_diff: bool = True) -> bool:
        if not plan.changed:
            print("Codex config: already matches the selected defaults.")
            return False
        if show_diff:
            print(plan.diff(), end="")
        if self.dry_run:
            print("Codex config dry run complete. No files were modified.")
            return False
        current, existed, _ = self._read()
        if current != plan.original or existed != plan.existed:
            raise StateError(
                "Codex config changed after the diff was prepared; review it again",
                host="codex",
                stage=self.stage,
                operation="verify-precondition",
                path=str(self.path),
            )
        self.codex_home.mkdir(parents=True, exist_ok=True)
        if plan.existed:
            atomic_write_bytes(self.backup, plan.original, plan.mode)
        try:
            atomic_write_bytes(self.path, plan.proposed, plan.mode)
            self._doctor()
        except Exception as exc:
            try:
                if plan.existed:
                    atomic_write_bytes(self.path, plan.original, plan.mode)
                elif self.path.exists():
                    self.path.unlink()
            except OSError as rollback_error:
                raise StateError(
                    "Codex config validation failed and the original could not be restored",
                    host="codex",
                    stage=self.stage,
                    operation="rollback-config",
                    path=str(self.path),
                ) from rollback_error
            if isinstance(exc, InstallerError):
                raise
            raise InstallerError(
                "cannot update global Codex config: {}".format(exc),
                host="codex",
                stage=self.stage,
                operation="write-config",
                path=str(self.path),
            ) from exc
        print("  [ok] global Codex config -> {}".format(self.path))
        return True

    def verify(self, plan: ConfigPlan) -> None:
        if self.dry_run:
            return
        current, existed, _ = self._read()
        if not existed:
            raise StateError(
                "Codex config.toml is missing after component installation",
                host="codex",
                stage=self.stage,
                operation="verify",
                path=str(self.path),
            )
        expected = current_values(
            plan.proposed.decode("utf-8"),
            managed_keys=plan.managed_keys,
            stage=plan.stage,
        )
        actual = current_values(
            current.decode("utf-8"),
            managed_keys=plan.managed_keys,
            stage=plan.stage,
        )
        mismatched = [
            key for key, value in expected.items() if actual.get(key) != value
        ]
        mismatched.extend(key for key in plan.removed if key in actual)
        if mismatched:
            raise StateError(
                "managed Codex config changed during component installation: {}".format(
                    ".".join(mismatched[0])
                ),
                host="codex",
                stage=self.stage,
                operation="verify",
                path=str(self.path),
            )
        self._doctor()


class CodexSubagentModel:
    """Inspect model pins and explicitly remove only global child overrides."""

    def __init__(self, codex_home: Path, *, dry_run: bool = False) -> None:
        self.codex_home = codex_home.expanduser()
        self.dry_run = dry_run
        self.config = CodexConfigEditor(
            self.codex_home, dry_run=dry_run,
            managed_keys=SUBAGENT_MODEL_KEYS, stage="agents-model",
        )

    def inspect(self) -> dict:
        parent_keys = (("model",), ("model_reasoning_effort",))
        original, _, _ = self.config._read()
        settings = current_values(
            original.decode("utf-8"),
            managed_keys=(*parent_keys, *SUBAGENT_MODEL_KEYS),
            stage="agents-model",
        )
        roles = {}
        directory = self.codex_home / "agents"
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise StateError("agent directory must be a regular directory", stage="agents-model")
        for path in sorted(directory.glob("*.toml")):
            if path.is_symlink() or not path.is_file():
                raise StateError("agent config must be a regular file",
                                 stage="agents-model", path=str(path))
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise StateError("agent config must be UTF-8", stage="agents-model",
                                 path=str(path)) from exc
            pins = current_values(text,
                                  managed_keys=parent_keys, stage="agents-model")
            roles[path.stem] = {".".join(key): value for key, value in pins.items()}
        return {
            "parent": {".".join(key): settings.get(key) for key in parent_keys},
            "global_child_overrides": {
                ".".join(key): settings.get(key) for key in SUBAGENT_MODEL_KEYS
            },
            "role_file_pins": roles,
            "runtime": "Not observed. Invocation overrides, profiles, and role pins may affect selection; verify child execution records.",
        }

    def plan_inherit(self) -> ConfigPlan:
        return self.config.plan({}, remove=SUBAGENT_MODEL_KEYS)

    def apply(self, plan: ConfigPlan) -> bool:
        if self.dry_run:
            print("Codex child model dry run complete. No files were modified.")
            return False
        if not plan.changed and not any(
            (self.codex_home / ".hukuhaka-transactions").glob("*/journal.json")
        ):
            if self.plan_inherit() != plan:
                raise StateError("Codex config changed after the diff was prepared; review it again",
                                 stage="agents-model", operation="verify-precondition")
            print("Codex child model: no global overrides to remove.")
            return False
        with installer_state(self.codex_home, dry_run=False) as writable:
            if self.plan_inherit() != plan:
                raise StateError(
                    "Codex config changed after the diff was prepared; review it again",
                    stage="agents-model", operation="verify-precondition",
                )
            if not plan.changed:
                print("Codex child model: no global overrides to remove.")
                return False
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                if plan.existed:
                    transaction.write_bytes(self.config.backup, plan.original, plan.mode)
                transaction.write_bytes(self.config.path, plan.proposed, plan.mode)
                self.config.verify(plan)
                transaction.commit()
        print("  [ok] removed only global child model and effort overrides")
        return True


@dataclass(frozen=True)
class AgentPolicyPlan:
    action: str
    settings: Dict[Key, str]
    config: ConfigPlan
    manifest_path: Path
    manifest_original: bytes
    manifest_proposed: Optional[bytes]
    manifest_existed: bool
    manifest_mode: int

    @property
    def changed(self) -> bool:
        expected_manifest = (
            b"" if self.manifest_proposed is None else self.manifest_proposed
        )
        return self.config.changed or self.manifest_original != expected_manifest

    def diff(self) -> str:
        return self.config.diff()


@dataclass(frozen=True)
class AgentPolicyState:
    """Observed agent execution limits and their ownership state."""

    kind: str
    settings: Mapping[Key, str]

    @property
    def label(self) -> str:
        return {
            "default": "Codex defaults",
            "legacy": "legacy Evidence Scout limit",
            "managed": "custom (Hukuhaka managed)",
            "unmanaged": "custom (not managed by Hukuhaka)",
            "drifted": "drifted (Hukuhaka managed)",
        }[self.kind]

    @property
    def actionable(self) -> bool:
        return self.kind in ("default", "legacy", "managed")

    def display(self, key: Key) -> str:
        value = self.settings.get(key)
        if value is not None:
            if self.kind in ("managed", "drifted"):
                source = "Hukuhaka managed override"
            elif self.kind == "legacy":
                source = "legacy Evidence Scout override"
            else:
                source = "user override"
            return "{} ({})".format(value, source)
        if key == ("agents", "max_depth"):
            return "Codex V1 default (not exposed)"
        return "Codex default (no override)"

    def integer(self, key: Key, *, fallback: int) -> int:
        value = self.settings.get(key, "")
        return int(value) if value.isdigit() and int(value) > 0 else fallback


class CodexAgentPolicy:
    """Own explicit agent capacity settings without coupling them to install."""

    def __init__(self, codex_home: Path, *, dry_run: bool = False) -> None:
        self.codex_home = codex_home.expanduser()
        self.config = CodexConfigEditor(
            self.codex_home,
            dry_run=dry_run,
            managed_keys=AGENT_POLICY_KEYS,
            stage="agents",
        )
        self.manifest_path = self.codex_home / AGENT_POLICY_MANIFEST
        self.dry_run = dry_run

    def _legacy_scout_limit_owned(self, actual: Mapping[Key, str]) -> bool:
        """Recognize the exact capacity override written by older scout installs."""
        if actual != {
            ("agents", "max_concurrent_threads_per_session"): "4"
        }:
            return False
        manifest = self.codex_home / ".hukuhaka-evidence-scout-manifest.json"
        if manifest.is_symlink() or not manifest.is_file():
            return False
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        return (
            isinstance(payload, dict)
            and payload.get("component") == "evidence-scout"
            and payload.get("schemaVersion") in (2, 3, 4)
        )

    @staticmethod
    def _key_name(key: Key) -> str:
        return ".".join(key)

    def _read_manifest(self) -> Tuple[bytes, bool, int]:
        if not self.manifest_path.exists() and not self.manifest_path.is_symlink():
            return b"", False, 0o600
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            raise StateError(
                "Codex agent policy manifest must be a regular file",
                host="codex",
                stage="agents",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        return (
            self.manifest_path.read_bytes(),
            True,
            stat.S_IMODE(self.manifest_path.stat().st_mode),
        )

    @staticmethod
    def _positive_integer(value: str, *, label: str) -> int:
        if not value.isdigit() or int(value) <= 0:
            raise StateError(
                "{} must be a positive integer".format(label),
                host="codex",
                stage="agents",
                operation="validate-policy",
            )
        return int(value)

    @classmethod
    def _validate_settings(cls, settings: Mapping[Key, str]) -> None:
        if set(settings) != set(AGENT_POLICY_KEYS):
            raise StateError(
                "agent policy must set every agent execution override",
                host="codex",
                stage="agents",
                operation="validate-policy",
            )
        cls._positive_integer(
            settings[("agents", "max_concurrent_threads_per_session")],
            label="concurrent spawned threads",
        )
        cls._positive_integer(
            settings[("agents", "max_depth")],
            label="V1 nesting depth",
        )

    def _decode_manifest(self, raw: bytes) -> Dict[Key, str]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError(
                "Codex agent policy manifest must be valid UTF-8 JSON",
                host="codex",
                stage="agents",
                operation="read-manifest",
                path=str(self.manifest_path),
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schemaVersion") != 1
            or set(payload) != {"schemaVersion", "settings"}
            or not isinstance(payload.get("settings"), dict)
        ):
            raise StateError(
                "Codex agent policy manifest has an unsupported shape",
                host="codex",
                stage="agents",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        raw_settings = payload["settings"]
        expected_names = {self._key_name(key) for key in AGENT_POLICY_KEYS}
        if set(raw_settings) != expected_names or not all(
            isinstance(value, str) for value in raw_settings.values()
        ):
            raise StateError(
                "Codex agent policy manifest has invalid settings",
                host="codex",
                stage="agents",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        settings = {
            key: raw_settings[self._key_name(key)] for key in AGENT_POLICY_KEYS
        }
        self._validate_settings(settings)
        return settings

    def _manifest_bytes(self, settings: Mapping[Key, str]) -> bytes:
        payload = {
            "schemaVersion": 1,
            "settings": {
                self._key_name(key): settings[key] for key in AGENT_POLICY_KEYS
            },
        }
        return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _build_plan(
        self, action: str, settings: Optional[Mapping[Key, str]] = None
    ) -> AgentPolicyPlan:
        manifest_original, manifest_existed, manifest_mode = self._read_manifest()
        manifest_settings = (
            self._decode_manifest(manifest_original) if manifest_existed else None
        )
        if action == "set":
            assert settings is not None
            next_settings = dict(settings)
            self._validate_settings(next_settings)
            config_plan = self.config.plan(next_settings)
            manifest_proposed = self._manifest_bytes(next_settings)
        elif action == "reset":
            next_settings = {}  # type: Dict[Key, str]
            config_plan = self.config.plan(
                {}, remove=AGENT_POLICY_KEYS if manifest_existed else ()
            )
            manifest_proposed = None
        else:
            raise StateError(
                "unsupported Codex agent policy action: {}".format(action),
                host="codex",
                stage="agents",
                operation="plan-policy",
            )

        actual = current_values(
            config_plan.original.decode("utf-8"),
            managed_keys=AGENT_POLICY_KEYS,
            stage="agents",
        )
        legacy_scout_limit = (
            manifest_settings is None and self._legacy_scout_limit_owned(actual)
        )
        if action == "reset" and legacy_scout_limit:
            config_plan = self.config.plan(
                {},
                remove=(("agents", "max_concurrent_threads_per_session"),),
            )
        if manifest_settings is None:
            if actual and not legacy_scout_limit:
                raise StateError(
                    "agent execution overrides already exist and are not owned by Hukuhaka; preserving them",
                    host="codex",
                    stage="agents",
                    operation="validate-ownership",
                    path=str(self.config.path),
                )
        elif actual != manifest_settings:
            raise StateError(
                "Hukuhaka agent policy drifted; review the agent execution overrides before changing them",
                host="codex",
                stage="agents",
                operation="validate-ownership",
                path=str(self.config.path),
            )

        return AgentPolicyPlan(
            action,
            next_settings,
            config_plan,
            self.manifest_path,
            manifest_original,
            manifest_proposed,
            manifest_existed,
            manifest_mode,
        )

    def plan_set(self, *, max_concurrent: int, max_depth: int) -> AgentPolicyPlan:
        return self._build_plan(
            "set",
            {
                ("agents", "max_concurrent_threads_per_session"): str(
                    max_concurrent
                ),
                ("agents", "max_depth"): str(max_depth),
            },
        )

    def plan_reset(self) -> AgentPolicyPlan:
        return self._build_plan("reset")

    def replan(self, plan: AgentPolicyPlan) -> AgentPolicyPlan:
        return self._build_plan(plan.action, plan.settings or None)

    def state(self) -> AgentPolicyState:
        manifest, exists, _ = self._read_manifest()
        original, _, _ = self.config._read()
        actual = current_values(
            original.decode("utf-8"),
            managed_keys=AGENT_POLICY_KEYS,
            stage="agents",
        )
        if not exists:
            if not actual:
                kind = "default"
            elif self._legacy_scout_limit_owned(actual):
                kind = "legacy"
            else:
                kind = "unmanaged"
            return AgentPolicyState(kind, actual)
        expected = self._decode_manifest(manifest)
        return AgentPolicyState(
            "managed" if actual == expected else "drifted",
            actual,
        )

    def status(self) -> str:
        return self.state().label

    def apply(self, plan: AgentPolicyPlan) -> bool:
        if self.dry_run:
            print("Codex agent policy dry run complete. No files were modified.")
            return False
        with installer_state(self.codex_home, dry_run=False) as writable:
            replanned = self._build_plan(plan.action, plan.settings or None)
            if replanned != plan:
                raise StateError(
                    "Codex agent policy changed after the diff was prepared; review it again",
                    host="codex",
                    stage="agents",
                    operation="verify-precondition",
                    path=str(self.config.path),
                )
            if not plan.changed:
                print(
                    "Codex agent policy already uses Codex defaults."
                    if plan.action == "reset"
                    else "Codex agent policy already matches the selected values."
                )
                return False
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                if plan.config.changed:
                    if plan.config.existed:
                        transaction.write_bytes(
                            self.config.backup,
                            plan.config.original,
                            plan.config.mode,
                        )
                    transaction.write_bytes(
                        self.config.path,
                        plan.config.proposed,
                        plan.config.mode,
                    )
                if plan.manifest_proposed is None:
                    transaction.remove(plan.manifest_path)
                else:
                    transaction.write_bytes(
                        plan.manifest_path,
                        plan.manifest_proposed,
                        plan.manifest_mode,
                    )
                self.config._doctor()
                transaction.commit()
        print("  [ok] Codex agent policy -> {}".format(self.config.path))
        return True

    def verify(self, plan: AgentPolicyPlan) -> None:
        if self.dry_run:
            return
        verified = self.replan(plan)
        if verified.changed:
            raise StateError(
                "managed Codex agent policy changed during component installation",
                host="codex",
                stage="agents",
                operation="verify",
                path=str(self.config.path),
            )
        self.config._doctor()


@dataclass(frozen=True)
class ContextPolicyPlan:
    action: str
    settings: Dict[Key, str]
    config: ConfigPlan
    manifest_path: Path
    manifest_original: bytes
    manifest_proposed: Optional[bytes]
    manifest_existed: bool
    manifest_mode: int

    @property
    def changed(self) -> bool:
        expected_manifest = (
            b"" if self.manifest_proposed is None else self.manifest_proposed
        )
        return self.config.changed or self.manifest_original != expected_manifest

    def diff(self) -> str:
        return self.config.diff()


@dataclass(frozen=True)
class ContextPolicyState:
    """Observed context overrides and whether Hukuhaka may change them."""

    kind: str
    settings: Mapping[Key, str]
    model: Optional[str] = None
    documented_context_capacity: Optional[int] = None

    @property
    def label(self) -> str:
        return {
            "default": "Codex/model defaults",
            "managed": "custom (Hukuhaka managed)",
            "unmanaged": "custom (not managed by Hukuhaka)",
            "drifted": "drifted (Hukuhaka managed)",
        }[self.kind]

    @property
    def source(self) -> str:
        return {
            "default": "Codex/model override",
            "managed": "Hukuhaka managed override",
            "unmanaged": "user override",
            "drifted": "drifted override",
        }[self.kind]

    @property
    def actionable(self) -> bool:
        return self.kind in ("default", "managed")


class CodexContextPolicy:
    """Own one explicit context policy without touching general defaults."""

    def __init__(self, codex_home: Path, *, dry_run: bool = False) -> None:
        self.codex_home = codex_home.expanduser()
        self.config = CodexConfigEditor(
            self.codex_home,
            dry_run=dry_run,
            managed_keys=CONTEXT_POLICY_KEYS,
            stage="context",
        )
        self.manifest_path = self.codex_home / CONTEXT_POLICY_MANIFEST
        self.dry_run = dry_run

    @staticmethod
    def _key_name(key: Key) -> str:
        return ".".join(key)

    def _read_manifest(self) -> Tuple[bytes, bool, int]:
        if not self.manifest_path.exists() and not self.manifest_path.is_symlink():
            return b"", False, 0o600
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            raise StateError(
                "Codex context policy manifest must be a regular file",
                host="codex",
                stage="context",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        return (
            self.manifest_path.read_bytes(),
            True,
            stat.S_IMODE(self.manifest_path.stat().st_mode),
        )

    def _decode_manifest(self, raw: bytes) -> Dict[Key, str]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError(
                "Codex context policy manifest must be valid UTF-8 JSON",
                host="codex",
                stage="context",
                operation="read-manifest",
                path=str(self.manifest_path),
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schemaVersion") != 1
            or set(payload) != {"schemaVersion", "settings"}
            or not isinstance(payload.get("settings"), dict)
        ):
            raise StateError(
                "Codex context policy manifest has an unsupported shape",
                host="codex",
                stage="context",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        raw_settings = payload["settings"]
        expected_names = {self._key_name(key) for key in CONTEXT_POLICY_KEYS}
        if set(raw_settings) != expected_names or not all(
            isinstance(value, str) for value in raw_settings.values()
        ):
            raise StateError(
                "Codex context policy manifest has invalid settings",
                host="codex",
                stage="context",
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        settings = {
            key: raw_settings[self._key_name(key)] for key in CONTEXT_POLICY_KEYS
        }
        self._validate_settings(settings)
        return settings

    @staticmethod
    def _positive_integer(value: str, *, label: str) -> int:
        if not value.isdigit() or int(value) <= 0:
            raise StateError(
                "{} must be a positive integer".format(label),
                host="codex",
                stage="context",
                operation="validate-policy",
            )
        return int(value)

    @classmethod
    def _validate_settings(cls, settings: Mapping[Key, str]) -> None:
        if set(settings) != set(CONTEXT_POLICY_KEYS):
            raise StateError(
                "context policy must set every context override",
                host="codex",
                stage="context",
                operation="validate-policy",
            )
        window = cls._positive_integer(
            settings[("model_context_window",)], label="context window"
        )
        compact = cls._positive_integer(
            settings[("model_auto_compact_token_limit",)],
            label="auto-compaction threshold",
        )
        if compact >= window:
            raise StateError(
                "auto-compaction threshold must be lower than the context window",
                host="codex",
                stage="context",
                operation="validate-policy",
            )
        try:
            scope = json.loads(
                settings[("model_auto_compact_token_limit_scope",)]
            )
        except json.JSONDecodeError as exc:
            raise StateError(
                "context policy scope must be a quoted TOML string",
                host="codex",
                stage="context",
                operation="validate-policy",
            ) from exc
        if scope not in CONTEXT_POLICY_SCOPES:
            raise StateError(
                "context policy scope must be one of: {}".format(
                    ", ".join(CONTEXT_POLICY_SCOPES)
                ),
                host="codex",
                stage="context",
                operation="validate-policy",
            )

    def _manifest_bytes(self, settings: Mapping[Key, str]) -> bytes:
        payload = {
            "schemaVersion": 1,
            "settings": {
                self._key_name(key): settings[key] for key in CONTEXT_POLICY_KEYS
            },
        }
        return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _build_plan(
        self, action: str, settings: Optional[Mapping[Key, str]] = None
    ) -> ContextPolicyPlan:
        manifest_original, manifest_existed, manifest_mode = self._read_manifest()
        manifest_settings = (
            self._decode_manifest(manifest_original) if manifest_existed else None
        )
        if action == "set":
            assert settings is not None
            next_settings = dict(settings)
            self._validate_settings(next_settings)
            config_plan = self.config.plan(next_settings)
            manifest_proposed = self._manifest_bytes(next_settings)
        elif action == "reset":
            next_settings = {}  # type: Dict[Key, str]
            config_plan = self.config.plan(
                {}, remove=CONTEXT_POLICY_KEYS if manifest_existed else ()
            )
            manifest_proposed = None
        else:
            raise StateError(
                "unsupported Codex context policy action: {}".format(action),
                host="codex",
                stage="context",
                operation="plan-policy",
            )

        actual = current_values(
            config_plan.original.decode("utf-8"),
            managed_keys=CONTEXT_POLICY_KEYS,
            stage="context",
        )
        if manifest_settings is None:
            if actual:
                raise StateError(
                    "context overrides already exist and are not owned by Hukuhaka; preserving them",
                    host="codex",
                    stage="context",
                    operation="validate-ownership",
                    path=str(self.config.path),
                )
        elif actual != manifest_settings:
            raise StateError(
                "Hukuhaka context policy drifted; review the context overrides before changing them",
                host="codex",
                stage="context",
                operation="validate-ownership",
                path=str(self.config.path),
            )

        return ContextPolicyPlan(
            action,
            next_settings,
            config_plan,
            self.manifest_path,
            manifest_original,
            manifest_proposed,
            manifest_existed,
            manifest_mode,
        )

    def plan_set(
        self, *, context_window: int, compact_at: int, scope: str
    ) -> ContextPolicyPlan:
        return self._build_plan(
            "set",
            {
                ("model_context_window",): str(context_window),
                ("model_auto_compact_token_limit",): str(compact_at),
                ("model_auto_compact_token_limit_scope",): json.dumps(scope),
            },
        )

    def plan_reset(self) -> ContextPolicyPlan:
        return self._build_plan("reset")

    def replan(self, plan: ContextPolicyPlan) -> ContextPolicyPlan:
        """Refresh a displayed policy plan without widening its ownership."""
        return self._build_plan(plan.action, plan.settings or None)

    def state(self) -> ContextPolicyState:
        manifest, exists, _ = self._read_manifest()
        original, _, _ = self.config._read()
        observed = current_values(
            original.decode("utf-8"),
            managed_keys=CONTEXT_POLICY_KEYS + (MODEL_KEY,),
            stage="context",
        )
        actual = {
            key: value
            for key, value in observed.items()
            if key in CONTEXT_POLICY_KEYS
        }
        model = _decode_string(observed.get(MODEL_KEY, ""), "") or None
        documented_context_capacity = (
            DOCUMENTED_MODEL_CONTEXT_CAPACITIES.get(model.lower())
            if model is not None
            else None
        )
        if not exists:
            return ContextPolicyState(
                "default" if not actual else "unmanaged",
                actual,
                model,
                documented_context_capacity,
            )
        expected = self._decode_manifest(manifest)
        return ContextPolicyState(
            "managed" if actual == expected else "drifted",
            actual,
            model,
            documented_context_capacity,
        )

    def status(self) -> str:
        """Compatibility label for compact callers such as the installer menu."""
        return self.state().label

    def apply(self, plan: ContextPolicyPlan) -> bool:
        if self.dry_run:
            print("Codex context dry run complete. No files were modified.")
            return False
        with installer_state(self.codex_home, dry_run=False) as writable:
            replanned = self._build_plan(plan.action, plan.settings or None)
            if replanned != plan:
                raise StateError(
                    "Codex context policy changed after the diff was prepared; review it again",
                    host="codex",
                    stage="context",
                    operation="verify-precondition",
                    path=str(self.config.path),
                )
            if not plan.changed:
                print(
                    "Codex context policy already uses Codex defaults."
                    if plan.action == "reset"
                    else "Codex context policy already matches the selected values."
                )
                return False
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                if plan.config.changed:
                    if plan.config.existed:
                        transaction.write_bytes(
                            self.config.backup,
                            plan.config.original,
                            plan.config.mode,
                        )
                    transaction.write_bytes(
                        self.config.path,
                        plan.config.proposed,
                        plan.config.mode,
                    )
                if plan.manifest_proposed is None:
                    transaction.remove(plan.manifest_path)
                else:
                    transaction.write_bytes(
                        plan.manifest_path,
                        plan.manifest_proposed,
                        plan.manifest_mode,
                    )
                self.config._doctor()
                transaction.commit()
        print("  [ok] Codex context policy -> {}".format(self.config.path))
        return True

    def verify(self, plan: ContextPolicyPlan) -> None:
        """Ensure component installation did not change the selected policy."""
        if self.dry_run:
            return
        verified = self.replan(plan)
        if verified.changed:
            raise StateError(
                "managed Codex context policy changed during component installation",
                host="codex",
                stage="context",
                operation="verify",
                path=str(self.config.path),
            )
        self.config._doctor()
