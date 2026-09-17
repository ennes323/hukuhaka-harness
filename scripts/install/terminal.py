"""Arrow-key installer UI on the caller's standard input and output."""

from __future__ import annotations

import termios
import tty
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, TextIO, Tuple


CLEAR = "\x1b[2J\x1b[H"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
SECTION_LABELS = {
    "components-section": "Components",
    "settings-section": "Settings",
    "reset-section": "Reset",
}


@dataclass(frozen=True)
class HostInstallPlan:
    host: str
    components: List[str]
    reset: bool = False
    include_template: bool = False
    configure_codex: bool = False
    change_context_window: bool = False
    change_agent_policy: bool = False


@dataclass
class _HostState:
    host: str
    label: str
    version: str
    enabled: bool
    components: Sequence[Dict[str, Any]]
    selected: Set[str]
    reset: bool = False
    include_template: bool = False
    configure_codex: bool = False
    context_status: str = ""
    change_context_window: bool = False
    agent_policy_status: str = ""
    change_agent_policy: bool = False


def csv_items(value: str) -> List[str]:
    return list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def csv_value(items: Iterable[str]) -> str:
    return ",".join(items)


def _read_key(stream: TextIO) -> str:
    value = stream.read(1)
    if value == "\x1b":
        tail = stream.read(2)
        if tail == "[A":
            return "up"
        if tail == "[B":
            return "down"
        return ""
    if value in ("k", "K"):
        return "up"
    if value in ("j", "J"):
        return "down"
    if value == " ":
        return "toggle"
    if value in ("\r", "\n"):
        return "enter"
    if value in ("q", "Q"):
        return "exit"
    return ""


def _rows(states: Sequence[_HostState]) -> List[Tuple[str, int, int]]:
    rows = []  # type: List[Tuple[str, int, int]]
    for host_index, state in enumerate(states):
        rows.append(("header", host_index, -1))
        rows.append(("components-section", host_index, -1))
        rows.append(("host", host_index, -1))
        for component_index, _ in enumerate(state.components):
            rows.append(("component", host_index, component_index))
        rows.append(("recommended", host_index, -1))
        if state.host == "codex":
            rows.append(("settings-section", host_index, -1))
            rows.append(("configure", host_index, -1))
        rows.append(("reset-section", host_index, -1))
        rows.append(("reset", host_index, -1))
        rows.append(("template", host_index, -1))
    rows.extend((("install", -1, -1), ("exit", -1, -1)))
    return rows


def _render(
    output: TextIO,
    states: Sequence[_HostState],
    rows: Sequence[Tuple[str, int, int]],
    cursor: int,
) -> None:
    output.write(CLEAR)
    output.write("Hukuhaka Installer\n")
    output.write("  Up/Down move  Space select  Enter apply  q exit\n\n")
    for row_index, (kind, host_index, component_index) in enumerate(rows):
        marker = "> " if row_index == cursor else "  "
        if kind == "header":
            state = states[host_index]
            detail = "detected{}".format(
                " ({})".format(state.version) if state.version else ""
            )
            output.write("{} — {}\n".format(state.label, detail))
            continue
        if kind in SECTION_LABELS:
            output.write("  {}\n".format(SECTION_LABELS[kind]))
            continue
        if kind == "install":
            output.write("\n{}Install\n".format(marker))
            continue
        if kind == "exit":
            output.write("{}Exit\n".format(marker))
            continue

        state = states[host_index]
        disabled = "" if state.enabled else " (disabled)"
        if kind == "host":
            output.write(
                "{}[{}] Install/update{}\n".format(
                    marker, "x" if state.enabled else " ", disabled
                )
            )
        elif kind == "component":
            component = state.components[component_index]
            checked = component["name"] in state.selected
            suffix = " — optional" if component.get("default") is not True else ""
            descriptor = str(component["kind"])
            version = component.get("version")
            if (
                component.get("kind") == "plugin"
                and isinstance(version, str)
                and version
            ):
                descriptor = "{} {}".format(descriptor, version)
            elif component.get("kind") == "agent":
                description = str(component.get("description", "")).strip()
                descriptor = "agent{}".format(
                    ": " + description if description else ""
                )
            output.write(
                "{}    [{}] {} ({}){}\n".format(
                    marker,
                    "x" if checked else " ",
                    component["name"],
                    descriptor,
                    suffix,
                )
            )
        elif kind == "recommended":
            output.write("{}    Select recommended components\n".format(marker))
        elif kind == "configure":
            output.write(
                "{}    [{}] Review Codex settings or apply a profile\n".format(
                    marker, "x" if state.configure_codex else " "
                )
            )
        elif kind == "context":
            output.write(
                "{}    [{}] Configure context & auto-compaction ({})\n".format(
                    marker,
                    "x" if state.change_context_window else " ",
                    state.context_status,
                )
            )
        elif kind == "agent-policy":
            output.write(
                "{}    [{}] Configure agent concurrency & nesting ({})\n".format(
                    marker,
                    "x" if state.change_agent_policy else " ",
                    state.agent_policy_status,
                )
            )
        elif kind == "reset":
            output.write(
                "{}    [{}] Reset managed components before install\n".format(
                    marker, "x" if state.reset else " "
                )
            )
        elif kind == "template":
            output.write(
                "{}    [{}] Also reset managed instruction template{}\n".format(
                    marker,
                    "x" if state.include_template else " ",
                    "" if state.reset else " (enable Reset first)",
                )
            )
    output.flush()


def prompt_install_plan(
    input_stream: TextIO,
    output_stream: TextIO,
    *,
    sections: Sequence[Dict[str, Any]],
    keys: Optional[Iterable[str]] = None,
) -> List[HostInstallPlan]:
    states = [
        _HostState(
            host=str(section["host"]),
            label=str(section["label"]),
            version=str(section.get("version", "")),
            enabled=True,
            components=list(section["components"]),
            selected=set(section["selected"]),
            context_status=str(section.get("context_status", "")),
            agent_policy_status=str(section.get("agent_policy_status", "")),
        )
        for section in sections
    ]
    rows = _rows(states)
    selectable = [
        index
        for index, row in enumerate(rows)
        if row[0] != "header" and row[0] not in SECTION_LABELS
    ]
    cursor_position = 0
    cursor = selectable[cursor_position]
    key_iterator = iter(keys) if keys is not None else None
    file_descriptor = None
    previous = None
    if key_iterator is None:
        file_descriptor = input_stream.fileno()
        previous = termios.tcgetattr(file_descriptor)
        tty.setcbreak(file_descriptor)
        output_stream.write(HIDE_CURSOR)

    try:
        while True:
            _render(output_stream, states, rows, cursor)
            key = next(key_iterator, "exit") if key_iterator is not None else _read_key(input_stream)
            if key == "up":
                cursor_position = (cursor_position - 1) % len(selectable)
            elif key == "down":
                cursor_position = (cursor_position + 1) % len(selectable)
            elif key == "exit":
                return []
            elif key in ("toggle", "enter"):
                kind, host_index, component_index = rows[cursor]
                if kind == "install":
                    return [
                        HostInstallPlan(
                            host=state.host,
                            components=[
                                str(component["name"])
                                for component in state.components
                                if component["name"] in state.selected
                            ],
                            reset=state.reset,
                            include_template=state.include_template,
                            configure_codex=state.configure_codex,
                            change_context_window=state.change_context_window,
                            change_agent_policy=state.change_agent_policy,
                        )
                        for state in states
                        if state.enabled
                    ]
                if kind == "exit":
                    return []
                state = states[host_index]
                if kind == "host":
                    state.enabled = not state.enabled
                elif kind == "component" and state.enabled:
                    name = str(state.components[component_index]["name"])
                    if name in state.selected:
                        state.selected.remove(name)
                    else:
                        state.selected.add(name)
                elif kind == "recommended" and state.enabled:
                    state.selected = {
                        str(component["name"])
                        for component in state.components
                        if component.get("default") is True
                        and component.get("lifecycle") == "supported"
                    }
                elif kind == "configure" and state.enabled:
                    state.configure_codex = not state.configure_codex
                elif kind == "context" and state.enabled:
                    state.change_context_window = not state.change_context_window
                elif kind == "agent-policy" and state.enabled:
                    state.change_agent_policy = not state.change_agent_policy
                elif kind == "reset" and state.enabled:
                    state.reset = not state.reset
                    if not state.reset:
                        state.include_template = False
                elif kind == "template" and state.enabled and state.reset:
                    state.include_template = not state.include_template
            cursor = selectable[cursor_position]
    finally:
        if file_descriptor is not None and previous is not None:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous)
            output_stream.write(SHOW_CURSOR + "\n")
            output_stream.flush()
