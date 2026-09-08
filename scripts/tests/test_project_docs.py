from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "marketplace" / "hukuhaka-project-docs" / "skills" / "project-docs" / "scripts" / "project_docs.py"
SPEC = importlib.util.spec_from_file_location("project_docs", SCRIPT)
assert SPEC and SPEC.loader
PROJECT_DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROJECT_DOCS)


class ProjectDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="project docs ")
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "architecture.md").write_text("# Architecture\n\nCurrent contract.\n", encoding="utf-8")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "check.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest(self, **overrides: object) -> dict[str, object]:
        document: dict[str, object] = {
            "id": "architecture",
            "path": "docs/architecture.md",
            "role": "contract",
            "status": "current",
            "authority": "normative",
            "summary": "System boundaries.",
            "appliesTo": ["src/**"],
            "readWhen": ["architecture changes"],
            "verifyWith": ["scripts/check.sh"],
        }
        document.update(overrides)
        return {"schemaVersion": 1, "documents": [document]}

    def write_manifest(self, value: object) -> None:
        (self.root / "project-docs.json").write_text(json.dumps(value), encoding="utf-8")

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("python3", str(SCRIPT)) + arguments,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_manifest_is_deterministic(self) -> None:
        self.write_manifest(self.manifest())
        first = self.run_cli("validate", "--root", str(self.root))
        second = self.run_cli("validate", "--root", str(self.root))
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual("valid", json.loads(first.stdout)["status"])

    def test_reader_catalog_returns_validated_metadata_without_content(self) -> None:
        self.write_manifest(self.manifest())
        first = self.run_cli("reader-catalog", "--root", str(self.root))
        second = self.run_cli("reader-catalog", "--root", str(self.root))
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual("ready", payload["status"])
        self.assertEqual(1, len(payload["documents"]))
        document = payload["documents"][0]
        self.assertEqual("architecture", document["id"])
        self.assertEqual(0, document["index"])
        self.assertEqual(
            (self.root / "docs" / "architecture.md").stat().st_size,
            document["bytes"],
        )
        self.assertNotIn("numberedContent", document)

    def test_reader_read_batches_selected_documents_in_manifest_order(self) -> None:
        decisions = self.root / "docs" / "decisions.md"
        decisions.write_text("# Decisions\n\nKeep this indexed evidence.\n", encoding="utf-8")
        value = self.manifest()
        second = dict(value["documents"][0])
        second.update(
            {
                "id": "decisions",
                "path": "docs/decisions.md",
                "role": "decision",
                "authority": "evidence",
                "summary": "Decision evidence.",
                "appliesTo": ["docs/**"],
                "readWhen": ["decision rationale"],
            }
        )
        value["documents"].append(second)
        self.write_manifest(value)
        result = self.run_cli(
            "reader-read",
            "--root",
            str(self.root),
            "--ids",
            "decisions,architecture",
            "--max-documents",
            "2",
            "--max-bytes",
            str(PROJECT_DOCS.MAX_READER_BYTES),
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("complete", payload["status"])
        self.assertEqual(
            ["architecture", "decisions"],
            [item["id"] for item in payload["documents"]],
        )
        self.assertTrue(payload["documents"][0]["numberedContent"].startswith("1\t# Architecture"))
        self.assertIn("3\tKeep this indexed evidence.", payload["documents"][1]["numberedContent"])
        self.assertEqual(
            sum(item["bytes"] for item in payload["documents"]),
            payload["documentBytes"],
        )

    def test_reader_read_rejects_unknown_duplicate_and_over_budget_selection(self) -> None:
        self.write_manifest(self.manifest())
        cases = (
            ("missing", "selection.unknown", "4", str(PROJECT_DOCS.MAX_READER_BYTES), "unavailable"),
            ("architecture,architecture", "selection.duplicate", "4", str(PROJECT_DOCS.MAX_READER_BYTES), "unavailable"),
            ("architecture", "selection.byte-limit", "4", "1", "partial"),
        )
        for identifiers, expected, max_documents, max_bytes, status in cases:
            with self.subTest(identifiers=identifiers, expected=expected):
                result = self.run_cli(
                    "reader-read",
                    "--root",
                    str(self.root),
                    "--ids",
                    identifiers,
                    "--max-documents",
                    max_documents,
                    "--max-bytes",
                    max_bytes,
                )
                self.assertEqual(1, result.returncode)
                payload = json.loads(result.stdout)
                self.assertEqual(status, payload["status"])
                self.assertEqual([], payload["documents"])
                self.assertIn(expected, {item["code"] for item in payload["errors"]})

    def test_reader_catalog_fails_closed_on_parsed_manifest_validation_error(self) -> None:
        self.write_manifest(self.manifest(path="docs/missing.md"))
        result = self.run_cli("reader-catalog", "--root", str(self.root))
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("unavailable", payload["status"])
        self.assertEqual([], payload["documents"])
        self.assertIn("path.missing", {item["code"] for item in payload["errors"]})

    def test_reader_read_maps_post_validation_read_failure_to_partial(self) -> None:
        self.write_manifest(self.manifest())
        resolved_root = self.root.resolve()
        validation, data = PROJECT_DOCS.validate(resolved_root, "project-docs.json")
        (self.root / "docs" / "architecture.md").unlink()
        with mock.patch.object(
            PROJECT_DOCS,
            "validate",
            return_value=(validation, data),
        ):
            payload = PROJECT_DOCS.reader_read(
                resolved_root,
                "project-docs.json",
                ["architecture"],
                4,
                PROJECT_DOCS.MAX_READER_BYTES,
            )
        self.assertEqual("partial", payload["status"])
        self.assertEqual([], payload["documents"])
        self.assertEqual(0, payload["documentBytes"])
        self.assertIn("selection.read-error", {item["code"] for item in payload["errors"]})

    def test_all_three_contract_schemas_are_valid_json(self) -> None:
        references = SCRIPT.parent.parent / "references"
        schemas = sorted(references.glob("*.schema.json"))
        self.assertEqual(3, len(schemas))
        for schema in schemas:
            with self.subTest(schema=schema.name):
                value = json.loads(schema.read_text(encoding="utf-8"))
                self.assertEqual("object", value["type"])
                self.assertFalse(value["additionalProperties"])

    def test_missing_empty_duplicate_and_additional_fields_fail(self) -> None:
        missing = self.run_cli("validate", "--root", str(self.root))
        self.assertEqual(1, missing.returncode)
        self.assertEqual("manifest.missing", json.loads(missing.stdout)["errors"][0]["code"])

        self.write_manifest({"schemaVersion": 1, "documents": []})
        empty = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("documents.empty", {item["code"] for item in empty["errors"]})

        (self.root / "project-docs.json").write_text('{"schemaVersion":1,"schemaVersion":1,"documents":[]}', encoding="utf-8")
        duplicate = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertEqual("manifest.invalid-json", duplicate["errors"][0]["code"])

        value = self.manifest(extra="no")
        self.write_manifest(value)
        additional = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("document.additional-property", {item["code"] for item in additional["errors"]})

    def test_malformed_schema_enum_and_document_limit_fail(self) -> None:
        (self.root / "project-docs.json").write_text("[", encoding="utf-8")
        malformed = json.loads(
            self.run_cli("validate", "--root", str(self.root)).stdout
        )
        self.assertEqual("manifest.invalid-json", malformed["errors"][0]["code"])

        self.write_manifest(
            self.manifest(status="retired", authority="official", role="wiki")
        )
        enums = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertTrue(
            {"document.status", "document.authority", "document.role"}
            <= {item["code"] for item in enums["errors"]}
        )

        value = self.manifest()
        value["schemaVersion"] = 2
        self.write_manifest(value)
        schema = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn(
            "manifest.schema-version", {item["code"] for item in schema["errors"]}
        )

        value["schemaVersion"] = 1
        value["documents"] = [dict(value["documents"][0]) for _ in range(257)]
        self.write_manifest(value)
        limit = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("documents.too-many", {item["code"] for item in limit["errors"]})

    def test_manifest_byte_limit_and_operational_errors_are_json(self) -> None:
        (self.root / "project-docs.json").write_bytes(
            b" " * (PROJECT_DOCS.MAX_MANIFEST_BYTES + 1)
        )
        large = self.run_cli("validate", "--root", str(self.root))
        self.assertEqual(1, large.returncode)
        self.assertEqual("", large.stderr)
        self.assertEqual("manifest.too-large", json.loads(large.stdout)["errors"][0]["code"])

        missing_root = self.run_cli(
            "validate", "--root", str(self.root / "does-not-exist")
        )
        self.assertEqual(2, missing_root.returncode)
        self.assertEqual("", missing_root.stderr)
        self.assertEqual(
            "operation.failed", json.loads(missing_root.stdout)["errors"][0]["code"]
        )

    def test_identity_enum_path_glob_and_verification_failures(self) -> None:
        cases = (
            ({"id": "Bad ID"}, "document.id"),
            ({"role": "wiki"}, "document.role"),
            ({"path": "/tmp/outside.md"}, "path.invalid"),
            ({"path": "../outside.md"}, "path.invalid"),
            ({"path": "docs\\architecture.md"}, "path.invalid"),
            ({"appliesTo": ["src/[ab].py"]}, "document.glob"),
            ({"verifyWith": ["scripts/missing.sh"]}, "path.missing"),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                self.write_manifest(self.manifest(**overrides))
                result = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
                self.assertIn(expected, {item["code"] for item in result["errors"]})

    def test_duplicate_id_and_path_fail(self) -> None:
        value = self.manifest()
        value["documents"].append(dict(value["documents"][0]))
        self.write_manifest(value)
        result = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("document.id.duplicate", codes)
        self.assertIn("document.path.duplicate", codes)

    def test_symlink_and_non_utf8_document_fail(self) -> None:
        target = self.root / "docs" / "target.md"
        target.write_text("ok\n", encoding="utf-8")
        link = self.root / "docs" / "link.md"
        link.symlink_to(target)
        self.write_manifest(self.manifest(path="docs/link.md"))
        symlink = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("path.symlink", {item["code"] for item in symlink["errors"]})

        binary = self.root / "docs" / "binary.md"
        binary.write_bytes(b"\xff")
        self.write_manifest(self.manifest(path="docs/binary.md"))
        invalid = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("path.not-utf8", {item["code"] for item in invalid["errors"]})

    def test_verification_route_rejects_symlink_and_directory(self) -> None:
        outside = self.root.parent / "{}-outside-check.txt".format(self.root.name)
        outside.write_text("outside\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        route = self.root / "scripts" / "linked-check"
        route.symlink_to(outside)
        self.write_manifest(self.manifest(verifyWith=["scripts/linked-check"]))
        symlink = json.loads(self.run_cli("validate", "--root", str(self.root)).stdout)
        self.assertIn("path.symlink", {item["code"] for item in symlink["errors"]})

        route.unlink()
        (self.root / "scripts" / "check-dir").mkdir()
        self.write_manifest(self.manifest(verifyWith=["scripts/check-dir"]))
        directory = json.loads(
            self.run_cli("validate", "--root", str(self.root)).stdout
        )
        self.assertIn("path.not-file", {item["code"] for item in directory["errors"]})
        outside.unlink()

    def test_non_git_inventory_excludes_worklog_and_symlinks(self) -> None:
        (self.root / "README.md").write_text("# Root\n", encoding="utf-8")
        (self.root / ".hukuhaka").mkdir()
        (self.root / ".hukuhaka" / "work.md").write_text("# Work\n", encoding="utf-8")
        (self.root / "linked.md").symlink_to(self.root / "README.md")
        result = self.run_cli("inventory", "--root", str(self.root))
        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("filesystem", payload["source"])
        self.assertIn("README.md", {item["path"] for item in payload["documents"]})
        self.assertNotIn("linked.md", {item["path"] for item in payload["documents"]})
        self.assertIn({"path": ".hukuhaka/work.md", "reason": "worklog-owned"}, payload["excluded"])

    def test_non_git_inventory_excludes_vendor_build_and_is_stably_sorted(self) -> None:
        for directory in ("vendor", "build", "dist", "node_modules"):
            path = self.root / directory
            path.mkdir()
            (path / "ignored.md").write_text("# Ignored\n", encoding="utf-8")
        (self.root / "z-last.md").write_text("# Z\n", encoding="utf-8")
        (self.root / "a-first.md").write_text("# A\n", encoding="utf-8")

        first = self.run_cli("inventory", "--root", str(self.root))
        second = self.run_cli("inventory", "--root", str(self.root))
        self.assertEqual(first.stdout, second.stdout)
        paths = [item["path"] for item in json.loads(first.stdout)["documents"]]
        self.assertEqual(sorted(paths), paths)
        self.assertFalse(
            any(path.startswith(("vendor/", "build/", "dist/", "node_modules/")) for path in paths)
        )

    def test_git_inventory_includes_untracked_and_excludes_ignored(self) -> None:
        subprocess.run(("git", "init", "-q", str(self.root)), check=True)
        (self.root / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
        (self.root / "tracked.md").write_text("# Tracked\n", encoding="utf-8")
        (self.root / "untracked.md").write_text("# Untracked\n", encoding="utf-8")
        (self.root / "ignored.md").write_text("# Ignored\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.root), "add", "tracked.md", ".gitignore"), check=True)
        payload = json.loads(self.run_cli("inventory", "--root", str(self.root)).stdout)
        entries = {item["path"]: item for item in payload["documents"]}
        self.assertTrue(entries["tracked.md"]["tracked"])
        self.assertFalse(entries["untracked.md"]["tracked"])
        self.assertNotIn("ignored.md", entries)

    def test_audit_reports_unindexed_overlap_and_lifecycle_conflict(self) -> None:
        (self.root / "docs" / "other.md").write_text("# Other\n", encoding="utf-8")
        value = self.manifest()
        second = dict(value["documents"][0])
        second.update({"id": "old-contract", "path": "docs/other.md", "status": "historical"})
        value["documents"].append(second)
        self.write_manifest(value)
        result = self.run_cli("audit", "--root", str(self.root))
        self.assertEqual(1, result.returncode)
        codes = {item["code"] for item in json.loads(result.stdout)["findings"]}
        self.assertIn("document.lifecycle-conflict", codes)

        second["status"] = "current"
        (self.root / "notes.md").write_text("# Notes\n", encoding="utf-8")
        self.write_manifest(value)
        overlap = json.loads(self.run_cli("audit", "--root", str(self.root)).stdout)
        codes = {item["code"] for item in overlap["findings"]}
        self.assertIn("authority.overlap", codes)
        self.assertIn("document.unindexed", codes)

    def test_cli_never_writes_project_files(self) -> None:
        self.write_manifest(self.manifest())
        before = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.run_cli("inventory", "--root", str(self.root))
        self.run_cli("validate", "--root", str(self.root))
        self.run_cli("audit", "--root", str(self.root))
        self.run_cli("reader-catalog", "--root", str(self.root))
        self.run_cli(
            "reader-read",
            "--root",
            str(self.root),
            "--ids",
            "architecture",
            "--max-documents",
            "4",
            "--max-bytes",
            str(PROJECT_DOCS.MAX_READER_BYTES),
        )
        after = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
