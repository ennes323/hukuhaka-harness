#!/usr/bin/env python3
"""Validate the repository's supported plugin manifest, skill metadata, and hook subset."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH_FIELDS = ("skills", "hooks", "mcpServers", "apps", "agents")
CODEX_HOOK_EVENTS = {
    "PermissionRequest",
    "PostCompact",
    "PostToolUse",
    "PreCompact",
    "PreToolUse",
    "SessionEnd",
    "SessionStart",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "UserPromptSubmit",
}
CLAUDE_HOOK_EVENTS = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PostToolUseFailure", "PermissionRequest", "Notification", "Stop",
    "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
    "TeammateIdle", "TaskCompleted", "InstructionsLoaded",
}
NO_MATCHER_EVENTS = {"Stop", "UserPromptSubmit"}
ROOT_PLACEHOLDER_RE = re.compile(r"\$\{(?:PLUGIN_ROOT|CLAUDE_PLUGIN_ROOT)\}/([^\s\"']+)")


class ContractError(ValueError):
    pass


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None


def validate_profile(path: Path, name: str) -> list[str]:
    """Check deployable defaults without asserting live provider capabilities."""
    errors: list[str] = []
    data = load_json(path, errors)
    if not isinstance(data, dict):
        errors.append(f"{path}: profile must be an object")
        return errors
    required = {"name", "provider", "model", "modeId", "notes"}
    allowed = required | {"thinkingOptionId", "featureValues"}
    require(required <= set(data) <= allowed,
            f"{path}: profile fields must be launch defaults without runtime IDs", errors)
    for key in required | ({"thinkingOptionId"} & set(data)):
        value = data.get(key)
        require(isinstance(value, str) and bool(value.strip()),
                f"{path}: {key} must be a non-empty string", errors)
    require(data.get("name") == name, f"{path}: profile name differs from catalog", errors)
    features = data.get("featureValues")
    if "featureValues" in data:
        require(isinstance(features, dict) and all(
            isinstance(key, str) and bool(key) and isinstance(value, bool)
            for key, value in features.items()),
            f"{path}: featureValues must map feature names to booleans", errors)
    require(re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                      json.dumps(data), re.IGNORECASE) is None,
            f"{path}: source defaults must not contain UUIDs", errors)
    return errors


def parse_scalar(raw: str, *, line_number: int) -> object:
    value = raw.strip()
    if not value:
        raise ContractError(f"line {line_number}: missing scalar value")
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractError(f"line {line_number}: malformed quoted scalar: {exc.msg}") from exc
        if not isinstance(parsed, str):
            raise ContractError(f"line {line_number}: expected a string scalar")
        return parsed
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    raise ContractError(f"line {line_number}: scalars must be quoted strings or booleans")


def parse_openai_yaml(path: Path) -> dict[str, object]:
    """Parse the intentionally small mapping-only YAML subset used by this repo."""

    text = path.read_text(encoding="utf-8")
    if "\t" in text:
        raise ContractError("tabs are not allowed")
    result: dict[str, object] = {}
    active: dict[str, object] | None = None
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  "):
            if raw_line.startswith("    ") or active is None:
                raise ContractError(f"line {line_number}: only one nested mapping level is supported")
            match = re.fullmatch(r"  ([a-z_][a-z0-9_]*):\s*(.+)", raw_line)
            if not match:
                raise ContractError(f"line {line_number}: malformed nested mapping entry")
            key, raw_value = match.groups()
            if key in active:
                raise ContractError(f"line {line_number}: duplicate key {key}")
            active[key] = parse_scalar(raw_value, line_number=line_number)
            continue
        match = re.fullmatch(r"([a-z_][a-z0-9_]*):\s*", raw_line)
        if not match:
            raise ContractError(f"line {line_number}: expected a top-level mapping")
        key = match.group(1)
        if key in result:
            raise ContractError(f"line {line_number}: duplicate key {key}")
        active = {}
        result[key] = active
    return result


def validate_openai_yaml(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = parse_openai_yaml(path)
    except (OSError, UnicodeDecodeError, ContractError) as exc:
        return [f"{path}: invalid agents/openai.yaml: {exc}"]
    require(set(data) <= {"interface", "policy"}, f"{path}: unsupported top-level key", errors)
    interface = data.get("interface")
    require(isinstance(interface, dict), f"{path}: interface mapping is required", errors)
    if isinstance(interface, dict):
        allowed = {
            "brand_color",
            "default_prompt",
            "display_name",
            "icon_large",
            "icon_small",
            "short_description",
        }
        require(set(interface) <= allowed, f"{path}: unsupported interface key", errors)
        for key in ("display_name", "short_description"):
            value = interface.get(key)
            require(isinstance(value, str) and bool(value.strip()), f"{path}: interface.{key} is required", errors)
        default_prompt = interface.get("default_prompt")
        if default_prompt is not None:
            require(
                isinstance(default_prompt, str) and bool(default_prompt.strip()),
                f"{path}: interface.default_prompt must be a non-empty string",
                errors,
            )
        brand_color = interface.get("brand_color")
        if brand_color is not None:
            require(
                isinstance(brand_color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color) is not None,
                f"{path}: interface.brand_color must be a six-digit hex color",
                errors,
            )
    policy = data.get("policy")
    if policy is not None:
        require(isinstance(policy, dict), f"{path}: policy must be a mapping", errors)
        if isinstance(policy, dict):
            require(set(policy) <= {"allow_implicit_invocation"}, f"{path}: unsupported policy key", errors)
            require(
                isinstance(policy.get("allow_implicit_invocation"), bool),
                f"{path}: policy.allow_implicit_invocation must be boolean",
                errors,
            )
    return errors


def resolve_plugin_path(plugin_root: Path, value: str, label: str, errors: list[str]) -> Path | None:
    require(value.startswith("./"), f"{label}: path must start with ./", errors)
    if not value.startswith("./"):
        return None
    resolved = (plugin_root / value).resolve()
    try:
        resolved.relative_to(plugin_root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes plugin root")
        return None
    require(resolved.exists(), f"{label}: declared path does not exist", errors)
    return resolved


def validate_hook_file(path: Path, hosts: set[str], errors: list[str]) -> None:
    data = load_json(path, errors)
    if not isinstance(data, dict):
        return
    groups = data.get("hooks")
    require(isinstance(groups, dict) and bool(groups), f"{path}: hooks must be a non-empty object", errors)
    if not isinstance(groups, dict):
        return
    require(len(hosts) == 1 and hosts <= {"codex", "claude"}, f"{path}: hooks must belong to one supported host", errors)
    allowed_events = CODEX_HOOK_EVENTS if hosts == {"codex"} else CLAUDE_HOOK_EVENTS
    for event, matcher_groups in groups.items():
        require(event in allowed_events, f"{path}: unsupported {sorted(hosts)} hook event {event}", errors)
        require(isinstance(matcher_groups, list) and bool(matcher_groups), f"{path}: {event} must be a non-empty array", errors)
        if not isinstance(matcher_groups, list):
            continue
        for group_index, group in enumerate(matcher_groups):
            label = f"{path}: {event}[{group_index}]"
            require(isinstance(group, dict), f"{label} must be an object", errors)
            if not isinstance(group, dict):
                continue
            if event in NO_MATCHER_EVENTS:
                require("matcher" not in group, f"{label}: matcher is unsupported for {event}", errors)
            elif "matcher" in group:
                require(isinstance(group["matcher"], str), f"{label}: matcher must be a string", errors)
            handlers = group.get("hooks")
            require(isinstance(handlers, list) and bool(handlers), f"{label}: hooks must be a non-empty array", errors)
            if not isinstance(handlers, list):
                continue
            for handler_index, handler in enumerate(handlers):
                handler_label = f"{label}.hooks[{handler_index}]"
                require(isinstance(handler, dict), f"{handler_label} must be an object", errors)
                if not isinstance(handler, dict):
                    continue
                require(handler.get("type") == "command", f"{handler_label}: only command hooks are supported", errors)
                command = handler.get("command")
                require(isinstance(command, str) and bool(command.strip()), f"{handler_label}: command is required", errors)
                timeout = handler.get("timeout")
                if timeout is not None:
                    require(isinstance(timeout, int) and timeout > 0, f"{handler_label}: timeout must be positive", errors)
                if isinstance(command, str):
                    require(
                        ("${CLAUDE_PLUGIN_ROOT}" not in command if hosts == {"codex"} else "${PLUGIN_ROOT}" not in command),
                        f"{handler_label}: plugin-root variable belongs to another host",
                        errors,
                    )
                    for match in ROOT_PLACEHOLDER_RE.finditer(command):
                        target = (path.parent.parent / match.group(1)).resolve()
                        require(target.is_file(), f"{handler_label}: referenced script does not exist: {match.group(1)}", errors)


def validate_repository(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    catalog_path = root / "components.json"
    catalog = load_json(catalog_path, errors)
    if not isinstance(catalog, dict):
        return errors

    hook_hosts: dict[Path, set[str]] = {}
    for component in catalog.get("components", []):
        if isinstance(component, dict) and component.get("kind") == "profile":
            errors.extend(validate_profile(root / str(component.get("path", "")),
                                           str(component.get("name", ""))))
        if not isinstance(component, dict) or component.get("kind") != "plugin":
            continue
        component_name = component.get("name")
        for host, metadata in component.get("hosts", {}).items():
            if not isinstance(metadata, dict) or "manifest" not in metadata:
                continue
            manifest_path = root / str(metadata["manifest"])
            manifest = load_json(manifest_path, errors)
            if not isinstance(manifest, dict):
                continue
            label = str(manifest_path.relative_to(root))
            for key in ("name", "version", "description"):
                value = manifest.get(key)
                require(isinstance(value, str) and bool(value.strip()), f"{label}: {key} is required", errors)
            require(manifest.get("name") == component_name, f"{label}: name differs from components.json", errors)
            plugin_root = manifest_path.parent.parent
            for key in PLUGIN_PATH_FIELDS:
                value = manifest.get(key)
                if value is None:
                    continue
                values = value if key == "agents" and host == "claude" and isinstance(value, list) else [value]
                for item in values:
                    require(isinstance(item, str), f"{label}: {key} must contain path strings", errors)
                    if not isinstance(item, str):
                        continue
                    resolved = resolve_plugin_path(plugin_root, item, f"{label}: {key}", errors)
                    if key == "agents":
                        require(host == "claude", f"{label}: packaged agents belong only to Claude", errors)
                        require(resolved is not None and resolved.is_file() and resolved.suffix == ".md",
                                f"{label}: Claude agents must be Markdown file paths", errors)
                    if key == "hooks" and resolved is not None and resolved.is_file():
                        require(item == f"./hooks/{host}.json", f"{label}: hook declaration must use its host-specific file", errors)
                        hook_hosts.setdefault(resolved, set()).add(host)
            if host == "codex":
                interface = manifest.get("interface")
                require(isinstance(interface, dict), f"{label}: Codex interface metadata is required", errors)
                if isinstance(interface, dict):
                    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
                        value = interface.get(key)
                        require(isinstance(value, str) and bool(value.strip()), f"{label}: interface.{key} is required", errors)
                    capabilities = interface.get("capabilities")
                    require(
                        isinstance(capabilities, list)
                        and bool(capabilities)
                        and all(isinstance(item, str) and item for item in capabilities),
                        f"{label}: interface.capabilities must be a non-empty string array",
                        errors,
                    )

    for plugin_root in sorted((root / "marketplace").iterdir()):
        if not plugin_root.is_dir():
            continue
        default_hooks = plugin_root / "hooks" / "hooks.json"
        require(not default_hooks.exists(), f"{default_hooks}: shared default hook discovery is forbidden", errors)

    for hook_path, hosts in hook_hosts.items():
        validate_hook_file(hook_path, hosts, errors)

    for metadata_path in sorted((root / "marketplace").glob("*/skills/*/agents/openai.yaml")):
        errors.extend(validate_openai_yaml(metadata_path))

    engineering = root / "marketplace" / "hukuhaka-engineering-plan"
    codex_manifest = load_json(engineering / ".codex-plugin" / "plugin.json", errors)
    if isinstance(codex_manifest, dict):
        require(codex_manifest.get("skills") == "./skills/", "engineering-plan Codex skills path differs", errors)
    metadata_path = engineering / "skills" / "engineering-plan" / "agents" / "openai.yaml"
    if metadata_path.is_file():
        metadata = parse_openai_yaml(metadata_path)
        prompt = metadata.get("interface", {}).get("default_prompt") if isinstance(metadata.get("interface"), dict) else None
        require(isinstance(prompt, str) and "$engineering-plan" in prompt, "engineering-plan canonical Codex invocation is missing", errors)

    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"plugin-contracts: {error}", file=sys.stderr)
        return 1
    print("plugin-contracts: manifests, skill metadata, hooks, and profile defaults are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
