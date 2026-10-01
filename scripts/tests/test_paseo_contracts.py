"""Exercise profile/package boundaries independently of live Paseo access."""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.tests.plugin_contracts import validate_profile, validate_repository


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("component_catalog", ROOT / "scripts/tests/check-component-catalog.py")
catalog_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_validator)


class PaseoContractsTests(unittest.TestCase):
    def test_role_authority_boundaries_remain_explicit(self):
        skill_root = ROOT / "marketplace/hukuhaka-paseo/skills/hukuhaka-paseo"
        text = (skill_root / "references/roles.md").read_text()
        blocks = {section.split("\n", 1)[0]: " ".join(section.split("\n", 1)[1].split())
                  for section in text.split("\n## ")[1:]}
        shared = blocks["Shared child rules"]
        self.assertIn("Main owns allocation, Git, Worklog", shared)
        self.assertIn("Do not create further agents unless Main explicitly authorizes it.", shared)
        self.assertNotIn("Main copies", shared)
        writer = blocks["Writer"]
        self.assertIn("Propose wording with reasons while preserving original meaning and facts.", writer)
        self.assertIn("do not edit source or final documents", writer)
        self.assertIn("Flag any possible semantic change for Main to review.", writer)
        self.assertIn("Main applies accepted wording", writer)
        self.assertNotIn("Edit only assigned outputs", writer)
        vision = blocks["Vision"]
        self.assertIn("Use available image tools", vision)
        self.assertIn("Keep the work read-only.", vision)
        self.assertNotIn("unless", vision)
        designer = blocks["Designer"]
        self.assertIn("create or edit a prototype only when assigned", designer)
        self.assertIn("Production implementation belongs to Worker.", designer)
        skill = " ".join((skill_root / "SKILL.md").read_text().split())
        self.assertIn("Include Shared child rules and the selected role rule", skill)
        self.assertIn("keep its work local within Main's capability and authority", skill)
        self.assertNotIn("use upstream provider discovery", skill)

    def test_approved_profile_defaults_and_native_registration(self):
        expected = {
            "advisor-gpt": ("codex", "gpt-6-astra", "auto-review", "high"),
            "advisor-claude": ("claude", "claude-opus-5-5", "default", "high"),
            "worker": ("codex", "gpt-6.1-sol", "auto-review", "high"),
            "scouter": ("codex", "gpt-6-luna", "auto-review", "xhigh"),
            "designer": ("claude", "claude-opus-5-5", "default", "high"),
            "writer": ("antigravity", "gemini-3.8-flash-high", "default", None),
            "vision": ("codex", "gpt-6.1-sol", "auto", "high"),
        }
        original_notes = {
            "worker": "Use for clearly scoped implementation, modification, testing, debugging, or benchmark execution after the main agent has determined the required outcome.",
            "scouter": "Use for repository, documentation, dependency, and log exploration when the main agent needs concise source-backed findings and relevant locations.",
            "designer": "Use for UI/UX, layouts, interaction flows, visual hierarchy, design critique, and interface prototypes; not general software or backend architecture.",
            "writer": "Use for meaning-preserving wording, style, readability, and redundancy improvements to existing text, returning proposals for the main agent to review.",
            "vision": "Use for analysis of existing images, screenshots, charts, diagrams, visual comparisons, and FP/FN patterns; choose designer for creating visual structure.",
        }
        paths = {path.stem: path for path in (ROOT / "templates/paseo").glob("*.json")}
        self.assertEqual(set(expected), set(paths))
        for name, values in expected.items():
            profile = json.loads(paths[name].read_text())
            if name in original_notes:
                self.assertEqual(original_notes[name], profile["notes"])
            self.assertEqual([], validate_profile(paths[name], name))
            self.assertEqual(values, tuple(profile.get(key) for key in
                                          ("provider", "model", "modeId", "thinkingOptionId")))
            self.assertEqual({"fast_mode": True} if name == "scouter" else None,
                             profile.get("featureValues"))
        self.assertNotIn("thinkingOptionId", json.loads(paths["writer"].read_text()))
        self.assertEqual([], validate_repository(ROOT))
        catalog = catalog_validator.load_catalog(ROOT)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, catalog_validator.validate(ROOT, catalog))

    def test_profile_rejects_runtime_ids_invalid_features_and_wrong_identity(self):
        profile = json.loads((ROOT / "templates/paseo/worker.json").read_text())
        invalid = (
            {**profile, "id": "00000000-0000-0000-0000-000000000000"},
            {**profile, "featureValues": {"fast_mode": "true"}},
            {**profile, "featureValues": None},
            {**profile, "name": "other"},
            {**profile, "notes": ""},
            {**profile, "notes": "00000000-0000-0000-0000-000000000000"},
            None,
            [],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "worker.json"
            for data in invalid:
                path.write_text(json.dumps(data))
                self.assertTrue(validate_profile(path, "worker"), data)

    def test_profile_host_cannot_become_a_native_plugin_or_marketplace(self):
        catalog = catalog_validator.load_catalog(ROOT)
        for kind, hosts in (("profile", {"codex": {}}), ("plugin", {"paseo": {}})):
            invalid = copy.deepcopy(catalog)
            profile = next(item for item in invalid["components"] if item["name"] == "worker")
            profile.update(kind=kind, hosts=hosts)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, catalog_validator.validate(ROOT, invalid))


if __name__ == "__main__":
    unittest.main()
