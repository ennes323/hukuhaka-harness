#!/usr/bin/env python3
"""Strict JSON parsing and schema-backed validation for Reader protocol v2.

The module intentionally implements only the small JSON Schema vocabulary used
by the two bundled protocol schemas.  Unknown schema keywords fail closed.
Protocol correlations that JSON Schema cannot express clearly are checked after
structural validation.  Validation never reads the requested repository.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


Error = Dict[str, str]
_MISSING = object()
_SCHEMA_KEYWORDS = {
    "$schema", "title", "$defs", "$ref", "type", "const", "enum",
    "required", "properties", "additionalProperties", "items", "minItems",
    "maxItems", "minLength", "minimum", "maximum", "pattern",
}


def _error(code: str, path: str, message: str) -> Error:
    return {"code": code, "path": path or "$", "message": message}


def _pairs(items: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate object key {!r}".format(key))
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("non-finite JSON number {!r}".format(value))


def parse_json(text: str) -> Any:
    """Parse one strict JSON value or raise ValueError."""
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non-finite JSON number")
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return value


def _schema_path(filename: str) -> Path:
    here = Path(__file__).resolve().parent
    candidates = (
        here.parent / "references" / filename,
        here / "project-doc-reader" / filename,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("bundled Reader schema is missing: {}".format(filename))


def _check_schema(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise RuntimeError("schema node {} must be an object".format(path))
    unsupported = set(schema) - _SCHEMA_KEYWORDS
    if unsupported:
        raise RuntimeError(
            "unsupported schema keyword(s) at {}: {}".format(
                path, ", ".join(sorted(unsupported))
            )
        )
    if "$ref" in schema and len(schema) != 1:
        raise RuntimeError("schema reference at {} cannot have sibling keywords".format(path))
    for name in ("properties", "$defs"):
        children = schema.get(name, {})
        if not isinstance(children, dict):
            raise RuntimeError("{} at {} must be an object".format(name, path))
        for key, child in children.items():
            _check_schema(child, "{}.{}/{}".format(path, name, key))
    if "items" in schema:
        _check_schema(schema["items"], path + ".items")
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        raise RuntimeError("schema-valued additionalProperties at {} is unsupported".format(path))
    if additional not in (None, True, False):
        raise RuntimeError("additionalProperties at {} is unsupported".format(path))


def _load_schema(filename: str) -> Dict[str, Any]:
    try:
        value = parse_json(_schema_path(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot load {}: {}".format(filename, exc)) from exc
    _check_schema(value)
    return value


def _join(path: str, name: str) -> str:
    return "{}.{}".format(path, name) if path != "$" else "$.{}".format(name)


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    raise RuntimeError("unsupported schema type {!r}".format(expected))


def _resolve_ref(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise RuntimeError("only local schema references are supported: {}".format(reference))
    current: Any = root
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise RuntimeError("unresolved schema reference: {}".format(reference))
        current = current[token]
    if not isinstance(current, dict):
        raise RuntimeError("schema reference is not an object: {}".format(reference))
    return current


def _evaluate(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any], path: str, errors: List[Error]) -> None:
    if "$ref" in schema:
        _evaluate(value, _resolve_ref(root, schema["$ref"]), root, path, errors)
        return
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not all(isinstance(choice, str) for choice in choices):
            raise RuntimeError("schema type must be a string or string array")
        if not any(_type_matches(value, choice) for choice in choices):
            errors.append(_error("schema.type", path, "must be {}".format(" or ".join(choices))))
            return
    if "const" in schema and value != schema["const"]:
        errors.append(_error("schema.const", path, "must equal {!r}".format(schema["const"])))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(_error("schema.enum", path, "must be one of {!r}".format(schema["enum"])))
    if isinstance(value, dict):
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                errors.append(_error("schema.required", _join(path, name), "is required"))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    errors.append(_error("schema.additional-property", _join(path, name), "is not allowed"))
        for name, child in properties.items():
            if name in value:
                _evaluate(value[name], child, root, _join(path, name), errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(_error("schema.min-items", path, "has too few items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(_error("schema.max-items", path, "has too many items"))
        if "items" in schema:
            for index, item in enumerate(value):
                _evaluate(item, schema["items"], root, "{}[{}]".format(path, index), errors)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(_error("schema.min-length", path, "is too short"))
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(_error("schema.pattern", path, "does not match required pattern"))
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(_error("schema.minimum", path, "is below minimum {}".format(schema["minimum"])))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(_error("schema.maximum", path, "is above maximum {}".format(schema["maximum"])))


def _structural(value: Any, filename: str) -> List[Error]:
    schema = _load_schema(filename)
    errors: List[Error] = []
    _evaluate(value, schema, schema, "$", errors)
    return errors


def _canonical_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or "\x00" in value:
        return False
    return all(part not in ("", ".", "..") for part in value.split("/"))


def _absolute_posix(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("/") and "\\" not in value and "\x00" not in value


def _add_unique_errors(values: Sequence[Any], key: str, path: str, errors: List[Error]) -> None:
    seen = set()
    for index, item in enumerate(values):
        if not isinstance(item, dict) or key not in item:
            continue
        value = item[key]
        if value in seen:
            errors.append(_error("protocol.duplicate", "{}[{}].{}".format(path, index, key), "must be unique"))
        else:
            seen.add(value)


def validate_request(value: Any) -> List[Error]:
    errors = _structural(value, "reader-request-v2.schema.json")
    if errors:
        return errors
    if "root" in value and not _absolute_posix(value["root"]):
        errors.append(_error("request.root", "$.root", "must be an absolute POSIX path"))
    paths = value.get("paths")
    if isinstance(paths, list):
        for index, path in enumerate(paths):
            if not _canonical_relative(path):
                errors.append(_error("request.path", "$.paths[{}]".format(index), "must be a canonical repository-relative POSIX path"))
    questions = value.get("questions")
    if isinstance(questions, list):
        _add_unique_errors(questions, "id", "$.questions", errors)
    return errors


def _sources(response: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    result: List[Tuple[str, Mapping[str, Any]]] = []
    for collection in ("answers", "conflicts", "requiredChecks", "affectedDocuments"):
        values = response.get(collection, [])
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict) or not isinstance(item.get("sources"), list):
                continue
            for offset, source in enumerate(item["sources"]):
                if isinstance(source, dict):
                    result.append(("$.{}[{}].sources[{}]".format(collection, index, offset), source))
    return result


def _safe_request_fields(request: Mapping[str, Any]) -> Dict[str, Any]:
    budget = request.get("budget") if isinstance(request.get("budget"), dict) else {}
    max_documents = budget.get("maxDocuments")
    max_bytes = budget.get("maxBytes")
    return {
        "requestId": request.get("requestId") if isinstance(request.get("requestId"), str) and request.get("requestId", "").strip() else None,
        "mode": request.get("mode") if request.get("mode") in ("context", "impact") else None,
        "root": request.get("root") if _absolute_posix(request.get("root")) else None,
        "maxDocuments": max_documents if isinstance(max_documents, int) and not isinstance(max_documents, bool) and 1 <= max_documents <= 32 else None,
        "maxBytes": max_bytes if isinstance(max_bytes, int) and not isinstance(max_bytes, bool) and 1 <= max_bytes <= 1048576 else None,
    }


def validate_response(response: Any, request: Any = _MISSING) -> List[Error]:
    errors = _structural(response, "reader-response-v2.schema.json")
    if errors:
        return errors

    status = response.get("status")
    mode = response.get("mode")
    if response.get("requestId") is not None and (not isinstance(response.get("requestId"), str) or not response["requestId"].strip()):
        errors.append(_error("response.request-id", "$.requestId", "must be null or a nonblank string"))
    if response.get("root") is not None and not _absolute_posix(response.get("root")):
        errors.append(_error("response.root", "$.root", "must be null or an absolute POSIX path"))
    if status != "unavailable":
        for field in ("requestId", "mode", "root"):
            if response.get(field) is None:
                errors.append(_error("response.null", "$.{}".format(field), "may be null only when status is unavailable"))
        budget = response.get("budgetUsed", {})
        if isinstance(budget, dict):
            for field in ("maxDocuments", "maxBytes"):
                if budget.get(field) is None:
                    errors.append(_error("response.null", "$.budgetUsed.{}".format(field), "may be null only when status is unavailable"))

    if mode == "context":
        if "requiredChecks" not in response:
            errors.append(_error("response.mode", "$.requiredChecks", "is required in context mode"))
        if "affectedDocuments" in response:
            errors.append(_error("response.mode", "$.affectedDocuments", "is not allowed in context mode"))
    elif mode == "impact":
        if "affectedDocuments" not in response:
            errors.append(_error("response.mode", "$.affectedDocuments", "is required in impact mode"))
        if "requiredChecks" in response:
            errors.append(_error("response.mode", "$.requiredChecks", "is not allowed in impact mode"))
    elif mode is None:
        for field in ("requiredChecks", "affectedDocuments"):
            if field in response:
                errors.append(_error("response.mode", "$.{}".format(field), "is not allowed when mode is null"))

    selected = response.get("selectedDocuments", [])
    excluded = response.get("excludedDocuments", [])
    if isinstance(selected, list) and isinstance(excluded, list):
        for key in ("id", "path"):
            _add_unique_errors(selected, key, "$.selectedDocuments", errors)
            _add_unique_errors(excluded, key, "$.excludedDocuments", errors)
            selected_values = {item.get(key) for item in selected if isinstance(item, dict)}
            for index, item in enumerate(excluded):
                if isinstance(item, dict) and item.get(key) in selected_values:
                    errors.append(_error("response.document-overlap", "$.excludedDocuments[{}].{}".format(index, key), "must be disjoint from selected documents"))
        for collection_name, collection in (("selectedDocuments", selected), ("excludedDocuments", excluded)):
            for index, item in enumerate(collection):
                if isinstance(item, dict) and "path" in item and not _canonical_relative(item["path"]):
                    errors.append(_error("response.path", "$.{}[{}].path".format(collection_name, index), "must be a canonical repository-relative POSIX path"))

    selected_paths = {item.get("path") for item in selected if isinstance(item, dict)} if isinstance(selected, list) else set()
    for path, source in _sources(response):
        if not _canonical_relative(source.get("path")):
            errors.append(_error("response.source-path", path + ".path", "must be a canonical repository-relative POSIX path"))
        elif source.get("path") not in selected_paths:
            errors.append(_error("response.source-selection", path + ".path", "must refer to a selected document"))

    answers = response.get("answers", [])
    if isinstance(answers, list):
        _add_unique_errors(answers, "questionId", "$.answers", errors)
        for index, answer in enumerate(answers):
            if not isinstance(answer, dict):
                continue
            base = "$.answers[{}]".format(index)
            if answer.get("status") == "answered":
                if not isinstance(answer.get("answer"), str) or not answer["answer"].strip():
                    errors.append(_error("response.answer", base + ".answer", "answered responses require a nonblank answer"))
                if not isinstance(answer.get("sources"), list) or not answer["sources"]:
                    errors.append(_error("response.answer", base + ".sources", "answered responses require at least one source"))
                if answer.get("reason") != "":
                    errors.append(_error("response.answer", base + ".reason", "answered responses require an empty reason"))
            elif answer.get("status") == "unknown":
                if answer.get("answer") != "":
                    errors.append(_error("response.answer", base + ".answer", "unknown responses require an empty answer"))
                if answer.get("sources") != []:
                    errors.append(_error("response.answer", base + ".sources", "unknown responses require no sources"))
                if not isinstance(answer.get("reason"), str) or not answer["reason"].strip():
                    errors.append(_error("response.answer", base + ".reason", "unknown responses require a nonblank reason"))

    conflicts = response.get("conflicts", [])
    errors_value = response.get("errors", [])
    budget = response.get("budgetUsed", {})
    unknown = isinstance(answers, list) and any(isinstance(item, dict) and item.get("status") == "unknown" for item in answers)
    truncated = isinstance(budget, dict) and budget.get("truncated") is True
    has_errors = isinstance(errors_value, list) and bool(errors_value)
    selection_failure = isinstance(errors_value, list) and any(
        isinstance(item, dict) and item.get("code") in ("selection.read-error", "selection.byte-limit")
        for item in errors_value
    )
    if selection_failure:
        if status != "partial":
            errors.append(_error("response.selection-failure", "$.status", "read or byte selection failures require partial status"))
        if not truncated:
            errors.append(_error("response.selection-failure", "$.budgetUsed.truncated", "read or byte selection failures require truncation"))
        if selected:
            errors.append(_error("response.selection-failure", "$.selectedDocuments", "read or byte selection failures cannot retain selected documents"))
        if isinstance(answers, list) and any(isinstance(item, dict) and item.get("status") != "unknown" for item in answers):
            errors.append(_error("response.selection-failure", "$.answers", "read or byte selection failures require unknown answers"))
        if conflicts:
            errors.append(_error("response.selection-failure", "$.conflicts", "read or byte selection failures cannot retain content claims"))
        for field in ("requiredChecks", "affectedDocuments"):
            if response.get(field):
                errors.append(_error("response.selection-failure", "$.{}".format(field), "read or byte selection failures cannot retain claims"))
    limiting_exclusion = isinstance(excluded, list) and any(
        isinstance(item, dict) and item.get("reason") in ("document-limit", "byte-limit", "read-error")
        for item in excluded
    )
    if limiting_exclusion and status != "unavailable":
        if status != "partial":
            errors.append(_error("response.status", "$.status", "limited or unread documents require partial status"))
        if not truncated:
            errors.append(_error("response.budget", "$.budgetUsed.truncated", "limited or unread documents require truncation"))
    if status == "complete" and (unknown or has_errors or truncated or any(isinstance(item, dict) and item.get("status") != "answered" for item in answers)):
        errors.append(_error("response.status", "$.status", "complete requires every answer answered, no errors, and no truncation"))
    if status == "partial" and not (unknown or has_errors or truncated):
        errors.append(_error("response.status", "$.status", "partial requires an unknown answer, error, or truncation"))
    if status == "unavailable":
        if not has_errors:
            errors.append(_error("response.status", "$.errors", "unavailable requires at least one error"))
        if selected:
            errors.append(_error("response.status", "$.selectedDocuments", "unavailable cannot select documents"))
        if isinstance(answers, list) and any(isinstance(item, dict) and item.get("status") == "answered" for item in answers):
            errors.append(_error("response.status", "$.answers", "unavailable cannot contain answered claims"))
        if conflicts:
            errors.append(_error("response.status", "$.conflicts", "unavailable cannot contain conflicts"))
        for field in ("requiredChecks", "affectedDocuments"):
            if response.get(field):
                errors.append(_error("response.status", "$.{}".format(field), "unavailable cannot contain claims"))

    if isinstance(budget, dict) and isinstance(selected, list):
        byte_values = [item.get("bytes") for item in selected if isinstance(item, dict)]
        if all(isinstance(item, int) and not isinstance(item, bool) for item in byte_values):
            if budget.get("documentBytes") != sum(byte_values):
                errors.append(_error("response.budget", "$.budgetUsed.documentBytes", "must equal selected document byte sum"))
        if budget.get("documents") != len(selected):
            errors.append(_error("response.budget", "$.budgetUsed.documents", "must equal selected document count"))
        max_documents = budget.get("maxDocuments")
        max_bytes = budget.get("maxBytes")
        if isinstance(max_documents, int) and not isinstance(max_documents, bool) and len(selected) > max_documents:
            errors.append(_error("response.budget", "$.budgetUsed.maxDocuments", "selected document count exceeds the limit"))
        if isinstance(max_bytes, int) and not isinstance(max_bytes, bool):
            manifest_bytes = budget.get("manifestBytes")
            document_bytes = budget.get("documentBytes")
            if isinstance(manifest_bytes, int) and isinstance(document_bytes, int) and manifest_bytes + document_bytes > max_bytes:
                exception = manifest_bytes > max_bytes and not selected and document_bytes == 0 and budget.get("truncated") is True
                if not exception:
                    errors.append(_error("response.budget", "$.budgetUsed.maxBytes", "manifest and selected documents exceed the byte limit"))

    affected = response.get("affectedDocuments", [])
    document_ids = {
        item.get("id")
        for item in list(selected if isinstance(selected, list) else []) + list(excluded if isinstance(excluded, list) else [])
        if isinstance(item, dict)
    }
    required_checks = response.get("requiredChecks", [])
    if isinstance(required_checks, list):
        for index, item in enumerate(required_checks):
            if not isinstance(item, dict):
                continue
            base = "$.requiredChecks[{}]".format(index)
            if item.get("documentId") not in document_ids:
                errors.append(_error("response.check-identity", base + ".documentId", "must match a selected or excluded document"))
            if item.get("basis") == "content" and not item.get("sources"):
                errors.append(_error("response.check-basis", base + ".sources", "content basis requires at least one selected source"))
            if item.get("basis") == "metadata" and item.get("sources") != []:
                errors.append(_error("response.check-basis", base + ".sources", "metadata basis requires no sources"))
    if isinstance(affected, list):
        for key in ("id", "path"):
            _add_unique_errors(affected, key, "$.affectedDocuments", errors)
        identities = {
            (item.get("id"), item.get("path"))
            for item in list(selected if isinstance(selected, list) else []) + list(excluded if isinstance(excluded, list) else [])
            if isinstance(item, dict)
        }
        for index, item in enumerate(affected):
            if not isinstance(item, dict):
                continue
            base = "$.affectedDocuments[{}]".format(index)
            if (item.get("id"), item.get("path")) not in identities:
                errors.append(_error("response.affected-identity", base, "id and path must match one selected or excluded document"))
            if item.get("basis") == "content" and not item.get("sources"):
                errors.append(_error("response.affected-basis", base + ".sources", "content basis requires at least one selected source"))
            if item.get("basis") == "metadata" and item.get("sources") != []:
                errors.append(_error("response.affected-basis", base + ".sources", "metadata basis is an inference and requires no sources"))

    if request is not _MISSING:
        request_errors = validate_request(request)
        if request_errors:
            if status != "unavailable":
                errors.append(_error("response.request", "$.status", "an invalid request requires an unavailable response"))
            safe = _safe_request_fields(request) if isinstance(request, dict) else {
                "requestId": None,
                "mode": None,
                "root": None,
                "maxDocuments": None,
                "maxBytes": None,
            }
            for field in ("requestId", "mode", "root"):
                if response.get(field) != safe[field]:
                    errors.append(_error("response.echo", "$.{}".format(field), "must safely echo the request field or null"))
            if isinstance(budget, dict):
                for field in ("maxDocuments", "maxBytes"):
                    if budget.get(field) != safe[field]:
                        errors.append(_error("response.echo", "$.budgetUsed.{}".format(field), "must safely echo the request limit or null"))
            if answers != []:
                errors.append(_error("response.request", "$.answers", "an invalid request response must omit question claims"))
            if excluded != []:
                errors.append(_error("response.request", "$.excludedDocuments", "an invalid request response cannot contain catalog claims"))
            if conflicts != []:
                errors.append(_error("response.request", "$.conflicts", "an invalid request response cannot contain factual claims"))
            for field in ("requiredChecks", "affectedDocuments"):
                if response.get(field):
                    errors.append(_error("response.request", "$.{}".format(field), "an invalid request response cannot contain claims"))
            if isinstance(budget, dict):
                for field in ("manifestBytes", "documentBytes", "documents"):
                    if budget.get(field) != 0:
                        errors.append(_error("response.request", "$.budgetUsed.{}".format(field), "must be zero for an invalid request"))
                if budget.get("truncated") is not False:
                    errors.append(_error("response.request", "$.budgetUsed.truncated", "must be false for an invalid request"))
            if isinstance(errors_value, list):
                for index, item in enumerate(errors_value):
                    if isinstance(item, dict) and item.get("path") != "$":
                        errors.append(_error("response.request", "$.errors[{}].path".format(index), "request errors must use '$'"))
        else:
            expected = {
                "requestId": request["requestId"],
                "mode": request["mode"],
                "root": request["root"],
            }
            for field, value in expected.items():
                if response.get(field) != value:
                    errors.append(_error("response.echo", "$.{}".format(field), "must exactly echo the request"))
            if isinstance(budget, dict):
                for field in ("maxDocuments", "maxBytes"):
                    if budget.get(field) != request["budget"][field]:
                        errors.append(_error("response.echo", "$.budgetUsed.{}".format(field), "must exactly echo the request budget"))
            expected_ids = [item["id"] for item in request["questions"]]
            actual_ids = [item.get("questionId") for item in answers if isinstance(item, dict)] if isinstance(answers, list) else []
            if actual_ids != expected_ids:
                errors.append(_error("response.questions", "$.answers", "must cover request questions once and in request order"))
    return errors
