from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("document_contracts.py")
SPEC = importlib.util.spec_from_file_location("document_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
document_contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(document_contracts)


class DocumentLinkTests(unittest.TestCase):
    def test_non_git_public_candidate_uses_all_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            nested = root / "marketplace" / "plugin" / "README.md"
            nested.parent.mkdir(parents=True)
            source.write_text("# Root\n", encoding="utf-8")
            nested.write_text("# Plugin\n", encoding="utf-8")

            self.assertEqual([source, nested], document_contracts.tracked_markdown(root))

    def test_reports_missing_target_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            target = root / "guide.md"
            source.write_text("[missing](none.md) [anchor](guide.md#absent)\n", encoding="utf-8")
            target.write_text("# Present\n", encoding="utf-8")
            with mock.patch.object(document_contracts, "tracked_markdown", return_value=[source, target]):
                errors = document_contracts.validate_links(root)
            self.assertTrue(any("missing link target" in error for error in errors))
            self.assertTrue(any("missing anchor" in error for error in errors))

    def test_accepts_existing_relative_target_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            target = root / "guide.md"
            source.write_text("[guide](guide.md#current-contract)\n", encoding="utf-8")
            target.write_text("## Current contract\n", encoding="utf-8")
            with mock.patch.object(document_contracts, "tracked_markdown", return_value=[source, target]):
                self.assertEqual([], document_contracts.validate_links(root))


class ProjectDocsStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {"components": [
            {"name": name, "default": False, "lifecycle": "supported"}
            for name in ("hukuhaka-project-docs", "project-doc-reader")
        ]}
        self.readme = "\n".join(
            f"| **{name}** | — | Experimental / opt-in | Codex only | Description |"
            for name in ("hukuhaka-project-docs", "Project Doc Reader")
        )

    def test_public_candidate_does_not_require_private_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            self.assertEqual([], document_contracts.validate_project_docs_status(
                Path(temp_name), self.catalog, self.readme))

    def test_both_components_must_remain_opt_in_with_native_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            for component in self.catalog["components"]:
                for field, value in (("default", True), ("lifecycle", "deprecated")):
                    with self.subTest(component=component["name"], field=field):
                        original = component[field]
                        component[field] = value
                        errors = document_contracts.validate_project_docs_status(
                            Path(temp_name), self.catalog, self.readme)
                        self.assertTrue(any(component["name"] in error for error in errors))
                        component[field] = original

    def test_supported_only_readme_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            errors = document_contracts.validate_project_docs_status(
                Path(temp_name), self.catalog,
                self.readme.replace("Experimental / opt-in", "Supported"))
            self.assertEqual(2, len(errors))

    def test_stale_private_pilot_verdict_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            path = root / "docs/hukuhaka-project-docs/README.md"
            path.parent.mkdir(parents=True)
            path.write_text("Experimental / opt-in; human quality verdict pending\n", encoding="utf-8")
            errors = document_contracts.validate_project_docs_status(root, self.catalog, self.readme)
            self.assertTrue(any("pilot verdict is stale" in error for error in errors))
            path.write_text("Experimental / opt-in; pilot closed\n", encoding="utf-8")
            self.assertEqual([], document_contracts.validate_project_docs_status(root, self.catalog, self.readme))

    def test_current_product_contracts_are_included(self) -> None:
        for relative in (
            "AGENTS.md",
            "docs/README.md",
            "docs/host-support.md",
            "docs/hukuhaka-project-docs/README.md",
            "docs/hukuhaka-project-docs/implementation-plan.md",
            "docs/hukuhaka-project-docs/decisions.md",
            "docs/hukuhaka-report-planner/README.md",
            "docs/hukuhaka-report-planner/craft-sources.md",
            "docs/plugin-guide/README.md",
            "docs/plugin-guide/agents-and-hooks.md",
            "docs/plugin-guide/automation-and-loops.md",
            "docs/plugin-guide/codex.md",
            "docs/plugin-guide/distribution.md",
            "docs/plugin-guide/headless-and-automation.md",
            "docs/plugin-guide/plugins.md",
            "docs/plugin-guide/skill-design.md",
            "docs/plugin-guide/skills.md",
            "docs/plugin-guide/team-coordination.md",
            "docs/scripts/README.md",
        ):
            self.assertIn(relative, document_contracts.CURRENT_DOCS)

    def test_public_candidate_does_not_require_private_root_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            required = document_contracts.required_current_docs(Path(temp_name))
            self.assertNotIn("AGENTS.md", required)

    def test_private_checkout_requires_root_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            release_tool = root / "scripts" / "release" / "main.py"
            release_tool.parent.mkdir(parents=True)
            release_tool.write_text("# private release tool\n", encoding="utf-8")
            self.assertIn("AGENTS.md", document_contracts.required_current_docs(root))


class CodexOnlyDocumentTests(unittest.TestCase):
    def test_retired_root_and_private_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "CLAUDE.md").write_text("retired host", encoding="utf-8")
            (root / "docs" / "hukuhaka-codex").mkdir(parents=True)
            self.assertEqual(
                2,
                len(document_contracts.validate_codex_only_docs(root)),
            )

    def test_active_docs_reject_retired_host_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            path = root / "README.md"
            path.write_text("Codex and Claude Code", encoding="utf-8")
            self.assertTrue(
                any("retired host reference" in error
                    for error in document_contracts.validate_codex_only_docs(root))
            )


if __name__ == "__main__":
    unittest.main()
