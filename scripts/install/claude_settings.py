"""Explicit Claude user preferences; independent of component installation.

Only the catalog below is editable. Unknown JSON remains in settings.json but
never appears in previews, profiles, or receipts. Validation establishes JSON
syntax and selected value types, not that a Claude session loaded the settings.
"""
from __future__ import annotations

import json
import re
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .common import FileTransaction, StateError, ensure_within, installer_state

SOURCE = "https://code.claude.com/docs/en/settings-reference"


@dataclass(frozen=True)
class Option:
    key: str
    kind: str
    description: str
    official_default: Any = None
    choices: Tuple[str, ...] = ()
    caveat: str = ""

    @property
    def source(self) -> str:
        return SOURCE + "#" + self.key.lower()


# Checked against the official reference on 2026-10-01. No automatic preset.
OPTIONS = (
    Option("model", "string", "Model alias or full model ID for new sessions.",
           caveat="Account, provider and organization availability is not checked."),
    Option("effortLevel", "string", "Default effort for models without a saved level.",
           choices=("low", "medium", "high", "xhigh"),
           caveat="Legacy user-level setting: Opus 5.5 and later models ignore it; per-model settings and session overrides also apply."),
    Option("language", "string", "Language name for responses and session titles.",
           caveat="Language names are not a fixed enumeration; dictation support differs."),
    Option("autoMemoryEnabled", "boolean", "Read and write Claude auto memory.", True,
           caveat="Session flags and environment overrides may change the effective behavior."),
)
CATALOG = {option.key: option for option in OPTIONS}
_IDENTIFIER = re.compile(r"[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}\Z")


def error(message: str) -> StateError:
    return StateError(message, host="claude", stage="settings")


def validate_value(key: str, value: Any) -> Any:
    option = CATALOG.get(key)
    if option is None:
        raise error("Unsupported Claude setting")
    valid = isinstance(value, str) if option.kind == "string" else type(value) is bool
    if not valid:
        raise error("{} requires {}".format(key, option.kind))
    if option.choices and value not in option.choices:
        raise error("{} accepts {}".format(key, ", ".join(option.choices)))
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise error("Invalid Unicode in selected setting") from exc
    return value


def cli_value(key: str, value: str) -> Any:
    if key not in CATALOG:
        raise error("Unsupported Claude setting")
    if CATALOG[key].kind == "string" and not value.startswith('"'):
        return validate_value(key, value)
    try:
        parsed = json.loads(value)
    except ValueError as exc:
        raise error("Selected setting must use a valid JSON value") from exc
    return validate_value(key, parsed)


def _decode(raw: bytes, label: str) -> Dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-finite JSON number")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=invalid_constant)
        if not isinstance(result, dict):
            raise ValueError("not an object")
        # Avoid loss of invalid Unicode and number overflow during serialization.
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise error(label + " must be a strict UTF-8 JSON object") from exc


def _encode(data: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(data), indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def read_profile(path: Path) -> Dict[str, Any]:
    try:
        values = _decode(Path(path).read_bytes(), "Claude profile")
    except OSError as exc:
        raise error("Cannot read Claude settings profile") from exc
    if not values:
        raise error("Profile contains no selected settings")
    return {key: validate_value(key, value) for key, value in values.items()}


@dataclass(frozen=True)
class ClaudeSettingsPlan:
    path: Path
    original: bytes
    proposed: bytes
    existed: bool
    mode: int
    before: Mapping[str, Any]
    after: Mapping[str, Any]

    @property
    def changed(self) -> bool:
        return bool(self.before)

    def diff(self) -> str:
        if not self.changed:
            return "Selected Claude settings already match.\n"
        lines = ["Saved user settings: {} (runtime not observed)".format(self.path)]
        for key in self.before:
            for prefix, values in (("-", self.before), ("+", self.after)):
                value = "[unset]" if values[key] is None else json.dumps(values[key], ensure_ascii=True)
                lines.append("{} {} = {}".format(prefix, key, value))
        return "\n".join(lines) + "\n"


class ClaudeSettings:
    def __init__(self, home: Path, *, dry_run: bool = False):
        self.home = Path(home).expanduser().absolute()
        self.path = self.home / "settings.json"
        self.history_root = self.home / ".hukuhaka-claude-settings-history"
        self.dry_run = dry_run

    def _check(self, path: Path, *, directory: bool = False) -> None:
        target = ensure_within(self.home, path, operation="claude-settings")
        for current in (target, *target.parents):
            if current.is_symlink():
                raise error("Claude settings paths must not be symlinks")
            if current == self.home:
                if current.exists() and not current.is_dir():
                    raise error("Claude config home must be a directory")
                break
            if current != target and current.exists() and not current.is_dir():
                raise error("Claude settings parent must be a directory")
        if target.exists() and not (target.is_dir() if directory else target.is_file()):
            raise error("Claude settings path has the wrong file type")

    def _read(self):
        self._check(self.path)
        if not self.path.exists():
            return {}, b"", False, 0o600
        try:
            raw = self.path.read_bytes()
            mode = stat.S_IMODE(self.path.stat().st_mode)
        except OSError as exc:
            raise error("Cannot read Claude user settings") from exc
        return _decode(raw, "Claude settings"), raw, True, mode

    def plan(self, settings: Optional[Mapping[str, Any]] = None, *, remove: Sequence[str] = ()) -> ClaudeSettingsPlan:
        selected = {key: validate_value(key, value) for key, value in (settings or {}).items()}
        removals = tuple(remove)
        if any(key not in CATALOG for key in removals):
            raise error("Unsupported Claude setting")
        if set(selected) & set(removals):
            raise error("A setting cannot be selected and unset together")
        values, original, existed, mode = self._read()
        proposed = dict(values)
        proposed.update(selected)
        for key in removals:
            proposed.pop(key, None)
        touched = set(selected) | set(removals)
        changed = [option.key for option in OPTIONS if option.key in touched
                   and ((option.key in values) != (option.key in proposed)
                        or values.get(option.key) != proposed.get(option.key))]
        # Receipts must contain only values that this bounded editor can restore.
        for key in changed:
            if key in values:
                validate_value(key, values[key])
        before = {key: values.get(key) for key in changed}
        after = {key: proposed.get(key) for key in changed}
        return ClaudeSettingsPlan(self.path, original, _encode(proposed) if changed else original,
                                  existed, mode, before, after)

    def records(self):
        self._check(self.history_root, directory=True)
        if not self.history_root.exists():
            return []
        records = []
        try:
            for path in sorted(self.history_root.iterdir()):
                self._check(path)
                if path.suffix != ".json" or _IDENTIFIER.fullmatch(path.stem) is None:
                    raise error("Invalid Claude settings receipt filename")
                data = _decode(path.read_bytes(), "Claude settings receipt")
                if (set(data) != {"schemaVersion", "label", "before", "after"}
                        or type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1
                        or not isinstance(data["label"], str) or data["label"] not in {"settings", "set", "unset", "profile", "restore"}
                        or not isinstance(data["before"], dict) or not isinstance(data["after"], dict)
                        or not data["before"] or set(data["before"]) != set(data["after"])):
                    raise error("Invalid Claude settings receipt shape")
                for key in data["before"]:
                    if key not in CATALOG or data["before"][key] == data["after"][key]:
                        raise error("Invalid Claude settings receipt values")
                    for side in ("before", "after"):
                        if data[side][key] is not None:
                            validate_value(key, data[side][key])
                records.append((path.stem, data))
        except OSError as exc:
            raise error("Cannot read Claude settings history") from exc
        return records

    def snapshot(self) -> dict:
        values, _, _, _ = self._read()
        origins = {}
        for identifier, record in self.records():
            for key, value in record["after"].items():
                origins[key] = (identifier, value)
        rows = []
        for option in OPTIONS:
            value = values.get(option.key)
            valid = True
            if option.key in values:
                try:
                    validate_value(option.key, value)
                except StateError:
                    value, valid = "[invalid saved value]", False
            last = origins.get(option.key)
            origin = "not recorded" if last is None else ("receipt " + last[0] if last[1] == values.get(option.key) else "changed since " + last[0])
            rows.append(dict(key=option.key, value=value, saved=option.key in values, valid=valid,
                             official_default=option.official_default, choices=list(option.choices),
                             description=option.description, caveat=option.caveat, source=option.source,
                             origin=origin))
        return dict(source=str(self.path), scope="saved user settings", runtime="not observed",
                    validation="JSON syntax and selected value types only", options=rows)

    def show(self, *, as_json: bool = False) -> None:
        data = self.snapshot()
        if as_json:
            print(json.dumps(data, indent=2, ensure_ascii=True))
            return
        print("Saved user settings: {} (runtime not observed)".format(self.path))
        for row in data["options"]:
            value = json.dumps(row["value"], ensure_ascii=True) if row["saved"] else "[unset]"
            print("  {} = {} ({})".format(row["key"], value, row["origin"]))
            print("    {} {}".format(row["description"], row["caveat"]))
        print("Validation checks JSON syntax and selected value types only; confirm loaded sources with Claude /status.")

    def restore_plan(self, identifier: str) -> ClaudeSettingsPlan:
        record = dict(self.records()).get(identifier)
        if record is None:
            raise error("Unknown Claude settings receipt")
        values, _, _, _ = self._read()
        for key, expected in record["after"].items():
            if (key in values) != (expected is not None) or values.get(key) != expected:
                raise error("Restore conflict: {} changed after this receipt".format(key))
        selected = {key: value for key, value in record["before"].items() if value is not None}
        remove = [key for key, value in record["before"].items() if value is None]
        return self.plan(selected, remove=remove)

    def apply(self, plan: ClaudeSettingsPlan, *, label: str = "settings") -> Optional[str]:
        if label not in {"settings", "set", "unset", "profile", "restore"}:
            raise error("Unsupported Claude settings operation label")
        selected = {key: value for key, value in plan.after.items() if value is not None}
        remove = [key for key, value in plan.after.items() if value is None]
        # Rebuild even supplied plans, so edits cannot widen the bounded surface.
        if self.plan(selected, remove=remove) != plan:
            raise error("Claude settings changed after preview; review it again")
        self.records()
        if not plan.changed:
            print("Claude settings already match; no files changed.")
            return None
        if self.dry_run:
            print("Claude settings dry run complete; no files or locks created.")
            return None
        self._check(self.home / ".hukuhaka-installer.lock")
        self._check(self.home / ".hukuhaka-transactions", directory=True)
        with installer_state(self.home, dry_run=False):
            if self.plan(selected, remove=remove) != plan:
                raise error("Claude settings changed after preview; review it again")
            self.records()
            identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
            receipt = dict(schemaVersion=1, label=label, before=dict(plan.before), after=dict(plan.after))
            with FileTransaction(self.home) as transaction:
                transaction.write_bytes(self.path, plan.proposed, plan.mode)
                _decode(self.path.read_bytes(), "Claude settings")
                transaction.write_bytes(self.history_root / (identifier + ".json"), _encode(receipt), 0o600)
                transaction.commit()
        print("Claude saved settings applied; runtime not observed. Receipt: " + identifier)
        return identifier

    def export(self, path: Path) -> None:
        values, _, _, _ = self._read()
        profile = {option.key: validate_value(option.key, values[option.key])
                   for option in OPTIONS if option.key in values}
        if not profile:
            raise error("No supported saved Claude settings to export")
        if self.dry_run:
            print("Would export selected Claude settings; no files created.")
            return
        try:
            with Path(path).open("xb") as stream:
                Path(path).chmod(0o600)
                stream.write(_encode(profile))
        except OSError as exc:
            raise error("Cannot create Claude profile; existing files are preserved") from exc


def wizard(settings: ClaudeSettings) -> Optional[ClaudeSettingsPlan]:
    settings.show()
    print("\nEnter a setting key, 'profile PATH', 'unset KEY', or blank to exit.")
    command = input("Claude settings> ").strip()
    if not command:
        return None
    if command.startswith("profile "):
        return settings.plan(read_profile(Path(command[8:]).expanduser()))
    if command.startswith("unset "):
        return settings.plan(remove=(command[6:],))
    option = CATALOG.get(command)
    if option is None:
        raise error("Unsupported Claude setting")
    print(option.description)
    if option.choices:
        print("Choices: " + ", ".join(option.choices))
    print(option.caveat)
    return settings.plan({command: cli_value(command, input("Value> "))})
