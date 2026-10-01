"""Receipt-owned Paseo profiles; native CLI owns configuration persistence.

Profiles are launch settings, not native agents or injected instructions.
The native profile array has no revision guard. Refuse observed concurrent
changes, verify after one write, and never roll back the shared config file.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .common import FileTransaction, InstallerError, InstallerLock, StateError, safe_join
from .state import InstallState
from .paseo_transport import LocalPaseoTransport

PROFILE_FIELDS = {"name", "provider", "model", "modeId", "thinkingOptionId", "featureValues", "notes"}

def resolve_paseo_home(environ: Optional[Mapping[str, str]] = None, *, fallback_home: Optional[Path] = None) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("PASEO_HOME", "").strip()
    return (Path(configured).expanduser() if configured else (fallback_home or Path.home()) / ".paseo").absolute()


def _error(message: str, stage: str = "profiles") -> InstallerError:
    return InstallerError(message, host="paseo", stage=stage)


def _decode(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("non-finite number")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise _error("Profile/config input must be a strict UTF-8 JSON object") from exc


def profile_hash(profile: dict) -> str:
    values = {key: value for key, value in profile.items() if key != "id"}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _profiles(value: Any) -> list:
    if not isinstance(value, list):
        raise _error("Paseo agentProfiles must be an array")
    ids = set()
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise _error("Paseo profile requires a nonempty id")
        if row["id"] in ids:
            raise _error("Duplicate Paseo profile id")
        ids.add(row["id"])
        if any(not isinstance(row.get(key), str) or not row[key] for key in ("name", "provider")):
            raise _error("Paseo profile requires name and provider")
        profile_hash(row)
    return copy.deepcopy(value)


@dataclass
class ProfilePlan:
    before: list
    after: list
    records_before: dict
    receipts: dict
    removals: list
    actions: list
    blocked: list
    requested: list

    @property
    def changed(self) -> bool:
        return self.before != self.after


class PaseoInstaller:
    def __init__(self, repo_root: Path, catalog: dict, version: str, *,
                 local_source: bool = False, dry_run: bool = False, force: bool = False,
                 adopt: Optional[Mapping[str, str]] = None, rename_adopted: Sequence[str] = ()) -> None:
        self.repo_root = Path(repo_root)
        self.catalog = catalog
        self.version = version
        self.home = resolve_paseo_home()
        self.state = InstallState(self.home)
        self.dry_run = dry_run
        self.force = force
        self.adopt = dict(adopt or {})
        self.rename_adopted = set(rename_adopted)
        self.completed = []
        self.components = {row["name"]: row for row in catalog["components"]
                           if "paseo" in row.get("hosts", {})}
        self.transport = LocalPaseoTransport(self.home)
        self._previewed = None
        self._safe("config.json")
        self._safe("hk-operation.lock")
        self._safe(".hukuhaka-installer.lock")

    def _safe(self, relative: str) -> Path:
        path = safe_join(self.home, relative, operation="paseo-path")
        for parent in (path, *path.parents):
            if parent.is_symlink():
                raise _error("Paseo managed paths must not be symlinks")
            if parent == self.home:
                break
        return path

    def require_cli(self) -> str:
        return self.transport.require_cli()

    def _saved(self) -> list:
        path = self._safe("config.json")
        if not path.exists():
            return []
        try:
            config = _decode(path.read_bytes())
        except OSError as exc:
            raise _error("Cannot read Paseo config") from exc
        daemon = config.get("daemon", {})
        if not isinstance(daemon, dict):
            raise _error("Paseo daemon configuration must be an object")
        return _profiles(daemon.get("agentProfiles", []))

    def _source(self, role: str) -> dict:
        component = self.components[role]
        if component.get("kind") != "profile":
            raise _error("Paseo accepts profile components only")
        path = safe_join(self.repo_root, component["path"], operation="profile-source")
        try:
            values = _decode(path.read_bytes())
        except OSError as exc:
            raise _error("Cannot read profile source for " + role) from exc
        if set(values) - PROFILE_FIELDS or values.get("name") != role:
            raise _error("Invalid profile source fields for " + role)
        if any(not isinstance(values.get(key), str) or not values[key] for key in ("name", "provider", "model", "modeId", "notes")):
            raise _error("Missing profile source fields for " + role)
        if "thinkingOptionId" in values and not isinstance(values["thinkingOptionId"], str):
            raise _error("Invalid profile thinking option")
        if "featureValues" in values and not isinstance(values["featureValues"], dict):
            raise _error("Invalid profile features")
        return values

    def _receipts(self) -> dict:
        records = self.state.read()["components"]
        result = {}
        identities = set()
        for role, record in records.items():
            if record["kind"] != "profile":
                raise _error("Unexpected non-profile record in Paseo home")
            receipt = record.get("receipt")
            required = {"id", "origin", "source_sha256", "version"}
            if (not isinstance(receipt, dict) or not required <= set(receipt)
                    or set(receipt) - required - {"applied", "previous_sha256", "previous_source_sha256", "pending_action", "pending_removal"}
                    or not isinstance(receipt.get("id"), str) or not receipt["id"]
                    or receipt.get("origin") not in {"created", "adopted"}
                    or not isinstance(receipt.get("source_sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", receipt["source_sha256"]) is None
                    or not isinstance(receipt.get("version"), str)):
                raise _error("Invalid profile ownership receipt for " + role)
            if ("applied" in receipt and type(receipt["applied"]) is not bool
                    or "pending_removal" in receipt and type(receipt["pending_removal"]) is not bool
                    or "pending_action" in receipt and receipt["pending_action"] not in {"source", "rename"}
                    or "previous_sha256" in receipt and (not isinstance(receipt["previous_sha256"], str)
                        or re.fullmatch(r"[0-9a-f]{64}", receipt["previous_sha256"]) is None)
                    or "previous_source_sha256" in receipt and (not isinstance(receipt["previous_source_sha256"], str)
                        or re.fullmatch(r"[0-9a-f]{64}", receipt["previous_source_sha256"]) is None)):
                raise _error("Invalid pending profile receipt for " + role)
            if receipt["id"] in identities:
                raise _error("A profile id is owned by more than one role")
            identities.add(receipt["id"])
            result[role] = receipt
        return result

    def current_components(self) -> set:
        return set(self._receipts())

    def current_component_state(self):
        return self.current_components(), {}

    def status(self) -> dict:
        profiles = self._saved()
        receipts = self._receipts()
        by_id = {row["id"]: row for row in profiles}
        roles = []
        for role in self.components:
            receipt = receipts.get(role)
            row = by_id.get(receipt["id"]) if receipt else None
            names = {role, "advisor"} if role == "advisor-gpt" else {role}
            candidates = [p for p in profiles if p["name"] in names] if not receipt else []
            status = ("missing" if row is None else "managed" if profile_hash(row) == receipt["source_sha256"]
                      else "local override") if receipt else ("existing, unmanaged" if candidates else "not installed")
            if receipt and receipt.get("applied") is False:
                status += ", pending apply"
            roles.append({"role": role, "status": status, "id": row["id"] if row else None,
                          "profile": row, "candidate_ids": [p["id"] for p in candidates]})
        return {"home": str(self.home), "profiles": profiles, "managed": receipts,
                "components": list(receipts), "roles": roles, "runtime_verified": False}

    def plan(self, names: Sequence[str], *, reset: bool = False, before: Optional[list] = None) -> ProfilePlan:
        requested = list(dict.fromkeys(names))
        if set(requested) - set(self.components):
            raise _error("Unknown Paseo profile selection")
        if set(self.adopt) - set(requested) or self.rename_adopted - set(self.adopt):
            raise _error("Adoption roles must be selected; rename requires explicit adoption")
        if len(set(self.adopt.values())) != len(self.adopt):
            raise _error("One profile id cannot be adopted for multiple roles")
        saved = self._saved() if before is None else _profiles(before)
        original = self._receipts()
        by_id = {row["id"]: row for row in saved}
        owners = {receipt["id"]: role for role, receipt in original.items()}
        after = copy.deepcopy(saved)
        receipts, removals, actions, blocked = {}, [], [], []
        def action(role, kind, detail, previous=None, proposed=None):
            actions.append({"role": role, "action": kind, "detail": detail,
                            "before": previous, "after": proposed})
        def replace(row):
            for index, item in enumerate(after):
                if item["id"] == row["id"]:
                    after[index] = row
                    return
            after.append(row)
        for role in requested:
            source = self._source(role)
            receipt = original.get(role)
            identity = self.adopt.get(role)
            if identity:
                if identity not in by_id:
                    raise _error("Adoption id does not exist for " + role)
                if identity in owners and owners[identity] != role:
                    raise _error("Adoption id already belongs to another role")
                if receipt and receipt["id"] != identity:
                    raise _error("Role already owns a different profile id")
                row = by_id[identity]
                adopted = copy.deepcopy(row)
                if role in self.rename_adopted:
                    if any(p["id"] != identity and p["name"] == source["name"] for p in saved):
                        raise _error("Profile name already exists: " + source["name"])
                    adopted.update(name=source["name"], notes=source["notes"])
                    replace(adopted)
                receipts[role] = receipt or {"id": identity, "origin": "adopted",
                                            "source_sha256": profile_hash(source), "version": self.version}
                action(role, "adopt + rename" if adopted != row else "adopt", "Keep UUID and existing launch settings", row, adopted)
                continue
            row = by_id.get(receipt["id"]) if receipt else None
            if row is None:
                collisions = [p for p in saved if p["name"] == role or (role == "advisor-gpt" and p["name"] == "advisor")]
                if collisions:
                    owned = [owners[p["id"]] for p in collisions if p["id"] in owners]
                    detail = ("Name is used by another managed role ({}); rename it in Paseo before retrying".format(", ".join(owned))
                              if owned else "Existing unmanaged profile; use --adopt " + role + "=<UUID>")
                    blocked.append(role + ": " + detail)
                    action(role, "blocked", detail)
                    continue
                created = dict(source, id=receipt["id"] if receipt and receipt.get("applied") is False else str(uuid.uuid4()))
                replace(created)
                receipts[role] = {"id": created["id"], "origin": "created", "source_sha256": profile_hash(source), "version": self.version}
                action(role, "create", "New profile" if not receipt else "Retry pending creation with its recorded UUID"
                       if receipt.get("applied") is False else "Recreate missing profile with a new UUID", None, created)
            elif (receipt.get("applied") is False and receipt.get("pending_action") == "rename"
                  and profile_hash(row) == receipt.get("previous_sha256")):
                if any(p["id"] != row["id"] and p["name"] == source["name"] for p in saved):
                    raise _error("Pending rename conflicts with an existing profile name")
                replacement = dict(row, name=source["name"], notes=source["notes"])
                replace(replacement)
                receipts[role] = dict(receipt, source_sha256=profile_hash(source), version=self.version)
                action(role, "adopt + rename", "Retry only the approved name and notes change", row, replacement)
            elif (profile_hash(row) not in {receipt["source_sha256"], profile_hash(source)}
                  and not (receipt.get("applied") is False and receipt.get("pending_action") == "source"
                           and profile_hash(row) == receipt.get("previous_sha256"))
                  and not (reset or self.force)):
                receipts[role] = dict(receipt)
                action(role, "keep", "Local override preserved; source differs" if profile_hash(row) != profile_hash(source) else "Current values match source; previous override retained", row, row)
            else:
                # Reset owns known profile fields, not future Paseo extensions.
                replacement = {key: value for key, value in row.items() if key not in PROFILE_FIELDS}
                replacement.update(source)
                replace(replacement)
                receipts[role] = dict(receipt, source_sha256=profile_hash(source), version=self.version)
                action(role, "update" if replacement != row else "keep", "Restore source values" if reset or self.force else "Source defaults", row, replacement)
                if set(replacement) - PROFILE_FIELDS - {"id"}:
                    actions[-1]["detail"] += "; unknown fields retained, remains a local override"
        for role, receipt in original.items():
            if role in requested:
                continue
            row = by_id.get(receipt["id"])
            removals.append(role)
            removable_hashes = {receipt["source_sha256"]}
            if receipt.get("applied") is False and receipt.get("pending_action") == "source":
                removable_hashes.add(receipt.get("previous_source_sha256"))
            if row and receipt["origin"] == "created" and profile_hash(row) in removable_hashes:
                after = [p for p in after if p["id"] != row["id"]]
                action(role, "remove", "Remove unchanged installer-created profile", row, None)
            else:
                action(role, "release", "Keep adopted or edited profile; remove management record" if row else "Remove missing profile record", row, row)
        return ProfilePlan(saved, after, original, receipts, removals, actions, blocked, requested)

    def _write_intent(self, plan: ProfilePlan) -> None:
        """Own exact UUIDs before native effects; never infer ownership by name."""
        before = {row["id"]: row for row in plan.before}
        actions = {item["role"]: item for item in plan.actions}
        with FileTransaction(self.home) as tx:
            for role, receipt in plan.receipts.items():
                item = actions[role]
                changed = item["before"] != item["after"]
                pending = dict(receipt, applied=not changed)
                for key in ("previous_sha256", "previous_source_sha256", "pending_action", "pending_removal"):
                    pending.pop(key, None)
                previous = before.get(receipt["id"])
                if changed:
                    pending["pending_action"] = "rename" if item["action"] == "adopt + rename" else "source"
                if changed and previous is not None:
                    pending["previous_sha256"] = profile_hash(previous)
                    prior = plan.records_before.get(role)
                    if prior:
                        older = prior.get("previous_source_sha256")
                        pending["previous_source_sha256"] = older if older == profile_hash(previous) else prior["source_sha256"]
                self.state.put_receipt(tx, role, pending, "profile", self.version, None)
            for role in plan.removals:
                pending = dict(plan.records_before[role], applied=False, pending_removal=True)
                self.state.put_receipt(tx, role, pending, "profile", self.version, None)
            tx.commit()

    def preview(self, names: Sequence[str], *, reset: bool = False) -> ProfilePlan:
        plan = self.plan(names, reset=reset)
        self._previewed = plan
        print("  Paseo profiles: shared by Codex and Claude main agents")
        print("  Target: " + str(self.home))
        print("  Do not edit Paseo profiles while applying; the native API has no conditional update.")
        print("  Validation requires Node 22+ and the pinned Paseo SDK (@getpaseo/client 0.10.2).")
        print("  First apply prepares the SDK under this Paseo home's hk-runtime; dry runs do not install it.")
        print("  Live provider/model/mode/feature availability is unverified in this preview; apply validates profile changes.")
        if any(receipt.get("applied") is False for receipt in plan.records_before.values()):
            print("  Reconcile pending profile operations; reload only if saved and live profiles differ.")
        for item in plan.actions:
            print("  {}: {} — {}".format(item["role"], item["action"], item["detail"]))
            before, after = item["before"] or {}, item["after"] or {}
            for key in ("name", "provider", "model", "modeId", "thinkingOptionId", "featureValues", "notes"):
                if before.get(key) != after.get(key):
                    print("    {}: {} -> {}".format(key, json.dumps(before.get(key)), json.dumps(after.get(key))))
            if after.get("featureValues", {}).get("fast_mode"):
                print("    Fast mode on: priority inference, increased usage.")
        for reason in plan.blocked:
            print("  [blocked] " + reason)
        return plan

    def install(self, names: Sequence[str], *, reset: bool = False, include_template: bool = False) -> None:
        if include_template:
            raise _error("Paseo profiles have no managed instruction template")
        plan = self._previewed or self.plan(names, reset=reset)
        if plan.requested != list(dict.fromkeys(names)):
            raise _error("Profile selection changed after preview")
        if self.dry_run:
            print("  [dry-run] Profile values and installer records were not changed.")
            return
        # Never put config.json in a FileTransaction: Paseo and its UI own it.
        with InstallerLock(self.home, name="hk-operation.lock"):
            if self.state.has_pending_transactions():
                self._recover_receipts()
            if self._saved() != plan.before or self._receipts() != plan.records_before:
                raise _error("Profiles or ownership changed after preview; review a fresh plan", "preflight")
            self.transport.prepare()
            live = _profiles(self.transport.read_profiles())
            if live != plan.before:
                if any(receipt.get("applied") is False for receipt in plan.records_before.values()) and self._saved() == plan.before:
                    outcome = self.transport.reload_profiles(plan.before)
                    if not outcome.get("applied") or _profiles(self.transport.read_profiles()) != plan.before:
                        raise _error("Saved profiles are still pending application", "apply")
                    self.completed.append("verified pending profile reload")
                else:
                    raise _error("Paseo profiles changed since preview; resolve them before applying", "preflight")
            failures = list(plan.blocked)
            for item in plan.actions:
                if item["action"] in {"blocked", "release", "remove"} or item["before"] == item["after"]:
                    continue
                reason = self.transport.validate_profile(item["after"])
                if reason:
                    failures.append(item["role"] + ": " + reason)
                    role = item["role"]
                    proposed = item["after"]
                    if item["before"] is None:
                        plan.after = [p for p in plan.after if p["id"] != proposed["id"]]
                    else:
                        plan.after = [item["before"] if p["id"] == proposed["id"] else p for p in plan.after]
                    plan.receipts.pop(role, None)
                    item["action"] = "blocked"
            operation = self.state.begin_operation("install" if names else "uninstall", self.version, list(names))
            try:
                if plan.changed:
                    self._write_intent(plan)
                    self.state.update_operation(operation, "apply-profiles", self.completed)
                    outcome = self.transport.apply_profiles(plan.before, plan.after)
                    if not isinstance(outcome, dict) or type(outcome.get("saved")) is not bool or type(outcome.get("applied")) is not bool:
                        self.completed.append("native profile update attempted; outcome requires inspection")
                        raise _error("Native profile update returned an unknown outcome", "apply")
                    if outcome["saved"]:
                        self.completed.append("saved profiles")
                    self.state.update_operation(operation, "verify-profiles", self.completed)
                    if not outcome["saved"] or not outcome["applied"]:
                        raise _error("Profiles saved but not confirmed active; inspect status before retrying" if outcome["saved"]
                                     else "Profile save was not confirmed; inspect pending receipts", "apply")
                    self.completed.append("verified active profiles")
                    for notice in outcome.get("notices", []):
                        print("  " + notice)
                else:
                    # Adoption still confirms the selected UUID online; no reload.
                    if _profiles(self.transport.read_profiles()) != plan.before:
                        raise _error("Profiles changed during validation; review a fresh plan", "preflight")
                with FileTransaction(self.home) as tx:
                    for role in plan.removals:
                        self.state.remove_receipt(tx, role, None)
                    for role, receipt in plan.receipts.items():
                        confirmed = dict(receipt, applied=True)
                        confirmed.pop("previous_sha256", None)
                        confirmed.pop("previous_source_sha256", None)
                        confirmed.pop("pending_action", None)
                        confirmed.pop("pending_removal", None)
                        self.state.put_receipt(tx, role, confirmed, "profile", self.version, None)
                    tx.commit()
                self.completed.extend(item["action"] + " " + item["role"] for item in plan.actions if item["action"] != "blocked")
                if failures:
                    raise _error("Some profiles were not applied: " + "; ".join(failures), "profile-validation")
                self.state.finish_operation(operation, "success", self.completed)
            except Exception as exc:
                if getattr(exc, "mutation_attempted", False):
                    self.completed.append("saved profiles" if getattr(exc, "saved", None) is True
                                          else "native profile update attempted; outcome requires inspection")
                self.state.finish_operation(operation, "partial" if self.completed else "failed", self.completed, exc)
                raise

    def _recover_receipts(self) -> None:
        # Old/corrupt journals must not turn a record recovery into config rollback.
        root = self.home / ".hukuhaka-transactions"
        for journal in root.glob("*/journal.json"):
            if journal.is_symlink() or journal.parent.is_symlink():
                raise _error("Invalid Paseo receipt transaction path")
            data = _decode(journal.read_bytes())
            for entry in data.get("entries", []):
                if Path(entry.get("target", "")).absolute() not in {self.state.path, self.state.backup_path}:
                    raise _error("Paseo recovery refuses non-receipt transaction targets")
        self.state.recover_transactions()

    def uninstall(self) -> None:
        self.install([])

    def recover(self) -> None:
        """Recover installer records only, including when profile preview fails."""
        print("Recover Paseo installer receipts only; saved profiles and runtime are unchanged.")
        if self.dry_run:
            return
        with InstallerLock(self.home, name="hk-operation.lock"):
            if self.state.has_pending_transactions():
                self._recover_receipts()
            else:
                self.state.restore_backup()
            self._receipts()
        self.completed.append("recovered profile receipts; rerun status before applying")
