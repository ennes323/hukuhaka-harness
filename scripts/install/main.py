"""Host-aware hukuhaka-harness installer."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .codex import CodexInstaller
from .codex_config import (
    CONTEXT_POLICY_SCOPES,
    RECOMMENDED_SETTINGS,
    AgentPolicyPlan,
    CodexAgentPolicy,
    CodexSubagentModel,
    CodexContextPolicy,
    CodexConfigEditor,
    ConfigPlan,
    ContextPolicyPlan,
    prompt_agent_action,
    prompt_agent_settings,
    prompt_context_action,
    prompt_context_settings,
    prompt_settings,
)
from .common import InstallerError, StateError, load_json
from .terminal import HostInstallPlan, csv_items, csv_value, prompt_install_plan
from .settings import Settings, cli_literal, read_profile, wizard
from .settings_catalog import RECOMMENDED, KEYS


HOST_LABELS = {"codex": "Codex"}


@dataclass(frozen=True)
class HostResult:
    host: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class HostComponentState:
    components: Set[str]
    plugin_versions: Mapping[str, str]


class Installer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo_root = args.repo_root.resolve()
        self.catalog = load_json(self.repo_root / "components.json", {})
        if not isinstance(self.catalog, dict) or not isinstance(
            self.catalog.get("components"), list
        ):
            raise StateError(
                "component catalog must contain a components array",
                operation="read-catalog",
                path=str(self.repo_root / "components.json"),
            )
        self.component_map = {
            str(component["name"]): component
            for component in self.catalog["components"]
        }
        self.aliases = {
            str(alias): str(component["name"])
            for component in self.catalog["components"]
            for alias in component.get("aliases", [])
        }
        self._target_version_cache = {}  # type: Dict[Tuple[str, str], str]
        self.version = args.resolved_version or self._source_version()

    def _source_version(self) -> str:
        path = self.repo_root / "VERSION"
        try:
            version = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StateError(
                "cannot read source VERSION: {}".format(exc),
                operation="read-version",
                path=str(path),
            ) from exc
        if not version:
            raise StateError("source VERSION is empty", path=str(path))
        return version

    @staticmethod
    def _tty_available() -> bool:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())

    @staticmethod
    def _host_version(host: str) -> str:
        command = shutil.which(host)
        if not command:
            return ""
        result = subprocess.run(
            (command, "--version"),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        return (result.stdout or result.stderr).strip().splitlines()[0][:80]

    def _components(self, host: str) -> List[Dict[str, Any]]:
        components = []
        for component in self.catalog["components"]:
            if host not in component.get("hosts", {}):
                continue
            item = dict(component)
            version = self._target_plugin_version(host, str(component["name"]))
            if version:
                item["version"] = version
            components.append(item)
        return components

    def _target_plugin_version(self, host: str, name: str) -> str:
        component = self.component_map[name]
        if component.get("kind") != "plugin":
            return ""
        key = (host, name)
        if key in self._target_version_cache:
            return self._target_version_cache[key]

        host_data = component.get("hosts", {}).get(host, {})
        manifest_value = (
            host_data.get("manifest") if isinstance(host_data, dict) else None
        )
        if not isinstance(manifest_value, str) or not manifest_value:
            raise StateError(
                "{} plugin manifest path is missing for {}".format(host, name),
                operation="read-plugin-manifest",
                path=str(self.repo_root / "components.json"),
            )
        path = self.repo_root / manifest_value
        metadata = load_json(path, {})
        version = metadata.get("version") if isinstance(metadata, dict) else None
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != name
            or not isinstance(version, str)
            or not version.strip()
        ):
            raise StateError(
                "invalid plugin manifest for {}".format(name),
                operation="read-plugin-manifest",
                path=str(path),
            )
        self._target_version_cache[key] = version.strip()
        return version.strip()

    def _recommended(self, host: str) -> List[str]:
        return [
            str(component["name"])
            for component in self._components(host)
            if component.get("default") is True
            and component.get("lifecycle") == "supported"
        ]

    def _validate_components(self, host: str, names: Iterable[str]) -> List[str]:
        available = {
            str(component["name"]) for component in self._components(host)
        }
        ordered = list(dict.fromkeys(self.aliases.get(name, name) for name in names))
        unknown = [name for name in ordered if name not in available]
        if unknown:
            raise InstallerError(
                "unknown {} component '{}'. Available: {}".format(
                    HOST_LABELS[host], unknown[0], " ".join(sorted(available))
                ),
                host=host,
                stage="component-selection",
            )
        if not ordered:
            raise InstallerError(
                "empty component selection is not allowed; use uninstall instead",
                host=host,
                stage="component-selection",
            )
        deprecated = [
            name
            for name in ordered
            if self.component_map[name].get("lifecycle") == "deprecated"
        ]
        if deprecated:
            print(
                "Warning: deprecated component(s) selected: {}".format(
                    csv_value(deprecated)
                ),
                file=sys.stderr,
            )
        return ordered

    def _codex(self) -> CodexInstaller:
        return CodexInstaller(
            self.repo_root,
            self.catalog,
            self.version,
            local_source=bool(self.args.local_source),
            dry_run=bool(getattr(self.args, "dry_run", False)),
            force=bool(getattr(self.args, "force", False)),
        )

    def _current_state(self, host: str) -> HostComponentState:
        components, versions = self._codex().current_component_state()

        normalized = {}  # type: Dict[str, str]
        for name, version in sorted(
            versions.items(),
            key=lambda item: (
                item[0] != self.aliases.get(item[0], item[0]),
                item[0],
            ),
        ):
            canonical = self.aliases.get(name, name)
            normalized.setdefault(canonical, version)
        normalized_components = {
            self.aliases.get(name, name) for name in components
        }
        return HostComponentState(normalized_components, normalized)

    def _current(self, host: str) -> Set[str]:
        return self._codex().current_components()

    def _version_summary(
        self,
        plan: HostInstallPlan,
        before: Set[str],
        installed_versions: Mapping[str, str],
    ) -> List[Tuple[str, str]]:
        summary = []
        for name in plan.components:
            target = self._target_plugin_version(plan.host, name)
            if not target:
                continue
            if name not in before:
                detail = "not installed → {}".format(target)
            else:
                installed = installed_versions.get(name)
                if not installed:
                    detail = "unknown → {}".format(target)
                elif installed == target:
                    detail = "{} (same version)".format(target)
                else:
                    detail = "{} → {}".format(installed, target)
            summary.append((name, detail))
        return summary

    def _print_detection(self, detected: Mapping[str, bool]) -> None:
        print("Hukuhaka Installer")
        print("")
        print("Detecting supported hosts...")
        print("")
        for host in ("codex",):
            prefix = "✓" if detected[host] else "-"
            suffix = "detected" if detected[host] else "not found"
            print("{} {} {}".format(prefix, HOST_LABELS[host], suffix))
        print("")

    def _print_plan(
        self,
        plans: Sequence[HostInstallPlan],
        current: Mapping[str, Set[str]],
        installed_versions: Mapping[str, Mapping[str, str]],
        config_plan: Optional[ConfigPlan],
        context_plan: Optional[ContextPolicyPlan],
        agent_plan: Optional[AgentPolicyPlan],
    ) -> None:
        print("Installation plan")
        print("")
        for plan in plans:
            desired = set(plan.components)
            before = current.get(plan.host, set())
            print(HOST_LABELS[plan.host])
            print("  Components")
            print(
                "    Install/update: {}".format(
                    csv_value(plan.components) or "none"
                )
            )
            version_summary = self._version_summary(
                plan,
                before,
                installed_versions.get(plan.host, {}),
            )
            if version_summary:
                width = max(len(name) for name, _ in version_summary)
                print("    Component versions:")
                for name, detail in version_summary:
                    print("      {name:<{width}}  {detail}".format(
                        name=name,
                        width=width,
                        detail=detail,
                    ))
            print(
                "    Remove:         {}".format(
                    csv_value(sorted(before - desired)) or "none"
                )
            )
            if plan.host == "codex" and (plan.reset or desired or before):
                print("    Agent runtime:  existing settings preserved (V1/V2 state not inferred)")
                print("    Optional agent files do not enable subagents.")
            if plan.configure_codex:
                print("  Settings")
                print("    Global defaults: update")
            if plan.change_context_window:
                assert context_plan is not None
                if not plan.configure_codex:
                    print("  Settings")
                action = (
                    "set custom policy"
                    if context_plan.action == "set"
                    else "reset to Codex defaults"
                )
                print("    Context window: {}".format(action))
            if plan.change_agent_policy:
                assert agent_plan is not None
                if not plan.configure_codex and not plan.change_context_window:
                    print("  Settings")
                action = (
                    "set custom policy"
                    if agent_plan.action == "set"
                    else "reset to Codex defaults"
                )
                print("    Agent execution: {}".format(action))
            print("  Reset")
            print(
                "    Managed components: {}".format(
                    "yes" if plan.reset else "no"
                )
            )
            if plan.include_template:
                print("    Instruction template: yes")
            print("")
        if config_plan is not None or context_plan is not None or agent_plan is not None:
            print("Settings changes")
        if config_plan is not None:
            print("Global Codex defaults")
            if config_plan.changed:
                print(config_plan.diff(), end="")
            else:
                print("Global Codex config already matches the selected values.")
            print("")
        if context_plan is not None:
            print("Context window")
            if context_plan.changed:
                print(context_plan.diff(), end="")
            elif context_plan.action == "reset":
                print("Codex context policy already uses Codex defaults.")
            else:
                print("Codex context policy already matches the selected values.")
            print("")
        if agent_plan is not None:
            print("Agent execution")
            if agent_plan.changed:
                print(agent_plan.diff(), end="")
            elif agent_plan.action == "reset":
                print("Codex agent policy already uses Codex defaults.")
            else:
                print("Codex agent policy already matches the selected values.")
            print("")

    def _confirm(self) -> bool:
        if bool(getattr(self.args, "dry_run", False)):
            return True
        if bool(getattr(self.args, "yes", False)):
            return True
        if not self._tty_available():
            raise InstallerError(
                "confirmation requires a terminal or --yes",
                stage="confirmation",
            )
        return input("Proceed? [y/N] ").strip().lower() == "y"

    def _apply_host(
        self, plan: HostInstallPlan, before: Optional[Set[str]] = None
    ) -> HostResult:
        if not plan.reset and not plan.components and not before:
            return HostResult(plan.host, "noop")
        installer = self._codex()
        try:
            installer.install(
                plan.components,
                reset=plan.reset,
                include_template=plan.include_template,
            )
            return HostResult("codex", "success")
        except InstallerError as exc:
            status = "partial" if installer.completed else "failed"
            return HostResult("codex", status, exc.render())

    @staticmethod
    def _combine_codex_result(
        component_result: HostResult,
        *,
        config_requested: bool,
        config_changed: bool,
        config_applied: bool,
        config_errors: Sequence[str],
        context_requested: bool = False,
        context_changed: bool = False,
        context_applied: bool = False,
        context_errors: Sequence[str] = (),
        agent_requested: bool = False,
        agent_changed: bool = False,
        agent_applied: bool = False,
        agent_errors: Sequence[str] = (),
    ) -> HostResult:
        settings_requested = config_requested or context_requested or agent_requested
        if not settings_requested:
            return component_result

        setting_errors = list(config_errors) + list(context_errors) + list(agent_errors)
        details = list(setting_errors)
        if component_result.detail:
            details.append(component_result.detail)

        if setting_errors:
            status = (
                "failed"
                if component_result.status == "failed"
                and not (config_applied or context_applied or agent_applied)
                else "partial"
            )
        elif component_result.status in ("failed", "partial"):
            status = "partial"
        elif component_result.status == "noop" and (
            config_changed or context_changed or agent_changed
        ):
            status = "success"
        else:
            status = component_result.status

        return HostResult("codex", status, "\n    ".join(details))

    @staticmethod
    def _print_results(results: Sequence[HostResult], *, dry_run: bool) -> int:
        print("")
        print("Host results:")
        for result in results:
            print("  {:12} {}".format(HOST_LABELS[result.host] + ":", result.status))
            if result.detail:
                print("    {}".format(result.detail))
        if all(result.status in ("success", "noop") for result in results):
            print("")
            print(
                "Dry run complete. No files were modified."
                if dry_run
                else "Installation complete."
            )
            return 0
        print(
            "Installation incomplete: one or more host operations failed.",
            file=sys.stderr,
        )
        return 1

    def interactive(self) -> int:
        if not self._tty_available():
            print(
                "installer: interactive installation requires a terminal; "
                "use a host subcommand with --yes",
                file=sys.stderr,
            )
            return 2
        detected = {"codex": shutil.which("codex") is not None}
        self._print_detection(detected)
        if not any(detected.values()):
            print(
                "No supported host was detected. Install Codex first.",
                file=sys.stderr,
            )
            return 1

        sections = []
        current = {}  # type: Dict[str, Set[str]]
        installed_versions = {}  # type: Dict[str, Mapping[str, str]]
        for host in ("codex",):
            if not detected[host]:
                continue
            state = self._current_state(host)
            current[host] = state.components
            installed_versions[host] = state.plugin_versions
            section = {
                "host": host,
                "label": HOST_LABELS[host],
                "version": self._host_version(host),
                "components": self._components(host),
                "selected": state.components or set(self._recommended(host)),
            }
            sections.append(section)

        plans = prompt_install_plan(sys.stdin, sys.stdout, sections=sections)
        if not plans:
            print("Exit. No changes were made.")
            return 0

        config_editor = None  # type: Optional[CodexConfigEditor]
        config_plan = None  # type: Optional[ConfigPlan]
        if any(plan.configure_codex for plan in plans):
            config_editor = CodexConfigEditor(
                self._codex().codex_home,
                dry_run=bool(getattr(self.args, "dry_run", False)),
                managed_keys=KEYS,
                stage="settings",
            )
            settings = prompt_settings(config_editor.inspect())
            config_plan = config_editor.plan(settings)

        context_policy = None  # type: Optional[CodexContextPolicy]
        context_plan = None  # type: Optional[ContextPolicyPlan]
        if any(plan.change_context_window for plan in plans):
            context_policy = CodexContextPolicy(
                self._codex().codex_home,
                dry_run=bool(getattr(self.args, "dry_run", False)),
            )
            context_action = prompt_context_action(context_policy.state())
            if context_action is None:
                print("Exit. No changes were made.")
                return 0
            if context_action == "set":
                context_window, compact_at, scope = prompt_context_settings(
                    context_policy.state()
                )
                context_plan = context_policy.plan_set(
                    context_window=context_window,
                    compact_at=compact_at,
                    scope=scope,
                )
            else:
                context_plan = context_policy.plan_reset()

        agent_policy = None  # type: Optional[CodexAgentPolicy]
        agent_plan = None  # type: Optional[AgentPolicyPlan]
        if any(plan.change_agent_policy for plan in plans):
            agent_policy = CodexAgentPolicy(
                self._codex().codex_home,
                dry_run=bool(getattr(self.args, "dry_run", False)),
            )
            agent_action = prompt_agent_action(agent_policy.state())
            if agent_action is None:
                print("Exit. No changes were made.")
                return 0
            if agent_action == "set":
                max_concurrent, max_depth = prompt_agent_settings(
                    agent_policy.state()
                )
                agent_plan = agent_policy.plan_set(
                    max_concurrent=max_concurrent,
                    max_depth=max_depth,
                )
            else:
                agent_plan = agent_policy.plan_reset()

        self._print_plan(
            plans,
            current,
            installed_versions,
            config_plan,
            context_plan,
            agent_plan,
        )
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0

        results = []
        for plan in plans:
            config_errors = []  # type: List[str]
            config_ready = False
            config_applied = False
            context_errors = []  # type: List[str]
            context_ready = False
            context_applied = False
            applied_context_plan = None  # type: Optional[ContextPolicyPlan]
            agent_errors = []  # type: List[str]
            agent_ready = False
            agent_applied = False
            applied_agent_plan = None  # type: Optional[AgentPolicyPlan]
            if plan.host == "codex" and plan.configure_codex:
                assert config_editor is not None and config_plan is not None
                try:
                    config_applied = bool(
                        config_editor.apply(config_plan, show_diff=False)
                    )
                    config_ready = True
                except InstallerError as exc:
                    config_applied = exc.operation == "rollback-config"
                    config_errors.append(exc.render())

            if plan.host == "codex" and plan.change_context_window:
                assert context_policy is not None and context_plan is not None
                try:
                    applied_context_plan = context_policy.replan(context_plan)
                    context_applied = bool(
                        context_policy.apply(applied_context_plan)
                    )
                    context_ready = True
                except InstallerError as exc:
                    context_errors.append(exc.render())

            if plan.host == "codex" and plan.change_agent_policy:
                assert agent_policy is not None and agent_plan is not None
                try:
                    applied_agent_plan = agent_policy.replan(agent_plan)
                    agent_applied = bool(agent_policy.apply(applied_agent_plan))
                    agent_ready = True
                except InstallerError as exc:
                    agent_errors.append(exc.render())

            result = self._apply_host(plan, current.get(plan.host))

            if (
                plan.host == "codex"
                and plan.configure_codex
                and config_ready
                and config_editor is not None
                and config_plan is not None
            ):
                try:
                    config_editor.verify(config_plan)
                except InstallerError as exc:
                    config_errors.append(exc.render())

            if (
                plan.host == "codex"
                and plan.change_context_window
                and context_ready
                and context_policy is not None
                and applied_context_plan is not None
            ):
                try:
                    context_policy.verify(applied_context_plan)
                except InstallerError as exc:
                    context_errors.append(exc.render())

            if (
                plan.host == "codex"
                and plan.change_agent_policy
                and agent_ready
                and agent_policy is not None
                and applied_agent_plan is not None
            ):
                try:
                    agent_policy.verify(applied_agent_plan)
                except InstallerError as exc:
                    agent_errors.append(exc.render())

            result = self._combine_codex_result(
                result,
                config_requested=plan.host == "codex" and plan.configure_codex,
                config_changed=bool(
                    config_plan is not None and config_plan.changed
                ),
                config_applied=config_applied,
                config_errors=config_errors,
                context_requested=(
                    plan.host == "codex" and plan.change_context_window
                ),
                context_changed=bool(
                    context_plan is not None and context_plan.changed
                ),
                context_applied=context_applied,
                context_errors=context_errors,
                agent_requested=(
                    plan.host == "codex" and plan.change_agent_policy
                ),
                agent_changed=bool(
                    agent_plan is not None and agent_plan.changed
                ),
                agent_applied=agent_applied,
                agent_errors=agent_errors,
            )
            results.append(result)
        return self._print_results(
            results, dry_run=bool(getattr(self.args, "dry_run", False))
        )

    def _automation_components(self, host: str) -> List[str]:
        if self.args.recommended:
            return self._recommended(host)
        return self._validate_components(host, csv_items(self.args.components))

    def _context_policy(self) -> int:
        policy = CodexContextPolicy(
            self._codex().codex_home,
            dry_run=bool(getattr(self.args, "dry_run", False)),
        )
        action = self.args.context_action
        if action is None:
            if not self._tty_available():
                print(
                    "installer: codex context requires a terminal or an explicit "
                    "set/reset action",
                    file=sys.stderr,
                )
                return 2
            action = prompt_context_action(policy.state())
            if action is None:
                print("Exit. No changes were made.")
                return 0
            if action == "set":
                context_window, compact_at, scope = prompt_context_settings(
                    policy.state()
                )
                plan = policy.plan_set(
                    context_window=context_window,
                    compact_at=compact_at,
                    scope=scope,
                )
            else:
                plan = policy.plan_reset()
        elif action == "set":
            plan = policy.plan_set(
                context_window=self.args.window,
                compact_at=self.args.compact_at,
                scope=self.args.scope,
            )
        else:
            plan = policy.plan_reset()

        print("Codex context policy")
        if plan.changed:
            print(plan.diff(), end="")
        elif action == "reset":
            print("Codex context policy already uses Codex defaults.")
        else:
            print("Codex context policy already matches the selected values.")
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0
        policy.apply(plan)
        return 0

    def _agent_policy(self) -> int:
        if self.args.agent_action == "model":
            policy = CodexSubagentModel(
                self._codex().codex_home,
                dry_run=bool(getattr(self.args, "dry_run", False)),
            )
            if self.args.model_action == "inspect":
                print(json.dumps(policy.inspect(), indent=2, sort_keys=True))
                return 0
            plan = policy.plan_inherit()
            print("Remove only global child model and effort overrides; retain role pins.")
            print(plan.diff(), end="")
            if not self._confirm():
                print("Exit. No changes were made.")
                return 0
            policy.apply(plan)
            return 0
        policy = CodexAgentPolicy(
            self._codex().codex_home,
            dry_run=bool(getattr(self.args, "dry_run", False)),
        )
        action = self.args.agent_action
        if action is None:
            if not self._tty_available():
                print(
                    "installer: codex agents requires a terminal or an explicit "
                    "set/reset action",
                    file=sys.stderr,
                )
                return 2
            action = prompt_agent_action(policy.state())
            if action is None:
                print("Exit. No changes were made.")
                return 0
            if action == "set":
                max_concurrent, max_depth = prompt_agent_settings(policy.state())
                plan = policy.plan_set(
                    max_concurrent=max_concurrent,
                    max_depth=max_depth,
                )
            else:
                plan = policy.plan_reset()
        elif action == "set":
            plan = policy.plan_set(
                max_concurrent=self.args.max_concurrent,
                max_depth=self.args.max_depth,
            )
        else:
            plan = policy.plan_reset()

        print("Codex agent execution policy")
        print("Note: max_depth is V1-only and is ignored by V2.")
        if plan.changed:
            print(plan.diff(), end="")
        elif action == "reset":
            print("Codex agent policy already uses Codex defaults.")
        else:
            print("Codex agent policy already matches the selected values.")
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0
        policy.apply(plan)
        return 0

    def automation(self) -> int:
        host = self.args.host
        if (self.args.action == "agents"
                and self.args.agent_action == "model"
                and self.args.model_action == "inspect"):
            return self._agent_policy()
        if shutil.which(host) is None:
            print(
                "installer [host={} stage=detect]: {} CLI was not found".format(
                    host, host
                ),
                file=sys.stderr,
            )
            return 1

        if self.args.action == "settings":
            return self._settings()

        if self.args.action == "context":
            return self._context_policy()

        if self.args.action == "agents":
            return self._agent_policy()

        if self.args.action == "configure":
            # Compatibility spelling for the unified settings interface.
            self.args.settings_action = "apply" if self.args.recommended else None
            self.args.file = None
            return self._settings()

        if self.args.action == "uninstall":
            current = self._current(host)
            print("{} uninstall: {}".format(HOST_LABELS[host], csv_value(sorted(current)) or "none"))
            if not self._confirm():
                print("Exit. No changes were made.")
                return 0
            if not current:
                return self._print_results(
                    [HostResult(host, "noop")], dry_run=self.args.dry_run
                )
            adapter = self._codex()
            try:
                adapter.uninstall()
                result = HostResult(host, "success")
            except InstallerError as exc:
                result = HostResult(
                    host,
                    "partial" if adapter.completed else "failed",
                    exc.render(),
                )
            return self._print_results([result], dry_run=self.args.dry_run)

        components = self._automation_components(host)
        state = self._current_state(host)
        current = {host: state.components}
        installed_versions = {host: state.plugin_versions}
        plan = HostInstallPlan(
            host=host,
            components=components,
            reset=self.args.action == "reset",
            include_template=bool(getattr(self.args, "include_template", False)),
        )
        self._print_plan([plan], current, installed_versions, None, None, None)
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0
        result = self._apply_host(plan, current[host])
        return self._print_results([result], dry_run=self.args.dry_run)

    def run(self) -> int:
        if self.args.host is None:
            return self.interactive()
        return self.automation()

    def _settings(self) -> int:
        args = self.args
        manager = Settings(self._codex().codex_home, dry_run=getattr(args, "dry_run", False))
        action = args.settings_action
        if action == "show":
            manager.show(as_json=args.json)
            return 0
        if action == "history":
            for identifier, record in manager.records():
                print("{}  {}  {}".format(identifier, record.get("label", "settings"), ", ".join(record["after"]) or "formatting only"))
            return 0
        if action == "export":
            manager.export(args.file.expanduser())
            return 0
        if action is None:
            if not self._tty_available():
                manager.show()
                return 0
            plan = wizard(manager)
            if plan is None:
                return 0
        elif action == "set":
            plan = manager.plan({tuple(args.key.split(".")): cli_literal(args.key, args.value)})
        elif action == "unset":
            plan = manager.plan(remove=(tuple(args.key.split(".")),))
        elif action in ("apply", "diff"):
            plan = manager.plan(RECOMMENDED if args.recommended else read_profile(args.file.expanduser()))
        elif action == "restore":
            plan = manager.restore_plan(args.receipt)
        else:
            plan = manager.plan(organize=True)
        print(plan.diff(), end="")
        if action == "diff":
            return 0
        if not plan.changed or self._confirm():
            label = action or "wizard"
            if action == "apply":
                label = "recommended" if args.recommended else "profile " + args.file.name
            if action == "restore":
                label = "restore " + args.receipt
            manager.apply(plan, label=label)
        return 0


def _add_mutation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="skip confirmation")
    parser.add_argument("--dry-run", action="store_true", help="preview without applying changes")
    parser.add_argument("--force", action="store_true", help="authorize replacement of conflicting managed files")


def _add_bootstrap_passthrough(parser: argparse.ArgumentParser) -> None:
    # install.sh resolves these before Python starts, but keeps the original
    # arguments intact. Accept both before and after the host action so the
    # bootstrap contract does not depend on argparse subparser placement.
    parser.add_argument(
        "--version", default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--source-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )


def _add_selection(parser: argparse.ArgumentParser) -> None:
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--recommended",
        action="store_true",
        help="use supported components whose catalog default is true",
    )
    selection.add_argument(
        "--components",
        help="complete comma-separated desired component set",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/install.sh",
        description="Install and manage hukuhaka-harness for Codex.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run without arguments in a terminal for interactive installation.\n"
            "Examples:\n"
            "  scripts/install.sh codex install --recommended --dry-run\n"
            "  scripts/install.sh codex install --recommended --yes\n"
            "  scripts/install.sh codex uninstall --yes\n\n"
            "Component installation preserves independent settings, including V1/V2 agent switches.\n"
            "A local checkout uses its own files; remote bootstrap defaults to the latest release.\n"
            "See INSTALL.md for updates, selection, settings, and recovery."
        ),
    )
    parser.add_argument("--repo-root", type=Path, required=True, help=argparse.SUPPRESS)
    parser.add_argument("--resolved-version", help=argparse.SUPPRESS)
    parser.add_argument("--local-source", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", metavar="X.Y.Z", help="select a remote release or require this local source version")
    parser.add_argument("--source-dir", help="use an existing source checkout")
    hosts = parser.add_subparsers(dest="host")
    for host in ("codex",):
        host_parser = hosts.add_parser(host, help="manage Codex components and settings")
        actions = host_parser.add_subparsers(dest="action", required=True)
        for action in ("install", "reset"):
            action_parser = actions.add_parser(
                action,
                help="install/update the desired set" if action == "install" else "rebuild the desired managed set",
                description="Select the complete desired managed set. Independent settings are preserved.",
            )
            _add_selection(action_parser)
            if action == "reset":
                action_parser.add_argument("--include-template", action="store_true")
            _add_mutation_flags(action_parser)
            _add_bootstrap_passthrough(action_parser)
        uninstall = actions.add_parser("uninstall", help="remove managed components; preserve independent settings")
        _add_mutation_flags(uninstall)
        _add_bootstrap_passthrough(uninstall)
        if host == "codex":
            settings = actions.add_parser("settings", help="inspect, edit, compare, restore and organize settings")
            settings.add_argument("--yes", action="store_true")
            settings.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(settings)
            setting_actions = settings.add_subparsers(dest="settings_action")
            show = setting_actions.add_parser("show", help="saved values and provenance, not effective session state")
            show.add_argument("--json", action="store_true")
            _add_bootstrap_passthrough(show)
            history = setting_actions.add_parser("history")
            _add_bootstrap_passthrough(history)
            export = setting_actions.add_parser("export", help="create a partial TOML profile; never overwrite")
            export.add_argument("file", type=Path)
            export.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
            _add_bootstrap_passthrough(export)
            for operation in ("set", "unset", "apply", "diff", "restore", "organize"):
                sub = setting_actions.add_parser(operation)
                if operation in ("set", "unset"):
                    sub.add_argument("key")
                if operation == "set":
                    sub.add_argument("value")
                if operation in ("apply", "diff"):
                    source = sub.add_mutually_exclusive_group(required=True)
                    source.add_argument("--file", type=Path)
                    source.add_argument("--recommended", action="store_true")
                if operation == "restore":
                    sub.add_argument("receipt")
                sub.add_argument("--yes", action="store_true", default=argparse.SUPPRESS)
                sub.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
                _add_bootstrap_passthrough(sub)
            configure = actions.add_parser("configure", help="review or apply global Codex settings")
            configure.add_argument("--recommended", action="store_true")
            configure.add_argument("--yes", action="store_true")
            configure.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(configure)
            context = actions.add_parser(
                "context",
                help="set or reset only Codex context-window overrides",
            )
            _add_bootstrap_passthrough(context)
            context_actions = context.add_subparsers(dest="context_action")
            context_set = context_actions.add_parser("set")
            context_set.add_argument("--window", type=int, required=True)
            context_set.add_argument("--compact-at", type=int, required=True)
            context_set.add_argument(
                "--scope",
                choices=CONTEXT_POLICY_SCOPES,
                default="total",
            )
            context_set.add_argument("--yes", action="store_true")
            context_set.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(context_set)
            context_reset = context_actions.add_parser("reset")
            context_reset.add_argument("--yes", action="store_true")
            context_reset.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(context_reset)
            agents = actions.add_parser(
                "agents",
                help="manage agent capacity and model overrides; does not enable subagents",
            )
            _add_bootstrap_passthrough(agents)
            agent_actions = agents.add_subparsers(dest="agent_action")
            agent_model = agent_actions.add_parser("model")
            _add_bootstrap_passthrough(agent_model)
            model_actions = agent_model.add_subparsers(dest="model_action", required=True)
            model_inspect = model_actions.add_parser("inspect")
            _add_bootstrap_passthrough(model_inspect)
            model_inherit = model_actions.add_parser("inherit")
            model_inherit.add_argument("--yes", action="store_true")
            model_inherit.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(model_inherit)
            agents_set = agent_actions.add_parser("set")
            agents_set.add_argument(
                "--max-concurrent",
                type=int,
                required=True,
            )
            agents_set.add_argument("--max-depth", type=int, required=True)
            agents_set.add_argument("--yes", action="store_true")
            agents_set.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(agents_set)
            agents_reset = agent_actions.add_parser("reset")
            agents_reset.add_argument("--yes", action="store_true")
            agents_reset.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(agents_reset)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return Installer(args).run()
    except InstallerError as exc:
        print(exc.render(), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        detail = (getattr(exc, "stderr", None) or "").strip()
        print(
            "installer [stage=external-command]: command failed with status {}{}".format(
                exc.returncode, ": " + detail if detail else ""
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            "installer [stage=unexpected operation={}]: {}".format(
                type(exc).__name__, exc
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
