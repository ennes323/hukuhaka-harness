#!/usr/bin/env python3
"""Deterministic Project Docs manifest inventory, validation, and audit."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_DOCUMENTS = 256
MAX_READER_DOCUMENTS = 32
MAX_READER_BYTES = 1024 * 1024
MAX_SESSION_INPUT_BYTES = 1024 * 1024
SESSION_TIMEOUT_SECONDS = 180
ROLES = {"contract", "operations", "decision", "guide", "research", "history"}
STATUSES = {"current", "draft", "historical"}
AUTHORITIES = {"normative", "advisory", "evidence"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GLOB_RE = re.compile(r"^[A-Za-z0-9._/@+*?\-]+(?:/[A-Za-z0-9._@+*?\-]+)*$")
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "release",
}


class DuplicateKeyError(ValueError):
    pass


class OperationalError(RuntimeError):
    pass


def _pairs(items: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DuplicateKeyError("duplicate key {!r}".format(key))
        result[key] = value
    return result


def _json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), flush=True)


def _error(code: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _sorted(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: (str(item.get("code", "")), str(item.get("path", "")), str(item.get("message", ""))))


def _root(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.exists() or not candidate.is_dir():
        raise OperationalError("root is not a directory: {}".format(value))
    try:
        return candidate.resolve(strict=True)
    except OSError as exc:
        raise OperationalError("cannot resolve root {}: {}".format(value, exc)) from exc


def _relative_text(value: Any, label: str, errors: List[Dict[str, Any]]) -> Optional[PurePosixPath]:
    if not isinstance(value, str) or not value:
        errors.append(_error("path.invalid", label, "must be a non-empty string"))
        return None
    if "\\" in value or "\x00" in value or value.startswith("/"):
        errors.append(_error("path.invalid", label, "must be a repository-relative POSIX path"))
        return None
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        errors.append(_error("path.invalid", label, "must not contain empty, dot, or parent segments"))
        return None
    path = PurePosixPath(value)
    if path.is_absolute():
        errors.append(_error("path.invalid", label, "must be repository-relative"))
        return None
    return path


def _regular_path(
    root: Path,
    value: Any,
    label: str,
    errors: List[Dict[str, Any]],
    *,
    utf8: bool,
) -> Optional[Path]:
    relative = _relative_text(value, label, errors)
    if relative is None:
        return None
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            errors.append(_error("path.symlink", label, "path must not traverse a symlink"))
            return None
    try:
        resolved = current.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        errors.append(_error("path.escape", label, "path escapes the repository root"))
        return None
    if not current.exists():
        errors.append(_error("path.missing", label, "target does not exist"))
        return None
    if not current.is_file():
        errors.append(_error("path.not-file", label, "target must be a regular file"))
        return None
    if utf8:
        try:
            current.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(_error("path.not-utf8", label, "document must be readable UTF-8: {}".format(exc)))
            return None
    return current


def _string_list(
    value: Any,
    label: str,
    errors: List[Dict[str, Any]],
    *,
    required: bool = True,
) -> List[str]:
    if not isinstance(value, list) or (required and not value):
        errors.append(_error("field.invalid", label, "must be a non-empty array"))
        return []
    result: List[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(_error("field.invalid", "{}[{}]".format(label, index), "must be a non-empty string"))
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(_error("field.duplicate", label, "array values must be unique"))
    return result


def _valid_glob(value: str) -> bool:
    if "\\" in value or "\x00" in value or value.startswith("/"):
        return False
    if any(token in value for token in ("[", "]", "{", "}")):
        return False
    if any(part in {"", ".", ".."} for part in value.split("/")):
        return False
    return GLOB_RE.fullmatch(value) is not None


def _load_manifest(root: Path, manifest_name: str) -> Tuple[Optional[Dict[str, Any]], int, List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    relative = _relative_text(manifest_name, "manifest", errors)
    if relative is None:
        return None, 0, errors
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            return None, 0, [_error("manifest.symlink", manifest_name, "manifest must not traverse a symlink")]
    if not path.exists() or not path.is_file():
        return None, 0, [_error("manifest.missing", manifest_name, "manifest does not exist")]
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, 0, [_error("manifest.io", manifest_name, str(exc))]
    if size > MAX_MANIFEST_BYTES:
        return None, size, [_error("manifest.too-large", manifest_name, "manifest exceeds {} bytes".format(MAX_MANIFEST_BYTES))]
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text, object_pairs_hook=_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        return None, size, [_error("manifest.invalid-json", manifest_name, str(exc))]
    if not isinstance(data, dict):
        return None, size, [_error("manifest.invalid", manifest_name, "top level must be an object")]
    return data, size, errors


def validate(root: Path, manifest_name: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    data, size, errors = _load_manifest(root, manifest_name)
    documents: List[Dict[str, Any]] = []
    if data is not None:
        allowed_top = {"schemaVersion", "documents"}
        required_top = allowed_top
        for key in sorted(set(data) - allowed_top):
            errors.append(_error("manifest.additional-property", key, "unsupported top-level field"))
        for key in sorted(required_top - set(data)):
            errors.append(_error("manifest.required", key, "required field is missing"))
        if data.get("schemaVersion") != SCHEMA_VERSION:
            errors.append(_error("manifest.schema-version", "schemaVersion", "must equal {}".format(SCHEMA_VERSION)))
        raw_documents = data.get("documents")
        if not isinstance(raw_documents, list):
            errors.append(_error("documents.invalid", "documents", "must be an array"))
        elif not raw_documents:
            errors.append(_error("documents.empty", "documents", "must contain at least one document"))
        elif len(raw_documents) > MAX_DOCUMENTS:
            errors.append(_error("documents.too-many", "documents", "must contain at most {} documents".format(MAX_DOCUMENTS)))
        else:
            documents = [item for item in raw_documents if isinstance(item, dict)]
            if len(documents) != len(raw_documents):
                errors.append(_error("document.invalid", "documents", "every document must be an object"))

    seen_ids: Set[str] = set()
    seen_paths: Set[str] = set()
    allowed_document = {"id", "path", "role", "status", "authority", "summary", "appliesTo", "readWhen", "verifyWith"}
    required_document = allowed_document - {"verifyWith"}
    for index, document in enumerate(documents):
        base = "documents[{}]".format(index)
        for key in sorted(set(document) - allowed_document):
            errors.append(_error("document.additional-property", "{}.{}".format(base, key), "unsupported document field"))
        for key in sorted(required_document - set(document)):
            errors.append(_error("document.required", "{}.{}".format(base, key), "required field is missing"))
        identifier = document.get("id")
        if not isinstance(identifier, str) or ID_RE.fullmatch(identifier) is None:
            errors.append(_error("document.id", "{}.id".format(base), "must be a kebab-case identifier"))
        elif identifier in seen_ids:
            errors.append(_error("document.id.duplicate", "{}.id".format(base), "identifier is duplicated"))
        else:
            seen_ids.add(identifier)
        path_value = document.get("path")
        if isinstance(path_value, str):
            if path_value in seen_paths:
                errors.append(_error("document.path.duplicate", "{}.path".format(base), "document path is duplicated"))
            seen_paths.add(path_value)
        _regular_path(root, path_value, "{}.path".format(base), errors, utf8=True)
        for field, allowed in (("role", ROLES), ("status", STATUSES), ("authority", AUTHORITIES)):
            value = document.get(field)
            if value not in allowed:
                errors.append(_error("document.{}".format(field), "{}.{}".format(base, field), "unsupported value"))
        summary = document.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            errors.append(_error("document.summary", "{}.summary".format(base), "must be a non-empty string"))
        globs = _string_list(document.get("appliesTo"), "{}.appliesTo".format(base), errors)
        for offset, pattern in enumerate(globs):
            if not _valid_glob(pattern):
                errors.append(_error("document.glob", "{}.appliesTo[{}]".format(base, offset), "unsupported POSIX glob subset"))
        _string_list(document.get("readWhen"), "{}.readWhen".format(base), errors)
        if "verifyWith" in document:
            routes = _string_list(document.get("verifyWith"), "{}.verifyWith".format(base), errors)
            for offset, route in enumerate(routes):
                _regular_path(root, route, "{}.verifyWith[{}]".format(base, offset), errors, utf8=False)

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "command": "validate",
        "status": "valid" if not errors else "invalid",
        "manifest": manifest_name,
        "manifestBytes": size,
        "documentCount": len(documents),
        "errors": _sorted(errors),
    }
    return payload, data if data is not None and not errors else None


def _git_files(root: Path) -> Optional[Tuple[Set[str], Set[str]]]:
    probe = subprocess.run(("git", "-C", str(root), "rev-parse", "--show-toplevel"), text=True, capture_output=True, check=False)
    if probe.returncode != 0:
        return None
    try:
        top = Path(probe.stdout.strip()).resolve(strict=True)
    except OSError as exc:
        raise OperationalError("cannot resolve Git root: {}".format(exc)) from exc
    if top != root:
        raise OperationalError("root must be the Git toplevel: {}".format(top))

    def listed(*arguments: str) -> Set[str]:
        result = subprocess.run(("git", "-C", str(root), "ls-files", "-z") + arguments, capture_output=True, check=False)
        if result.returncode != 0:
            raise OperationalError(result.stderr.decode("utf-8", "replace").strip() or "git ls-files failed")
        return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}

    tracked = listed("--cached", "--", "*.md")
    candidates = listed("--cached", "--others", "--exclude-standard", "--", "*.md")
    return candidates, tracked


def _walk_files(root: Path) -> Set[str]:
    values: Set[str] = set()
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        )
        for name in sorted(files):
            path = current_path / name
            if name.lower().endswith(".md") and not path.is_symlink():
                values.add(path.relative_to(root).as_posix())
    return values


def _worklog_owned(path: str) -> bool:
    return path in {".hukuhaka/work.md", ".hukuhaka/changelog.md"} or path.startswith(".hukuhaka/changelog/")


def inventory(root: Path) -> Dict[str, Any]:
    git_files = _git_files(root)
    if git_files is None:
        candidates = _walk_files(root)
        tracked: Optional[Set[str]] = None
        source = "filesystem"
    else:
        candidates, tracked_values = git_files
        tracked = tracked_values
        source = "git"
    documents: List[Dict[str, Any]] = []
    excluded: List[Dict[str, str]] = []
    for relative in sorted(candidates):
        if _worklog_owned(relative):
            excluded.append({"path": relative, "reason": "worklog-owned"})
            continue
        path = root / relative
        if path.is_symlink() or not path.is_file():
            excluded.append({"path": relative, "reason": "not-regular"})
            continue
        try:
            content = path.read_text(encoding="utf-8")
            size = path.stat().st_size
        except (OSError, UnicodeDecodeError):
            excluded.append({"path": relative, "reason": "not-utf8"})
            continue
        heading = ""
        status = ""
        for line in content.splitlines()[:40]:
            if not heading and line.startswith("# "):
                heading = line[2:].strip()
            if not status and "Status:" in line:
                status = line.strip().lstrip("> ").strip()
        item: Dict[str, Any] = {"path": relative, "bytes": size, "heading": heading, "status": status}
        if tracked is not None:
            item["tracked"] = relative in tracked
        documents.append(item)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "command": "inventory",
        "status": "complete",
        "source": source,
        "documents": documents,
        "excluded": sorted(excluded, key=lambda item: (item["path"], item["reason"])),
    }


def audit(root: Path, manifest_name: str) -> Dict[str, Any]:
    validation, data = validate(root, manifest_name)
    findings: List[Dict[str, Any]] = []
    inventory_payload = inventory(root)
    if data is not None:
        documents = data["documents"]
        indexed = {document["path"] for document in documents}
        for item in inventory_payload["documents"]:
            if item["path"] not in indexed:
                findings.append(_error("document.unindexed", item["path"], "Markdown document is not indexed"))
        coverage: Dict[str, List[str]] = {}
        for document in documents:
            if document["status"] == "historical" and document["authority"] == "normative":
                findings.append(_error("document.lifecycle-conflict", document["id"], "historical document cannot be normative"))
            if document["status"] == "current" and document["authority"] == "normative":
                for pattern in document["appliesTo"]:
                    coverage.setdefault(pattern, []).append(document["id"])
        for pattern, identifiers in coverage.items():
            if len(identifiers) > 1:
                findings.append(_error("authority.overlap", pattern, "current normative coverage is shared by {}".format(", ".join(sorted(identifiers)))))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "command": "audit",
        "status": "invalid" if validation["errors"] else ("findings" if findings else "clean"),
        "manifest": manifest_name,
        "errors": validation["errors"],
        "findings": _sorted(findings),
        "inventory": inventory_payload,
    }


def _reader_document(
    root: Path,
    document: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    path = root / PurePosixPath(document["path"])
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise OperationalError(
            "cannot stat indexed document {}: {}".format(document["path"], exc)
        ) from exc
    result = dict(document)
    result.update({"index": index, "bytes": size})
    return result


def reader_catalog(root: Path, manifest_name: str) -> Dict[str, Any]:
    validation, data = validate(root, manifest_name)
    ready = data is not None and not validation["errors"]
    payload: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "command": "reader-catalog",
        "status": "ready" if ready else "unavailable",
        "manifest": manifest_name,
        "manifestBytes": validation["manifestBytes"],
        "documents": [],
        "errors": validation["errors"],
    }
    if ready:
        payload["documents"] = [
            _reader_document(root, document, index)
            for index, document in enumerate(data["documents"])
        ]
    return payload


def reader_read(
    root: Path,
    manifest_name: str,
    identifiers: Sequence[str],
    max_documents: int,
    max_bytes: int,
) -> Dict[str, Any]:
    validation, data = validate(root, manifest_name)
    errors = list(validation["errors"])
    partial_errors: List[Dict[str, str]] = []
    selected = list(identifiers)
    if not selected:
        errors.append(_error("selection.empty", "ids", "at least one document ID is required"))
    if len(selected) != len(set(selected)):
        errors.append(_error("selection.duplicate", "ids", "document IDs must be unique"))
    if not 1 <= max_documents <= MAX_READER_DOCUMENTS:
        errors.append(
            _error(
                "selection.max-documents",
                "maxDocuments",
                "must be between 1 and {}".format(MAX_READER_DOCUMENTS),
            )
        )
    if not 1 <= max_bytes <= MAX_READER_BYTES:
        errors.append(
            _error(
                "selection.max-bytes",
                "maxBytes",
                "must be between 1 and {}".format(MAX_READER_BYTES),
            )
        )
    if len(selected) > max_documents:
        errors.append(
            _error(
                "selection.document-limit",
                "ids",
                "selection exceeds maxDocuments {}".format(max_documents),
            )
        )

    documents: List[Dict[str, Any]] = []
    document_bytes = 0
    if data is not None:
        by_id = {document["id"]: document for document in data["documents"]}
        unknown = sorted(set(selected) - set(by_id))
        for identifier in unknown:
            errors.append(
                _error(
                    "selection.unknown",
                    identifier,
                    "document ID is not present in the manifest",
                )
            )
        selected_ids = set(selected)
        if not errors:
            for index, document in enumerate(data["documents"]):
                if document["id"] not in selected_ids:
                    continue
                path = root / PurePosixPath(document["path"])
                try:
                    raw = path.read_bytes()
                    text = raw.decode("utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    partial_errors.append(
                        _error(
                            "selection.read-error",
                            document["path"],
                            "cannot read selected document: {}".format(exc),
                        )
                    )
                    continue
                document_bytes += len(raw)
                item = dict(document)
                item.update(
                    {
                        "index": index,
                        "bytes": len(raw),
                        "numberedContent": "\n".join(
                            "{}\t{}".format(number, line)
                            for number, line in enumerate(text.splitlines(), 1)
                        ),
                    }
                )
                documents.append(item)

    if errors or partial_errors:
        documents = []
        document_bytes = 0
    total_bytes = validation["manifestBytes"] + document_bytes
    if not errors and not partial_errors and total_bytes > max_bytes:
        partial_errors.append(
            _error(
                "selection.byte-limit",
                "ids",
                "manifest and selected documents use {} bytes, exceeding maxBytes {}".format(
                    total_bytes, max_bytes
                ),
            )
        )
        documents = []
        document_bytes = 0

    return {
        "schemaVersion": SCHEMA_VERSION,
        "command": "reader-read",
        "status": (
            "unavailable"
            if errors
            else ("partial" if partial_errors else "complete")
        ),
        "manifest": manifest_name,
        "manifestBytes": validation["manifestBytes"],
        "documentBytes": document_bytes,
        "documents": documents,
        "errors": _sorted(errors + partial_errors),
    }


def _session_failure(manifest_name: str, manifest_bytes: int, code: str, message: str) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION, "command": "reader-read", "status": "unavailable",
        "manifest": manifest_name, "manifestBytes": manifest_bytes,
        "documentBytes": 0, "documents": [],
        "errors": [_error(code, "ids", message)],
    }


def _session_line(fd: int, timeout: float) -> bytes:
    """Read one bounded newline frame with a deadline, including on a partial pipe/PTY line."""
    deadline = time.monotonic() + timeout
    raw = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise TimeoutError("selection was not completed before the session deadline")
        chunk = os.read(fd, min(4096, MAX_SESSION_INPUT_BYTES + 1 - len(raw)))
        if not chunk:
            raise EOFError("selection ended before a newline-terminated JSON object")
        raw.extend(chunk)
        if len(raw) > MAX_SESSION_INPUT_BYTES:
            raise ValueError("selection exceeds {} bytes".format(MAX_SESSION_INPUT_BYTES))
        if b"\n" in raw:
            line, rest = raw.split(b"\n", 1)
            if rest.strip():
                raise ValueError("expected exactly one selection frame")
            return bytes(line)


def _session_ids(raw: bytes, catalog: Dict[str, Any]) -> List[str]:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError("invalid JSON constant {}".format(token))),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("selection must be strict UTF-8 JSON: {}".format(exc)) from exc
    if not isinstance(value, dict) or set(value) != {"ids"} or not isinstance(value["ids"], list):
        raise ValueError("selection must have exactly one ids array")
    ids = value["ids"]
    known = {document["id"] for document in catalog["documents"]}
    if any(not isinstance(identifier, str) or ID_RE.fullmatch(identifier) is None or identifier not in known for identifier in ids):
        raise ValueError("ids must be catalog kebab-case identifiers")
    if len(ids) != len(set(ids)):
        raise ValueError("ids must be unique")
    return ids


def reader_session(
    root: Path, manifest_name: str, max_documents: int, max_bytes: int,
    *, fd: int = 0, timeout: float = SESSION_TIMEOUT_SECONDS,
) -> int:
    """Emit a catalog, accept one selection, then emit a read and exit.

    An empty ids array intentionally closes without reading documents. Its ordinary
    complete reader-read envelope leaves the agent to report unknown/partial as needed.
    """
    catalog = reader_catalog(root, manifest_name)
    if not 1 <= max_documents <= MAX_READER_DOCUMENTS:
        _json(_session_failure(manifest_name, catalog["manifestBytes"], "selection.max-documents",
                               "must be between 1 and {}".format(MAX_READER_DOCUMENTS)))
        return 1
    if not 1 <= max_bytes <= MAX_READER_BYTES:
        _json(_session_failure(manifest_name, catalog["manifestBytes"], "selection.max-bytes",
                               "must be between 1 and {}".format(MAX_READER_BYTES)))
        return 1
    # Disable terminal echo and canonical input so a PTY does not echo JSON onto
    # stdout or truncate a valid selection at its platform line-buffer limit.
    # Do this before publishing the catalog, which signals that input may start.
    terminal = None
    if catalog["status"] == "ready" and catalog["manifestBytes"] <= max_bytes and os.isatty(fd):
        import termios
        terminal = termios.tcgetattr(fd)
        adjusted = termios.tcgetattr(fd)
        adjusted[3] &= ~(termios.ECHO | termios.ICANON)
        adjusted[6][termios.VMIN] = 1
        adjusted[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, adjusted)
    try:
        _json(catalog)
        if catalog["status"] != "ready" or catalog["manifestBytes"] > max_bytes:
            return 1
        try:
            ids = _session_ids(_session_line(fd, timeout), catalog)
        except TimeoutError as exc:
            payload = _session_failure(manifest_name, catalog["manifestBytes"], "session.timeout", str(exc))
        except EOFError as exc:
            payload = _session_failure(manifest_name, catalog["manifestBytes"], "session.eof", str(exc))
        except (ValueError, OSError) as exc:
            payload = _session_failure(manifest_name, catalog["manifestBytes"], "session.invalid-selection", str(exc))
        else:
            if ids:
                payload = reader_read(root, manifest_name, ids, max_documents, max_bytes)
            else:
                payload = {
                    "schemaVersion": SCHEMA_VERSION, "command": "reader-read", "status": "complete",
                    "manifest": manifest_name, "manifestBytes": catalog["manifestBytes"],
                    "documentBytes": 0, "documents": [], "errors": [],
                }
    finally:
        if terminal is not None:
            termios.tcsetattr(fd, termios.TCSANOW, terminal)
    _json(payload)
    return 0 if payload["status"] == "complete" else 1


def reader_protocol_module() -> Any:
    """Load the same validator from the Skill or standalone managed resources."""
    directory = Path(__file__).resolve().parent
    filename = ("project-doc-reader-protocol.py"
                if Path(__file__).name == "project-doc-reader-tool.py"
                else "reader_protocol.py")
    spec = importlib.util.spec_from_file_location("project_doc_reader_protocol", directory / filename)
    if spec is None or spec.loader is None:
        raise OperationalError("Reader protocol validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_wire(command: str, raw: str) -> Dict[str, Any]:
    protocol = reader_protocol_module()
    try:
        value = protocol.parse_json(raw)
    except ValueError as exc:
        errors = [_error("json.invalid", "$", str(exc))]
    else:
        if command == "reader-validate-request":
            errors = protocol.validate_request(value)
        elif not isinstance(value, dict) or set(value) != {"request", "response"}:
            errors = [_error("pair.invalid", "$", "expected exactly request and response fields")]
        else:
            errors = protocol.validate_response(value["response"], request=value["request"])
    return {"schemaVersion": 2, "command": command,
            "status": "invalid" if errors else "valid", "errors": errors}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="project_docs.py")
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("reader-validate-request", "reader-validate-response"):
        subparsers.add_parser(name, help="validate JSON v2 from stdin without repository access")
    for name in ("inventory", "validate", "audit", "reader-catalog", "reader-read", "reader-session"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", required=True)
        if name != "inventory":
            command.add_argument("--manifest", default="project-docs.json")
        if name in ("reader-read", "reader-session"):
            if name == "reader-read":
                command.add_argument("--ids", required=True)
            command.add_argument("--max-documents", required=True, type=int)
            command.add_argument("--max-bytes", required=True, type=int)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command in ("reader-validate-request", "reader-validate-response"):
        try:
            payload = validate_wire(arguments.command, sys.stdin.read())
        except (OSError, ValueError, RuntimeError) as exc:
            _json({"schemaVersion": 2, "command": arguments.command, "status": "error",
                   "errors": [_error("protocol.unavailable", "$", str(exc))]})
            return 2
        _json(payload)
        return 0 if payload["status"] == "valid" else 1
    try:
        root = _root(arguments.root)
        if arguments.command == "inventory":
            payload = inventory(root)
            code = 0
        elif arguments.command == "validate":
            payload, _ = validate(root, arguments.manifest)
            code = 0 if payload["status"] == "valid" else 1
        elif arguments.command == "audit":
            payload = audit(root, arguments.manifest)
            code = 0 if payload["status"] == "clean" else 1
        elif arguments.command == "reader-catalog":
            payload = reader_catalog(root, arguments.manifest)
            code = 0 if payload["status"] == "ready" else 1
        elif arguments.command == "reader-session":
            return reader_session(root, arguments.manifest, arguments.max_documents, arguments.max_bytes)
        else:
            payload = reader_read(
                root,
                arguments.manifest,
                arguments.ids.split(",") if arguments.ids else (),
                arguments.max_documents,
                arguments.max_bytes,
            )
            code = 0 if payload["status"] == "complete" else 1
    except OperationalError as exc:
        _json({"schemaVersion": SCHEMA_VERSION, "command": getattr(arguments, "command", ""), "status": "error", "errors": [_error("operation.failed", "root", str(exc))]})
        return 2
    _json(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
