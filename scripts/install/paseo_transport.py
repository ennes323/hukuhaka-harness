"""Bounded, local Paseo CLI access for registered agent profiles.

Paseo 0.10.2 replaces the profile array without a conditional revision. The
before/after checks detect observed drift; they are not an atomic compare and
swap. Callers must tell users not to edit profiles while applying a batch.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import InstallerError


CONCURRENCY_NOTICE = (
    "Do not edit Paseo profiles while applying; native API has no conditional update."
)


class PaseoTransportError(InstallerError):
    """A native operation failed; attempted writes are never retried or reverted."""

    def __init__(self, message: str, *, mutation_attempted: bool = False, saved: Optional[bool] = None) -> None:
        super().__init__(message, host="paseo", stage="native-config")
        self.mutation_attempted = mutation_attempted
        self.attempted = mutation_attempted
        self.saved = saved


class LocalPaseoTransport:
    capabilities = {
        "local_only": True,
        "conditional_update": False,
        "profile_source": "live-daemon-config",
        "mode_validation": "provider-metadata",
        "feature_validation": True,
        "concurrency_notice": CONCURRENCY_NOTICE,
    }

    def __init__(self, home: Path, cli: Optional[str] = None, timeout: float = 20.0, cache: Optional[Path] = None) -> None:
        self.home = Path(home).expanduser().resolve()
        self.cli = cli or shutil.which("paseo")
        self.timeout = timeout
        self._deadline: Optional[float] = None
        self.cache = Path(cache) if cache is not None else self.home / "hk-runtime/paseo-sdk-0.10.2"
        self.node = shutil.which("node")
        self.npm = shutil.which("npm")
        self._cli_version: Optional[str] = None

    def require_cli(self) -> str:
        if not self.cli:
            raise PaseoTransportError("Paseo CLI is unavailable; install it or add paseo to PATH.")
        if self._cli_version is None:
            try:
                result = subprocess.run([self.cli, "--version"], capture_output=True, text=True, timeout=5)
                match = re.fullmatch(r"(?:paseo\s+)?v?(\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?", result.stdout.strip())
                if result.returncode or not match or tuple(map(int, match.groups())) < (0, 10, 2):
                    raise ValueError()
                self._cli_version = ".".join(match.groups())
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                raise PaseoTransportError("Paseo CLI 0.10.2 or later is required.") from exc
        return self._cli_version

    def prerequisites(self) -> List[str]:
        notices = ["Paseo profile validation requires Node 22 or later and the pinned public Paseo SDK 0.10.2."]
        if not self._sdk_ready():
            notices.append("Install the pinned SDK dependencies with npm ci --ignore-scripts into {} (about 25 MB).".format(self.cache))
        return notices

    def _sdk_ready(self) -> bool:
        self._check_cache_path()
        sources = Path(__file__).with_name("paseo-sdk")
        try:
            return all((self.cache / name).read_bytes() == (sources / name).read_bytes()
                       for name in ("package.json", "package-lock.json")) and json.loads(
                           (self.cache / "node_modules/@getpaseo/client/package.json").read_text()
                       ).get("version") == "0.10.2"
        except (OSError, ValueError):
            return False

    def _check_cache_path(self) -> None:
        paths = [self.cache, *self.cache.parents]
        paths.extend(self.cache / name for name in ("package.json", "package-lock.json", "node_modules", "npm-cache"))
        for path in paths:
            if path.is_symlink():
                raise PaseoTransportError("Paseo SDK cache path must not contain symlinks.")

    @staticmethod
    def _runtime_env() -> Dict[str, str]:
        env = dict(os.environ)
        for name in ("PASEO_HOST", "PASEO_HOME", "NODE_OPTIONS", "NODE_PATH"):
            env.pop(name, None)
        return env

    def _require_node(self) -> str:
        if not self.node:
            raise PaseoTransportError("Node 22 or later is required for Paseo profile validation.")
        try:
            result = subprocess.run([self.node, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode or int(result.stdout.strip().lstrip("v").split(".")[0]) < 22:
                raise ValueError()
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise PaseoTransportError("Node 22 or later is required for Paseo profile validation.") from exc
        return self.node

    def prepare(self) -> None:
        """Install only after caller review; reads and dry runs never call this."""
        self.require_cli()
        self._require_node()
        if self._sdk_ready():
            return
        if not self.npm:
            raise PaseoTransportError("npm is required to prepare the pinned Paseo SDK cache.")
        source = Path(__file__).with_name("paseo-sdk")
        self._check_cache_path()
        if self.cache.exists() and any(self.cache.iterdir()):
            try:
                owned = all((self.cache / name).read_bytes() == (source / name).read_bytes()
                            for name in ("package.json", "package-lock.json"))
            except OSError:
                owned = False
            if not owned:
                raise PaseoTransportError("Existing Paseo SDK cache is unmanaged; preserve it and select a clean cache path.")
        self.cache.mkdir(parents=True, exist_ok=True)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(source / name, self.cache / name)
        try:
            result = subprocess.run(
                [self.npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", str(self.cache / "npm-cache")],
                cwd=str(self.cache), capture_output=True, text=True, timeout=120, env=self._runtime_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PaseoTransportError("Pinned Paseo SDK setup failed; no profiles were changed.") from exc
        if result.returncode or not self._sdk_ready():
            raise PaseoTransportError("Pinned Paseo SDK setup failed; no profiles were changed.")

    def _sdk(self, operation: str, **extra: Any) -> Dict[str, Any]:
        node = self._require_node()
        if not self._sdk_ready():
            raise PaseoTransportError("Pinned Paseo SDK cache is missing; review and apply prerequisite setup first.")
        status = self.status()
        if status.get("localDaemon") != "running" or status.get("connectedDaemon") != "reachable":
            raise PaseoTransportError("The selected local Paseo daemon must be running and reachable.")
        listen = status.get("listen")
        if not isinstance(listen, str):
            raise PaseoTransportError("Paseo has no usable local listen address.")
        url = "ws://" + listen + "/ws"
        try:
            parsed = urlsplit(url)
        except ValueError as exc:
            raise PaseoTransportError("Paseo has an unsupported local listen address.") from exc
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.username or parsed.password:
            raise PaseoTransportError("Initial Paseo support requires a loopback TCP daemon; remote and IPC targets are unsupported.")
        request = {"operation": operation, "home": str(self.home), "cache": str(self.cache), "url": url, "cwd": str(Path.cwd()), **extra}
        timeout = 90.0
        if self._deadline is not None:
            timeout = min(timeout, self._deadline - time.monotonic())
            if timeout <= 0:
                raise PaseoTransportError("Paseo profile operation exceeded its time limit.")
        try:
            result = subprocess.run(
                [node, str(Path(__file__).with_name("paseo_sdk.mjs"))],
                input=json.dumps(request), capture_output=True, text=True, timeout=timeout, env=self._runtime_env(),
            )
            value = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise PaseoTransportError("Paseo SDK request failed; no profile write was requested.") from exc
        if result.returncode or not isinstance(value, dict) or value.get("error"):
            raise PaseoTransportError("Paseo SDK request failed; inspect the selected local daemon and SDK prerequisites.")
        return value

    def _call(self, *arguments: str, mutating: bool = False) -> Any:
        self.require_cli()
        timeout = self.timeout
        if self._deadline is not None:
            timeout = min(timeout, self._deadline - time.monotonic())
            if timeout <= 0:
                raise PaseoTransportError("Paseo profile operation exceeded its time limit.")
        env = self._runtime_env()
        command = [self.cli, "--home", str(self.home), "--json", *arguments]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, env=env, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise PaseoTransportError(
                "Paseo native command timed out{}; inspect registered profiles before retrying.".format(
                    " after a write was attempted" if mutating else ""
                ), mutation_attempted=mutating,
            ) from exc
        except OSError as exc:
            raise PaseoTransportError("Could not execute Paseo CLI.", mutation_attempted=mutating) from exc
        # Native errors can contain complete settings or credentials. Do not echo
        # native output, command arguments, or subprocess exceptions into reports.
        if result.returncode != 0:
            raise PaseoTransportError(
                "Paseo native command failed (exit {}){}; inspect Paseo locally.".format(
                    result.returncode, " after a write was attempted" if mutating else ""
                ), mutation_attempted=mutating,
            )
        try:
            return json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            raise PaseoTransportError(
                "Paseo native command returned invalid JSON.", mutation_attempted=mutating,
            ) from exc

    def status(self) -> Dict[str, Any]:
        """Inspect local status without starting or restarting the daemon."""
        value = self._call("daemon", "status")
        if not isinstance(value, dict):
            raise PaseoTransportError("Paseo daemon status has an unsupported shape.")
        home = value.get("home")
        if not isinstance(home, str) or Path(home).expanduser().resolve() != self.home:
            raise PaseoTransportError("Paseo status does not match the selected local home.")
        return value

    def _require_running(self) -> None:
        value = self.status()
        if value.get("localDaemon") != "running" or value.get("connectedDaemon") != "reachable":
            raise PaseoTransportError("The selected local Paseo daemon must be running and reachable.")

    def _registered_profiles(self) -> List[Dict[str, Any]]:
        value = self._call("daemon", "config", "get", "daemon.agentProfiles")
        if not isinstance(value, dict) or value.get("source") != "configured":
            raise PaseoTransportError("Paseo configured-profile response has an unsupported shape.")
        profiles = value.get("value", []) if value.get("set") else []
        self._check_profiles(profiles)
        return profiles

    @staticmethod
    def _check_profiles(profiles: Any) -> None:
        if not isinstance(profiles, list) or any(not isinstance(item, dict) for item in profiles):
            raise PaseoTransportError("Paseo profiles must be an array of objects.")
        ids = [item.get("id") for item in profiles]
        if any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
            raise PaseoTransportError("Paseo profiles contain missing or duplicate IDs.")

    def read_profiles(self) -> List[Dict[str, Any]]:
        """Return the selected running daemon's currently configured profiles."""
        value = self._sdk("profiles").get("profiles")
        self._check_profiles(value)
        return value

    def validate_profile(self, profile: Dict[str, Any]) -> Optional[str]:
        """Validate exact model, mode, thinking and feature values through native metadata."""
        try:
            provider = profile.get("provider")
            if not isinstance(provider, str) or not provider:
                return "Profile provider is required."
            if profile.get("featureValues") is not None and not isinstance(profile["featureValues"], dict):
                return "Profile feature values must be an object."
            value = self._sdk("validate", profile=profile)
            reason = value.get("reason")
            if reason is not None and not isinstance(reason, str):
                return "Paseo validation returned an unsupported result."
            return reason
        except PaseoTransportError as exc:
            return str(exc)

    def apply_profiles(self, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, Any]:
        """One native field write, observed-drift checks, no retry or snapshot rollback."""
        self._check_profiles(before)
        self._check_profiles(after)
        self._deadline = time.monotonic() + 90.0
        try:
            self._require_running()
            previous = {item["id"]: item for item in before}
            for profile in after:
                if previous.get(profile["id"]) != profile:
                    reason = self.validate_profile(profile)
                    if reason:
                        raise PaseoTransportError(reason)
            if self.read_profiles() != before or self._registered_profiles() != before:
                raise PaseoTransportError("Paseo profiles changed since preview; review the new profiles before applying.")
            if before == after:
                return {"registered": True, "saved": True, "applied": True, "changed": False, "conditional_update": False, "notices": []}
            result = self._call(
                "daemon", "config", "set", "daemon.agentProfiles",
                json.dumps(after, ensure_ascii=False, separators=(",", ":")), mutating=True,
            )
            if not isinstance(result, dict) or result.get("action") != "saved":
                raise PaseoTransportError("Paseo returned an unsupported apply result; inspect registered profiles.", mutation_attempted=True)
            for field in ("appliedPaths", "restartRequiredPaths", "overrideControlledPaths"):
                if field in result and (not isinstance(result[field], list) or any(not isinstance(path, str) for path in result[field])):
                    raise PaseoTransportError("Paseo returned unsupported apply details; inspect live profiles.", mutation_attempted=True, saved=True)
            applied = result.get("applied") is not False and "daemon.agentProfiles" in result.get("appliedPaths", [])
            notices = []
            if not applied:
                notices.append("Paseo saved profiles without confirming live reload; inspect Paseo before retrying.")
            if "daemon.agentProfiles" in result.get("overrideControlledPaths", []):
                applied = False
                notices.append("Paseo launch overrides prevented live profile application.")
            try:
                if self._registered_profiles() != after:
                    raise PaseoTransportError("Paseo profiles differ after applying; inspect them before retrying.")
                if applied and self.read_profiles() != after:
                    raise PaseoTransportError("Paseo live profiles differ after applying; inspect them before retrying.")
            except PaseoTransportError as exc:
                raise PaseoTransportError(str(exc), mutation_attempted=True, saved=True) from exc
            for path in result.get("restartRequiredPaths", []):
                notices.append("Paseo reports restart required for {}.".format(path))
            return {
                "registered": True, "saved": True, "applied": applied, "changed": True, "notices": notices,
                "conditional_update": False,
                "appliedPaths": result.get("appliedPaths", []),
                "restartRequiredPaths": result.get("restartRequiredPaths", []),
                "overrideControlledPaths": result.get("overrideControlledPaths", []),
            }
        finally:
            self._deadline = None

    def reload_profiles(self, expected: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reviewed recovery of saved profiles: one reload, no profile write."""
        self._check_profiles(expected)
        self._deadline = time.monotonic() + 90.0
        try:
            self._require_running()
            if self._registered_profiles() != expected:
                raise PaseoTransportError("Saved Paseo profiles changed before reload; review them before applying.")
            try:
                result = self._call("daemon", "reload", mutating=True)
            except PaseoTransportError as exc:
                raise PaseoTransportError(str(exc), mutation_attempted=True, saved=True) from exc
            if not isinstance(result, dict) or not isinstance(result.get("appliedPaths"), list):
                raise PaseoTransportError("Paseo returned an unsupported reload result; inspect live profiles.", mutation_attempted=True, saved=True)
            for field in ("appliedPaths", "restartRequiredPaths", "overrideControlledPaths"):
                if field in result and (not isinstance(result[field], list) or any(not isinstance(path, str) for path in result[field])):
                    raise PaseoTransportError("Paseo returned unsupported reload details; inspect live profiles.", mutation_attempted=True, saved=True)
            notices = ["Paseo reports restart required for {}.".format(path)
                       for path in result.get("restartRequiredPaths", [])]
            try:
                applied = self.read_profiles() == expected and self._registered_profiles() == expected
            except PaseoTransportError:
                applied = False
            if "daemon.agentProfiles" in result.get("overrideControlledPaths", []):
                applied = False
            if not applied:
                notices.append("Paseo reload did not confirm the expected live profiles; inspect Paseo before retrying.")
            return {"saved": True, "applied": applied, "notices": notices,
                    "appliedPaths": result["appliedPaths"], "conditional_update": False}
        finally:
            self._deadline = None
