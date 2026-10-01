#!/usr/bin/env python3
"""Model-free native Claude CLI lifecycle in disposable HOME/config directories.

Requires an installed Claude CLI; never installs a CLI, copies authentication,
or starts a model session. JSON reports describe registration and file checks,
not session activation. Only this test's temporary source copy is removed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.install.claude import MIN_VERSION, SOURCE_RECORD
from scripts.install.state import InstallState


class E2EFailure(RuntimeError):
    pass


def isolated_environment(root: Path, binary: Path) -> Dict[str, str]:
    """Allow only process basics; ambient credentials/config variables are absent."""
    values = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TERM", "SHELL") if key in os.environ}
    for name in ("home", "claude-home", "codex-home", "xdg-config", "xdg-cache", "temp", "bin"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "bin" / "claude").symlink_to(binary)
    values.update({"HOME": str(root / "home"), "CLAUDE_CONFIG_DIR": str(root / "claude-home"),
                   "CODEX_HOME": str(root / "codex-home"), "XDG_CONFIG_HOME": str(root / "xdg-config"),
                   "XDG_CACHE_HOME": str(root / "xdg-cache"), "TMPDIR": str(root / "temp"),
                   "PATH": str(root / "bin") + os.pathsep + values.get("PATH", os.defpath),
                   "PYTHONDONTWRITEBYTECODE": "1", "DISABLE_AUTOUPDATER": "1",
                   "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1",
                   "DISABLE_ERROR_REPORTING": "1"})
    return values


def run(command: Sequence[str], *, cwd: Path, environment: Mapping[str, str],
        records: list, stage: str) -> str:
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=str(cwd), env=dict(environment), text=True,
                                capture_output=True, check=False, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise E2EFailure(stage + " failed: " + type(exc).__name__) from exc
    records.append(dict(stage=stage, exit_code=result.returncode,
                        seconds=round(time.monotonic() - started, 3)))
    if result.returncode:
        # Do not promote arbitrary native output or authentication diagnostics.
        raise E2EFailure("{} exited {}".format(stage, result.returncode))
    return result.stdout


def inventory(output: str, field: str) -> list:
    try:
        data = json.loads(output)
        rows = data if isinstance(data, list) else data[field]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError()
        return rows
    except (ValueError, KeyError, TypeError) as exc:
        raise E2EFailure("Invalid native Claude " + field + " inventory") from exc


def copy_source(source: Path, target: Path) -> None:
    """Copy installer inputs, never private Git data, auth, or evaluation runs."""
    target.mkdir()
    for name in ("scripts", "marketplace", "templates"):
        shutil.copytree(source / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("VERSION", "components.json"):
        shutil.copy2(source / name, target / name)


def scenario(source: Path, version: str, root: Path, binary: Path, records: list) -> dict:
    env = isolated_environment(root, binary)
    cli_version = run((str(binary), "--version"), cwd=root, environment=env,
                      records=records, stage="claude-version").strip()
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", cli_version)
    if match is None or tuple(map(int, match.groups())) < MIN_VERSION:
        raise E2EFailure("Claude Code {}.{}.{} or later is required".format(*MIN_VERSION))
    catalog = json.loads((source / "components.json").read_text())
    components = {item["name"]: item for item in catalog["components"]
                  if item.get("lifecycle") == "supported" and "claude" in item.get("hosts", {})}
    plugins = {name: item for name, item in components.items() if item["kind"] == "plugin"}
    if not plugins or "claude-md" not in components:
        raise E2EFailure("Expected active Claude plugins and claude-md")
    recommended = {name for name, item in components.items() if item.get("default") is True}
    marketplace = catalog["marketplaces"]["claude"]
    home = Path(env["CLAUDE_CONFIG_DIR"])
    staged = home / "plugins" / marketplace
    clone = root / "input-source"
    copy_source(source, clone)
    guide = home / "CLAUDE.md"
    personal_guide = b"# Personal Claude guide\n\nPreserve this exact user text.\n"
    guide.write_bytes(personal_guide)
    settings = home / "settings.json"
    personal_settings = dict(model="sonnet", effortLevel="medium", language="Korean", autoMemoryEnabled=False,
                             env={"HUKUHAKA_E2E_SENTINEL": "personal-setting"})
    settings.write_text(json.dumps(personal_settings, indent=2) + "\n")
    preserved = {home / "agents" / "personal.md": b"---\nname: personal\ndescription: Personal agent\n---\nKeep user agent.\n",
                 home / "plugins" / "data" / "unmanaged-other" / "sentinel": b"unmanaged data",
                 Path(env["CODEX_HOME"]) / "config.toml": b'model = "personal-codex"\n'}
    # Documented CLAUDE_PLUGIN_DATA directory: replace punctuation in plugin ID.
    # https://code.claude.com/docs/en/plugins-reference#environment-variables
    for name in plugins:
        plugin_id = re.sub(r"[^A-Za-z0-9_-]", "-", name + "@" + marketplace)
        preserved[home / "plugins" / "data" / plugin_id / "sentinel"] = b"managed plugin persistent data"
    for path, content in preserved.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def check_personal(*, guidance: bool) -> None:
        values = json.loads(settings.read_text())
        if any(values.get(key) != value for key, value in personal_settings.items()):
            raise E2EFailure("Component lifecycle changed personal preferences")
        if any(not path.is_file() or path.read_bytes() != content for path, content in preserved.items()):
            raise E2EFailure("Component lifecycle changed user agent, data, or Codex files")
        if guidance:
            if personal_guide.rstrip(b"\n") not in guide.read_bytes():
                raise E2EFailure("Managed guidance lost user text")
        elif guide.read_bytes() != personal_guide:
            raise E2EFailure("Removed managed guidance did not restore personal file")

    def native(*args: str, stage: str) -> str:
        return run((str(binary), *args), cwd=root, environment=env, records=records, stage=stage)

    def check_selection(expected: set, label: str) -> None:
        rows = inventory(native("plugin", "list", "--json", stage=label + "-inventory"), "plugins")
        managed = {row["id"].split("@", 1)[0]: row for row in rows
                   if str(row.get("id", "")).endswith("@" + marketplace) and row.get("scope") == "user"}
        if set(managed) != expected & set(plugins):
            raise E2EFailure("Native installed selection differs at " + label)
        records_now = InstallState(home).read()
        expected_records = expected | ({SOURCE_RECORD} if any(path.is_file() for path in staged.rglob("*")) else set())
        if set(records_now["components"]) != expected_records:
            raise E2EFailure("Installer component receipts differ at " + label)
        for name, row in managed.items():
            metadata = json.loads((source / plugins[name]["hosts"]["claude"]["manifest"]).read_text())
            if row.get("version") != metadata["version"] or row.get("enabled") is not True:
                raise E2EFailure("Native plugin version/enabled state differs: " + name)
        if records_now["operations"] and records_now["operations"][-1]["status"] != "success":
            raise E2EFailure("Installer recorded an unsuccessful operation")
        check_personal(guidance="claude-md" in expected)

    def install(action: str, *flags: str, label: str) -> None:
        run(("/bin/bash", str(source / "scripts/install.sh"), "--source-dir", str(clone),
             "--version", version, "claude", action, *flags), cwd=root, environment=env,
            records=records, stage=label)

    config_before = settings.read_bytes()
    install("install", "--recommended", "--dry-run", "--yes", label="recommended-dry-run")
    if settings.read_bytes() != config_before or (home / "hk-config.toml").exists() or staged.exists():
        raise E2EFailure("Dry run changed settings, receipts, or managed source")
    check_personal(guidance=False)
    all_names = sorted(components)
    for label in ("all-install", "all-repeat"):
        install("install", "--components", ",".join(all_names), "--yes", label=label)
        check_selection(set(all_names), label)
    disabled = sorted(plugins)[0]
    native("plugin", "disable", disabled + "@" + marketplace, "--scope", "user", "--json",
           stage="disable-selected-plugin")
    disabled_rows = inventory(native("plugin", "list", "--json", stage="disabled-inventory"), "plugins")
    matching = [row for row in disabled_rows if row.get("id") == disabled + "@" + marketplace
                and row.get("scope") == "user"]
    if len(matching) != 1 or matching[0].get("enabled") is not False:
        raise E2EFailure("Native CLI did not establish the disabled-plugin test precondition")
    check_personal(guidance=True)
    install("install", "--components", ",".join(all_names), "--yes", label="disabled-plugin-reconcile")
    check_selection(set(all_names), "disabled-plugin-reconcile")
    staged_before = {path.relative_to(staged).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in staged.rglob("*") if path.is_file()}
    # The durable managed copy must remain usable after this input clone is gone.
    shutil.rmtree(clone)
    for name in sorted(plugins):
        native("plugin", "validate", "--strict", str(staged / name), stage="durable-validate-" + name)
    native("plugin", "marketplace", "update", marketplace, stage="durable-marketplace-update")
    native("plugin", "update", next(iter(sorted(plugins))) + "@" + marketplace,
           "--scope", "user", "--json", stage="durable-plugin-update")
    staged_after = {path.relative_to(staged).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in staged.rglob("*") if path.is_file()}
    if staged_before != staged_after:
        raise E2EFailure("Input clone removal changed durable source")
    check_selection(set(all_names), "durable-source")
    copy_source(source, clone)
    for label in ("recommended-deselect", "recommended-repeat"):
        install("install", "--recommended", "--yes", label=label)
        check_selection(recommended, label)
    install("reset", "--recommended", "--include-template", "--yes", label="recommended-reset")
    # --include-template adds the host's global-guidance component explicitly.
    check_selection(recommended | {"claude-md"}, "recommended-reset")
    for label in ("uninstall", "uninstall-repeat"):
        install("uninstall", "--yes", label=label)
        check_selection(set(), label)
        marketplaces = inventory(native("plugin", "marketplace", "list", "--json",
                                        stage=label + "-marketplaces"), "marketplaces")
        if any(row.get("name") == marketplace for row in marketplaces):
            raise E2EFailure("Uninstall left the managed marketplace registered")
        if staged_before.keys() & {path.relative_to(staged).as_posix() for path in staged.rglob("*") if path.is_file()}:
            raise E2EFailure("Uninstall left receipt-owned source files")
    return dict(cli_version=cli_version, plugin_count=len(plugins), model_calls=0,
                authentication_copied=False, runtime_activation="not observed")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", "--source-dir", dest="source", type=Path, required=True)
    parser.add_argument("--version")
    parser.add_argument("--report", type=Path, help="optional model-free check metadata JSON")
    args = parser.parse_args(argv)
    records = []
    report = dict(status="failed", checks=records, model_calls=0)
    try:
        binary_name = shutil.which("claude")
        if binary_name is None:
            raise E2EFailure("Installed Claude CLI not found; this check does not install it")
        source = args.source.resolve()
        version = args.version or (source / "VERSION").read_text().strip()
        with tempfile.TemporaryDirectory(prefix="hukuhaka-claude-real-e2e-") as name:
            report.update(scenario(source, version, Path(name).resolve(), Path(binary_name).resolve(), records))
        report.update(status="pass", installer_version=version)
        print("Claude isolated real-CLI lifecycle PASS; {} plugins, zero model calls; session activation not observed.".format(report["plugin_count"]))
        return 0
    except (E2EFailure, OSError, ValueError) as exc:
        report["error"] = str(exc) if isinstance(exc, E2EFailure) else type(exc).__name__
        print("Claude real-CLI lifecycle failed: " + report["error"], file=sys.stderr)
        return 1
    finally:
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
