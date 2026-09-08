#!/usr/bin/env python3
"""Deterministic setup, status, and archive operations for Hukuhaka Worklog."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, TextIO


WORKLOG_DIR = ".hukuhaka"
WORK_FILE = "work.md"
CHANGELOG_FILE = "changelog.md"
ARCHIVE_DIR = "changelog"
BEGIN_MARKER = "<!-- hukuhaka-worklog:begin -->"
END_MARKER = "<!-- hukuhaka-worklog:end -->"
WORK_SECTIONS = ("In Progress", "Planned", "On Hold")
ENTRY_RE = re.compile(r"^### (\d{4})-(\d{2})-(\d{2}) — (.+?)\s*$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}\.md$")
PLUGIN_NAME = "hukuhaka-worklog"
SKILL_NAME = "worklog"
COMMANDS = ("setup", "status", "archive")
RECENT_LIMIT = 25
CODEX_INVOCATION = f"${PLUGIN_NAME}:{SKILL_NAME}"
CODEX_LEGACY_INVOCATION = f"${SKILL_NAME}"
CODEX_COMMANDS = {
    f"{invocation} {command}": command
    for invocation in (CODEX_INVOCATION, CODEX_LEGACY_INVOCATION)
    for command in COMMANDS
}
CODEX_BOUND_COMMAND = re.compile(
    rf"\[{re.escape(CODEX_INVOCATION)}\]\([^\r\n]+\) "
    rf"(?P<command>{'|'.join(COMMANDS)})"
)

WORK_TEMPLATE = """# Work

> Current work only. Completed and closed outcomes belong in `changelog.md`.

## In Progress

## Planned

## On Hold
"""

CHANGELOG_TEMPLATE = f"""# Changelog

> Recent completed and closed work. Newest first; keep at most {RECENT_LIMIT} entries.
> Older entries live in `changelog/YYYY-MM.md`.

## Recent
"""


class WorklogError(RuntimeError):
    """Raised when a mechanical operation cannot proceed safely."""


@dataclass(frozen=True)
class HistoryEntry:
    date: str
    month: str
    title: str
    text: str

    @property
    def identity(self) -> tuple[str, str]:
        return self.date, self.title


def worklog_paths(root: Path) -> tuple[Path, Path, Path]:
    base = root / WORKLOG_DIR
    return base / WORK_FILE, base / CHANGELOG_FILE, base / ARCHIVE_DIR


def refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise WorklogError(f"refusing symlink target: {path}")


def atomic_write(path: Path, content: str) -> None:
    refuse_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def managed_block() -> str:
    return "\n".join(
        (
            BEGIN_MARKER,
            "## Worklog",
            "",
            "- `.hukuhaka/work.md` contains current Planned, In Progress, and On Hold work.",
            "- On the first non-trivial project task in a new session, read it before changing project files when both Worklog files exist.",
            "- Read `.hukuhaka/changelog.md` only when resuming, completing, closing, or checking prior decisions.",
            f"- Use the installed `{CODEX_INVOCATION}` Skill automatically when non-trivial project work starts, resumes, pauses, completes, or closes.",
            "- Analysis, implementation planning, routine one-off edits, and mechanical Worklog commands do not change lifecycle state.",
            "- If the files are missing during automatic use, continue the task without creating them; explicit Worklog requests require setup.",
            "- Only the primary agent changes Worklog state; delegated agents may read it but must not modify it.",
            "- Completed and closed work belongs in `.hukuhaka/changelog.md`.",
            END_MARKER,
        )
    )


def update_managed_text(current: str, block: str, path: Path) -> tuple[str, str]:
    begins = current.count(BEGIN_MARKER)
    ends = current.count(END_MARKER)
    if begins != ends or begins > 1:
        raise WorklogError(f"malformed or duplicate worklog markers in {path}")
    if begins == 0:
        separator = "" if not current else ("\n" if current.endswith("\n") else "\n\n")
        return current + separator + block + "\n", "updated"

    start = current.index(BEGIN_MARKER)
    end = current.index(END_MARKER, start) + len(END_MARKER)
    replacement = current[:start] + block + current[end:]
    if replacement == current:
        return current, "unchanged"
    return replacement, "updated"


def setup(root: Path) -> int:
    instruction = root / "AGENTS.md"
    refuse_symlink(instruction)
    current_instruction = instruction.read_text(encoding="utf-8") if instruction.exists() else ""
    next_instruction, instruction_state = update_managed_text(
        current_instruction,
        managed_block(),
        instruction,
    )

    work, changelog, archive = worklog_paths(root)
    for path in (work, changelog, archive):
        refuse_symlink(path)

    created: list[str] = []
    archive.mkdir(parents=True, exist_ok=True)
    if not work.exists():
        atomic_write(work, WORK_TEMPLATE)
        created.append(str(work.relative_to(root)))
    if not changelog.exists():
        atomic_write(changelog, CHANGELOG_TEMPLATE)
        created.append(str(changelog.relative_to(root)))
    if next_instruction != current_instruction:
        atomic_write(instruction, next_instruction)
        if not current_instruction:
            created.append(str(instruction.relative_to(root)))

    print("worklog setup (codex)")
    print("Created: " + (", ".join(created) if created else "none"))
    print(f"Instructions: {instruction.relative_to(root)} ({instruction_state})")
    print("Existing worklog files were left unchanged.")
    print("Start a new Codex session to load the instruction update.")
    return 0


def split_h2_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            if current in sections:
                raise WorklogError(f"duplicate section: ## {current}")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def work_items(text: str) -> dict[str, list[str]]:
    sections = split_h2_sections(text)
    if set(sections) != set(WORK_SECTIONS):
        raise WorklogError(
            "work.md must contain exactly: " + ", ".join(f"## {name}" for name in WORK_SECTIONS)
        )
    result: dict[str, list[str]] = {}
    for section in WORK_SECTIONS:
        result[section] = [
            line[2:].strip()
            for line in sections[section]
            if line.startswith("- ")
        ]
    return result


def parse_history(text: str, source: Path) -> tuple[str, list[HistoryEntry]]:
    marker = "## Recent"
    if text.count(marker) != 1:
        raise WorklogError(f"{source} must contain exactly one ## Recent section")
    prefix, body = text.split(marker, 1)
    if re.search(r"^## ", body, re.MULTILINE):
        raise WorklogError(f"{source} contains an unsupported section after ## Recent")

    lines = body.splitlines()
    chunks: list[list[str]] = []
    leading: list[str] = []
    for line in lines:
        if ENTRY_RE.match(line):
            chunks.append([line])
        elif chunks:
            chunks[-1].append(line)
        else:
            leading.append(line)
    if any(line.strip() for line in leading):
        raise WorklogError(f"{source} has content before its first history entry")

    entries: list[HistoryEntry] = []
    identities: set[tuple[str, str]] = set()
    for chunk in chunks:
        match = ENTRY_RE.match(chunk[0])
        assert match is not None
        year, month, day, title = match.groups()
        identity = (f"{year}-{month}-{day}", title)
        if identity in identities:
            raise WorklogError(f"duplicate history entry in {source}: {identity[0]} — {title}")
        identities.add(identity)
        entries.append(
            HistoryEntry(
                date=identity[0],
                month=f"{year}-{month}",
                title=title,
                text="\n".join(chunk).strip(),
            )
        )
    canonical_prefix = prefix.rstrip() + "\n\n" + marker
    return canonical_prefix, entries


def render_history(prefix: str, entries: Iterable[HistoryEntry]) -> str:
    bodies = [entry.text for entry in entries]
    return prefix.rstrip() + ("\n\n" + "\n\n".join(bodies) if bodies else "") + "\n"


def load_archive(path: Path, month: str) -> list[HistoryEntry]:
    if not path.exists():
        return []
    refuse_symlink(path)
    expected = f"# Changelog — {month}"
    text = path.read_text(encoding="utf-8")
    if not text.startswith(expected):
        raise WorklogError(f"{path} must start with {expected}")
    synthetic = "# Changelog\n\n## Recent\n" + text[len(expected):].lstrip("\n")
    _, entries = parse_history(synthetic, path)
    if any(entry.month != month for entry in entries):
        raise WorklogError(f"{path} contains an entry from another month")
    return entries


def render_archive(month: str, entries: Iterable[HistoryEntry]) -> str:
    bodies = [entry.text for entry in entries]
    return f"# Changelog — {month}\n" + ("\n" + "\n\n".join(bodies) if bodies else "") + "\n"


def archive_history(root: Path, keep: int = RECENT_LIMIT) -> int:
    if keep < 0:
        raise WorklogError("--keep must be zero or greater")
    _, changelog, archive_dir = worklog_paths(root)
    if not changelog.is_file():
        raise WorklogError(f"missing {changelog}; run worklog setup first")
    refuse_symlink(changelog)
    refuse_symlink(archive_dir)
    prefix, entries = parse_history(changelog.read_text(encoding="utf-8"), changelog)
    moving = entries[keep:]
    if not moving:
        print(f"worklog archive: Recent has {len(entries)} item(s); keep limit {keep}; nothing to move")
        return 0

    grouped: dict[str, list[HistoryEntry]] = {}
    for entry in moving:
        grouped.setdefault(entry.month, []).append(entry)

    writes: list[tuple[Path, str]] = []
    for month, month_entries in sorted(grouped.items(), reverse=True):
        path = archive_dir / f"{month}.md"
        existing = load_archive(path, month)
        by_identity = {entry.identity: entry for entry in existing}
        additions: list[HistoryEntry] = []
        for entry in month_entries:
            prior = by_identity.get(entry.identity)
            if prior is not None and prior.text != entry.text:
                raise WorklogError(
                    f"conflicting archive entry: {entry.date} — {entry.title} in {path}"
                )
            if prior is None:
                additions.append(entry)
        writes.append((path, render_archive(month, additions + existing)))

    # Archive destinations are written first. An interruption can duplicate a
    # Recent entry, but a rerun recognizes the exact archived copy and finishes.
    for path, content in writes:
        atomic_write(path, content)
    atomic_write(changelog, render_history(prefix, entries[:keep]))

    print(
        f"worklog archive: kept {min(keep, len(entries))} in Recent; "
        f"moved {len(moving)} to {len(grouped)} monthly archive(s)"
    )
    return 0


def status(root: Path) -> int:
    work, changelog, archive_dir = worklog_paths(root)
    if not work.is_file() or not changelog.is_file():
        raise WorklogError("worklog is not set up; run worklog setup first")
    refuse_symlink(work)
    refuse_symlink(changelog)

    items = work_items(work.read_text(encoding="utf-8"))
    _, recent = parse_history(changelog.read_text(encoding="utf-8"), changelog)
    months = (
        sorted(path.stem for path in archive_dir.iterdir() if path.is_file() and MONTH_RE.match(path.name))
        if archive_dir.is_dir()
        else []
    )

    print("Worklog status")
    for section in WORK_SECTIONS:
        values = items[section]
        print(f"\n{section} ({len(values)})")
        for value in values:
            print(f"- {value}")
    print(f"\nRecent history: {len(recent)}/{RECENT_LIMIT}")
    print("Archives: " + (", ".join(months) if months else "none"))
    return 0


def hook_response(reason: str) -> str:
    return json.dumps(
        {
            "decision": "block",
            "reason": reason.rstrip(),
        },
        ensure_ascii=False,
    )


def hook_command(prompt: str) -> str | None:
    prompt = prompt.rstrip("\r\n")
    command = CODEX_COMMANDS.get(prompt)
    if command is not None:
        return command
    match = CODEX_BOUND_COMMAND.fullmatch(prompt)
    return match.group("command") if match else None


def run_hook(
    source: TextIO,
    destination: TextIO,
    environment: Mapping[str, str],
) -> int:
    try:
        payload = json.load(source)
    except (json.JSONDecodeError, UnicodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    codex = "PLUGIN_DATA" in environment
    prompt = payload.get("prompt")
    command = hook_command(prompt) if codex and isinstance(prompt, str) else None
    if command is None:
        return 0

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        destination.write(hook_response("worklog: hook input is missing cwd"))
        return 0

    root = Path(cwd).resolve()
    output = io.StringIO()
    try:
        if not root.is_dir():
            raise WorklogError(f"project root is not a directory: {root}")
        with redirect_stdout(output):
            if command == "setup":
                setup(root)
            elif command == "status":
                status(root)
            else:
                archive_history(root)
        reason = output.getvalue()
    except (OSError, UnicodeError, WorklogError) as exc:
        reason = f"worklog {command}: {exc}"

    destination.write(hook_response(reason))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project root (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup_parser = subparsers.add_parser("setup")
    subparsers.add_parser("status")
    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("--keep", type=int, default=RECENT_LIMIT)
    subparsers.add_parser("hook")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "hook":
        return run_hook(sys.stdin, sys.stdout, os.environ)
    root = args.root.resolve()
    try:
        if args.command == "setup":
            return setup(root)
        if args.command == "status":
            return status(root)
        if args.command == "archive":
            return archive_history(root, args.keep)
        raise WorklogError(f"unsupported command: {args.command}")
    except (OSError, UnicodeError, WorklogError) as exc:
        print(f"worklog: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
