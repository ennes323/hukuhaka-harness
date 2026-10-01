"""Claude native lifecycle with a durable, receipt-owned marketplace source.

File transactions never claim to roll back native CLI side effects. Every
completed step is recorded so an interrupted or partial install can be retried.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Set, Tuple

from .common import (DriftError, FileTransaction, InstallerError, InstallerLock,
                     StateError, installer_state, load_json, safe_join, sha256_file)
from .guidance import GuidanceDeployment, _block, _hash
from .state import InstallState

MIN_VERSION = (2, 1, 281)
SOURCE_RECORD = "claude-marketplace"
RETIRED = {"hukuhaka-codex"}


def resolve_claude_home(environ: Optional[Mapping[str, str]] = None, *, fallback_home: Optional[Path] = None) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(configured).expanduser() if configured else (fallback_home or Path.home()) / ".claude"


class ClaudeInstaller:
    def __init__(self, repo_root: Path, catalog: dict, version: str, *,
                 local_source: bool = False, dry_run: bool = False, force: bool = False) -> None:
        self.repo_root = repo_root
        self.catalog = catalog
        self.version = version
        self.home = resolve_claude_home()
        self.state = InstallState(self.home)
        self.marketplace = catalog.get("marketplaces", {}).get("claude", "hukuhaka-plugin")
        self.source = self.home / "plugins" / self.marketplace
        self.legacy_path = self.home / ".hukuhaka-manifest.json"
        self.dry_run = dry_run
        self.force = force
        self.completed = []
        self.operation_id = None
        self.stage = "start"
        self.components = {c["name"]: c for c in catalog["components"] if "claude" in c.get("hosts", {})}
        self.plugin_names = {name for name, item in self.components.items() if item["kind"] == "plugin"}
        # Reject linked state/locks before even a native CLI or lock acquisition
        # can write into an unexpected location.
        self._safe("hk-operation.lock")
        self._safe(".hukuhaka-installer.lock")

    def _error(self, message: str, stage: Optional[str] = None) -> InstallerError:
        return InstallerError(message, host="claude", stage=stage or self.stage)

    def _safe(self, relative: str) -> Path:
        path = safe_join(self.home, relative, operation="claude-path")
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise self._error("managed path is a symlink: " + relative)
            if candidate == self.home.absolute():
                break
        return path

    def _cli(self, *args: str, json_output: bool = False, mutate: bool = False) -> Any:
        if mutate and self.dry_run:
            print("  [dry-run] claude " + " ".join(args))
            return None
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(self.home.absolute())
        try:
            result = subprocess.run(["claude", *args], cwd=str(self.repo_root), env=env,
                                    capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise self._error("Claude CLI unavailable or timed out ({})".format(type(exc).__name__)) from exc
        if result.returncode:
            # Do not promote arbitrary CLI output (which can contain credentials).
            raise self._error("Claude CLI {} exited {}".format(" ".join(args[:3]), result.returncode))
        if not json_output:
            return result.stdout.strip()
        try:
            value = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise self._error("Claude CLI returned invalid JSON") from exc
        if isinstance(value, dict) and value.get("success") is False:
            raise self._error("Claude CLI reported an unsuccessful operation")
        return value

    def require_cli(self) -> str:
        version = self._cli("--version")
        match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", version)
        if match is None or tuple(map(int, match.groups())) < MIN_VERSION:
            raise self._error("Claude Code 2.1.281 or later is required", "detect")
        return version

    def _plugins(self, *, all_scopes: bool = False) -> list:
        data = self._cli("plugin", "list", "--json", json_output=True)
        rows = data if isinstance(data, list) else data.get("plugins") if isinstance(data, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise self._error("invalid Claude plugin inventory")
        return [row for row in rows if str(row.get("id", "")).endswith("@" + self.marketplace)
                and (all_scopes or row.get("scope") == "user")]

    def _marketplace_info(self) -> Optional[dict]:
        data = self._cli("plugin", "marketplace", "list", "--json", json_output=True)
        rows = data if isinstance(data, list) else data.get("marketplaces") if isinstance(data, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise self._error("invalid Claude marketplace inventory")
        matches = [row for row in rows if row.get("name") == self.marketplace]
        if len(matches) > 1:
            raise self._error("duplicate Claude marketplace identity")
        return matches[0] if matches else None

    def _check_marketplace(self) -> Optional[dict]:
        info = self._marketplace_info()
        if info is not None:
            if info.get("source") != "directory" or not isinstance(info.get("path"), str):
                raise self._error("existing Claude marketplace is not the managed directory source")
            if Path(info["path"]).resolve() != self.source.resolve():
                raise self._error("existing Claude marketplace points to a different source")
        return info

    def _legacy(self) -> Optional[dict]:
        self._safe(self.legacy_path.name)
        value = self.state._legacy(self.legacy_path)
        if value is None:
            return None
        if value.get("schemaVersion") != 2 or not isinstance(value.get("version"), str) or not value["version"]:
            raise self._error("legacy Claude ownership requires a versioned hash receipt", "legacy-preflight")
        components, files, hashes = (value.get(key) for key in ("components", "files", "hashes"))
        if (not isinstance(components, list) or any(not isinstance(n, str) for n in components)
                or not set(components) <= self.plugin_names | RETIRED | {"claude-md"}
                or not isinstance(files, list) or any(not isinstance(p, str) for p in files)
                or len(set(files)) != len(files) or not isinstance(hashes, dict) or set(files) != set(hashes)):
            raise self._error("invalid legacy Claude ownership entries", "legacy-preflight")
        prefix = "plugins/" + self.marketplace + "/"
        for relative in files:
            if relative != "CLAUDE.md" and not relative.startswith(prefix):
                raise self._error("legacy receipt contains an unknown target", "legacy-preflight")
            self._safe(relative)
            if not isinstance(hashes[relative], str) or not re.fullmatch(r"[a-f0-9]{64}", hashes[relative]):
                raise self._error("legacy ownership hash is invalid", "legacy-preflight")
        if self.state.read()["components"].get(SOURCE_RECORD):
            raise self._error("legacy and current Claude ownership coexist; recover before continuing", "legacy-preflight")
        return value

    def _files(self) -> Dict[str, str]:
        receipt = self.state.receipt(SOURCE_RECORD, None)
        if receipt is None:
            legacy = self._legacy()
            return {p: digest for p, digest in (legacy or {}).get("hashes", {}).items() if p != "CLAUDE.md"}
        files = receipt.get("files")
        if not isinstance(files, dict):
            raise self._error("invalid Claude source receipt")
        for relative, digest in files.items():
            if not isinstance(relative, str) or not relative.startswith("plugins/" + self.marketplace + "/"):
                raise self._error("unknown Claude source receipt target")
            self._safe(relative)
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise self._error("invalid Claude source digest")
        return files

    def _check_hashes(self, files: Mapping[str, str]) -> None:
        for relative, expected in files.items():
            path = self._safe(relative)
            if path.exists() and not path.is_file():
                raise self._error("managed file has changed type: " + relative)
            if path.is_file() and sha256_file(path) != expected and not self.force:
                raise DriftError("managed Claude file changed: " + relative, host="claude", stage="preflight")

    def guidance(self, enabled: bool = True) -> GuidanceDeployment:
        return GuidanceDeployment(self.repo_root / "templates" / "CLAUDE.md", self.home, self.version,
                                  enabled=enabled, dry_run=self.dry_run, force=self.force,
                                  host="claude", component="claude-md", target_name="CLAUDE.md")

    def current_component_state(self) -> Tuple[Set[str], Dict[str, str]]:
        legacy = self._legacy()
        recorded = set(self.state.read()["components"]) | set((legacy or {}).get("components", []))
        rows = self._plugins()
        versions = {row["id"].split("@", 1)[0]: str(row.get("version", "unknown")) for row in rows}
        return (recorded | set(versions)) & set(self.components), versions

    def current_components(self) -> Set[str]:
        return self.current_component_state()[0]

    def preview(self) -> None:
        legacy = self._legacy()
        if legacy:
            print("  Legacy ownership: {} hashed files; convert to current receipts.".format(len(legacy["files"])))
            if "CLAUDE.md" in legacy["files"]:
                print("  Global guidance: replace the unchanged legacy file with a managed common-guidance block.")
        retired = [row["id"] for row in self._plugins() if row["id"].split("@", 1)[0] in RETIRED]
        if retired:
            print("  Retained legacy plugins: " + ", ".join(retired))
        print("  Marketplace source: durable managed copy at {}".format(self.source))
        print("  User settings and unmanaged agents are preserved. Plugin data is retained on removal.")

    def _source_plan(self) -> Dict[str, Tuple[bytes, int]]:
        entries = []
        planned = {}
        for name in sorted(self.plugin_names):
            component = self.components[name]
            manifest = self.repo_root / component["hosts"]["claude"]["manifest"]
            if not manifest.resolve().is_relative_to(self.repo_root.resolve()):
                raise self._error("plugin manifest escapes repository")
            for part in (manifest, *manifest.parents):
                if part.is_symlink():
                    raise self._error("plugin manifest path contains a symlink")
                if part == self.repo_root:
                    break
            metadata = load_json(manifest, {})
            if metadata.get("name") != name or not isinstance(metadata.get("version"), str):
                raise self._error("missing or invalid Claude manifest for " + name)
            plugin_root = manifest.parent.parent
            if not plugin_root.resolve().is_relative_to(self.repo_root.resolve()):
                raise self._error("plugin source escapes repository")
            for source in sorted(plugin_root.rglob("*")):
                if source.is_symlink():
                    raise self._error("plugin source contains symlinks")
                if source.is_file() and "__pycache__" not in source.parts and not source.name.endswith(".pyc"):
                    relative = "plugins/{}/{}/{}".format(self.marketplace, name, source.relative_to(plugin_root).as_posix())
                    planned[relative] = (source.read_bytes(), source.stat().st_mode & 0o777)
            entries.append({"name": name, "source": "./" + name, "version": metadata["version"],
                            "description": metadata.get("description", name)})
        # Installed retired plugins remain local compatibility entries, never
        # resurrected in the distributed marketplace or offered for new installs.
        for name in sorted(RETIRED):
            prefix = "plugins/{}/{}/".format(self.marketplace, name)
            retained = {p: digest for p, digest in self._files().items() if p.startswith(prefix)}
            if retained:
                for relative in retained:
                    path = self._safe(relative)
                    if not path.is_file():
                        raise self._error("retained legacy plugin source is incomplete")
                    planned[relative] = (path.read_bytes(), path.stat().st_mode & 0o777)
                entries.append({"name": name, "source": "./" + name})
        marketplace = {"name": self.marketplace, "description": "Hukuhaka native Claude Code plugins",
                       "owner": {"name": "hukuhaka"}, "plugins": entries}
        planned["plugins/{}/.claude-plugin/marketplace.json".format(self.marketplace)] = (
            (json.dumps(marketplace, indent=2) + "\n").encode(), 0o644)
        return planned

    def _preflight(self, desired: Sequence[str], *, reset_template: bool = False) -> None:
        if set(desired) - set(self.components):
            raise self._error("unknown Claude component selection")
        self.require_cli()
        self._check_marketplace()
        legacy = self._legacy()
        owned = self._files()
        self._check_hashes((legacy or {}).get("hashes", owned))
        planned = self._source_plan()
        for relative in planned:
            path = self._safe(relative)
            if path.exists() and relative not in owned:
                raise self._error("unmanaged source file conflicts: " + relative)
        if not legacy or "CLAUDE.md" not in legacy["files"]:
            if reset_template:
                self.guidance(False)._plan_uninstall()
            if "claude-md" in desired:
                self.guidance()._plan_deploy()
            else:
                self.guidance(False)._plan_uninstall()

    def _done(self, detail: str) -> None:
        self.completed.append(detail)
        if self.operation_id:
            self.state.update_operation(self.operation_id, self.stage, self.completed)
        print(("  [dry-run] " if self.dry_run else "  [ok] ") + detail)

    @contextlib.contextmanager
    def _operation(self, action: str, desired: Sequence[str]):
        self.completed = []
        lock = contextlib.nullcontext() if self.dry_run else InstallerLock(self.home, name="hk-operation.lock")
        with lock:
            if not self.dry_run:
                with installer_state(self.home, dry_run=False):
                    self.state.read()
                self.operation_id = self.state.begin_operation(action, self.version, list(desired))
            try:
                yield
            except Exception as exc:
                if self.operation_id:
                    self.state.finish_operation(self.operation_id, "partial" if self.completed else "failed", self.completed, exc)
                raise
            else:
                if self.operation_id:
                    self.state.finish_operation(self.operation_id, "success", self.completed)
            finally:
                self.operation_id = None

    def _migrate(self, desired: Sequence[str]) -> None:
        legacy = self._legacy()
        if legacy is None:
            return
        if self.dry_run:
            print("  [dry-run] back up and migrate legacy Claude ownership")
            return
        self.stage = "legacy-migrate"
        with installer_state(self.home, dry_run=False):
            legacy = self._legacy()
            self._check_hashes(legacy["hashes"])
            with FileTransaction(self.home) as tx:
                files = {p: h for p, h in legacy["hashes"].items() if p != "CLAUDE.md"}
                self.state.put_receipt(tx, SOURCE_RECORD, {"version": legacy["version"], "files": files},
                                       "marketplace", self.version, self.legacy_path)
                if "CLAUDE.md" in legacy["files"]:
                    target = self._safe("CLAUDE.md")
                    if target.is_file():
                        tx.copy_file(target, self.home / "hk-backups" / "legacy" / ("CLAUDE-" + sha256_file(target) + ".md"))
                    if "claude-md" in desired:
                        block = _block((self.repo_root / "templates" / "CLAUDE.md").read_bytes())
                        tx.write_bytes(target, block + b"\n")
                        receipt = {"schemaVersion": 1, "component": "claude-md", "version": self.version,
                                   "target": "CLAUDE.md", "managedHash": _hash(block), "prefix": "", "suffix": "\n"}
                        self.state.put_receipt(tx, "claude-md", receipt, "template", self.version, None)
                    else:
                        tx.remove(target)
                tx.commit()
        self._done("migrated legacy ownership; retained retired plugin files")

    def _stage_source(self) -> None:
        self.stage = "source-stage"
        planned = self._source_plan()
        owned = self._files()
        if self.dry_run:
            print("  [dry-run] stage {} source files in {}".format(len(planned), self.source))
            return
        with installer_state(self.home, dry_run=False):
            self._check_hashes(owned)
            for relative in planned:
                if self._safe(relative).exists() and relative not in owned:
                    raise self._error("unmanaged source file appeared: " + relative)
            with FileTransaction(self.home) as tx:
                for relative in sorted(set(owned) - set(planned)):
                    tx.remove(self._safe(relative))
                for relative, (content, mode) in planned.items():
                    target = self._safe(relative)
                    if not target.is_file() or target.read_bytes() != content or target.stat().st_mode & 0o777 != mode:
                        tx.write_bytes(target, content, mode)
                for name in sorted(self.plugin_names):
                    self._cli("plugin", "validate", "--strict", str(self.source / name))
                self.state.put_receipt(tx, SOURCE_RECORD,
                                       {"version": self.version, "files": {p: _hash(v[0]) for p, v in planned.items()}},
                                       "marketplace", self.version, None)
                tx.commit()
        self._done("staged durable Claude marketplace source")

    def _register(self) -> None:
        self.stage = "marketplace-register"
        info = self._check_marketplace()
        if info is None:
            self._cli("plugin", "marketplace", "add", str(self.source.absolute()), "--scope", "user", mutate=True)
        else:
            self._cli("plugin", "marketplace", "update", self.marketplace, mutate=True)
        if not self.dry_run and self._check_marketplace() is None:
            raise self._error("Claude marketplace registration did not persist")
        self._done("registered Claude marketplace")

    def _remove_plugin(self, name: str) -> None:
        self.stage = "plugin-remove"
        self._cli("plugin", "uninstall", name + "@" + self.marketplace, "--scope", "user", "--keep-data", "--json",
                  json_output=True, mutate=True)
        if not self.dry_run:
            if any(row["id"].split("@", 1)[0] == name for row in self._plugins()):
                raise self._error("Claude plugin remains installed: " + name)
            self.state.remove_plugin(name)
        self._done("removed {} (persistent data retained)".format(name))

    def install(self, components: Sequence[str], *, reset: bool = False, include_template: bool = False) -> None:
        self.stage = "preflight"
        self.require_cli()
        with self._operation("reset" if reset else "install", components):
            # Re-read ownership after acquiring the operation lock and recovery.
            self._preflight(components, reset_template=reset and include_template)
            self._migrate(components)
            self._stage_source()
            self._register()
            rows = {row["id"].split("@", 1)[0]: row for row in self._plugins()}
            desired = set(components) & self.plugin_names
            for name in sorted(desired):
                if reset and name in rows:
                    self._remove_plugin(name)
                    rows.pop(name)
                self.stage = "plugin-install"
                self._cli("plugin", "update" if name in rows else "install", name + "@" + self.marketplace,
                          "--scope", "user", "--json", json_output=True, mutate=True)
                if not self.dry_run:
                    installed = [row for row in self._plugins() if row["id"] == name + "@" + self.marketplace]
                    if len(installed) == 1 and installed[0].get("enabled") is False:
                        self._cli("plugin", "enable", name + "@" + self.marketplace,
                                  "--scope", "user", "--json", json_output=True, mutate=True)
                        installed = [row for row in self._plugins() if row["id"] == name + "@" + self.marketplace]
                    metadata = load_json(self.source / name / ".claude-plugin" / "plugin.json", {})
                    if len(installed) != 1 or installed[0].get("version") != metadata["version"] or installed[0].get("enabled") is not True:
                        raise self._error("Claude plugin version/enabled verification failed: " + name)
                    self.state.set_plugin(name, metadata["version"], self.version)
                self._done("installed " + name)
            # Desired plugins must be verified before deselection removes any
            # previously working component (reset remains explicitly destructive).
            for name in sorted((set(rows) & self.plugin_names) - desired):
                self._remove_plugin(name)
            self.stage = "guidance"
            if reset and include_template:
                self.guidance(False).uninstall()
            self.guidance("claude-md" in components).deploy()
            self._done("reconciled Claude global guidance")
            if not self.dry_run:
                actual = {row["id"].split("@", 1)[0] for row in self._plugins()} & self.plugin_names
                if actual != desired:
                    raise self._error("Claude final component set differs from requested selection", "verify")
        print("Restart Claude Code to load updated plugins and instructions; registration checks do not prove session activation.")

    def uninstall(self) -> None:
        # Retired or other-scope plugins keep their shared source and registration.
        self.stage = "preflight"
        self.require_cli()
        with self._operation("uninstall", []):
            self._check_marketplace()
            legacy = self._legacy()
            self._check_hashes((legacy or {}).get("hashes", self._files()))
            if not legacy or "CLAUDE.md" not in legacy["files"]:
                self.guidance(False)._plan_uninstall()
            self._migrate([])
            for row in self._plugins():
                name = row["id"].split("@", 1)[0]
                if name in self.plugin_names:
                    self._remove_plugin(name)
            self.guidance(False).uninstall()
            if self._plugins(all_scopes=True):
                print("Retained marketplace source for legacy or other-scope plugins.")
            else:
                if self._check_marketplace() is not None:
                    self._cli("plugin", "marketplace", "remove", self.marketplace, mutate=True)
                    if not self.dry_run and self._marketplace_info() is not None:
                        raise self._error("Claude marketplace remains registered after removal")
                files = self._files()
                self._check_hashes(files)
                if not self.dry_run and files:
                    with installer_state(self.home, dry_run=False):
                        with FileTransaction(self.home) as tx:
                            for relative in sorted(files):
                                tx.remove(self._safe(relative))
                            self.state.remove_receipt(tx, SOURCE_RECORD, None)
                            tx.commit()
                elif self.dry_run:
                    print("  [dry-run] remove managed Claude source files")
            if not self.dry_run:
                installed = {row["id"].split("@", 1)[0] for row in self._plugins()}
                for name in self.plugin_names - installed:
                    if name in self.state.read()["components"]:
                        self.state.remove_plugin(name)
            self._done("removed active Claude components; user settings and unmanaged files preserved")
