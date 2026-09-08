"""Codex native marketplace install adapter."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .common import (
    DriftError,
    FileTransaction,
    InstallerError,
    StateError,
    installer_state,
    load_json,
    sha256_file,
)
from .codex_config import (
    EVIDENCE_SCOUT_SETTINGS,
    SUBAGENT_SETTINGS,
    CodexConfigEditor,
    ConfigPlan,
)


BEGIN = b"<!-- hukuhaka-harness:begin -->"
END = b"<!-- hukuhaka-harness:end -->"
GUIDANCE_MANIFEST = ".hukuhaka-guidance-manifest.json"
EVIDENCE_SCOUT_MANIFEST = ".hukuhaka-evidence-scout-manifest.json"
SCOUT_BEGIN = b"<!-- hukuhaka-evidence-scout:begin -->"
SCOUT_END = b"<!-- hukuhaka-evidence-scout:end -->"
REMOTE_MARKETPLACE_SOURCE = "https://github.com/hukuhaka/hukuhaka-harness.git"


def resolve_codex_home(
    environ: Optional[Mapping[str, str]] = None,
    *,
    fallback_home: Optional[Path] = None,
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("CODEX_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    return (Path.home() if fallback_home is None else fallback_home) / ".codex"


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _preserved_mode(path: Path, *, default: int = 0o644) -> int:
    """Return an existing regular file's permissions for atomic replacement."""
    return path.stat().st_mode & 0o777 if path.exists() else default


def _block(template: bytes) -> bytes:
    return BEGIN + b"\n" + template.rstrip(b"\r\n") + b"\n" + END


def _bounds(content: bytes) -> Optional[Tuple[int, int]]:
    if not content.count(BEGIN) and not content.count(END):
        return None
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise StateError(
            "AGENTS.md contains duplicate or incomplete hukuhaka markers",
            host="codex",
            stage="guidance",
        )
    start = content.index(BEGIN)
    end_marker = content.index(END)
    if end_marker < start:
        raise StateError(
            "AGENTS.md managed markers are out of order",
            host="codex",
            stage="guidance",
        )
    return start, end_marker + len(END)


def _agent_bounds(
    content: bytes,
    begin: bytes,
    end: bytes,
    *,
    name: str,
) -> Optional[Tuple[int, int]]:
    if not content.count(begin) and not content.count(end):
        return None
    if content.count(begin) != 1 or content.count(end) != 1:
        raise StateError(
            "AGENTS.md contains duplicate or incomplete {} markers".format(name),
            host="codex",
            stage=name,
        )
    start = content.index(begin)
    end_marker = content.index(end)
    if end_marker < start:
        raise StateError(
            "AGENTS.md {} markers are out of order".format(name),
            host="codex",
            stage=name,
        )
    return start, end_marker + len(end)


class CodexGuidanceDeployment:
    def __init__(
        self,
        source: Path,
        codex_home: Path,
        version: str,
        *,
        enabled: bool,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.source = source
        self.codex_home = codex_home
        self.version = version
        self.enabled = enabled
        self.dry_run = dry_run
        self.force = force
        self.target = codex_home / "AGENTS.md"
        self.override = codex_home / "AGENTS.override.md"
        self.manifest_path = codex_home / GUIDANCE_MANIFEST

    def _read_target(self) -> bytes:
        if not self.target.exists() and not self.target.is_symlink():
            return b""
        if self.target.is_symlink() or not self.target.is_file():
            raise StateError(
                "Codex AGENTS.md must be a regular file",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        content = self.target.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "Codex AGENTS.md must be UTF-8",
                host="codex",
                stage="guidance",
                path=str(self.target),
            ) from exc
        return content

    def _manifest(self) -> Optional[Dict[str, Any]]:
        if not self.manifest_path.exists():
            return None
        data = load_json(self.manifest_path, {})
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
                "invalid Codex guidance manifest",
                host="codex",
                stage="guidance",
                path=str(self.manifest_path),
            )
        if (
            data["schemaVersion"] != 1
            or data["component"] != "agents-md"
            or data["target"] != "AGENTS.md"
            or data["prefix"] not in ("", "\n", "\n\n")
            or data["suffix"] not in ("", "\n")
        ):
            raise StateError(
                "unsupported Codex guidance manifest",
                host="codex",
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
                "managed AGENTS.md block exists without its manifest",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        if manifest is not None and bounds is None:
            raise DriftError(
                "Codex guidance manifest exists but its managed block is missing",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        if bounds is not None and manifest is not None:
            start, end = bounds
            if _hash(content[start:end]) != manifest["managedHash"] and not self.force:
                raise DriftError(
                    "managed AGENTS.md block changed; use --force to replace it",
                    host="codex",
                    stage="guidance",
                    path=str(self.target),
                )

    def _warn_override(self) -> None:
        if self.override.exists():
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
        bounds = _bounds(content)
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
            "component": "agents-md",
            "version": self.version,
            "target": "AGENTS.md",
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
                print("  [dry-run] merge agents-md into {}".format(self.target))
                return
            with FileTransaction(self.codex_home) as transaction:
                transaction.write_bytes(self.target, merged, target_mode)
                transaction.write_json(self.manifest_path, next_manifest)
                transaction.commit()
        print("  [ok] agents-md -> {}".format(self.target))

    def _plan_uninstall(self) -> Optional[bytes]:
        """Return the post-removal AGENTS.md bytes, or None when there is nothing
        to remove. Mutates nothing; same locking requirement as _plan_deploy."""
        content = self._read_target()
        bounds = _bounds(content)
        manifest = self._manifest()
        if bounds is None and manifest is None:
            return None
        self._validate_current(content, bounds, manifest)
        assert bounds is not None and manifest is not None
        start, end = bounds
        prefix = manifest["prefix"].encode()
        suffix = manifest["suffix"].encode()
        if content[max(0, start - len(prefix)):start] != prefix or content[end:end + len(suffix)] != suffix:
            if not self.force:
                raise DriftError(
                    "text surrounding the managed AGENTS.md block changed; use --force to remove it",
                    host="codex",
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
                print("  [dry-run] remove agents-md from {}".format(self.target))
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
                if merged:
                    transaction.write_bytes(self.target, merged, target_mode)
                else:
                    transaction.remove(self.target)
                transaction.remove(self.manifest_path)
                transaction.commit()
        print("  [ok] removed agents-md from {}".format(self.target))


class CodexCustomAgentDeployment:
    """Own one named Codex agent and migrate obsolete routing ownership."""

    def __init__(
        self,
        name: str,
        source: Path,
        codex_home: Path,
        version: str,
        *,
        enabled: bool,
        current_schema: int = 4,
        accepted_schemas: Optional[Sequence[int]] = None,
        resources: Sequence[Tuple[Path, str]] = (),
        legacy_evidence_scout: bool = False,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.name = name
        self.source = source
        self.codex_home = codex_home
        self.version = version
        self.enabled = enabled
        self.current_schema = current_schema
        self.accepted_schemas = tuple(
            accepted_schemas if accepted_schemas is not None else (1, current_schema)
        )
        self.resource_sources = {
            target: source for source, target in resources
        }
        self.resource_targets = {
            target: codex_home / target for target in self.resource_sources
        }
        self.legacy_evidence_scout = legacy_evidence_scout
        self.dry_run = dry_run
        self.force = force
        marker = "hukuhaka-{}".format(name).encode("ascii")
        self.begin = b"<!-- " + marker + b":begin -->"
        self.end = b"<!-- " + marker + b":end -->"
        self.target = codex_home / "agents" / "{}.toml".format(name)
        self.routing_target = codex_home / "AGENTS.md"
        self.catalog_target = codex_home / "models-luna-v2.json"
        self.manifest_path = codex_home / ".hukuhaka-{}-manifest.json".format(name)
        self.config = CodexConfigEditor(codex_home, dry_run=dry_run)

    def _read_regular(
        self,
        path: Path,
        *,
        label: str,
        missing_ok: bool = True,
    ) -> bytes:
        if not path.exists() and not path.is_symlink():
            if missing_ok:
                return b""
            raise StateError(
                "{} source is missing".format(label),
                host="codex",
                stage=self.name,
                path=str(path),
            )
        if path.is_symlink() or not path.is_file():
            raise StateError(
                "{} must be a regular file".format(label),
                host="codex",
                stage=self.name,
                path=str(path),
            )
        content = path.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "{} must be UTF-8".format(label),
                host="codex",
                stage=self.name,
                path=str(path),
            ) from exc
        return content

    def _manifest(self) -> Optional[Dict[str, Any]]:
        if not self.manifest_path.exists() and not self.manifest_path.is_symlink():
            return None
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            raise StateError(
                "invalid {} manifest".format(self.name),
                host="codex",
                stage=self.name,
                path=str(self.manifest_path),
            )
        data = load_json(self.manifest_path, {})
        required = {
            "schemaVersion": int,
            "component": str,
            "version": str,
            "agentTarget": str,
            "agentHash": str,
        }
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), value_type)
            for key, value_type in required.items()
        ):
            raise StateError(
                "invalid {} manifest".format(self.name),
                host="codex",
                stage=self.name,
                path=str(self.manifest_path),
            )
        if (
            data["schemaVersion"] not in self.accepted_schemas
            or data["component"] != self.name
            or data["agentTarget"] != "agents/{}.toml".format(self.name)
        ):
            raise StateError(
                "unsupported {} manifest".format(self.name),
                host="codex",
                stage=self.name,
                path=str(self.manifest_path),
            )
        if data["schemaVersion"] != self.current_schema:
            if (
                data.get("routingTarget") != "AGENTS.md"
                or not isinstance(data.get("routingHash"), str)
                or data.get("prefix") not in ("", "\n", "\n\n")
                or data.get("suffix") not in ("", "\n")
            ):
                raise StateError(
                    "invalid legacy {} routing manifest".format(self.name),
                    host="codex", stage=self.name, path=str(self.manifest_path),
                )
        elif any(key in data for key in ("routingTarget", "routingHash", "prefix", "suffix")):
            raise StateError(
                "current {} manifest must not own routing".format(self.name),
                host="codex", stage=self.name, path=str(self.manifest_path),
            )
        if self.resource_targets and data["schemaVersion"] != 1:
            resources = data.get("resources")
            if not isinstance(resources, list) or len(resources) != len(self.resource_targets) or any(
                not isinstance(item, dict)
                or set(item) != {"target", "hash"}
                or not isinstance(item.get("target"), str)
                or not isinstance(item.get("hash"), str)
                for item in resources
            ) or {item["target"] for item in resources} != set(self.resource_targets):
                raise StateError(
                    "invalid {} manifest".format(self.name),
                    host="codex",
                    stage=self.name,
                    path=str(self.manifest_path),
                )
        if self.legacy_evidence_scout and data["schemaVersion"] == 2:
            catalog_required = {
                "catalogSource": str,
                "catalogSourceHash": str,
                "catalogTarget": str,
                "catalogHash": str,
            }
            if any(
                not isinstance(data.get(key), value_type)
                for key, value_type in catalog_required.items()
            ) or (
                data["catalogSource"] != "models_cache.json"
                or data["catalogTarget"] != "models-luna-v2.json"
            ):
                raise StateError(
                    "invalid evidence-scout catalog manifest",
                    host="codex",
                    stage=self.name,
                    path=str(self.manifest_path),
                )
        return data

    def _runtime_settings(self) -> Dict[Tuple[str, ...], str]:
        return dict(EVIDENCE_SCOUT_SETTINGS)

    def _bounds(self, content: bytes) -> Optional[Tuple[int, int]]:
        return _agent_bounds(
            content,
            self.begin,
            self.end,
            name=self.name,
        )

    def _legacy_cleanup(
        self,
        manifest: Optional[Dict[str, Any]],
        catalog: bytes,
    ) -> Tuple[bool, bool]:
        if (
            not self.legacy_evidence_scout
            or manifest is None
            or manifest["schemaVersion"] != 2
        ):
            return False, False
        catalog_matches = bool(catalog) and _hash(catalog) == manifest["catalogHash"]
        remove_catalog = catalog_matches or (bool(catalog) and self.force)
        expected_pointer = json.dumps(str(self.catalog_target))
        actual_pointer = self.config.inspect().get(("model_catalog_json",))
        remove_pointer = actual_pointer == expected_pointer and (
            catalog_matches or not catalog or self.force
        )
        return remove_catalog, remove_pointer

    def _validate_owned(
        self,
        agent: bytes,
        manifest: Optional[Dict[str, Any]],
        catalog: bytes,
        resources: Mapping[str, bytes],
    ) -> None:
        if manifest is None:
            return
        if not agent:
            raise DriftError(
                "{} manifest exists but its agent file is missing".format(self.name),
                host="codex",
                stage=self.name,
                path=str(self.target),
            )
        drifted = _hash(agent) != manifest["agentHash"]
        if self.legacy_evidence_scout and manifest["schemaVersion"] == 2:
            drifted = drifted or (
                not catalog or _hash(catalog) != manifest["catalogHash"]
            )
        if self.resource_targets and "resources" in manifest:
            manifest_resources = {
                item["target"]: item["hash"] for item in manifest["resources"]
            }
            drifted = drifted or any(
                not resources.get(target)
                or _hash(resources[target]) != manifest_resources[target]
                for target in self.resource_targets
            )
        if drifted and not self.force:
            raise DriftError(
                "managed {} files changed; use --force to replace them".format(
                    self.name
                ),
                host="codex",
                stage=self.name,
            )

    def _plan_routing_removal(self, manifest: Optional[Dict[str, Any]]) -> Optional[bytes]:
        """Remove only a legacy manifest's block; new installs never read AGENTS.md."""
        if manifest is None or manifest["schemaVersion"] == self.current_schema:
            return None
        content = self._read_regular(self.routing_target, label="Codex AGENTS.md")
        bounds = self._bounds(content)
        if bounds is None:
            return None  # Already removed; finish migrating the remaining owned files.
        start, end = bounds
        if _hash(content[start:end]) != manifest["routingHash"] and not self.force:
            raise DriftError(
                "managed {} routing changed; review before removal or use --force".format(self.name),
                host="codex", stage=self.name, path=str(self.routing_target),
            )
        prefix = manifest["prefix"].encode()
        suffix = manifest["suffix"].encode()
        if (content[max(0, start - len(prefix)):start] != prefix
                or content[end:end + len(suffix)] != suffix):
            if not self.force:
                raise DriftError(
                    "text surrounding the {} routing block changed; use --force to remove it".format(self.name),
                    host="codex", stage=self.name, path=str(self.routing_target),
                )
            prefix = suffix = b""
        return content[:start - len(prefix)] + content[end + len(suffix):]

    def _write_routing_removal(self, transaction: FileTransaction, content: Optional[bytes]) -> None:
        if content is None:
            return
        if content:
            transaction.write_bytes(self.routing_target, content, _preserved_mode(self.routing_target))
        else:
            transaction.remove(self.routing_target)

    def _plan_deploy(
        self,
    ) -> Tuple[
        bytes,
        Optional[bytes],
        Dict[str, Any],
        ConfigPlan,
        bool,
        Dict[str, bytes],
    ]:
        agent_source = self._read_regular(
            self.source, label=self.name, missing_ok=False
        )
        agent = self._read_regular(self.target, label=self.name)
        manifest = self._manifest()
        catalog = (
            self._read_regular(self.catalog_target, label="Luna v2 model catalog")
            if self.legacy_evidence_scout
            and manifest is not None
            and manifest["schemaVersion"] == 2
            else b""
        )
        resource_sources = {
            target: self._read_regular(
                source,
                label="{} resource {}".format(self.name, target),
                missing_ok=False,
            )
            for target, source in self.resource_sources.items()
        }
        resources = {
            target: self._read_regular(
                path,
                label="{} resource {}".format(self.name, target),
            )
            for target, path in self.resource_targets.items()
        }
        self._validate_owned(agent, manifest, catalog, resources)
        merged = self._plan_routing_removal(manifest)
        remove_catalog, remove_pointer = self._legacy_cleanup(manifest, catalog)

        if manifest is None and agent and agent != agent_source and not self.force:
            raise DriftError(
                "an unmanaged {} agent already exists; use --force to replace it".format(
                    self.name
                ),
                host="codex",
                stage=self.name,
                path=str(self.target),
            )
        if manifest is None or "resources" not in manifest:
            for target, content in resources.items():
                if content and content != resource_sources[target] and not self.force:
                    raise DriftError(
                        "an unmanaged {} resource already exists; use --force to replace it".format(
                            self.name
                        ),
                        host="codex",
                        stage=self.name,
                        path=str(self.resource_targets[target]),
                    )
        next_manifest = {
            "schemaVersion": self.current_schema,
            "component": self.name,
            "version": self.version,
            "agentTarget": "agents/{}.toml".format(self.name),
            "agentHash": _hash(agent_source),
        }
        if resource_sources:
            next_manifest["resources"] = [
                {"target": target, "hash": _hash(resource_sources[target])}
                for target in self.resource_sources
            ]
        config_plan = self.config.plan(
            self._runtime_settings(),
            remove=(("model_catalog_json",),) if remove_pointer else (),
        )
        return (
            agent_source,
            merged,
            next_manifest,
            config_plan,
            remove_catalog,
            resource_sources,
        )

    def _write_config(self, transaction: FileTransaction, plan: ConfigPlan) -> None:
        if not plan.changed:
            return
        if plan.existed:
            transaction.write_bytes(self.config.backup, plan.original, plan.mode)
        transaction.write_bytes(self.config.path, plan.proposed, plan.mode)

    def deploy(self) -> None:
        if not self.enabled:
            self.uninstall()
            return
        with installer_state(self.codex_home, dry_run=self.dry_run) as writable:
            (
                agent,
                routing,
                manifest,
                config_plan,
                remove_catalog,
                resources,
            ) = self._plan_deploy()
            if not writable:
                print("  [dry-run] install {} -> {}".format(self.name, self.target))
                if routing is not None:
                    print("  [dry-run] remove obsolete {} routing block".format(self.name))
                print("  [dry-run] disable multi-agent")
                for target in resources:
                    print(
                        "  [dry-run] install {} resource -> {}".format(
                            self.name, self.resource_targets[target]
                        )
                    )
                if remove_catalog:
                    print(
                        "  [dry-run] remove obsolete Luna v2 model catalog -> {}".format(
                            self.catalog_target
                        )
                    )
                return
            with FileTransaction(self.codex_home) as transaction:
                transaction.write_bytes(self.target, agent, 0o644)
                for target, content in resources.items():
                    transaction.write_bytes(self.resource_targets[target], content, 0o644)
                self._write_routing_removal(transaction, routing)
                if remove_catalog:
                    transaction.remove(self.catalog_target)
                transaction.write_json(self.manifest_path, manifest)
                self._write_config(transaction, config_plan)
                self.config.verify(config_plan)
                transaction.commit()
        print("  [ok] {} -> {}".format(self.name, self.target))
        for target in resources:
            print(
                "  [ok] {} resource -> {}".format(
                    self.name, self.resource_targets[target]
                )
            )
        if routing is not None:
            print("  [ok] removed obsolete {} routing block".format(self.name))
        if remove_catalog:
            print("  [ok] removed obsolete Luna v2 model catalog")
        print("  [ok] multi-agent disabled")

    def _plan_uninstall(
        self,
    ) -> Optional[Tuple[Optional[bytes], bool, ConfigPlan, Sequence[Path]]]:
        manifest = self._manifest()
        if manifest is None:
            return None
        agent = self._read_regular(self.target, label=self.name)
        catalog = (
            self._read_regular(self.catalog_target, label="Luna v2 model catalog")
            if self.legacy_evidence_scout and manifest["schemaVersion"] == 2
            else b""
        )
        resources = {
            target: self._read_regular(
                path,
                label="{} resource {}".format(self.name, target),
            )
            for target, path in self.resource_targets.items()
        }
        self._validate_owned(agent, manifest, catalog, resources)
        merged = self._plan_routing_removal(manifest)
        remove_catalog, remove_pointer = self._legacy_cleanup(manifest, catalog)
        return (
            merged,
            remove_catalog,
            self.config.plan(
                {}, remove=(("model_catalog_json",),) if remove_pointer else ()
            ),
            tuple(
                self.resource_targets[target]
                for target in self.resource_targets
                if "resources" in manifest
            ),
        )

    def uninstall(self) -> None:
        if self.dry_run:
            plan = self._plan_uninstall()
            if plan is not None:
                print("  [dry-run] remove {}".format(self.name))
                if plan[0] is not None:
                    print("  [dry-run] remove obsolete {} routing block".format(self.name))
            return
        with installer_state(self.codex_home, dry_run=False) as writable:
            plan = self._plan_uninstall()
            if plan is None:
                return
            merged, remove_catalog, config_plan, resources = plan
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                transaction.remove(self.target)
                for resource in resources:
                    transaction.remove(resource)
                self._write_routing_removal(transaction, merged)
                if remove_catalog:
                    transaction.remove(self.catalog_target)
                transaction.remove(self.manifest_path)
                if config_plan.changed:
                    self._write_config(transaction, config_plan)
                    self.config.verify(config_plan)
                transaction.commit()
        print("  [ok] removed {}".format(self.name))

    def verify(self) -> None:
        manifest = self._manifest()
        if manifest is None:
            raise InstallerError(
                "{} manifest is missing after install".format(self.name),
                host="codex",
                stage="verify",
            )
        agent = self._read_regular(self.target, label=self.name)
        resources = {
            target: self._read_regular(
                path,
                label="{} resource {}".format(self.name, target),
            )
            for target, path in self.resource_targets.items()
        }
        if (
            _hash(agent) != manifest["agentHash"]
            or manifest["schemaVersion"] != self.current_schema
            or any(
                not resources.get(target)
                or _hash(resources[target])
                != {
                    item["target"]: item["hash"]
                    for item in manifest.get("resources", [])
                }.get(target)
                for target in self.resource_targets
            )
        ):
            raise InstallerError(
                "{} files differ after install".format(self.name),
                host="codex",
                stage="verify",
            )
        actual = self.config.inspect()
        mismatched = [
            key
            for key, value in self._runtime_settings().items()
            if actual.get(key) != value
        ]
        if mismatched:
            raise InstallerError(
                "{} runtime setting differs: {}".format(
                    self.name, ".".join(mismatched[0])
                ),
                host="codex",
                stage="verify",
            )


class CodexEvidenceScoutDeployment(CodexCustomAgentDeployment):
    """Compatibility wrapper for the existing evidence-scout deployment."""

    def __init__(
        self,
        source: Path,
        codex_home: Path,
        version: str,
        *,
        enabled: bool,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        super().__init__(
            "evidence-scout",
            source,
            codex_home,
            version,
            enabled=enabled,
            accepted_schemas=(1, 2, 3, 4),
            legacy_evidence_scout=True,
            dry_run=dry_run,
            force=force,
        )


def run_json(command: Sequence[str], *, stage: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise InstallerError(
            "command not found: {}".format(command[0]),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise InstallerError(
            "command failed ({}): {}".format(exc.returncode, detail or "no output"),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise InstallerError(
            "command timed out after 30 seconds: {}".format(" ".join(command)),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InstallerError(
            "command returned invalid JSON: {}".format(exc),
            host="codex",
            stage=stage,
            operation="parse-command-output",
        ) from exc
    if not isinstance(data, dict):
        raise InstallerError("command JSON root must be an object", host="codex", stage=stage)
    return data


def git_commit(root: Path, ref: str) -> Optional[str]:
    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", ref),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


class CodexInstaller:
    """Own the complete Codex plugin, guidance, and custom-agent lifecycle."""

    def __init__(
        self,
        repo_root: Path,
        catalog: Mapping[str, Any],
        version: str,
        *,
        local_source: bool,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.catalog = catalog
        self.version = version.lstrip("v")
        self.local_source = local_source
        self.dry_run = dry_run
        self.force = force
        self.codex_home = resolve_codex_home()
        self.marketplace = str(
            catalog.get("marketplaces", {}).get("codex", "hukuhaka-harness")
        )
        self.aliases = {
            str(alias): str(component["name"])
            for component in catalog.get("components", [])
            for alias in component.get("aliases", [])
        }
        self.completed = []  # type: List[str]
        self.install_results = {}  # type: Dict[str, Dict[str, Any]]

    @property
    def plugin_names(self) -> Set[str]:
        return {
            str(component["name"])
            for component in self.catalog.get("components", [])
            if component.get("kind") == "plugin"
            and "codex" in component.get("hosts", {})
        }

    @property
    def agent_names(self) -> Set[str]:
        return {
            str(component["name"])
            for component in self.catalog.get("components", [])
            if component.get("kind") == "agent"
            and "codex" in component.get("hosts", {})
        }

    def _custom_agent(
        self,
        name: str,
        *,
        enabled: bool,
    ) -> CodexCustomAgentDeployment:
        component = next(
            (
                item
                for item in self.catalog.get("components", [])
                if item.get("name") == name
                and item.get("kind") == "agent"
                and "codex" in item.get("hosts", {})
            ),
            None,
        )
        source_value = component.get("path") if component else None
        resource_values = component.get("resources", []) if component else []
        # A catalogued Scout installs from the active definition while keeping
        # its legacy schema cleanup. If it is absent from an older catalog, the
        # frozen fixture remains available only to remove an installed legacy
        # Scout without depending on mutable source bytes.
        if name == "evidence-scout":
            source = (
                self.repo_root / source_value
                if isinstance(source_value, str) and source_value
                else self.repo_root
                / "scripts/tests/fixtures/archived-agents/evidence-scout.toml"
            )
            if enabled and component is None:
                raise StateError(
                    "evidence-scout is not available in this component catalog",
                    host="codex",
                    stage="component-selection",
                )
            return CodexEvidenceScoutDeployment(
                source,
                self.codex_home,
                self.version,
                enabled=enabled,
                dry_run=self.dry_run,
                force=self.force,
            )
        if not isinstance(source_value, str) or not source_value:
            raise StateError(
                "{} source path is missing".format(name),
                host="codex",
                stage=name,
                path=str(self.repo_root / "components.json"),
            )
        if not isinstance(resource_values, list) or any(
            not isinstance(item, dict)
            or set(item) != {"source", "target"}
            or not isinstance(item.get("source"), str)
            or not item["source"]
            or item["source"].startswith("/")
            or "\\" in item["source"]
            or any(part in {"", ".", ".."} for part in item["source"].split("/"))
            or not isinstance(item.get("target"), str)
            or not item["target"]
            or item["target"].startswith("/")
            or "\\" in item["target"]
            or any(part in {"", ".", ".."} for part in item["target"].split("/"))
            for item in resource_values
        ) or len({item["target"] for item in resource_values}) != len(resource_values):
            raise StateError(
                "{} resources are invalid".format(name),
                host="codex",
                stage=name,
                path=str(self.repo_root / "components.json"),
            )
        return CodexCustomAgentDeployment(
            name,
            self.repo_root / source_value,
            self.codex_home,
            self.version,
            enabled=enabled,
            accepted_schemas=(1, 2, 4) if resource_values else (1, 4),
            resources=tuple(
                (self.repo_root / item["source"], item["target"])
                for item in resource_values
            ),
            dry_run=self.dry_run,
            force=self.force,
        )

    def _evidence_scout(self, *, enabled: bool) -> CodexEvidenceScoutDeployment:
        deployment = self._custom_agent("evidence-scout", enabled=enabled)
        assert isinstance(deployment, CodexEvidenceScoutDeployment)
        return deployment

    def _agent_order(self) -> List[str]:
        names = [
            str(component["name"])
            for component in self.catalog.get("components", [])
            if component.get("kind") == "agent"
            and "codex" in component.get("hosts", {})
        ]
        return names if "evidence-scout" in names else names + ["evidence-scout"]

    def _require_cli(self) -> None:
        if shutil.which("codex") is None and not self.dry_run:
            raise InstallerError(
                "codex CLI is required for Codex lifecycle operations",
                host="codex",
                stage="preflight",
            )

    def _plugins(self) -> List[Dict[str, Any]]:
        if shutil.which("codex") is None:
            return []
        data = run_json(("codex", "plugin", "list", "--json"), stage="read-state")
        return [
            plugin
            for plugin in data.get("installed", [])
            if isinstance(plugin, dict)
            and plugin.get("marketplaceName") == self.marketplace
            and plugin.get("name")
        ]

    def _plugin_source(self, component: str) -> Tuple[Path, Dict[str, Any]]:
        catalog_entry = next(
            (
                item
                for item in self.catalog.get("components", [])
                if item.get("name") == component
            ),
            None,
        )
        host = catalog_entry.get("hosts", {}).get("codex", {}) if catalog_entry else {}
        manifest_value = host.get("manifest") if isinstance(host, dict) else None
        if not isinstance(manifest_value, str) or not manifest_value:
            raise StateError(
                "Codex plugin manifest path is missing for {}".format(component),
                host="codex",
                stage="plugin-cache-verify",
                path=str(self.repo_root / "components.json"),
            )
        manifest_path = self.repo_root / manifest_value
        metadata = load_json(manifest_path, {})
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != component
            or not isinstance(metadata.get("version"), str)
            or not metadata["version"].strip()
        ):
            raise StateError(
                "invalid Codex plugin manifest for {}".format(component),
                host="codex",
                stage="plugin-cache-verify",
                path=str(manifest_path),
            )
        return manifest_path.parent.parent, metadata

    @staticmethod
    def _declared_payload_files(root: Path, metadata: Mapping[str, Any]) -> List[Path]:
        files = [root / ".codex-plugin" / "plugin.json"]
        for key in ("skills", "hooks"):
            declared = metadata.get(key, [])
            values = [declared] if isinstance(declared, str) else declared
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.startswith("./")
                for value in values
            ):
                raise StateError(
                    "invalid {} declaration in Codex plugin manifest".format(key),
                    host="codex",
                    stage="plugin-cache-verify",
                    path=str(root / ".codex-plugin" / "plugin.json"),
                )
            for value in values:
                source = root / value[2:]
                if source.is_dir():
                    files.extend(path for path in source.rglob("*") if path.is_file())
                elif source.is_file():
                    files.append(source)
                else:
                    raise StateError(
                        "declared Codex plugin payload is missing: {}".format(value),
                        host="codex",
                        stage="plugin-cache-verify",
                        path=str(source),
                    )
        return list(dict.fromkeys(files))

    def _validate_plugin_install(
        self, component: str, result: Mapping[str, Any]
    ) -> Path:
        source_root, metadata = self._plugin_source(component)
        version = str(metadata["version"]).strip()
        expected = {
            "pluginId": "{}@{}".format(component, self.marketplace),
            "name": component,
            "marketplaceName": self.marketplace,
            "version": version,
        }
        for key, value in expected.items():
            if result.get(key) != value:
                raise InstallerError(
                    "Codex plugin add returned unexpected {} for {}".format(
                        key, component
                    ),
                    host="codex",
                    stage="plugin-cache-verify",
                )

        installed_value = result.get("installedPath")
        if not isinstance(installed_value, str) or not installed_value:
            raise InstallerError(
                "Codex plugin add returned no installedPath for {}".format(component),
                host="codex",
                stage="plugin-cache-verify",
            )
        installed_raw = Path(installed_value).expanduser()
        try:
            installed = installed_raw.resolve(strict=True)
        except OSError as exc:
            raise InstallerError(
                "Codex plugin cache is missing after install: {}".format(exc),
                host="codex",
                stage="plugin-cache-verify",
                path=str(installed_raw),
            ) from exc
        expected_root = (
            self.codex_home
            / "plugins"
            / "cache"
            / self.marketplace
            / component
            / version
        ).resolve()
        if installed != expected_root or not installed.is_dir():
            raise InstallerError(
                "Codex plugin installedPath is outside the expected versioned cache",
                host="codex",
                stage="plugin-cache-verify",
                path=str(installed),
            )

        for source in self._declared_payload_files(source_root, metadata):
            relative = source.relative_to(source_root)
            cached = installed / relative
            if not cached.is_file() or sha256_file(source) != sha256_file(cached):
                raise InstallerError(
                    "Codex plugin cache payload is missing or stale: {}".format(
                        relative
                    ),
                    host="codex",
                    stage="plugin-cache-verify",
                    path=str(cached),
                )
        return installed

    def _run_plugin_add(self, component: str) -> Dict[str, Any]:
        return run_json(
            (
                "codex",
                "plugin",
                "add",
                "{}@{}".format(component, self.marketplace),
                "--json",
            ),
            stage="plugin-add",
        )

    def _install_plugin(self, component: str) -> Dict[str, Any]:
        result = self._run_plugin_add(component)
        try:
            self._validate_plugin_install(component, result)
            return result
        except StateError:
            raise
        except InstallerError:
            installed = next(
                (
                    plugin
                    for plugin in self._plugins()
                    if plugin.get("name") == component
                ),
                None,
            )
            if installed is not None:
                self._remove_plugin(installed, stage="plugin-cache-repair")
            print("  [repair] reinstalling invalid {} cache".format(component))
            result = self._run_plugin_add(component)
            try:
                self._validate_plugin_install(component, result)
            except StateError:
                raise
            except InstallerError as second_error:
                raise InstallerError(
                    "Codex plugin cache repair failed for {}: {}".format(
                        component, second_error
                    ),
                    host="codex",
                    stage="plugin-cache-repair",
                    path=second_error.path,
                ) from second_error
            print("  [ok] repaired {} cache".format(component))
            return result

    def _marketplace_info(self) -> Optional[Dict[str, Any]]:
        listing = run_json(
            ("codex", "plugin", "marketplace", "list", "--json"),
            stage="marketplace-list",
        )
        matches = [
            item
            for item in listing.get("marketplaces", [])
            if isinstance(item, dict) and item.get("name") == self.marketplace
        ]
        if len(matches) > 1:
            raise InstallerError(
                "marketplace '{}' was returned more than once".format(
                    self.marketplace
                ),
                host="codex",
                stage="marketplace-verify",
            )
        return matches[0] if matches else None

    def _add_marketplace(self, source: str, *, ref: Optional[str], stage: str) -> None:
        command = ["codex", "plugin", "marketplace", "add", source]
        if ref is not None:
            command.extend(("--ref", ref))
        command.append("--json")
        run_json(command, stage=stage)

    def _verify_remote_marketplace(self, expected_commit: str) -> Dict[str, Any]:
        info = self._marketplace_info()
        if info is None:
            raise InstallerError(
                "marketplace '{}' was not returned after add".format(self.marketplace),
                host="codex",
                stage="marketplace-verify",
            )
        source_info = info.get("marketplaceSource", {})
        source_type = (
            source_info.get("sourceType", "") if isinstance(source_info, dict) else ""
        )
        source_value = (
            source_info.get("source", "") if isinstance(source_info, dict) else ""
        )
        if source_type != "git" or source_value != REMOTE_MARKETPLACE_SOURCE:
            raise InstallerError(
                "marketplace '{}' points at a different source".format(
                    self.marketplace
                ),
                host="codex",
                stage="marketplace-verify",
            )
        root = Path(str(info.get("root", "")))
        current = git_commit(root, "HEAD")
        if not current or current != expected_commit:
            raise InstallerError(
                "marketplace '{}' did not resolve to the expected revision".format(
                    self.marketplace
                ),
                host="codex",
                stage="version-pin-verify",
                path=str(root),
            )
        return info

    def _ensure_marketplace(self, source: str) -> None:
        info = self._marketplace_info()
        if self.local_source:
            if info is None:
                self._add_marketplace(source, ref=None, stage="marketplace-add")
                self.completed.append("added marketplace")
                info = self._marketplace_info()
            if info is None:
                raise InstallerError(
                    "marketplace '{}' was not returned after add".format(
                        self.marketplace
                    ),
                    host="codex",
                    stage="marketplace-verify",
                )
            source_info = info.get("marketplaceSource", {})
            source_type = (
                source_info.get("sourceType", "")
                if isinstance(source_info, dict)
                else ""
            )
            source_value = (
                source_info.get("source", "")
                if isinstance(source_info, dict)
                else ""
            )
            try:
                actual = Path(str(source_value)).resolve(strict=True)
                expected = Path(source).resolve(strict=True)
            except OSError as exc:
                raise InstallerError(
                    "cannot resolve local marketplace source: {}".format(exc),
                    host="codex",
                    stage="marketplace-verify",
                    path=str(source_value),
                ) from exc
            if source_type != "local" or actual != expected:
                raise InstallerError(
                    "marketplace '{}' already points at a different source".format(
                        self.marketplace
                    ),
                    host="codex",
                    stage="marketplace-verify",
                )
            return

        target_ref = "v{}".format(self.version)
        if info is None:
            self._add_marketplace(source, ref=target_ref, stage="marketplace-add")
            self.completed.append("added marketplace")
            added = self._marketplace_info()
            if added is None:
                raise InstallerError(
                    "marketplace '{}' was not returned after add".format(
                        self.marketplace
                    ),
                    host="codex",
                    stage="marketplace-verify",
                )
            root = Path(str(added.get("root", "")))
            target_commit = git_commit(root, "{}^{{commit}}".format(target_ref))
            if not target_commit:
                raise InstallerError(
                    "marketplace '{}' does not contain {}".format(
                        self.marketplace, target_ref
                    ),
                    host="codex",
                    stage="version-pin-verify",
                    path=str(root),
                )
            self._verify_remote_marketplace(target_commit)
            return

        source_info = info.get("marketplaceSource", {})
        source_type = (
            source_info.get("sourceType", "") if isinstance(source_info, dict) else ""
        )
        source_value = (
            source_info.get("source", "") if isinstance(source_info, dict) else ""
        )
        if source_type == "local":
            raise InstallerError(
                "marketplace '{}' points at local source {}; remove or repoint it before using the public installer".format(
                    self.marketplace, source_value
                ),
                host="codex",
                stage="marketplace-verify",
            )
        if source_type != "git" or source_value != REMOTE_MARKETPLACE_SOURCE:
            raise InstallerError(
                "marketplace '{}' already points at a different source".format(
                    self.marketplace
                ),
                host="codex",
                stage="marketplace-verify",
            )

        old_root = Path(str(info.get("root", "")))
        old_commit = git_commit(old_root, "HEAD")
        if not old_commit:
            raise InstallerError(
                "cannot snapshot the existing marketplace revision",
                host="codex",
                stage="marketplace-update-preflight",
                path=str(old_root),
            )
        target_commit = git_commit(old_root, "{}^{{commit}}".format(target_ref))
        if target_commit and target_commit == old_commit:
            self._verify_remote_marketplace(target_commit)
            return

        removed = False
        try:
            run_json(
                (
                    "codex",
                    "plugin",
                    "marketplace",
                    "remove",
                    self.marketplace,
                    "--json",
                ),
                stage="marketplace-update",
            )
            removed = True
            self._add_marketplace(source, ref=target_ref, stage="marketplace-update")
            updated = self._marketplace_info()
            if updated is None:
                raise InstallerError(
                    "marketplace '{}' was not returned after update".format(
                        self.marketplace
                    ),
                    host="codex",
                    stage="marketplace-update",
                )
            updated_root = Path(str(updated.get("root", "")))
            updated_commit = git_commit(
                updated_root, "{}^{{commit}}".format(target_ref)
            )
            if not updated_commit:
                raise InstallerError(
                    "updated marketplace does not contain {}".format(target_ref),
                    host="codex",
                    stage="version-pin-verify",
                    path=str(updated_root),
                )
            self._verify_remote_marketplace(updated_commit)
        except InstallerError as original:
            if not removed:
                raise
            try:
                current = self._marketplace_info()
                if current is not None:
                    run_json(
                        (
                            "codex",
                            "plugin",
                            "marketplace",
                            "remove",
                            self.marketplace,
                            "--json",
                        ),
                        stage="marketplace-rollback",
                    )
                self._add_marketplace(
                    source, ref=old_commit, stage="marketplace-rollback"
                )
                self._verify_remote_marketplace(old_commit)
            except InstallerError as rollback_error:
                self.completed.append("marketplace update incomplete")
                raise InstallerError(
                    "marketplace update failed and rollback failed: {}; rollback: {}".format(
                        original.render(), rollback_error.render()
                    ),
                    host="codex",
                    stage="marketplace-rollback",
                ) from rollback_error
            raise InstallerError(
                "marketplace update to {} failed; restored previous revision {}: {}".format(
                    target_ref, old_commit[:12], original.render()
                ),
                host="codex",
                stage="marketplace-update",
                path=str(old_root),
            ) from original

        self.completed.append("updated marketplace to {}".format(target_ref))
        print("  [ok] marketplace {} -> {}".format(self.marketplace, target_ref))

    def _deploy_plugins(self, components: Sequence[str]) -> None:
        components = list(dict.fromkeys(item for item in components if item))
        if not components:
            return
        source = (
            str(self.repo_root)
            if self.local_source
            else "hukuhaka/hukuhaka-harness"
        )
        if self.dry_run:
            print("Codex deploy:")
            print("  [dry-run] marketplace add {}".format(source))
            for component in components:
                print("  [dry-run] plugin add {}@{}".format(component, self.marketplace))
            return

        self._ensure_marketplace(source)

        for component in components:
            self.install_results[component] = self._install_plugin(component)
            print("  [ok] {}@{}".format(component, self.marketplace))

    def current_components(self) -> Set[str]:
        components, _ = self.current_component_state()
        return components

    def current_component_state(self) -> Tuple[Set[str], Dict[str, str]]:
        plugins = self._plugins()
        names = {
            self.aliases.get(str(plugin["name"]), str(plugin["name"]))
            for plugin in plugins
        }
        versions = {}  # type: Dict[str, str]
        for plugin in sorted(
            plugins,
            key=lambda item: (
                str(item["name"]) != self.aliases.get(
                    str(item["name"]), str(item["name"])
                ),
                str(item["name"]),
            ),
        ):
            name = str(plugin["name"])
            canonical = self.aliases.get(name, name)
            version = plugin.get("version")
            if (
                canonical not in versions
                and isinstance(version, str)
                and version.strip()
            ):
                versions[canonical] = version.strip()
        if (self.codex_home / GUIDANCE_MANIFEST).is_file():
            names.add("agents-md")
        for name in self._agent_order():
            manifest = self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            if manifest.exists() or manifest.is_symlink():
                names.add(name)
        return names, versions

    def _remove_plugin(self, plugin: Mapping[str, Any], *, stage: str) -> None:
        plugin_id = str(plugin.get("pluginId", ""))
        if not plugin_id:
            raise InstallerError(
                "installed Codex plugin has no pluginId",
                host="codex",
                stage=stage,
            )
        if self.dry_run:
            print("  [dry-run] plugin remove {}".format(plugin_id))
        else:
            run_json(
                ("codex", "plugin", "remove", plugin_id, "--json"),
                stage=stage,
            )
        self.completed.append("removed {}".format(plugin_id))

    def _remove_marketplace(self) -> None:
        if self.dry_run:
            print("  [dry-run] marketplace remove {}".format(self.marketplace))
            return
        listing = run_json(
            ("codex", "plugin", "marketplace", "list", "--json"),
            stage="marketplace-list",
        )
        if not any(
            isinstance(item, dict) and item.get("name") == self.marketplace
            for item in listing.get("marketplaces", [])
        ):
            return
        run_json(
            ("codex", "plugin", "marketplace", "remove", self.marketplace, "--json"),
            stage="marketplace-remove",
        )
        self.completed.append("removed marketplace")

    def reset(self, *, include_template: bool) -> None:
        self._require_cli()
        print("Resetting Codex:")
        for plugin in self._plugins():
            self._remove_plugin(plugin, stage="reset")
        self._remove_marketplace()
        existing_agents = {
            name
            for name in self._agent_order()
            if (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).exists()
            or (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).is_symlink()
        }
        for name in self._agent_order():
            self._custom_agent(name, enabled=False).uninstall()
            if name in existing_agents:
                self.completed.append("reset {}".format(name))
        if include_template:
            guidance_existed = (
                (self.codex_home / GUIDANCE_MANIFEST).exists()
                or (self.codex_home / GUIDANCE_MANIFEST).is_symlink()
            )
            CodexGuidanceDeployment(
                self.repo_root / "templates" / "AGENTS.md",
                self.codex_home,
                self.version,
                enabled=False,
                dry_run=self.dry_run,
                force=self.force,
            ).uninstall()
            if guidance_existed:
                self.completed.append("reset agents-md")

    def install(
        self,
        components: Sequence[str],
        *,
        reset: bool = False,
        include_template: bool = False,
    ) -> None:
        self._require_cli()
        desired = set(components)
        desired_plugins = sorted(desired & self.plugin_names)
        desired_agents = [
            name for name in self._agent_order() if name in desired
        ]
        guidance_existed = (
            (self.codex_home / GUIDANCE_MANIFEST).exists()
            or (self.codex_home / GUIDANCE_MANIFEST).is_symlink()
        )
        existing_agents = {
            name
            for name in self._agent_order()
            if (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).exists()
            or (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).is_symlink()
        }
        if reset:
            self.reset(include_template=include_template)

        self._deploy_plugins(desired_plugins)
        self.completed.extend("installed {}".format(name) for name in desired_plugins)

        # Add canonical plugins first. Only after they succeed is it safe to
        # remove omitted components and declared aliases.
        for plugin in self._plugins():
            name = str(plugin["name"])
            canonical = self.aliases.get(name, name)
            if canonical not in desired_plugins or name in self.aliases:
                self._remove_plugin(plugin, stage="desired-state-remove")

        CodexGuidanceDeployment(
            self.repo_root / "templates" / "AGENTS.md",
            self.codex_home,
            self.version,
            enabled="agents-md" in desired,
            dry_run=self.dry_run,
            force=self.force,
        ).deploy()
        if "agents-md" in desired:
            self.completed.append("installed agents-md")
        elif guidance_existed:
            self.completed.append("removed agents-md")
        # Install every desired custom agent before removing excluded agents.
        # Each deployment owns its own transaction, so a later agent failure
        # does not roll back an earlier successful component.
        for name in desired_agents:
            self._custom_agent(name, enabled=True).deploy()
            self.completed.append("installed {}".format(name))
        for name in self._agent_order():
            if name in desired:
                continue
            self._custom_agent(name, enabled=False).uninstall()
            if name in existing_agents:
                self.completed.append("removed {}".format(name))
        # Apply the same feature policy even when no optional agent is selected.
        with installer_state(self.codex_home, dry_run=self.dry_run):
            config = CodexConfigEditor(
                self.codex_home,
                dry_run=self.dry_run,
                managed_keys=tuple(SUBAGENT_SETTINGS),
                stage="install-subagent-settings",
            )
            config.apply(config.plan(SUBAGENT_SETTINGS), show_diff=False)
        if not self.dry_run:
            self.verify(desired)

    def verify(self, desired: Set[str]) -> None:
        actual_plugins = {
            str(plugin["name"]): plugin
            for plugin in self._plugins()
            if str(plugin["name"]) in self.plugin_names
        }
        expected_plugins = desired & self.plugin_names
        guidance = (self.codex_home / GUIDANCE_MANIFEST).is_file()
        installed_agents = {
            name
            for name in self._agent_order()
            if (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).is_file()
        }
        expected_agents = desired & self.agent_names
        if (
            set(actual_plugins) != expected_plugins
            or guidance != ("agents-md" in desired)
            or installed_agents != expected_agents
        ):
            raise InstallerError(
                "Codex post-install state does not match the requested components",
                host="codex",
                stage="verify",
            )
        for component in sorted(expected_plugins):
            _, metadata = self._plugin_source(component)
            if actual_plugins[component].get("version") != metadata["version"]:
                raise InstallerError(
                    "Codex post-install version does not match for {}".format(component),
                    host="codex",
                    stage="verify",
                )
            result = self.install_results.get(component)
            if result is None:
                raise InstallerError(
                    "Codex install result is missing for {}".format(component),
                    host="codex",
                    stage="verify",
                )
            self._validate_plugin_install(component, result)
        for name in self._agent_order():
            if name in expected_agents:
                self._custom_agent(name, enabled=True).verify()

    def uninstall(self) -> None:
        self._require_cli()
        for plugin in self._plugins():
            self._remove_plugin(plugin, stage="uninstall")
        guidance_existed = (
            (self.codex_home / GUIDANCE_MANIFEST).exists()
            or (self.codex_home / GUIDANCE_MANIFEST).is_symlink()
        )
        existing_agents = {
            name
            for name in self._agent_order()
            if (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).exists()
            or (
                self.codex_home / ".hukuhaka-{}-manifest.json".format(name)
            ).is_symlink()
        }
        CodexGuidanceDeployment(
            self.repo_root / "templates" / "AGENTS.md",
            self.codex_home,
            self.version,
            enabled=False,
            dry_run=self.dry_run,
            force=self.force,
        ).uninstall()
        if guidance_existed:
            self.completed.append("removed agents-md")
        for name in self._agent_order():
            self._custom_agent(name, enabled=False).uninstall()
            if name in existing_agents:
                self.completed.append("removed {}".format(name))
        if not self.dry_run and self.current_components():
            raise InstallerError(
                "Codex uninstall left managed components behind",
                host="codex",
                stage="verify",
            )
