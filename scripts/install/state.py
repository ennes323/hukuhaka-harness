"""Installer receipts and operation history; never Codex runtime configuration.

The TOML codec intentionally accepts only the generated subset: quoted or bare
keys, tables, arrays of tables, and JSON-compatible scalar values/string arrays.
It is identical on Python 3.9 and newer and rejects unsupported syntax explicitly.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .common import FileTransaction, InstallerLock, StateError, ensure_within, installer_state, load_json


def _error(message: str) -> StateError:
    return StateError(message, host="codex", stage="installer-state")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is None:
        raise _error("invalid installer component name")


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _backups(record: dict) -> None:
    if "backups" not in record:
        return
    if not _strings(record["backups"]) or any(not value.startswith("hk-backups/") or ".." in Path(value).parts for value in record["backups"]):
        raise _error("invalid installer backup references")


def _validate(data: Any) -> dict:
    if not isinstance(data, dict) or set(data) != {"schema_version", "components", "operations"}:
        raise _error("invalid installer state fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise _error("unsupported installer state schema")
    if not isinstance(data["components"], dict) or not isinstance(data["operations"], list):
        raise _error("invalid installer state components or operations")
    for name, record in data["components"].items():
        _name(name)
        required = {"kind", "version", "installer_version", "installed_at", "provenance"}
        if not isinstance(record, dict) or not required <= set(record) or set(record) - required - {"receipt", "updated_at", "backups", "migrated_from_version"}:
            raise _error("invalid component record: " + name)
        if any(not isinstance(record[key], str) or not record[key] for key in required):
            raise _error("invalid component metadata: " + name)
        if record["provenance"] not in {"installed", "legacy"}:
            raise _error("invalid component provenance: " + name)
        if record["kind"] not in {"plugin", "agent", "template"}:
            raise _error("invalid component kind: " + name)
        _backups(record)
        if "migrated_from_version" in record and not isinstance(record["migrated_from_version"], str):
            raise _error("invalid migrated component version")
        if "updated_at" in record and not isinstance(record["updated_at"], str):
            raise _error("invalid component update time: " + name)
        if "receipt" in record and not isinstance(record["receipt"], dict):
            raise _error("invalid component receipt: " + name)
    ids = set()
    required = {"id", "action", "started_at", "installer_version", "requested", "completed", "stage", "status"}
    for record in data["operations"]:
        if not isinstance(record, dict) or not required <= set(record) or set(record) - required - {"finished_at", "error", "components_before", "components_after", "backups"}:
            raise _error("invalid operation record")
        for key in required - {"requested", "completed"}:
            if not isinstance(record[key], str) or not record[key]:
                raise _error("invalid operation metadata")
        if not _strings(record["requested"]) or not _strings(record["completed"]):
            raise _error("invalid operation component lists")
        if record["status"] not in {"running", "success", "failed", "partial", "interrupted"}:
            raise _error("invalid installer operation status")
        _backups(record)
        for key in ("components_before", "components_after"):
            if key in record:
                if not isinstance(record[key], dict) or any(not isinstance(value, str) for value in record[key].values()):
                    raise _error("invalid operation component versions")
                for name in record[key]:
                    _name(name)
        if record["id"] in ids:
            raise _error("duplicate operation id")
        ids.add(record["id"])
        if "finished_at" in record and not isinstance(record["finished_at"], str):
            raise _error("invalid operation finish time")
        if "error" in record and (not isinstance(record["error"], dict) or set(record["error"]) != {"stage", "type"}
                                  or any(not isinstance(value, str) for value in record["error"].values())):
            raise _error("operation errors may contain only stage and type")
    return data


def _key_path(text: str) -> list[str]:
    keys = []
    decoder = json.JSONDecoder()
    rest = text.strip()
    while rest:
        if rest.startswith('"'):
            key, end = decoder.raw_decode(rest)
        else:
            match = re.match(r"[A-Za-z0-9_-]+", rest)
            if not match:
                raise ValueError("unsupported key")
            key, end = match.group(), match.end()
        keys.append(key)
        rest = rest[end:].strip()
        if rest:
            if not rest.startswith(".") or not rest[1:].strip():
                raise ValueError("invalid key path")
            rest = rest[1:].strip()
    if not keys:
        raise ValueError("empty key path")
    return keys


def _scalar(value: Any) -> bool:
    return isinstance(value, str) or type(value) is bool or (type(value) is int and -(2 ** 63) <= value < 2 ** 63) or _strings(value)


def _validate_values(value: Any) -> None:
    """Reject unrepresentable nested receipts before any TOML is emitted."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _error("installer state keys must be strings")
            _validate_values(key)
            _validate_values(item)
    elif isinstance(value, list):
        if not _strings(value) and not all(isinstance(item, dict) for item in value):
            raise _error("unsupported installer state array")
        for item in value:
            _validate_values(item)
    elif not _scalar(value):
        raise _error("unsupported installer state value")
    elif isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise _error("invalid Unicode in installer state") from exc


def decode_state(raw: bytes) -> dict:
    """Decode and validate a state document without changing any files."""
    root: dict = {}
    current = root
    declared = set()
    assigned = set()
    try:
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                array = line.startswith("[[")
                ending = "]]" if array else "]"
                if not line.endswith(ending):
                    raise ValueError("invalid table")
                keys = _key_path(line[2 if array else 1:-len(ending)])
                current = root
                for key in keys[:-1]:
                    if (id(current), key) in assigned:
                        raise ValueError("table conflicts with assigned value")
                    child = current.setdefault(key, {})
                    if isinstance(child, list):
                        child = child[-1] if child else None
                    if not isinstance(child, dict):
                        raise ValueError("conflicting table")
                    current = child
                key = keys[-1]
                if (id(current), key) in assigned:
                    raise ValueError("table conflicts with assigned value")
                if array:
                    values = current.setdefault(key, [])
                    if not isinstance(values, list) or (values and not isinstance(values[-1], dict)):
                        raise ValueError("conflicting array table")
                    current = {}
                    values.append(current)
                else:
                    current = current.setdefault(key, {})
                    if not isinstance(current, dict) or id(current) in declared:
                        raise ValueError("duplicate or conflicting table")
                    declared.add(id(current))
                continue
            # Keys emitted by the writer can contain '=' inside quoted strings.
            if line.startswith('"'):
                _, end = json.JSONDecoder().raw_decode(line)
                key_text, rest = line[:end], line[end:].lstrip()
            else:
                key_text, separator, value_text = line.partition("=")
                if not separator:
                    raise ValueError("unsupported statement")
                rest = "=" + value_text
            keys = _key_path(key_text)
            if len(keys) != 1 or not rest.startswith("="):
                raise ValueError("unsupported assignment")
            key = keys[0]
            value = json.loads(rest[1:].strip())
            if key in current or not _scalar(value):
                raise ValueError("duplicate key or unsupported value")
            current[key] = value
            assigned.add((id(current), key))
    except (UnicodeError, ValueError, TypeError, IndexError) as exc:
        raise _error("invalid installer state TOML (unsupported syntax or duplicate fields)") from exc
    _validate_values(root)
    return _validate(root)


def encode_state(data: dict) -> bytes:
    """Serialize validated installer state as real, inspectable TOML tables."""
    _validate(data)
    _validate_values(data)
    lines = ["# Hukuhaka installer state; not Codex runtime configuration."]

    def table(value: dict, keys: list[str], array: bool = False) -> None:
        if keys:
            name = ".".join(json.dumps(key, ensure_ascii=False) for key in keys).replace("\x7f", "\\u007f")
            lines.extend(["", ("[[" if array else "[") + name + ("]]" if array else "]")])
        for key, item in value.items():
            if _scalar(item):
                lines.append((json.dumps(key, ensure_ascii=False) + " = " + json.dumps(item, ensure_ascii=False)).replace("\x7f", "\\u007f"))
        for key, item in value.items():
            if isinstance(item, dict):
                table(item, keys + [key])
            elif isinstance(item, list) and item and isinstance(item[0], dict):
                for entry in item:
                    table(entry, keys + [key], True)

    table(data, [])
    return ("\n".join(lines) + "\n").encode("utf-8")


class InstallState:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.path = self.home / "hk-config.toml"
        self.backup_path = self.home / "hk-config.toml.bak"

    def _check(self, path: Path, *, directory: bool = False) -> None:
        target = ensure_within(self.home, path, operation="installer-state")
        home = ensure_within(self.home, self.home, operation="installer-state")
        for parent in (target, *target.parents):
            if parent.is_symlink():
                raise _error("installer state path is a symlink: " + str(parent))
            if parent == home:
                break
            if parent != target and parent.exists() and not parent.is_dir():
                raise _error("installer state parent is not a directory")
        if target.exists() and not (target.is_dir() if directory else target.is_file()):
            raise _error("installer state path has the wrong file type: " + str(target))

    def read(self) -> dict:
        self._check(self.path)
        if not self.path.exists():
            self._check(self.backup_path)
            if self.backup_path.exists():
                detail = "pending transaction recovery" if self.has_pending_transactions() else "a backup"
                raise _error("installer state is missing but {} exists; run codex state recover before continuing".format(detail))
            return {"schema_version": 1, "components": {}, "operations": []}
        try:
            return decode_state(self.path.read_bytes())
        except OSError as exc:
            raise _error("cannot read installer state") from exc

    def has_pending_transactions(self) -> bool:
        """Inspect existing transaction journals without replaying or creating state."""
        root = self.home / ".hukuhaka-transactions"
        self._check(root, directory=True)
        if not root.exists():
            return False
        pending = False
        for transaction in root.iterdir():
            if transaction.is_symlink() or not transaction.is_dir():
                raise _error("invalid installer transaction path")
            journal = transaction / "journal.json"
            self._check(journal)
            if not journal.exists():
                # Existing recovery owns cleanup of interrupted journal creation.
                pending = True
                continue
            data = load_json(journal, {})
            if not isinstance(data, dict) or data.get("state") not in {"pending", "committed"} or not isinstance(data.get("entries"), list):
                raise _error("invalid installer transaction journal")
            if data["state"] == "pending":
                pending = True
        return pending

    def recover_transactions(self) -> int:
        """Explicitly replay existing file transactions, then validate their result."""
        self.has_pending_transactions()
        with InstallerLock(self.home):
            self.has_pending_transactions()
            recovered = FileTransaction.recover_pending(self.home)
            self.read()
            return recovered

    def _legacy(self, legacy_path: Optional[Path]) -> Optional[dict]:
        if legacy_path is None:
            return None
        self._check(legacy_path)
        if not legacy_path.exists():
            return None
        try:
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate JSON key")
                    result[key] = value
                return result
            value = json.loads(legacy_path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
            if not isinstance(value, dict):
                raise ValueError("receipt must be an object")
            return value
        except (OSError, UnicodeError, ValueError) as exc:
            raise _error("invalid legacy installer receipt: " + str(legacy_path)) from exc

    def receipt(self, name: str, legacy_path: Optional[Path]) -> Optional[dict]:
        _name(name)
        record = self.read()["components"].get(name)
        legacy = self._legacy(legacy_path)
        if record is not None:
            central = record.get("receipt")
            if legacy is not None and central != legacy:
                raise _error("central and legacy installer receipts conflict: " + name)
            return central
        return legacy

    def _write(self, tx: FileTransaction, data: dict) -> None:
        content = encode_state(data)
        self._check(self.path)
        self._check(self.backup_path)
        previous = self.path.read_bytes() if self.path.exists() else content
        decode_state(previous)
        tx.write_bytes(self.backup_path, previous, mode=0o600)
        tx.write_bytes(self.path, content, mode=0o600)

    def _retire_legacy(self, tx: FileTransaction, name: str, legacy_path: Optional[Path]) -> Optional[str]:
        if legacy_path is None or self._legacy(legacy_path) is None:
            return
        content = legacy_path.read_bytes()
        backup = self.home / "hk-backups" / "legacy" / (name + "-" + hashlib.sha256(content).hexdigest() + ".json")
        self._check(backup)
        if backup.exists() and backup.read_bytes() != content:
            raise _error("legacy backup contents conflict")
        if not backup.exists():
            tx.write_bytes(backup, content, mode=0o600)
        tx.remove(legacy_path)
        return backup.relative_to(self.home).as_posix()

    @staticmethod
    def _legacy_history(data: dict, name: str, legacy: Optional[dict], backup: Optional[str]) -> None:
        for operation in data["operations"]:
            if operation["status"] == "running":
                if legacy is not None:
                    version = legacy.get("version")
                    operation.setdefault("components_before", {}).setdefault(name, version if isinstance(version, str) else "unknown")
                if backup is not None and backup not in operation.setdefault("backups", []):
                    operation["backups"].append(backup)

    def put_receipt(self, tx: FileTransaction, name: str, receipt: dict, kind: str,
                    installer_version: str, legacy_path: Optional[Path]) -> None:
        self.receipt(name, legacy_path)  # Validate both records before any mutation.
        data = self.read()
        previous = data["components"].get(name)
        legacy = self._legacy(legacy_path)
        data["components"][name] = {
            "kind": kind, "version": receipt.get("version"), "installer_version": installer_version,
            "installed_at": previous["installed_at"] if previous else ("unknown" if legacy is not None else _now()),
            "updated_at": _now(), "provenance": previous["provenance"] if previous else ("legacy" if legacy is not None else "installed"),
            "receipt": receipt,
        }
        record = data["components"][name]
        for key in ("backups", "migrated_from_version"):
            if previous and key in previous:
                record[key] = previous[key]
        if legacy is not None and "migrated_from_version" not in record:
            version = legacy.get("version")
            record["migrated_from_version"] = version if isinstance(version, str) else "unknown"
        backup = self._retire_legacy(tx, name, legacy_path)
        if backup is not None and backup not in record.setdefault("backups", []):
            record["backups"].append(backup)
        self._legacy_history(data, name, legacy, backup)
        for reference in record.get("backups", []):
            self._legacy_history(data, name, None, reference)
        self._write(tx, data)

    def remove_receipt(self, tx: FileTransaction, name: str, legacy_path: Optional[Path]) -> None:
        self.receipt(name, legacy_path)
        data = self.read()
        legacy = self._legacy(legacy_path)
        previous = data["components"].get(name)
        backup = self._retire_legacy(tx, name, legacy_path)
        self._legacy_history(data, name, legacy, backup)
        if previous:
            for reference in previous.get("backups", []):
                self._legacy_history(data, name, None, reference)
        data["components"].pop(name, None)
        self._write(tx, data)

    def _mutate(self, change) -> Any:
        # Receipt changes use their caller's transaction instead of this lock.
        self._check(self.path)
        with installer_state(self.home, dry_run=False):
            data = self.read()
            result = change(data)
            with FileTransaction(self.home) as tx:
                self._write(tx, data)
                tx.commit()
            return result

    def set_plugin(self, name: str, version: str, installer_version: str) -> None:
        _name(name)
        def change(data):
            previous = data["components"].get(name)
            data["components"][name] = {
                "kind": "plugin", "version": version, "installer_version": installer_version,
                "installed_at": previous["installed_at"] if previous else _now(),
                "updated_at": _now(), "provenance": previous["provenance"] if previous else "installed",
            }
        self._mutate(change)

    def remove_plugin(self, name: str) -> None:
        _name(name)
        self._mutate(lambda data: data["components"].pop(name, None))

    @staticmethod
    def _trim(data: dict) -> None:
        completed = [record for record in data["operations"] if record["status"] != "running"]
        retained = {record["id"] for record in completed[-50:]}
        data["operations"] = [record for record in data["operations"] if record["status"] == "running" or record["id"] in retained]

    @staticmethod
    def _versions(data: dict) -> dict:
        return {name: record["version"] for name, record in data["components"].items()}

    def begin_operation(self, action: str, installer_version: str, requested: list[str]) -> str:
        def change(data):
            now = _now()
            for record in data["operations"]:
                if record["status"] == "running":
                    record.update(status="interrupted", finished_at=now, components_after=self._versions(data))
            identity = uuid.uuid4().hex
            data["operations"].append({"id": identity, "action": action, "started_at": now,
                "installer_version": installer_version, "requested": requested, "completed": [],
                "stage": "start", "status": "running", "components_before": self._versions(data)})
            self._trim(data)
            return identity
        return self._mutate(change)

    @staticmethod
    def _operation(data: dict, identity: str) -> dict:
        for record in data["operations"]:
            if record["id"] == identity and record["status"] == "running":
                return record
        raise _error("running installer operation not found")

    def update_operation(self, identity: str, stage: str, completed: list[str]) -> None:
        self._mutate(lambda data: self._operation(data, identity).update(stage=stage, completed=completed))

    def finish_operation(self, identity: str, status: str, completed: list[str], error=None) -> None:
        if status == "running" or not status:
            raise _error("operation finish requires a terminal status")
        def change(data):
            record = self._operation(data, identity)
            record.update(status=status, completed=completed, finished_at=_now(), components_after=self._versions(data))
            if error is not None:
                values = error if isinstance(error, dict) else {"stage": getattr(error, "stage", None), "type": type(error).__name__}
                record["error"] = {key: value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value) else "unknown"
                                   for key, value in (("stage", values.get("stage")), ("type", values.get("type")))}
            self._trim(data)
        self._mutate(change)

    def restore_backup(self) -> Optional[str]:
        """Restore records only; this does not verify agreement with installed files."""
        self._check(self.path)
        self._check(self.backup_path)
        with InstallerLock(self.home):
            if self.has_pending_transactions():
                raise _error("pending file transactions must be recovered before restoring a record backup; run codex state recover")
            self._check(self.path)
            self._check(self.backup_path)
            if not self.backup_path.exists():
                raise _error("installer state backup is missing")
            content = self.backup_path.read_bytes()
            decode_state(content)
            original = self.path.read_bytes() if self.path.exists() else None
            reference = None
            with FileTransaction(self.home) as tx:
                if original is not None:
                    archive = self.home / "hk-backups" / ("state-" + hashlib.sha256(original).hexdigest() + ".toml")
                    self._check(archive)
                    if archive.exists() and archive.read_bytes() != original:
                        raise _error("installer state recovery backup conflicts")
                    if not archive.exists():
                        tx.write_bytes(archive, original, mode=0o600)
                    reference = archive.relative_to(self.home).as_posix()
                tx.write_bytes(self.path, content, mode=0o600)
                tx.commit()
            return reference
