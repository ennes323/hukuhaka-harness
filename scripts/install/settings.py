"""Catalog-driven settings, partial profiles and conflict-aware change receipts."""
from __future__ import annotations

import json
import ast
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from .codex_config import CodexConfigEditor, ConfigPlan, _parse_assignments, _table_boundaries, current_values
from .common import FileTransaction, StateError, installer_state
from .settings_catalog import CATALOG, KEYS, OPTIONS, RECOMMENDED


def error(message: str) -> StateError:
    return StateError(message, host="codex", stage="settings")


def decode(value: str):
    """The profile surface accepts JSON-style TOML values and literal strings.

    Full config text remains opaque and is validated by the host. Unsupported
    profile syntax is rejected rather than guessed or silently discarded.
    """
    if value.startswith("'''") and value.endswith("'''"):
        return value[3:-3].removeprefix("\n")
    if value.startswith('"""') and value.endswith('"""'):
        try:
            return ast.literal_eval(value).removeprefix("\n")
        except (ValueError, SyntaxError) as exc:
            raise error("Invalid multiline profile string") from exc
    if value.startswith("'") and value.endswith("'") and "\n" not in value:
        return value[1:-1]
    try:
        return json.loads(value)
    except ValueError as exc:
        raise error("Use a JSON-style TOML scalar/array for this profile value") from exc


def validate_value(key: str, literal: str) -> str:
    option = CATALOG.get(key)
    if option is None:
        raise error("Unsupported setting: " + key)
    value = decode(literal)
    valid = {
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "boolean": type(value) is bool,
        "strings": isinstance(value, list) and all(isinstance(item, str) for item in value),
        "notifications": type(value) is bool or (isinstance(value, list) and all(isinstance(item, str) for item in value)),
    }[option.kind]
    if not valid:
        raise error("{} requires {}".format(key, option.kind))
    if option.choices and value not in option.choices:
        raise error("{} accepts {} (host/model support also applies)".format(key, ", ".join(option.choices)))
    if option.kind == "integer":
        if option.minimum is not None and value < option.minimum:
            raise error("{} must be >= {}".format(key, option.minimum))
        if option.maximum is not None and value > option.maximum:
            raise error("{} must be <= {}".format(key, option.maximum))
    return json.dumps(value, ensure_ascii=False)


def cli_literal(key: str, value: str) -> str:
    option = CATALOG.get(key)
    if option is None:
        raise error("Unsupported setting: " + key)
    if option.kind == "string" and not value.startswith(('"', "'")):
        value = json.dumps(value, ensure_ascii=False)
    return validate_value(key, value)


def validate_relations(values: Mapping, changed: Sequence) -> None:
    def integer(key):
        raw = values.get(tuple(key.split(".")))
        return int(raw) if raw is not None and re.fullmatch(r"[0-9]+", raw) else None
    changed_names = {".".join(key) for key in changed}
    if changed_names & {"model_context_window", "model_auto_compact_token_limit", "model_auto_compact_token_limit_scope"}:
        window = integer("model_context_window")
        compact = integer("model_auto_compact_token_limit")
        if window is not None and compact is not None and compact > window:
            raise error("Auto-compaction threshold must not exceed the explicit context window")
    prefix = "features.multi_agent_v2."
    waits = [prefix + name + "_wait_timeout_ms" for name in ("min", "default", "max")]
    if changed_names & set(waits):
        # Unspecified host defaults remain unknown; only compare explicit values.
        for left, right in ((0, 1), (1, 2), (0, 2)):
            a, b = integer(waits[left]), integer(waits[right])
            if a is not None and b is not None and a > b:
                raise error("Explicit wait settings must satisfy min <= default <= max")


def read_profile(path: Path) -> Dict:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise error("Cannot read profile: " + str(path)) from exc
    lines, assignments, sections = _parse_assignments(text)
    for section in sections:
        if not any(option.path[:len(section)] == section for option in OPTIONS):
            raise error("Unsupported profile table: " + ".".join(section))
    covered = set(sections.values())
    result = {}
    for item in assignments:
        covered.update(range(item.start, item.end))
        key = ".".join(item.path)
        if item.path in result:
            raise error("Duplicate profile setting: " + key)
        result[item.path] = validate_value(key, item.value)
    for i, line in enumerate(lines):
        if i not in covered and line.strip() and not line.lstrip().startswith("#"):
            raise error("Unsupported profile syntax at line {}".format(i + 1))
    if not result:
        raise error("Profile contains no supported settings")
    return result


def organize_config(text: str) -> str:
    """Reorder whole tables and root assignments without rewriting their values.

    Multiline values are identified by the existing config scanner. Unknown
    keys, tables and comments survive. Array tables are left unchanged because
    their order is meaningful.
    """
    lines, assignments, sections = _parse_assignments(text)
    if set(_table_boundaries(lines)) != set(sections.values()) or any(item.path[0] in ("<array-table>", "<unsupported-table>") for item in assignments):
        raise error("Organize does not reorder array or unsupported tables")
    starts = sorted(sections.values())
    first = starts[0] if starts else len(lines)
    root_items = [item for item in assignments if item.start < first]
    rank = {option.path: i for i, option in enumerate(OPTIONS)}
    root_chunks = []
    cursor = 0
    for item in root_items:
        root_chunks.append((rank.get(item.path, len(rank)), item.start, "".join(lines[cursor:item.end]).strip("\n") + "\n"))
        cursor = item.end
    root = "\n".join(chunk for _, _, chunk in sorted(root_chunks))
    root += "".join(lines[cursor:first])
    table_order = {name: i for i, name in enumerate(("features", "agents", "tui", "shell_environment_policy", "desktop", "projects", "marketplaces", "plugins", "mcp_servers", "hooks", "notice"))}
    blocks = []
    for path, start in sections.items():
        pos = starts.index(start)
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        blocks.append(((table_order.get(path[0], len(table_order)), path), "".join(lines[start:end]).strip("\n")))
    proposed = root.rstrip("\n") + ("\n\n" if root.strip() and blocks else "")
    proposed += "\n\n".join(block for _, block in sorted(blocks))
    proposed = proposed.rstrip("\n") + "\n"
    before = sorted((item.path, item.value) for item in assignments)
    after = sorted((item.path, item.value) for item in _parse_assignments(proposed)[1])
    if before != after:
        raise error("Organize would change settings; no changes applied")
    return proposed


class Settings:
    def __init__(self, home: Path, *, dry_run: bool = False):
        self.editor = CodexConfigEditor(home, dry_run=dry_run, managed_keys=KEYS, stage="settings")
        self.home = self.editor.codex_home
        self.dry_run = dry_run
        self.history_root = self.home / ".hukuhaka-settings-history"

    def plan(self, settings: Optional[Mapping] = None, *, remove: Sequence = (), organize: bool = False) -> ConfigPlan:
        checked = {key: validate_value(".".join(key), value) for key, value in (settings or {}).items()}
        plan = self.editor.plan(checked, remove=remove)
        validate_relations(current_values(plan.proposed.decode(), managed_keys=KEYS), tuple(checked) + tuple(remove))
        if organize:
            plan = replace(plan, proposed=organize_config(plan.proposed.decode()).encode())
        return plan

    def records(self):
        if self.history_root.is_symlink():
            raise error("Settings history must not be a symlink")
        if not self.history_root.exists():
            return []
        records = []
        for path in sorted(self.history_root.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise error("Settings receipt must be a regular file")
            try:
                data = json.loads(path.read_text())
                if data.get("schemaVersion") != 1 or not isinstance(data.get("before"), dict) or not isinstance(data.get("after"), dict):
                    raise ValueError()
                if set(data["before"]) != set(data["after"]) or any(key not in CATALOG for key in data["after"]):
                    raise ValueError()
                if any(value is not None and not isinstance(value, str) for side in ("before", "after") for value in data[side].values()):
                    raise ValueError()
            except (ValueError, AttributeError, OSError) as exc:
                raise error("Invalid settings receipt: " + path.name) from exc
            records.append((path.stem, data))
        return records

    def show(self, *, as_json: bool = False) -> None:
        values = self.editor.inspect()
        origins = {}
        for identifier, record in self.records():
            for key, value in record["after"].items():
                origins[key] = (identifier, value)
        rows = []
        for option in OPTIONS:
            value = values.get(option.path)
            last = origins.get(option.key)
            origin = "not recorded" if not last else ("receipt " + last[0] if last[1] == value else "changed since " + last[0])
            rows.append(dict(key=option.key, group=option.group, value=value, recommended=option.recommended,
                             official_default=option.official_default, origin=origin, description=option.description,
                             choices=list(option.choices), minimum=option.minimum, maximum=option.maximum))
        if as_json:
            print(json.dumps({"source": str(self.editor.path), "runtime": "not observed", "options": rows}, indent=2, ensure_ascii=False))
            return
        print("Saved config: {} (session/runtime overrides not observed)".format(self.editor.path))
        group = None
        for row in rows:
            if row["group"] != group:
                group = row["group"]
                print("\n" + group)
            value = row["value"] if row["value"] is not None else "[unset]"
            if row["key"] == "compact_prompt" and row["value"] is not None:
                value = "[custom text; use show --json to inspect]"
            print("  {} = {}".format(row["key"], value))
            print("    {} Recommended: {}; origin: {}.".format(row["description"], row["recommended"] or "preserve / unset", row["origin"]))
        print("\nV2 enabled takes precedence over agents.enabled. Role-file pins are separate.")

    def export(self, path: Path) -> None:
        values = self.editor.inspect()
        lines = ["# Partial Hukuhaka settings profile; omitted keys are preserved.\n"]
        for option in OPTIONS:
            if option.path in values:
                # Keep complex native TOML (such as custom multiline prompts)
                # out of an export if it cannot be losslessly decoded here.
                try:
                    literal = validate_value(option.key, values[option.path])
                except StateError:
                    raise error("Cannot export {} with this TOML spelling; existing config is unchanged".format(option.key))
                lines.append("{} = {}\n".format(option.key, literal))
        if self.dry_run:
            print("Would export supported settings to " + str(path))
            return
        # Never replace a pre-existing profile.
        try:
            with path.open("x", encoding="utf-8") as stream:
                path.chmod(0o600)
                stream.write("".join(lines))
        except OSError as exc:
            raise error("Cannot create profile (existing files are preserved): " + str(path)) from exc

    def restore_plan(self, identifier: str) -> ConfigPlan:
        records = dict(self.records())
        if identifier not in records:
            raise error("Unknown settings receipt: " + identifier)
        record = records[identifier]
        if not record["after"]:
            raise error("Formatting-only receipts have a full backup, but no setting values to restore")
        current = self.editor.inspect()
        settings, remove = {}, []
        for key, expected in record["after"].items():
            path = tuple(key.split("."))
            if current.get(path) != expected:
                raise error("Restore conflict: {} changed after this receipt".format(key))
            old = record["before"][key]
            if old is None:
                remove.append(path)
            else:
                # Receipts preserve original TOML spellings, including multiline strings.
                validate_value(key, old)
                settings[path] = old
        plan = self.editor.plan(settings, remove=remove)
        validate_relations(current_values(plan.proposed.decode(), managed_keys=KEYS), tuple(settings) + tuple(remove))
        return plan

    def apply(self, plan: ConfigPlan, *, label: str = "settings") -> Optional[str]:
        before = current_values(plan.original.decode(), managed_keys=KEYS)
        after = current_values(plan.proposed.decode(), managed_keys=KEYS)
        changed = [key for key in KEYS if before.get(key) != after.get(key)]
        for key in changed:
            if key in after:
                validate_value(".".join(key), after[key])
        validate_relations(after, changed)
        if not plan.changed:
            print("Settings already match; no files changed.")
            return None
        if self.dry_run:
            print("Dry run complete; no files or locks created.")
            return None
        self.records()  # Refuse malformed history before mutation.
        with installer_state(self.home, dry_run=False):
            current, existed, _ = self.editor._read()
            if current != plan.original or existed != plan.existed:
                raise error("Config changed after preview; review it again")
            identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
            receipt = {"schemaVersion": 1, "label": label,
                       "before": {".".join(key): before.get(key) for key in changed},
                       "after": {".".join(key): after.get(key) for key in changed}}
            with FileTransaction(self.home) as transaction:
                if existed:
                    transaction.write_bytes(self.history_root / (identifier + ".toml"), current, 0o600)
                transaction.write_bytes(self.editor.path, plan.proposed, plan.mode)
                self.editor._doctor()
                transaction.write_bytes(self.history_root / (identifier + ".json"), (json.dumps(receipt, indent=2) + "\n").encode(), 0o600)
                transaction.commit()
            print("Settings applied. Receipt: " + identifier)
            return identifier


def wizard(settings: Settings) -> Optional[ConfigPlan]:
    settings.show()
    print("\nEnter a setting key, 'recommended', 'profile PATH', 'unset KEY', or blank to exit.")
    command = input("Settings> ").strip()
    if not command:
        return None
    if command == "recommended":
        return settings.plan(RECOMMENDED)
    if command.startswith("profile "):
        return settings.plan(read_profile(Path(command[8:]).expanduser()))
    if command.startswith("unset "):
        return settings.plan(remove=(tuple(command[6:].split(".")),))
    option = CATALOG.get(command)
    if option is None:
        raise error("Unknown setting: " + command)
    print(option.description)
    if option.choices:
        print("Choices: " + ", ".join(option.choices))
    return settings.plan({option.path: cli_literal(command, input("Value> "))})
