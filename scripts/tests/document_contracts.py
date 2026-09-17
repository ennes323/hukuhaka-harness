#!/usr/bin/env python3
"""Validate tracked Markdown links and current public documentation contracts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
CURRENT_DOCS = (
    "AGENTS.md",
    "README.md",
    "INSTALL.md",
    "docs/README.md",
    "docs/host-support.md",
    "docs/hukuhaka-project-docs/README.md",
    "docs/hukuhaka-project-docs/implementation-plan.md",
    "docs/hukuhaka-project-docs/decisions.md",
    "docs/hukuhaka-report-planner/README.md",
    "docs/hukuhaka-report-planner/craft-sources.md",
    "docs/plugin-guide/README.md",
    "docs/plugin-guide/agents-and-hooks.md",
    "docs/plugin-guide/automation-and-loops.md",
    "docs/plugin-guide/codex.md",
    "docs/plugin-guide/distribution.md",
    "docs/plugin-guide/headless-and-automation.md",
    "docs/plugin-guide/plugins.md",
    "docs/plugin-guide/skill-design.md",
    "docs/plugin-guide/skills.md",
    "docs/plugin-guide/team-coordination.md",
    "docs/scripts/README.md",
)


def required_current_docs(root: Path) -> tuple[str, ...]:
    """Require repository instructions only in the private source checkout."""
    if (root / "scripts" / "release" / "main.py").is_file():
        return CURRENT_DOCS
    return tuple(relative for relative in CURRENT_DOCS if relative != "AGENTS.md")


def markdown_slug(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("`", "").strip().lower()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"[ -]+", "-", value).strip("-")


def tracked_markdown(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return [
            root / item.decode()
            for item in result.stdout.split(b"\0")
            if item and (root / item.decode()).is_file()
        ]
    # Staged public candidates are intentionally plain directories rather than
    # Git checkouts. Every Markdown file there came from the public allow-list,
    # so the filesystem is the exact validation surface.
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def validate_links(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    heading_cache: dict[Path, set[str]] = {}
    for path in tracked_markdown(root):
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "app://")):
                continue
            target_path, separator, anchor = target.partition("#")
            target_path = unquote(target_path.split("?", 1)[0])
            resolved = path if not target_path else (path.parent / target_path).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path.relative_to(root)}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{path.relative_to(root)}: missing link target: {target}")
                continue
            if separator and anchor and resolved.is_file() and resolved.suffix.lower() == ".md":
                if resolved not in heading_cache:
                    headings = HEADING_RE.findall(resolved.read_text(encoding="utf-8"))
                    heading_cache[resolved] = {markdown_slug(heading) for heading in headings}
                if unquote(anchor).lower() not in heading_cache[resolved]:
                    errors.append(f"{path.relative_to(root)}: missing anchor: {target}")
    return errors


def validate_current_docs(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifests: dict[str, str] = {}
    catalog = json.loads((root / "components.json").read_text(encoding="utf-8"))
    for component in catalog.get("components", []):
        if component.get("kind") != "plugin":
            continue
        versions = set()
        metadata = component.get("hosts", {}).get("codex", {})
        manifest = metadata.get("manifest")
        if manifest:
            versions.add(json.loads((root / manifest).read_text(encoding="utf-8"))["version"])
        if len(versions) == 1:
            manifests[component["name"]] = versions.pop()

    readme = (root / "README.md").read_text(encoding="utf-8")
    errors.extend(validate_project_docs_status(root, catalog, readme))
    for name, version in manifests.items():
        row = next((line for line in readme.splitlines() if line.startswith(f"| **{name}** |")), "")
        if f"| `{version}` |" not in row and f"| <code>{version}</code> |" not in row:
            errors.append(f"README.md: {name} version differs from manifest {version}")

    errors.extend(validate_codex_only_docs(root))
    for relative in required_current_docs(root):
        path = root / relative
        if not path.is_file():
            if relative.startswith("docs/") and not (root / "docs").exists():
                continue
            errors.append(f"{relative}: required current document is missing")
            continue
        text = path.read_text(encoding="utf-8")
        for stale in ("models-luna-v2.json", "model_catalog_json"):
            if stale in text:
                errors.append(f"{relative}: current contract contains obsolete Luna term {stale}")

    public_paths = [root / name for name in ("README.md", "INSTALL.md") if (root / name).is_file()]
    public_paths += sorted((root / "marketplace").glob("*/README.md"))
    for path in public_paths:
        text = path.read_text(encoding="utf-8")
        if re.search(r"\]\((?:\.\./)*docs/", text):
            errors.append(f"{path.relative_to(root)}: public document links to private docs/")
    return errors


def validate_codex_only_docs(root: Path = ROOT) -> list[str]:
    """Keep the active instruction and documentation surface Codex-only."""
    errors: list[str] = []
    if (root / "CLAUDE.md").exists():
        errors.append("CLAUDE.md: retired root instruction file must not remain")
    if (root / "docs" / "hukuhaka-codex").exists():
        errors.append("docs/hukuhaka-codex: retired maintenance records must live under docs/archive")
    for relative in CURRENT_DOCS:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bClaude(?: Code)?\b", text, re.IGNORECASE):
            errors.append(f"{relative}: active document contains retired host reference")
    return errors


def validate_project_docs_status(root: Path, catalog: dict, readme: str) -> list[str]:
    """Keep experimental maturity separate from native install support."""
    errors: list[str] = []
    components = {item["name"]: item for item in catalog.get("components", [])}
    for name, label in (
        ("hukuhaka-project-docs", "hukuhaka-project-docs"),
        ("project-doc-reader", "Project Doc Reader"),
    ):
        component = components.get(name, {})
        if component.get("default") is not False or component.get("lifecycle") != "supported":
            errors.append(f"components.json: {name} must retain supported installation and opt-in default")
        row = next((line for line in readme.splitlines() if line.startswith(f"| **{label}** |")), "")
        if "Experimental / opt-in" not in row or "Codex" not in row:
            errors.append(f"README.md: {name} must be experimental / opt-in and Codex-only")

    for relative in (
        "docs/README.md",
        "docs/host-support.md",
        "docs/hukuhaka-project-docs/README.md",
        "docs/hukuhaka-project-docs/implementation-plan.md",
        "docs/hukuhaka-project-docs/decisions.md",
    ):
        path = root / relative
        if not path.is_file():
            continue  # CURRENT_DOCS enforces presence in private checkouts.
        text = path.read_text(encoding="utf-8")
        if "experimental / opt-in" not in text.lower():
            errors.append(f"{relative}: missing Project Docs experimental / opt-in status")
        if re.search(r"human (?:quality )?verdict pending", text, re.IGNORECASE):
            errors.append(f"{relative}: Project Docs pilot verdict is stale")
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    return validate_links(root) + validate_current_docs(root)


def main() -> int:
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"document-contracts: {error}", file=sys.stderr)
        return 1
    print("document-contracts: tracked links, versions, and current-doc boundaries are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
