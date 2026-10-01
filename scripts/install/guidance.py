"""Managed host instruction blocks; preserve text outside the owned block."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from .common import DriftError, FileTransaction, StateError, installer_state
from .state import InstallState

BEGIN = b"<!-- hukuhaka-harness:begin -->"
END = b"<!-- hukuhaka-harness:end -->"
GUIDANCE_MANIFEST = ".hukuhaka-guidance-manifest.json"

def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def _preserved_mode(path: Path, *, default: int = 0o644) -> int:
    return path.stat().st_mode & 0o777 if path.exists() else default

def _block(template: bytes) -> bytes:
    return BEGIN + b"\n" + template.rstrip(b"\r\n") + b"\n" + END

def _bounds(content: bytes, target: str = "AGENTS.md", host: str = "codex") -> Optional[Tuple[int, int]]:
    if not content.count(BEGIN) and not content.count(END):
        return None
    if content.count(BEGIN) != 1 or content.count(END) != 1 or content.index(END) < content.index(BEGIN):
        raise StateError(target + " contains duplicate, incomplete or out-of-order hukuhaka markers", host=host, stage="guidance")
    return content.index(BEGIN), content.index(END) + len(END)

class GuidanceDeployment:
    def __init__(
        self,
        source: Path,
        codex_home: Path,
        version: str,
        *,
        enabled: bool,
        dry_run: bool = False,
        force: bool = False,
        host: str = "codex",
        component: str = "agents-md",
        target_name: str = "AGENTS.md",
    ) -> None:
        self.host = host
        self.component = component
        self.target_name = target_name
        self.source = source
        self.codex_home = codex_home
        self.version = version
        self.enabled = enabled
        self.dry_run = dry_run
        self.force = force
        self.target = codex_home / target_name
        self.override = codex_home / "AGENTS.override.md"
        self.manifest_path = codex_home / GUIDANCE_MANIFEST
        self.state = InstallState(codex_home)

    def _read_target(self) -> bytes:
        if not self.target.exists() and not self.target.is_symlink():
            return b""
        if self.target.is_symlink() or not self.target.is_file():
            raise StateError(
                "Managed instruction file must be a regular file",
                host=self.host,
                stage="guidance",
                path=str(self.target),
            )
        content = self.target.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "Managed instruction file must be UTF-8",
                host=self.host,
                stage="guidance",
                path=str(self.target),
            ) from exc
        return content

    def _manifest(self) -> Optional[Dict[str, Any]]:
        data = self.state.receipt(self.component, self.manifest_path)
        if data is None:
            return None
        required = {
            "schemaVersion": int,
            "component": str,
            "version": str,
            "target": str,
            "managedHash": str,
            "prefix": str,
            "suffix": str,
        }
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), value_type) for key, value_type in required.items()
        ):
            raise StateError(
                "invalid managed guidance manifest",
                host=self.host,
                stage="guidance",
                path=str(self.manifest_path),
            )
        if (
            data["schemaVersion"] != 1
            or data["component"] != self.component
            or data["target"] != self.target_name
            or data["prefix"] not in ("", "\n", "\n\n")
            or data["suffix"] not in ("", "\n")
        ):
            raise StateError(
                "unsupported managed guidance manifest",
                host=self.host,
                stage="guidance",
                path=str(self.manifest_path),
            )
        return data

    def _validate_current(
        self,
        content: bytes,
        bounds: Optional[Tuple[int, int]],
        manifest: Optional[Dict[str, Any]],
    ) -> None:
        if bounds is not None and manifest is None:
            raise StateError(
                "managed instruction block exists without its manifest",
                host=self.host,
                stage="guidance",
                path=str(self.target),
            )
        if bounds is not None and manifest is not None:
            start, end = bounds
            if _hash(content[start:end]) != manifest["managedHash"] and not self.force:
                raise DriftError(
                    "managed instruction block changed; use --force to replace it",
                    host=self.host,
                    stage="guidance",
                    path=str(self.target),
                )

    def _warn_override(self) -> None:
        if self.host == "codex" and self.override.exists():
            print(
                "Warning: {} shadows global AGENTS.md; managed guidance is inactive.".format(
                    self.override
                ),
                file=sys.stderr,
            )

    def _plan_deploy(self) -> Tuple[bytes, Dict[str, Any]]:
        """Read state, validate it, and compute the merge. Mutates nothing.

        Callers that write must run this inside installer_state(), after
        recover_pending(), so the state it reads is the state it writes over.
        """
        block = _block(self.source.read_bytes())
        content = self._read_target()
        bounds = _bounds(content, self.target_name, self.host)
        manifest = self._manifest()
        self._validate_current(content, bounds, manifest)

        if bounds is None:
            prefix = b"" if not content else (b"\n" if content.endswith(b"\n") else b"\n\n")
            suffix = b"\n"
            merged = content + prefix + block + suffix
        else:
            start, end = bounds
            prefix = str(manifest["prefix"]).encode()
            suffix = str(manifest["suffix"]).encode()
            merged = content[:start] + block + content[end:]

        next_manifest = {
            "schemaVersion": 1,
            "component": self.component,
            "version": self.version,
            "target": self.target_name,
            "managedHash": _hash(block),
            "prefix": prefix.decode(),
            "suffix": suffix.decode(),
        }
        return merged, next_manifest

    def deploy(self) -> None:
        if not self.enabled:
            # Delegate before taking the lock: uninstall() acquires it itself and
            # flock is not reentrant across file descriptors.
            self.uninstall()
            return
        with installer_state(self.codex_home, dry_run=self.dry_run) as writable:
            merged, next_manifest = self._plan_deploy()
            target_mode = _preserved_mode(self.target)
            self._warn_override()
            if not writable:
                print("  [dry-run] merge {} into {}".format(self.component, self.target))
                return
            with FileTransaction(self.codex_home) as transaction:
                transaction.write_bytes(self.target, merged, target_mode)
                self.state.put_receipt(
                    transaction, self.component, next_manifest, kind="template",
                    installer_version=self.version, legacy_path=self.manifest_path,
                )
                transaction.commit()
        print("  [ok] {} -> {}".format(self.component, self.target))

    def _plan_uninstall(self) -> Optional[bytes]:
        """Return the post-removal AGENTS.md bytes, or None when there is nothing
        to remove. Mutates nothing; same locking requirement as _plan_deploy."""
        content = self._read_target()
        bounds = _bounds(content, self.target_name, self.host)
        manifest = self._manifest()
        if bounds is None and manifest is None:
            return None
        self._validate_current(content, bounds, manifest)
        if bounds is None:
            # The receipt can outlive the block. Remove only that receipt;
            # the current document contains no managed bytes to delete.
            return content
        assert bounds is not None and manifest is not None
        start, end = bounds
        prefix = manifest["prefix"].encode()
        suffix = manifest["suffix"].encode()
        if content[max(0, start - len(prefix)):start] != prefix or content[end:end + len(suffix)] != suffix:
            if not self.force:
                raise DriftError(
                    "text surrounding the managed instruction block changed; use --force to remove it",
                    host=self.host,
                    stage="guidance",
                    path=str(self.target),
                )
            prefix = b""
            suffix = b""
        return content[:start - len(prefix)] + content[end + len(suffix):]

    def uninstall(self) -> None:
        if self.dry_run:
            merged = self._plan_uninstall()
            if merged is not None:
                print("  [dry-run] remove {} from {}".format(self.component, self.target))
            return
        with installer_state(self.codex_home, dry_run=self.dry_run) as writable:
            # Recovery must happen before the no-op decision. A killed removal
            # can leave the manifest absent while the journal still owns the
            # pre-removal state.
            merged = self._plan_uninstall()
            if merged is None:
                return
            target_mode = _preserved_mode(self.target)
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                if merged != self._read_target():
                    if merged:
                        transaction.write_bytes(self.target, merged, target_mode)
                    else:
                        transaction.remove(self.target)
                self.state.remove_receipt(transaction, self.component, self.manifest_path)
                transaction.commit()
        print("  [ok] removed {} from {}".format(self.component, self.target))
