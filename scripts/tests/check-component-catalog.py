#!/usr/bin/env python3
"""Validate the component catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HOSTS = ("codex",)


def load_catalog(root: Path) -> dict:
    with (root / "components.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(root: Path, catalog: dict) -> int:
    errors: list[str] = []
    if catalog.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    marketplaces = catalog.get("marketplaces", {})
    if set(marketplaces) != {"codex"}:
        errors.append("marketplaces must contain only codex")
    if marketplaces.get("codex") != "hukuhaka-harness":
        errors.append("Codex marketplace name must be hukuhaka-harness")
    components = catalog.get("components", [])
    names = [component.get("name") for component in components]
    if len(names) != len(set(names)):
        errors.append("component names must be unique")
    aliases: list[str] = []

    known_manifests: set[Path] = set()
    for component in components:
        name = component.get("name", "<unnamed>")
        component_aliases = component.get("aliases", [])
        if not isinstance(component_aliases, list) or any(
            not isinstance(alias, str) or not alias for alias in component_aliases
        ):
            errors.append(f"{name}: aliases must be an array of non-empty strings")
            component_aliases = []
        aliases.extend(component_aliases)
        if component.get("kind") not in {
            "plugin",
            "skill",
            "feature",
            "template",
            "agent",
        }:
            errors.append(f"{name}: unsupported kind")
        if component.get("lifecycle") not in {"supported", "deprecated"}:
            errors.append(f"{name}: unsupported lifecycle")
        if component.get("lifecycle") == "deprecated" and component.get("default") is True:
            errors.append(f"{name}: deprecated components cannot be default-on")
        hosts = component.get("hosts", {})
        if not hosts or any(host not in HOSTS for host in hosts):
            errors.append(f"{name}: hosts must contain only codex")
        versions: set[str] = set()
        for host, metadata in hosts.items():
            manifest = metadata.get("manifest")
            if not manifest:
                continue
            path = root / manifest
            known_manifests.add(path.resolve())
            if not path.is_file():
                errors.append(f"{name}: missing {host} manifest {manifest}")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{name}: invalid {host} manifest: {exc}")
                continue
            if data.get("name") != name:
                errors.append(f"{name}: {host} manifest name differs")
            version = data.get("version")
            if not version:
                errors.append(f"{name}: {host} manifest has no version")
            else:
                versions.add(version)
        if len(versions) > 1:
            errors.append(f"{name}: host manifest versions differ")
        path_value = component.get("path")
        if path_value and not (root / path_value).is_file():
            errors.append(f"{name}: missing path {path_value}")
        if "routingPath" in component:
            errors.append(f"{name}: routingPath is retired; agents do not install global guidance")
        resources = component.get("resources", [])
        if not isinstance(resources, list):
            errors.append(f"{name}: resources must be an array")
        else:
            for resource in resources:
                if not isinstance(resource, dict) or set(resource) != {"source", "target"}:
                    errors.append(f"{name}: invalid resource entry")
                    continue
                source = resource.get("source")
                target = resource.get("target")
                if (
                    not isinstance(source, str)
                    or source.startswith("/")
                    or "\\" in source
                    or any(part in {"", ".", ".."} for part in source.split("/"))
                    or not (root / source).is_file()
                ):
                    errors.append(f"{name}: missing resource source {source}")
                if (
                    not isinstance(target, str)
                    or target.startswith("/")
                    or "\\" in target
                    or any(part in {"", ".", ".."} for part in target.split("/"))
                ):
                    errors.append(f"{name}: invalid resource target {target}")

    identities = [str(name) for name in names] + aliases
    if len(identities) != len(set(identities)):
        errors.append("component names and aliases must be globally unique")

    discovered = {
        path.resolve()
        for path in root.glob("marketplace/*/.codex-plugin/plugin.json")
    }
    for path in sorted(discovered - known_manifests):
        errors.append(f"uncatalogued manifest: {path.relative_to(root)}")
    for path in sorted(root.glob("marketplace/*/.claude-plugin/plugin.json")):
        errors.append(f"unsupported Claude manifest: {path.relative_to(root)}")

    marketplace_path = root / ".agents/plugins/marketplace.json"
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid Codex marketplace: {exc}")
    else:
        if marketplace.get("name") != marketplaces.get("codex"):
            errors.append("Codex marketplace name differs from component catalog")
        exposed = {entry.get("name") for entry in marketplace.get("plugins", [])}
        expected = {
            component["name"]
            for component in components
            if component.get("kind") == "plugin"
            and component.get("lifecycle") == "supported"
            and "codex" in component.get("hosts", {})
        }
        if exposed != expected:
            errors.append(f"Codex marketplace entries {sorted(exposed)} != catalog {sorted(expected)}")

    if errors:
        for error in errors:
            print(f"component-catalog: {error}", file=sys.stderr)
        return 1
    print(f"component-catalog: {len(components)} component(s) consistent")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    catalog = load_catalog(root)
    return validate(root, catalog)


if __name__ == "__main__":
    raise SystemExit(main())
