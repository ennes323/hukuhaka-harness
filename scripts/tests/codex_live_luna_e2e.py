#!/usr/bin/env python3
"""Authenticated Luna smoke in a disposable Codex home.

The caller's file-backed auth is copied into a temporary directory with mode
0600. The copy and all generated sessions are removed when the test exits.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


class LunaE2EFailure(RuntimeError):
    pass


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=dict(environment),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise LunaE2EFailure(
            "command failed ({}): {}\n{}\n{}".format(
                result.returncode,
                " ".join(command),
                result.stdout,
                result.stderr,
            )
        )
    return result


def json_lines(path: Path) -> Iterable[Dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            yield item


def session_profile(path: Path) -> tuple[str, str, bool]:
    role = ""
    model = ""
    effort = ""
    completed = False
    for item in json_lines(path):
        if item.get("type") == "session_meta":
            payload = item.get("payload", {})
            source = payload.get("source", {}) if isinstance(payload, dict) else {}
            subagent = source.get("subagent", {}) if isinstance(source, dict) else {}
            spawn = subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}
            if isinstance(spawn, dict):
                role = str(spawn.get("agent_role", ""))
        elif item.get("type") == "turn_context":
            payload = item.get("payload", {})
            if isinstance(payload, dict):
                model = str(payload.get("model", ""))
                effort = str(payload.get("effort", payload.get("reasoning_effort", "")))
        elif item.get("type") == "event_msg":
            payload = item.get("payload", {})
            completed |= payload.get("type") in ("task_complete", "task_completed")
            if payload.get("type") == "thread_settings_applied":
                settings = payload.get("thread_settings", {})
                model = str(settings.get("model", model))
                effort = str(settings.get("reasoning_effort", effort))
    if role:
        raise LunaE2EFailure("disabled subagent execution produced a child rollout")
    return model, effort, completed


def agent_messages(output: str) -> Sequence[str]:
    messages = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                messages.append(text.strip())
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--auth-file")
    args = parser.parse_args()
    source = Path(args.source_dir).resolve()
    version = (source / "VERSION").read_text(encoding="utf-8").strip()
    active_home = Path(os.environ.get("CODEX_HOME", "")).expanduser()
    if not str(active_home) or str(active_home) == ".":
        active_home = Path.home() / ".codex"
    auth_source = Path(args.auth_file).expanduser() if args.auth_file else active_home / "auth.json"
    if not auth_source.is_file():
        raise LunaE2EFailure(
            "file-backed Codex auth is required for the release-tag Luna smoke"
        )

    with tempfile.TemporaryDirectory(prefix="hukuhaka-luna-live-e2e-") as temp_name:
        root = Path(temp_name)
        home = root / "home"
        codex_home = root / "codex-home"
        home.mkdir()
        codex_home.mkdir()
        auth_target = codex_home / "auth.json"
        shutil.copyfile(str(auth_source), str(auth_target))
        auth_target.chmod(0o600)
        environment = os.environ.copy()
        environment.update({"HOME": str(home), "CODEX_HOME": str(codex_home)})

        run(
            (
                "/bin/bash",
                str(source / "scripts" / "install.sh"),
                "--source-dir",
                str(source),
                "--version",
                version,
                "codex",
                "install",
                "--components",
                "result-runner",
                "--yes",
            ),
            cwd=source,
            environment=environment,
            timeout=120,
        )
        config = (codex_home / "config.toml").read_text(encoding="utf-8")
        if "model_catalog_json" in config or (codex_home / "models-luna-v2.json").exists():
            raise LunaE2EFailure("isolated install still depends on a model catalog override")
        if "multi_agent = false" not in config:
            raise LunaE2EFailure("isolated install did not disable subagents")

        prompt = (
            "Execute this exact command directly, without subagents: "
            "python3 -c 'print(314159)' . Working directory: " + str(root) + ". "
            "Python3 is available; no other prerequisites. Run only that command "
            "once, read its terminal output and exit code, and stop within 60 seconds. "
            "Do not edit files, run extra checks, retry, or spawn agents. "
            "If output is 314159 and exit code is 0, "
            "finish with exactly LUNA_TAG_E2E_OK."
        )
        result = run(
            (
                "codex",
                "exec",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--json",
                "-s",
                "read-only",
                "-m",
                "gpt-5.6-luna",
                "-C",
                str(root),
                "-c",
                'model_reasoning_effort="xhigh"',
                prompt,
            ),
            cwd=root,
            environment=environment,
            timeout=240,
        )
        if "LUNA_TAG_E2E_OK" not in agent_messages(result.stdout):
            raise LunaE2EFailure("parent Codex run did not confirm the Luna smoke")
        profiles = [
            session_profile(path)
            for path in (codex_home / "sessions").glob("**/rollout-*.jsonl")
        ]
        if profiles != [("gpt-5.6-luna", "xhigh", True)]:
            raise LunaE2EFailure(
                "expected exactly one completed standalone gpt-5.6-luna/xhigh rollout"
            )

    print("Authenticated isolated Luna smoke verified for v{}".format(version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
