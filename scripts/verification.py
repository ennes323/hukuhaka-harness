"""Local success receipts for immutable verification inputs.

Receipts contain digests and timing, never environment values or command output.
Remote readiness and authenticated model calls must not use this module.
"""

from __future__ import annotations

import hashlib
import functools
import json
import math
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional


SCHEMA = 1
MAX_AGE_SECONDS = 24 * 60 * 60
CACHE_DIR_ENV = "HUKUHAKA_VERIFICATION_CACHE_DIR"
FRESH_ENV = "HUKUHAKA_VERIFY_FRESH"
CONTRACT = "HUKUHAKA_VALIDATION_CONTRACT=2"


class VerificationError(RuntimeError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def tree_digest(root: Path) -> str:
    """Hash all candidate entries, including modes and empty directories, not Git metadata."""
    if not root.is_dir():
        raise VerificationError("verification root is missing: {}".format(root))
    hasher = hashlib.sha256()
    def unreadable(error: OSError) -> None:
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        base = Path(directory)
        if base == root:
            dirs[:] = [name for name in dirs if name != ".git"]
            files = [name for name in files if name != ".git"]
        dirs.sort()
        for name in sorted(dirs + files):
            path = base / name
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise VerificationError("unsupported verification input: {}".format(path))
            content = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            hasher.update(json.dumps([path.relative_to(root).as_posix(), info.st_mode, content]).encode())
            hasher.update(b"\n")
    return hasher.hexdigest()


@functools.lru_cache(maxsize=32)
def _binary_digest(path: str, metadata: tuple[int, ...]) -> str:
    # ctime/inode also invalidate this per-process memo when an update preserves
    # the executable's size, mtime, and advertised version.
    with open(path, "rb") as handle:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
        return hasher.hexdigest()


def tool_identity(command: str) -> object:
    path = shutil.which(command)
    if path is None:
        raise VerificationError("{} is unavailable for input identification".format(command))
    binary = Path(path).resolve()
    info = binary.stat()
    result = subprocess.run([str(binary), "--version"], capture_output=True, timeout=15)
    if result.returncode:
        raise VerificationError("cannot identify {}".format(command))
    metadata = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    binary_hash = _binary_digest(str(binary), metadata)
    after = binary.stat()
    if metadata != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise VerificationError("{} changed during input identification".format(command))
    return [str(binary), binary_hash, hashlib.sha256(result.stdout).hexdigest()]


def environment_digest(environment: Optional[Mapping[str, str]] = None) -> str:
    # These shell bookkeeping/cache-location values do not affect a check. All
    # other environment values are hashed, including PATH and Python overrides.
    ignored = {"PWD", "OLDPWD", "SHLVL", "_", CACHE_DIR_ENV, FRESH_ENV}
    return digest({
        "platform": [platform.system(), platform.release(), platform.machine()],
        "python": [sys.executable, sys.version],
        "tools": {name: tool_identity(name) for name in ("python3", "bash", "node", "git")},
        "environment": digest({key: value for key, value in
                               (os.environ if environment is None else environment).items() if key not in ignored}),
        "driver": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })


def cache_directory(repo: Path) -> Optional[Path]:
    explicit = os.environ.get(CACHE_DIR_ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=repo, capture_output=True, text=True,
    )
    if result.returncode:
        return None
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common.resolve() / "hukuhaka-verification"


def validation_environment(cache: Optional[Path]) -> dict[str, str]:
    values = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HUKUHAKA_RUN_LIVE_CLI="0",
                  GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONNOUSERSITE="1")
    # Git exports repository selectors to hooks. A child must inspect its own
    # detached checkout/plain snapshot, never the hook caller's index or tree.
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        values.pop(key, None)
    if cache is not None:
        values[CACHE_DIR_ENV] = str(cache)
    return values


def supports_receipts(root: Path) -> bool:
    validator = root / "scripts" / "validate.sh"
    return validator.is_file() and CONTRACT in validator.read_text(encoding="utf-8")


@dataclass(frozen=True)
class CheckResult:
    output: str
    reused: bool
    elapsed_seconds: float
    key: str

    def summary(self, name: str) -> str:
        if self.reused:
            return "[reuse] {}: successful inputs {} (original {:.2f}s)".format(
                name, self.key[:12], self.elapsed_seconds,
            )
        return "[verified] {}: {:.2f}s{}".format(
            name, self.elapsed_seconds, " inputs " + self.key[:12] if self.key else " (fresh)",
        )


def _read_receipt(path: Path, key: str, name: str, now: float) -> Optional[dict]:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        completed = data["completed_at"]
        elapsed = data["elapsed_seconds"]
        if (type(data.get("schema")) is not int or data["schema"] != SCHEMA
                or data.get("key") != key or data.get("check") != name
                or data.get("status") != "success" or type(data.get("exit_code")) is not int
                or data["exit_code"] != 0
                or type(completed) not in (float, int) or not math.isfinite(completed)
                or type(elapsed) not in (float, int) or not math.isfinite(elapsed)
                or elapsed < 0 or not 0 <= now - completed <= MAX_AGE_SECONDS):
            return None
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _write_receipt(path: Path, data: dict) -> bool:
    temporary = None
    try:
        if path.parent.is_symlink():
            return False
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass


def run_verified(
    name: str,
    identity: Callable[[], Mapping[str, object]],
    action: Callable[[], str],
    *,
    cache: Optional[Path],
    reusable: bool = True,
) -> CheckResult:
    """Reuse only a fresh success; interrupted/failed attempts never create a success."""
    def identify() -> str:
        inputs = identity()
        def known(value: object) -> bool:
            if value is None or value == "":
                return False
            if isinstance(value, dict):
                return all(known(item) for item in value.values())
            if isinstance(value, (list, tuple)):
                return all(known(item) for item in value)
            return True
        if not isinstance(inputs, Mapping) or not inputs or not known(inputs):
            raise VerificationError("{} has unidentified inputs".format(name))
        return digest({"schema": SCHEMA, "check": name, "inputs": inputs})
    key = ""
    if reusable and cache is not None:
        try:
            key = identify()
        except (OSError, ValueError, TypeError, VerificationError, subprocess.SubprocessError):
            pass  # Unidentifiable inputs are checked normally, without reuse.
    receipt = cache / (key + ".json") if key and cache is not None else None
    if receipt is not None and os.environ.get(FRESH_ENV) != "1" and not cache.is_symlink():
        previous = _read_receipt(receipt, key, name, time.time())
        if previous is not None:
            return CheckResult("", True, float(previous["elapsed_seconds"]), key)
    base = {"schema": SCHEMA, "key": key, "check": name}
    if receipt is not None:
        _write_receipt(receipt, dict(base, status="running"))
    started = time.monotonic()
    try:
        output = action()
        if key and identify() != key:
            raise VerificationError("{} inputs changed during verification".format(name))
    except BaseException:
        if receipt is not None:
            _write_receipt(receipt, dict(base, status="failed"))
        raise
    elapsed = time.monotonic() - started
    if receipt is not None:
        _write_receipt(receipt, dict(
            base, status="success", exit_code=0, completed_at=time.time(), elapsed_seconds=elapsed,
        ))
    return CheckResult(output, False, elapsed, key)
