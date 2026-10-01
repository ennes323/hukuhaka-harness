#!/usr/bin/env python3
"""Validate the declared native-host component boundaries."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "marketplace" / "hukuhaka-report-planner"
WORKLOG = ROOT / "marketplace" / "hukuhaka-worklog"
MEMORY_AUDIT = ROOT / "marketplace" / "hukuhaka-memory-audit"
PROJECT_DOCS = ROOT / "marketplace" / "hukuhaka-project-docs"
UIUX_FOUNDATION = ROOT / "marketplace" / "hukuhaka-uiux-foundation"
PASEO = ROOT / "marketplace" / "hukuhaka-paseo"
CATALOG = ROOT / "components.json"
CODEX_MANIFEST = PLANNER / ".codex-plugin" / "plugin.json"
WORKLOG_CODEX_MANIFEST = WORKLOG / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL = PLANNER / "skills" / "hukuhaka-report-planner" / "SKILL.md"
WORKLOG_SKILL = WORKLOG / "skills" / "worklog" / "SKILL.md"
WORKLOG_OPENAI = WORKLOG / "skills" / "worklog" / "agents" / "openai.yaml"
WORKLOG_SCRIPT = WORKLOG / "skills" / "worklog" / "scripts" / "worklog.py"
WORKLOG_HOOKS = WORKLOG / "hooks" / "codex.json"
MEMORY_AUDIT_MANIFEST = MEMORY_AUDIT / ".codex-plugin" / "plugin.json"
MEMORY_AUDIT_SKILL = MEMORY_AUDIT / "skills" / "memory-audit" / "SKILL.md"
MEMORY_AUDIT_OPENAI = MEMORY_AUDIT / "skills" / "memory-audit" / "agents" / "openai.yaml"
MEMORY_AUDIT_HOOKS = MEMORY_AUDIT / "hooks" / "codex.json"
MEMORY_AUDIT_SCRIPT = MEMORY_AUDIT / "scripts" / "memory_pressure_hook.py"
PROJECT_DOCS_MANIFEST = PROJECT_DOCS / ".codex-plugin" / "plugin.json"
PROJECT_DOCS_SKILL = PROJECT_DOCS / "skills" / "project-docs" / "SKILL.md"
UIUX_MANIFEST = UIUX_FOUNDATION / ".codex-plugin" / "plugin.json"
UIUX_SKILL = UIUX_FOUNDATION / "skills" / "uiux-foundation" / "SKILL.md"
UIUX_OPENAI = UIUX_FOUNDATION / "skills" / "uiux-foundation" / "agents" / "openai.yaml"
HOST_SUPPORT = ROOT / "docs" / "host-support.md"
DESIGNER_SKILL = PLANNER / "skills" / "artifact-designer" / "SKILL.md"
BUILD_HANDOFF = PLANNER / "skills" / "hukuhaka-report-planner" / "references" / "build-handoff.md"
DESIGN_SCHEMA = PLANNER / "skills" / "artifact-designer" / "references" / "design-schema.md"
PLAN_COMPATIBILITY = PLANNER / "skills" / "hukuhaka-report-planner" / "references" / "plan-compatibility.md"
AGENTS_TEMPLATE = ROOT / "templates" / "AGENTS.md"
ASTRA_WORKER = ROOT / "agents" / "astra_worker.toml"
EVIDENCE_SCOUT = ROOT / "agents" / "evidence-scout.toml"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def readme_row(readme: str, name: str) -> str:
    return next((line for line in readme.splitlines() if line.startswith(f"| **{name}** |")), "")


def main() -> int:
    errors: list[str] = []

    for path in (
        CATALOG,
        CODEX_MANIFEST,
        WORKLOG_CODEX_MANIFEST,
        MARKETPLACE,
        SKILL,
        WORKLOG_SKILL,
        WORKLOG_OPENAI,
        WORKLOG_SCRIPT,
        WORKLOG_HOOKS,
        MEMORY_AUDIT_MANIFEST,
        MEMORY_AUDIT_SKILL,
        MEMORY_AUDIT_OPENAI,
        MEMORY_AUDIT_HOOKS,
        MEMORY_AUDIT_SCRIPT,
        PROJECT_DOCS_MANIFEST,
        PROJECT_DOCS_SKILL,
        UIUX_MANIFEST,
        UIUX_SKILL,
        UIUX_OPENAI,
        DESIGNER_SKILL,
        BUILD_HANDOFF,
        DESIGN_SCHEMA,
        PLAN_COMPATIBILITY,
        AGENTS_TEMPLATE,
        ASTRA_WORKER,
        EVIDENCE_SCOUT,
    ):
        require(path.is_file(), f"missing required Codex file: {path.relative_to(ROOT)}", errors)
    if errors:
        return report(errors)

    codex = load_json(CODEX_MANIFEST)
    worklog_codex = load_json(WORKLOG_CODEX_MANIFEST)
    catalog = load_json(CATALOG)
    marketplace = load_json(MARKETPLACE)
    skill = SKILL.read_text(encoding="utf-8")
    worklog_skill = WORKLOG_SKILL.read_text(encoding="utf-8")
    worklog_openai = WORKLOG_OPENAI.read_text(encoding="utf-8")
    worklog_script = WORKLOG_SCRIPT.read_text(encoding="utf-8")
    worklog_hooks = load_json(WORKLOG_HOOKS)
    memory_audit_manifest = load_json(MEMORY_AUDIT_MANIFEST)
    memory_audit_skill = MEMORY_AUDIT_SKILL.read_text(encoding="utf-8")
    memory_audit_openai = MEMORY_AUDIT_OPENAI.read_text(encoding="utf-8")
    memory_audit_hooks = load_json(MEMORY_AUDIT_HOOKS)
    memory_audit_script = MEMORY_AUDIT_SCRIPT.read_text(encoding="utf-8")
    project_docs_manifest = load_json(PROJECT_DOCS_MANIFEST)
    project_docs_skill = PROJECT_DOCS_SKILL.read_text(encoding="utf-8")
    uiux_manifest = load_json(UIUX_MANIFEST)
    uiux_skill = UIUX_SKILL.read_text(encoding="utf-8")
    uiux_openai = UIUX_OPENAI.read_text(encoding="utf-8")
    host_support = HOST_SUPPORT.read_text(encoding="utf-8") if HOST_SUPPORT.is_file() else ""
    designer_skill = DESIGNER_SKILL.read_text(encoding="utf-8")
    build_handoff = BUILD_HANDOFF.read_text(encoding="utf-8")
    design_schema = DESIGN_SCHEMA.read_text(encoding="utf-8")
    plan_compatibility = PLAN_COMPATIBILITY.read_text(encoding="utf-8")
    agents_template = AGENTS_TEMPLATE.read_text(encoding="utf-8")
    astra_worker = ASTRA_WORKER.read_text(encoding="utf-8")
    evidence_scout = EVIDENCE_SCOUT.read_text(encoding="utf-8")

    require(codex.get("name") == "hukuhaka-report-planner",
            "report-planner Codex manifest name differs from its catalog identity", errors)
    require(worklog_codex.get("skills") == "./skills/",
            "worklog manifest must expose the shared ./skills/ tree", errors)
    require(codex.get("skills") == "./skills/",
            "report-planner manifest must expose the shared ./skills/ tree", errors)
    require("agents" not in codex, "Codex manifest must not claim unsupported packaged agents", errors)
    require(worklog_codex.get("name") == "hukuhaka-worklog",
            "worklog Codex manifest name differs from its catalog identity", errors)
    require(worklog_codex.get("version") == "0.5.1",
            "worklog plugin version must be 0.5.1", errors)
    require(worklog_codex.get("hooks") == "./hooks/codex.json",
            "worklog must explicitly select Codex hooks", errors)

    catalog_check = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/tests/check-component-catalog.py"),
            "--root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
    )
    require(catalog_check.returncode == 0, catalog_check.stderr.strip() or "component catalog validation failed", errors)

    components = {component["name"]: component for component in catalog.get("components", [])}
    paseo_component = components.get("hukuhaka-paseo", {})
    require(paseo_component.get("kind") == "plugin" and paseo_component.get("default") is False
            and set(paseo_component.get("hosts", {})) == {"codex", "claude"},
            "Paseo coordination must be an optional dual-host plugin", errors)
    for host in ("codex", "claude"):
        paseo_manifest_path = PASEO / f".{host}-plugin/plugin.json"
        require(paseo_manifest_path.is_file(), f"missing Paseo {host} manifest", errors)
        if paseo_manifest_path.is_file():
            paseo_manifest = load_json(paseo_manifest_path)
            require(paseo_manifest.get("skills") == "./skills/"
                    and paseo_manifest.get("version") == "0.1.0"
                    and not any(key in paseo_manifest for key in ("hooks", "agents", "mcpServers")),
                    f"Paseo {host} package must expose guidance without runtime interception", errors)
    profiles = [component for component in components.values() if component.get("kind") == "profile"]
    require({component["name"] for component in profiles} == {
        "advisor-gpt", "advisor-claude", "worker", "scouter", "designer", "writer", "vision"},
        "Paseo profile catalog differs from the seven approved defaults", errors)
    for profile in profiles:
        require(profile.get("default") is True and set(profile.get("hosts", {})) == {"paseo"},
                f"{profile['name']}: must be a recommended Paseo-only profile", errors)
    for component in components.values():
        if component.get("kind") == "plugin" and component.get("lifecycle") == "supported":
            require(set(component.get("hosts", {})) == {"codex", "claude"},
                    f"{component['name']}: must expose both native hosts", errors)
    claude_template = components.get("claude-md", {})
    require(claude_template.get("default") is True and claude_template.get("path") == "templates/CLAUDE.md"
            and set(claude_template.get("hosts", {})) == {"claude"},
            "claude-md must be the default Claude-only template", errors)
    claude_guidance = (ROOT / "templates/CLAUDE.md").read_text(encoding="utf-8")
    require("# Subagents" not in claude_guidance and "visualize" not in claude_guidance
            and "astra_worker" not in claude_guidance and "evidence-scout" not in claude_guidance,
            "Claude guidance must exclude Codex specialists and global visualization", errors)
    memory_claude = load_json(MEMORY_AUDIT / ".claude-plugin/plugin.json")
    require("hooks" not in memory_claude, "Claude memory audit must rely on native warning without pressure hooks", errors)
    memory_component = components.get("hukuhaka-memory-audit", {})
    require(memory_component.get("kind") == "plugin",
            "memory audit must be catalogued as a plugin", errors)
    require(memory_component.get("default") is False,
            "memory audit must remain opt-in", errors)
    require(set(memory_component.get("hosts", {})) == {"codex", "claude"},
            "memory audit must expose both native hosts", errors)
    require(memory_audit_manifest.get("version") == "0.2.1",
            "memory audit plugin version must be 0.2.1", errors)
    require(memory_audit_manifest.get("skills") == "./skills/",
            "memory audit manifest must expose its Skill", errors)
    require(memory_audit_manifest.get("hooks") == "./hooks/codex.json",
            "memory audit must explicitly select Codex hooks", errors)
    scout_component = components.get("evidence-scout", {})
    require(scout_component.get("kind") == "agent" and scout_component.get("default") is False,
            "evidence-scout must be an optional agent", errors)
    require(set(scout_component.get("hosts", {})) == {"codex"},
            "evidence-scout must be Codex-only", errors)
    require(scout_component.get("path") == "agents/evidence-scout.toml",
            "evidence-scout source differs", errors)
    worker_component = components.get("astra_worker", {})
    require(worker_component.get("kind") == "agent" and worker_component.get("default") is False,
            "astra_worker must be an optional agent", errors)
    require(set(worker_component.get("hosts", {})) == {"codex"},
            "astra_worker must be Codex-only", errors)
    require(worker_component.get("path") == "agents/astra_worker.toml",
            "astra_worker source differs", errors)
    runner_component = components.get("result-runner", {})
    require(set(runner_component.get("hosts", {})) == {"codex"},
            "result-runner must be Codex-only", errors)
    require(runner_component.get("kind") == "agent" and runner_component.get("default") is False,
            "result-runner must be an optional agent", errors)
    require(runner_component.get("path") == "agents/result-runner.toml",
            "result-runner source differs", errors)
    for component in components.values():
        if component.get("kind") == "agent":
            require("routingPath" not in component,
                    f"{component['name']}: agent must not install global routing", errors)
    require(not list((ROOT / "templates").glob("*-routing.md")),
            "obsolete agent routing templates must not be shipped", errors)
    runner_agent = (ROOT / "agents/result-runner.toml").read_text(encoding="utf-8")
    for contract in ('model = "gpt-5.6-luna"', 'model_reasoning_effort = "xhigh"',
                     "do not spawn agents", "whole-job terminal and exit evidence"):
        require(contract in runner_agent, f"result-runner contract is missing: {contract}", errors)
    for contract in (
        'name = "evidence-scout"',
        'model = "gpt-5.6-luna"',
        'model_reasoning_effort = "xhigh"',
        'sandbox_mode = "read-only"',
        "read-only",
        "parent",
    ):
        require(contract in evidence_scout,
                f"evidence-scout contract is missing: {contract}", errors)
    project_docs_component = components.get("hukuhaka-project-docs", {})
    require(project_docs_component.get("kind") == "plugin",
            "Project Docs must be catalogued as a plugin", errors)
    require(project_docs_component.get("default") is False,
            "Project Docs plugin must remain opt-in", errors)
    require(set(project_docs_component.get("hosts", {})) == {"codex", "claude"},
            "Project Docs must expose both native hosts", errors)
    require(project_docs_manifest.get("version") == "0.2.1",
            "Project Docs plugin version must be 0.2.1", errors)
    require(project_docs_manifest.get("skills") == "./skills/",
            "Project Docs manifest must expose its Skill", errors)
    uiux_component = components.get("hukuhaka-uiux-foundation", {})
    require(uiux_component.get("kind") == "plugin",
            "UI/UX Foundation must be catalogued as a plugin", errors)
    require(uiux_component.get("default") is False,
            "UI/UX Foundation must remain optional", errors)
    require(set(uiux_component.get("hosts", {})) == {"codex", "claude"},
            "UI/UX Foundation must expose both native hosts", errors)
    require(uiux_manifest.get("version") == "0.1.2",
            "UI/UX Foundation plugin version must be 0.1.2", errors)
    require(uiux_manifest.get("skills") == "./skills/",
            "UI/UX Foundation manifest must expose its Skill", errors)
    require("hooks" not in uiux_manifest,
            "UI/UX Foundation must not declare hooks", errors)
    require("$uiux-foundation" in str(uiux_manifest.get("interface", {}).get("defaultPrompt", "")),
            "UI/UX Foundation manifest lacks its canonical invocation", errors)
    require("$uiux-foundation" in uiux_openai,
            "UI/UX Foundation metadata lacks its canonical invocation", errors)
    require("allow_implicit_invocation: false" not in uiux_openai,
            "UI/UX Foundation must keep implicit invocation enabled", errors)
    uiux_frontmatter = re.match(r"^---\n(.*?)\n---", uiux_skill, re.DOTALL)
    require(uiux_frontmatter is not None,
            "UI/UX Foundation Skill has no frontmatter", errors)
    if uiux_frontmatter:
        require(
            re.search(r"^name:\s*uiux-foundation\s*$", uiux_frontmatter.group(1), re.MULTILINE)
            is not None,
            "UI/UX Foundation Skill name differs from its invocation",
            errors,
        )
    for reference in (
        "design-principles.md",
        "visual-design.md",
        "experience-design.md",
        "design-system.md",
        "application.md",
        "synchronization.md",
        "design-review.md",
        "verification.md",
    ):
        target = f"references/{reference}"
        require(target in uiux_skill and (UIUX_SKILL.parent / target).is_file(),
                f"UI/UX Foundation topic route is missing: {target}", errors)
    if host_support:
        require("# Host support contract" in host_support,
                "host-support docs do not declare native host support", errors)
        require("| <code>hukuhaka-uiux-foundation</code> | Native optional plugin | Native optional plugin | Supported |" in host_support,
                "host-support matrix does not declare UI/UX Foundation", errors)
        require("lifecycle hooks and commands" in host_support and "trusted by" in host_support and "Codex" in host_support,
                "host-support docs omit Codex hook trust behavior", errors)
    require("project-doc-reader" not in components,
            "retired project-doc-reader must not be installable", errors)
    require(not (ROOT / "agents/project-doc-reader.toml").exists(),
            "retired project-doc-reader role must not be distributed", errors)
    expected_codex = {
        name for name, component in components.items()
        if component.get("kind") == "plugin"
        and component.get("lifecycle") == "supported"
        and "codex" in component.get("hosts", {})
    }
    entries = marketplace.get("plugins", [])
    exposed_codex = {entry.get("name") for entry in entries}
    require(exposed_codex == expected_codex, "Codex marketplace entries differ from component catalog", errors)
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source", {})
        require(source.get("source") == "local", "Codex marketplace source must be local", errors)
        source_path = source.get("path")
        expected_path = f"./marketplace/{name}"
        require(source_path == expected_path, f"Codex marketplace path does not target {name}", errors)
        if isinstance(source_path, str):
            require((ROOT / source_path).resolve() == (ROOT / "marketplace" / str(name)).resolve(),
                    f"Codex marketplace path does not resolve to {name}", errors)

    frontmatter = re.match(r"^---\n(.*?)\n---", skill, re.DOTALL)
    require(frontmatter is not None, "report-planner skill has no frontmatter", errors)
    if frontmatter:
        header = frontmatter.group(1)
        require(re.search(r"^name:\s*hukuhaka-report-planner\s*$", header, re.MULTILINE) is not None,
                "report-planner skill name is not portable", errors)
        host_specific_keys = ("allowed-tools:", "disable-model-invocation:", "argument-hint:")
        for key in host_specific_keys:
            require(key not in header, f"report-planner frontmatter contains unsupported key: {key[:-1]}", errors)

    require("${CLAUDE_PLUGIN_ROOT}" not in skill, "report-planner skill contains a Claude-only plugin-root variable", errors)
    require("!`" not in skill, "report-planner skill contains Claude-only shell interpolation", errors)
    require(".hukuhaka/reports/<short-name>/" in skill, "host-neutral report output path contract is missing", errors)
    require("design.md" in skill, "split design output contract is missing", errors)
    require("plan-compatibility.md" in skill and "plan-compatibility.md" in designer_skill,
            "both roles must classify legacy plans before writing", errors)
    require(".claude/reports/" in plan_compatibility, "legacy report read fallback is missing", errors)
    require("Legacy paths are read-only" in plan_compatibility, "legacy report path is not explicitly read-only", errors)
    require("Never dual-write" in plan_compatibility, "dual-write prohibition is missing", errors)
    require("Never auto-load" in plan_compatibility, "uppercase DESIGN.md exclusion is missing", errors)
    require("artifact-designer" in skill, "report-planner does not route build-preflight to artifact-designer", errors)
    require("name: artifact-designer" in designer_skill, "portable artifact-designer skill is malformed", errors)
    require("Do not edit `spec.md`" in designer_skill, "designer can rewrite the finalized spec", errors)
    require("Own its Design Direction, Anchors, Build Boundaries, and Realization" in designer_skill,
            "new content plans must leave the whole design to the designer", errors)
    require("only Realization is designer-mutable" in plan_compatibility,
            "legacy paired design ownership boundary is missing", errors)
    require("Every `A#` resolves to one or more `U#`, `S#`, and `T#`" in design_schema,
            "design dependency contract is missing", errors)
    require("spec path:" in build_handoff and "selects its own craft references" in build_handoff,
            "build handoff must pass content and delegate design selection", errors)
    codex_handoff = (BUILD_HANDOFF.parent / "hosts/codex.md").read_text(encoding="utf-8")
    claude_handoff = (BUILD_HANDOFF.parent / "hosts/claude.md").read_text(encoding="utf-8")
    require("hosts/codex.md" in build_handoff and "# Codex handoff" in codex_handoff,
            "build handoff does not define the Codex worker adapter", errors)
    require("Claude Code" in build_handoff,
            "build handoff lacks its native Claude designer route", errors)
    require("write-capable worker" in codex_handoff,
            "Codex build handoff does not define its worker adapter", errors)
    require("model: gpt-5.6-terra" in codex_handoff and "reasoning_effort: high" in codex_handoff,
            "designer handoff must explicitly select Terra high", errors)
    require("fork_turns: none" in codex_handoff and "references/worker-contract.md" in codex_handoff,
            "designer handoff must pass its specialist contract in a fresh context", errors)
    require("hosts/claude.md" in build_handoff and "hukuhaka-report-planner:artifact-designer" in claude_handoff,
            "build handoff lacks the exact native Claude designer route", errors)
    worker_contract = (PLANNER / "skills/artifact-designer/references/worker-contract.md").read_text(encoding="utf-8")
    require("Do not spawn agents" in worker_contract and "finalized spec" in worker_contract
            and "directly inspect" in worker_contract and "SKILL.md" in worker_contract,
            "designer specialist must preserve ownership, skill use, and visual verification", errors)
    require("do not build in the parent" in build_handoff.lower(),
            "build handoff permits same-context construction", errors)

    worklog_frontmatter = re.match(r"^---\n(.*?)\n---", worklog_skill, re.DOTALL)
    require(worklog_frontmatter is not None, "worklog skill has no frontmatter", errors)
    worklog_skill_name = None
    if worklog_frontmatter:
        header = worklog_frontmatter.group(1)
        name_match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", header, re.MULTILINE)
        require(name_match is not None, "worklog skill name is not portable", errors)
        worklog_skill_name = name_match.group(1) if name_match else None
        require(worklog_skill_name == "worklog",
                "worklog skill name is not portable", errors)
        for key in ("allowed-tools:", "disable-model-invocation:", "argument-hint:"):
            require(key not in header,
                    f"worklog frontmatter contains unsupported key: {key[:-1]}", errors)
        description_match = re.search(r"^description:\s*(.+)$", header, re.MULTILINE)
        description = description_match.group(1) if description_match else ""
        for boundary in (
            "Maintain ongoing progress in .hukuhaka/work.md",
            "record work outcomes in .hukuhaka/changelog.md",
            "Use automatically throughout project work when these files exist",
            "when explicitly asked to update Worklog",
        ):
            require(boundary in description,
                    f"worklog description is missing its recording boundary: {boundary}", errors)
    require("${CLAUDE_PLUGIN_ROOT}" not in worklog_skill,
            "worklog skill contains a retired Claude plugin-root variable", errors)
    require("!`" not in worklog_skill,
            "worklog skill contains Claude-only shell interpolation", errors)
    require("references/writing-guide.md" not in worklog_skill,
            "worklog skill still depends on the removed writing guide", errors)
    require("throughout project work" in worklog_script,
            "worklog continuous recording guidance is missing", errors)
    require(".hukuhaka/work.md" in worklog_skill,
            "worklog host-neutral current-work path is missing", errors)
    require(".hukuhaka/changelog.md" in worklog_skill,
            "worklog host-neutral history path is missing", errors)
    require("Record the outcome in changelog.md.\n    Then remove the finished item from work.md." in worklog_skill,
            "worklog completion ordering is missing", errors)
    worklog_plugin_name = worklog_codex.get("name")
    if isinstance(worklog_plugin_name, str) and worklog_skill_name:
        canonical = f"${worklog_plugin_name}:{worklog_skill_name}"
        require(f'PLUGIN_NAME = "{worklog_plugin_name}"' in worklog_script,
                "worklog runtime plugin identity differs from its manifest", errors)
        require(f'SKILL_NAME = "{worklog_skill_name}"' in worklog_script,
                "worklog runtime Skill identity differs from its frontmatter", errors)
        require(canonical in worklog_openai,
                "worklog OpenAI metadata does not use the canonical identity", errors)
        require(canonical in str(worklog_codex.get("interface", {}).get("defaultPrompt", "")),
                "worklog Codex manifest does not use the canonical identity", errors)
    for contract in (
        'instruction = root / ("CLAUDE.md" if host == "claude"',
        "hukuhaka-worklog:begin",
        "Archive destinations are written first",
        "def run_hook(",
        '("PLUGIN_DATA" if host == "codex" else "CLAUDE_PLUGIN_DATA") in environment',
        'def setup(root: Path, host: str = "codex")',
        '"decision": "block"',
    ):
        require(contract in worklog_script,
                f"worklog mechanical contract is missing: {contract}", errors)
    hook_groups = worklog_hooks.get("hooks", {})
    require(set(hook_groups) == {"UserPromptSubmit", "PreToolUse", "PostToolUse"},
            "worklog must register commands and paired archive hooks", errors)
    for event in ("PreToolUse", "PostToolUse"):
        entries = hook_groups.get(event, [])
        require(len(entries) == 1 and entries[0].get("hooks") == [{
            "type": "command",
            "command": 'python3 "${PLUGIN_ROOT}/skills/worklog/scripts/worklog.py" --host codex hook',
            "timeout": 5,
        }] and "matcher" not in entries[0],
                f"worklog {event} must use the synchronous paired adapter for all tools", errors)
    hook_entries = hook_groups.get("UserPromptSubmit", [])
    require(len(hook_entries) == 1,
            "worklog must register exactly one UserPromptSubmit group", errors)
    if len(hook_entries) == 1:
        handlers = hook_entries[0].get("hooks", [])
        require(len(handlers) == 1,
                "worklog must register exactly one command handler", errors)
        if len(handlers) == 1:
            require(
                handlers[0].get("command")
                == 'python3 "${PLUGIN_ROOT}/skills/worklog/scripts/worklog.py" --host codex hook',
                "worklog hook must invoke the bundled mechanical adapter directly",
                errors,
            )
            require("commandWindows" not in handlers[0],
                    "worklog hook must not carry a retired host-specific command",
                    errors)

    memory_frontmatter = re.match(r"^---\n(.*?)\n---", memory_audit_skill, re.DOTALL)
    require(memory_frontmatter is not None, "memory audit skill has no frontmatter", errors)
    if memory_frontmatter:
        require(
            re.search(
                r"^name:\s*memory-audit\s*$",
                memory_frontmatter.group(1),
                re.MULTILINE,
            ) is not None,
            "memory audit skill name differs from its invocation",
            errors,
        )
    for contract in (
        "Check the user's latest direction and current authoritative sources",
        "Provide the exact replacement or removal",
        "IF the proposed changes are not yet approved:\n    Present the concrete change set for approval without applying it.",
        "IF the host provides a supported memory update mechanism:\n        Submit the approved changes through that mechanism.",
        "IF it records only a request or note:\n            Report submission, not confirmed memory regeneration.",
        "Never manually edit generated memory stores, rollout summaries, or evidence.",
        "Do not alter repositories, Git state, services, or external systems merely to\nmake a memory claim true.",
    ):
        require(contract in memory_audit_skill,
                f"memory audit Skill contract is missing: {contract}", errors)
    require("$memory-audit" in memory_audit_openai,
            "memory audit metadata lacks its canonical invocation", errors)
    require("$memory-audit" in memory_audit_manifest.get("interface", {}).get("defaultPrompt", ""),
            "memory audit manifest lacks its canonical invocation", errors)

    memory_hook_groups = memory_audit_hooks.get("hooks", {})
    require(set(memory_hook_groups) == {"SessionStart"},
            "memory audit must register only SessionStart", errors)
    memory_hook_entries = memory_hook_groups.get("SessionStart", [])
    require(len(memory_hook_entries) == 1,
            "memory audit must register one SessionStart group", errors)
    if len(memory_hook_entries) == 1:
        require(memory_hook_entries[0].get("matcher") == "^(startup|resume)$",
                "memory audit hook must match startup and resume only", errors)
        memory_handlers = memory_hook_entries[0].get("hooks", [])
        require(len(memory_handlers) == 1,
                "memory audit must register one command handler", errors)
        if len(memory_handlers) == 1:
            require(
                memory_handlers[0].get("command")
                == 'python3 "${PLUGIN_ROOT}/scripts/memory_pressure_hook.py" --host codex',
                "memory audit hook must invoke the bundled pressure script",
                errors,
            )
    for contract in (
        "25 * 1024",
        "HOT_LINES = 200",
        "1024 * 1024",
        "COLD_ROLLOUT_FILES = 300",
        'os.environ.get("PLUGIN_DATA")',
        'os.environ.get("CODEX_HOME"',
        "Codex memory pressure:",
        "$memory-audit",
    ):
        require(contract in memory_audit_script,
                f"memory audit hook contract is missing: {contract}", errors)

    agents_template_rules = (
        "Apply only to authorized changes in an existing Git repository",
        "Analysis-only tasks remain read-only",
        "Preserve pre-existing staged, unstaged, and untracked work",
        "Discarding, overwriting, or committing pre-existing user changes requires explicit permission",
        "Stage only this task's changes explicitly and commit them, including fixes",
        "Merge into target with --ff-only",
        "On success, remove this task's clean worktree and branch, if created",
        "If a separate integration approval is required and still missing",
        "Run required checks, fixing task-related failures and rerunning affected checks",
        "If required checks still fail or remain unavailable",
        "On divergence, preserve the work and ask for direction",
        "Deleting pre-existing branches or worktrees, pushing, tagging, publishing, and deploying require explicit authorization",
    )
    normalized_agents = " ".join(agents_template.split())
    require([line for line in agents_template.splitlines() if line.startswith("# ")]
            == ["# Ground Decisions", "# Code Quality", "# Scope and Execution", "# Change Preview",
                "# Verification", "# Codex tools", "# Subagents", "# Git Workflow"],
            "AGENTS.md template must contain the shared working principles and Git workflow", errors)
    for rule in agents_template_rules:
        require(rule in normalized_agents,
                f"AGENTS.md template lacks required guidance: {rule}", errors)
    require("engineering-plan" not in agents_template,
            "AGENTS.md template names the optional Skill", errors)

    for contract in (
        'model = "gpt-5.6-sol"',
        'model_reasoning_effort = "medium"',
        "do not spawn agents",
        "edit only owned files",
        "Investigation and review are read-only",
    ):
        require(contract in astra_worker,
                f"astra_worker contract is missing: {contract}", errors)
    # Package reachability, not a proxy for native routing or semantic quality.
    project_docs_references = PROJECT_DOCS_SKILL.parent / "references"
    for name in ("context", "impact", "maintenance"):
        reference = project_docs_references / f"{name}.md"
        require(reference.is_file() and bool(reference.read_text(encoding="utf-8").strip()),
                f"Project Docs workflow reference is missing or empty: {name}", errors)
        require(f"references/{name}.md" in project_docs_skill,
                f"Project Docs entrypoint does not link its {name} workflow", errors)
    for name in ("project-docs.schema.json",):
        require((project_docs_references / name).is_file(),
                f"Project Docs compatibility resource is missing: {name}", errors)

    require(not (ROOT / "skills" / "hukuhaka-team" / "SKILL.md").exists(), "removed hukuhaka-team skill still exists", errors)
    team_refs = list((ROOT / "eval").rglob("TEAM-*.json"))
    require(not team_refs, "removed TEAM eval scenarios still exist", errors)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if isinstance(worklog_codex.get("name"), str) and worklog_skill_name:
        canonical = f"${worklog_codex['name']}:{worklog_skill_name}"
        require(canonical in readme,
                "README does not use the canonical worklog identity", errors)
    for removed_name in ("hukuhaka-project-mapper", "hukuhaka-ltm"):
        require(removed_name not in components,
                f"removed component remains in catalog: {removed_name}", errors)
        require(not (ROOT / "marketplace" / removed_name).exists(),
                f"removed component tree remains: marketplace/{removed_name}", errors)
        require(not readme_row(readme, removed_name),
                f"README still exposes removed component: {removed_name}", errors)
    for component_name in (
        "hukuhaka-report-planner",
        "hukuhaka-engineering-plan",
        "hukuhaka-worklog",
        "hukuhaka-memory-audit",
        "hukuhaka-project-docs",
        "hukuhaka-uiux-foundation",
    ):
        require(readme_row(readme, component_name),
                f"README does not expose {component_name}", errors)
    require("hukuhaka-codex" not in readme,
            "README still exposes the retired hukuhaka-codex component", errors)
    require("Claude Code" in readme,
            "README does not expose the supported Claude host", errors)

    if errors:
        return report(errors)
    print("host-support: native host plugin contracts and component lifecycle are consistent")
    return 0


def report(errors: list[str]) -> int:
    for error in errors:
        print(f"host-support: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
