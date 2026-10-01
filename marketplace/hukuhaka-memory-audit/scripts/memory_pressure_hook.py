#!/usr/bin/env python3
"""Emit a one-shot Codex warning when local memory crosses review thresholds."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


HOT_BYTES = 25 * 1024
HOT_LINES = 200
COLD_INDEX_BYTES = 1024 * 1024
COLD_ROLLOUT_FILES = 300
STATE_VERSION = 1
STATE_FILE = "memory-pressure-state.json"
TIER_RANK = {"none": 0, "cold": 1, "hot": 2}


def physical_line_count(file_path: Path, limit: int) -> int:
    """Count physical lines only until the configured threshold is reached."""

    if file_path.is_symlink():
        return 0
    lines = 0
    saw_bytes = False
    last_byte = None
    try:
        with file_path.open("rb") as handle:
            while lines < limit:
                chunk = handle.read(8192)
                if not chunk:
                    break
                saw_bytes = True
                lines += chunk.count(b"\n")
                last_byte = chunk[-1]
    except OSError:
        return 0
    if lines >= limit:
        return limit
    if saw_bytes and last_byte != 0x0A:
        lines += 1
    return lines


def file_size(file_path: Path) -> int:
    try:
        return (
            file_path.stat().st_size
            if not file_path.is_symlink() and file_path.is_file()
            else 0
        )
    except OSError:
        return 0


def count_regular_files(directory: Path, limit: int) -> int:
    count = 0
    pending = [directory]
    while pending and count < limit:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        count += 1
                        if count >= limit:
                            break
                    elif entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
        except OSError:
            continue
    return count


def measure(memory_root: Path) -> dict[str, int]:
    summary_path = memory_root / "memory_summary.md"
    return {
        "summary_bytes": file_size(summary_path),
        "summary_lines": physical_line_count(summary_path, HOT_LINES),
        "index_bytes": file_size(memory_root / "MEMORY.md"),
        "rollout_files": count_regular_files(
            memory_root / "rollout_summaries",
            COLD_ROLLOUT_FILES,
        ),
    }


def pressure_tier(metrics: dict[str, int]) -> str:
    if metrics["summary_bytes"] >= HOT_BYTES or metrics["summary_lines"] >= HOT_LINES:
        return "hot"
    if (
        metrics["index_bytes"] >= COLD_INDEX_BYTES
        or metrics["rollout_files"] >= COLD_ROLLOUT_FILES
    ):
        return "cold"
    return "none"


def read_state(state_path: Path) -> dict[str, object]:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("version") == STATE_VERSION and state.get("tier") in TIER_RANK:
            return state
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        pass
    return {"version": STATE_VERSION, "tier": "none"}


def write_state(state_path: Path, tier: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_name(
        f"{state_path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp"
    )
    temporary.write_text(
        json.dumps({"version": STATE_VERSION, "tier": tier}, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, state_path)


def warning_for(tier: str) -> str:
    if tier == "hot":
        return (
            "Codex memory pressure: the always-loaded memory summary has reached "
            "25 KiB or 200 lines. Older, duplicated, or overly specific entries may "
            "reduce answer quality. Consider running $memory-audit."
        )
    return (
        "Codex memory pressure: MEMORY.md has reached 1 MiB or rollout summaries "
        "have reached 300 files. Retrieval may carry more stale or duplicated "
        "history. Consider running $memory-audit."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex",), default="codex")
    parser.parse_args()
    try:
        hook_input = json.load(sys.stdin)
        if (
            hook_input.get("hook_event_name") != "SessionStart"
            or hook_input.get("source") not in {"startup", "resume"}
        ):
            return

        plugin_data_value = os.environ.get("PLUGIN_DATA")
        if not plugin_data_value:
            return
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        next_tier = pressure_tier(measure(codex_home / "memories"))
        state_path = Path(plugin_data_value) / STATE_FILE
        previous_tier = str(read_state(state_path)["tier"])

        if next_tier == previous_tier:
            return
        write_state(state_path, next_tier)

        if TIER_RANK[next_tier] <= TIER_RANK[previous_tier]:
            return
        print(json.dumps({"systemMessage": warning_for(next_tier)}))
    except Exception:
        # Memory-pressure checks must never block a Codex session.
        return


if __name__ == "__main__":
    main()
