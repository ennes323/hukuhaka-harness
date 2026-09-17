from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "marketplace" / "hukuhaka-project-docs" / "skills" / "project-docs" / "scripts" / "reader_protocol.py"
SPEC = importlib.util.spec_from_file_location("reader_protocol", MODULE_PATH)
assert SPEC and SPEC.loader
PROTOCOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROTOCOL)


class ReaderProtocolTests(unittest.TestCase):
    def request(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schemaVersion": 2,
            "requestId": "request-1",
            "mode": "context",
            "root": "/tmp/project",
            "task": "Inspect the runtime contract.",
            "action": "inspect",
            "paths": ["src/runtime.py", "odd:name.md"],
            "symbols": ["Runtime.start"],
            "questions": [
                {"id": "q1", "question": "What owns startup?"},
                {"id": "q2", "question": "What remains unknown?"},
            ],
            "budget": {"maxDocuments": 4, "maxBytes": 4096},
        }
        value.update(overrides)
        return value

    def selected(self) -> dict[str, object]:
        return {
            "id": "runtime",
            "path": "docs/runtime.md",
            "reason": "Defines startup.",
            "role": "contract",
            "status": "current",
            "authority": "normative",
            "bytes": 200,
        }

    def context_response(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schemaVersion": 2,
            "requestId": "request-1",
            "mode": "context",
            "root": "/tmp/project",
            "status": "partial",
            "manifest": "project-docs.json",
            "selectedDocuments": [self.selected()],
            "excludedDocuments": [],
            "answers": [
                {
                    "questionId": "q1",
                    "status": "answered",
                    "answer": "The runtime contract owns startup.",
                    "sources": [{"path": "docs/runtime.md", "line": 3}],
                    "reason": "",
                },
                {
                    "questionId": "q2",
                    "status": "unknown",
                    "answer": "",
                    "sources": [],
                    "reason": "No selected document answers it.",
                },
            ],
            "conflicts": [],
            "requiredChecks": [
                {
                    "route": "scripts/check.sh",
                    "documentId": "runtime",
                    "basis": "content",
                    "sources": [{"path": "docs/runtime.md", "line": 8}],
                }
            ],
            "budgetUsed": {
                "manifestBytes": 100,
                "documentBytes": 200,
                "documents": 1,
                "maxDocuments": 4,
                "maxBytes": 4096,
                "truncated": False,
            },
            "errors": [],
        }
        value.update(overrides)
        return value

    def test_strict_json_rejects_duplicate_nonfinite_and_trailing_text(self) -> None:
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '{} trailing'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                PROTOCOL.parse_json(text)
        self.assertEqual({"x": 1}, PROTOCOL.parse_json('{"x":1}'))

    def test_request_accepts_nonexistent_canonical_paths_and_colons(self) -> None:
        self.assertEqual([], PROTOCOL.validate_request(self.request()))
        invalid_paths = self.request(
            paths=["/absolute", "a\\b", "a/../b", "a//b", "a/./b", "bad\x00path"],
        )
        errors = PROTOCOL.validate_request(invalid_paths)
        self.assertGreaterEqual(len([item for item in errors if item["code"] == "request.path"]), 6)

        invalid_shape = self.request(requestId="  ")
        self.assertIn(
            "schema.pattern",
            {item["code"] for item in PROTOCOL.validate_request(invalid_shape)},
        )
        duplicate_questions = self.request(
            questions=[
                {"id": "same", "question": "One"},
                {"id": "same", "question": "Two"},
            ],
        )
        errors = PROTOCOL.validate_request(duplicate_questions)
        self.assertIn("protocol.duplicate", {item["code"] for item in errors})

    def test_structural_errors_return_without_semantic_type_crashes(self) -> None:
        bad_request = self.request(questions=[{"id": [], "question": "Bad"}])
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_request(bad_request)})

        decimal_integer = self.request(budget={"maxDocuments": 1.0, "maxBytes": 4096})
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_request(decimal_integer)})
        float_version = self.request(schemaVersion=2.0)
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_request(float_version)})
        bool_limit = self.request(budget={"maxDocuments": True, "maxBytes": 4096})
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_request(bool_limit)})

        bad_selected = self.context_response()
        bad_selected["selectedDocuments"][0]["id"] = []
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_response(bad_selected)})

        bad_answers = self.context_response(answers=None)
        self.assertIn("schema.type", {item["code"] for item in PROTOCOL.validate_response(bad_answers)})

    def test_context_response_correlates_questions_sources_and_budget(self) -> None:
        response = self.context_response()
        self.assertEqual([], PROTOCOL.validate_response(response, self.request()))

        response["answers"] = list(reversed(response["answers"]))
        response["answers"][1]["sources"] = [{"path": "docs/not-selected.md", "line": 1}]
        response["budgetUsed"] = dict(response["budgetUsed"], documentBytes=199, documents=2)
        errors = PROTOCOL.validate_response(response, self.request())
        codes = {item["code"] for item in errors}
        self.assertIn("response.questions", codes)
        self.assertIn("response.source-selection", codes)
        self.assertIn("response.budget", codes)

    def test_required_checks_distinguish_manifest_metadata_from_content(self) -> None:
        metadata = self.context_response()
        metadata["excludedDocuments"] = [
            {"id": "operations", "path": "docs/operations.md", "reason": "not-relevant"}
        ]
        metadata["requiredChecks"] = [{
            "route": "scripts/operations-check.sh",
            "documentId": "operations",
            "basis": "metadata",
            "sources": [],
        }]
        self.assertEqual([], PROTOCOL.validate_response(metadata, self.request()))

        invalid = self.context_response()
        invalid["requiredChecks"] = [
            {
                "route": "scripts/unknown.sh",
                "documentId": "unknown",
                "basis": "metadata",
                "sources": [],
            },
            {
                "route": "scripts/metadata.sh",
                "documentId": "runtime",
                "basis": "metadata",
                "sources": [{"path": "docs/runtime.md", "line": 8}],
            },
            {
                "route": "scripts/content.sh",
                "documentId": "runtime",
                "basis": "content",
                "sources": [],
            },
        ]
        codes = {item["code"] for item in PROTOCOL.validate_response(invalid)}
        self.assertTrue({"response.check-identity", "response.check-basis"} <= codes)

    def test_answer_and_status_state_machine_is_enforced(self) -> None:
        response = self.context_response(status="complete")
        response["answers"][0]["reason"] = "extra"
        response["answers"][1].update(answer="guess", sources=[{"path": "docs/runtime.md", "line": 4}], reason="")
        response["errors"] = [{"code": "read.failed", "path": "docs/runtime.md", "message": "failed"}]
        codes = {item["code"] for item in PROTOCOL.validate_response(response, self.request())}
        self.assertIn("response.answer", codes)
        self.assertIn("response.status", codes)

        complete = self.context_response(status="complete")
        complete["answers"][1] = {
            "questionId": "q2",
            "status": "answered",
            "answer": "Nothing remains unknown.",
            "sources": [{"path": "docs/runtime.md", "line": 9}],
            "reason": "",
        }
        self.assertEqual([], PROTOCOL.validate_response(complete, self.request()))

    def test_selection_read_or_byte_failure_cannot_retain_content_claims(self) -> None:
        valid = self.context_response(
            status="partial",
            selectedDocuments=[],
            excludedDocuments=[
                {"id": "runtime", "path": "docs/runtime.md", "reason": "read-error"}
            ],
            answers=[
                {"questionId": "q1", "status": "unknown", "answer": "", "sources": [], "reason": "Read failed."},
                {"questionId": "q2", "status": "unknown", "answer": "", "sources": [], "reason": "Read failed."},
            ],
            requiredChecks=[],
            conflicts=[],
            errors=[{"code": "selection.read-error", "path": "docs/runtime.md", "message": "read failed"}],
            budgetUsed={
                "manifestBytes": 100,
                "documentBytes": 0,
                "documents": 0,
                "maxDocuments": 4,
                "maxBytes": 4096,
                "truncated": True,
            },
        )
        self.assertEqual([], PROTOCOL.validate_response(valid, self.request()))

        malicious = self.context_response()
        malicious["budgetUsed"]["truncated"] = True
        malicious["errors"] = [
            {"code": "selection.byte-limit", "path": "docs/runtime.md", "message": "over limit"}
        ]
        malicious["conflicts"] = [{
            "statement": "Retained content.",
            "sources": [
                {"path": "docs/runtime.md", "line": 2},
                {"path": "docs/runtime.md", "line": 3},
            ],
        }]
        self.assertIn(
            "response.selection-failure",
            {item["code"] for item in PROTOCOL.validate_response(malicious, self.request())},
        )

    def test_impact_identity_and_content_metadata_basis(self) -> None:
        request = self.request(mode="impact", questions=[{"id": "q1", "question": "What changes?"}])
        response = self.context_response(mode="impact")
        response.pop("requiredChecks")
        response["answers"] = [response["answers"][0]]
        response["affectedDocuments"] = [
            {
                "id": "runtime",
                "path": "docs/runtime.md",
                "reason": "Startup changes.",
                "requiredAction": "review",
                "verification": ["scripts/check.sh"],
                "basis": "content",
                "sources": [{"path": "docs/runtime.md", "line": 3}],
            }
        ]
        response["status"] = "complete"
        self.assertEqual([], PROTOCOL.validate_response(response, request))

        response["affectedDocuments"][0].update(id="other", basis="metadata")
        errors = PROTOCOL.validate_response(response, request)
        self.assertTrue(
            {"response.affected-identity", "response.affected-basis"}
            <= {item["code"] for item in errors}
        )

        response["affectedDocuments"].append(dict(response["affectedDocuments"][0]))
        self.assertIn(
            "protocol.duplicate",
            {item["code"] for item in PROTOCOL.validate_response(response, request)},
        )

        malformed = self.context_response(mode="impact")
        malformed.pop("requiredChecks")
        malformed["answers"] = [malformed["answers"][0]]
        malformed["affectedDocuments"] = [{
            "id": "Bad_ID",
            "path": "docs/runtime.md",
            "reason": "Bad catalog identity.",
            "requiredAction": "review",
            "verification": ["   "],
            "basis": "metadata",
            "sources": [],
        }]
        self.assertIn(
            "schema.pattern",
            {item["code"] for item in PROTOCOL.validate_response(malformed)},
        )

    def test_limits_disjoint_documents_and_manifest_only_exception(self) -> None:
        response = self.context_response()
        response["excludedDocuments"] = [
            {"id": "runtime", "path": "docs/other.md", "reason": "not-relevant"},
            {"id": "other", "path": "docs/runtime.md", "reason": "byte-limit"},
        ]
        response["budgetUsed"].update(maxDocuments=1, maxBytes=250)
        codes = {item["code"] for item in PROTOCOL.validate_response(response)}
        self.assertIn("response.document-overlap", codes)
        self.assertIn("response.budget", codes)

        unavailable = {
            "schemaVersion": 2,
            "requestId": None,
            "mode": None,
            "root": None,
            "status": "unavailable",
            "manifest": "project-docs.json",
            "selectedDocuments": [],
            "excludedDocuments": [],
            "answers": [],
            "conflicts": [],
            "budgetUsed": {
                "manifestBytes": 500,
                "documentBytes": 0,
                "documents": 0,
                "maxDocuments": None,
                "maxBytes": 100,
                "truncated": True,
            },
            "errors": [{"code": "request.invalid", "path": "$", "message": "invalid request"}],
        }
        self.assertEqual([], PROTOCOL.validate_response(unavailable))

        limited = self.context_response(status="complete")
        limited["answers"][1] = {
            "questionId": "q2",
            "status": "answered",
            "answer": "Known.",
            "sources": [{"path": "docs/runtime.md", "line": 9}],
            "reason": "",
        }
        limited["excludedDocuments"] = [
            {"id": "other", "path": "docs/other.md", "reason": "document-limit"}
        ]
        limited_codes = {item["code"] for item in PROTOCOL.validate_response(limited)}
        self.assertTrue({"response.status", "response.budget"} <= limited_codes)

    def test_invalid_request_requires_safe_unavailable_envelope(self) -> None:
        request = self.request(requestId=" ", root="relative", mode="wrong", budget={"maxDocuments": 0, "maxBytes": 4096})
        response = {
            "schemaVersion": 2,
            "requestId": None,
            "mode": None,
            "root": None,
            "status": "unavailable",
            "manifest": "project-docs.json",
            "selectedDocuments": [],
            "excludedDocuments": [],
            "answers": [],
            "conflicts": [],
            "budgetUsed": {
                "manifestBytes": 0,
                "documentBytes": 0,
                "documents": 0,
                "maxDocuments": None,
                "maxBytes": 4096,
                "truncated": False,
            },
            "errors": [{"code": "request.invalid", "path": "$", "message": "invalid request"}],
        }
        self.assertEqual([], PROTOCOL.validate_response(response, request))
        response["requestId"] = "invented"
        self.assertIn("response.echo", {item["code"] for item in PROTOCOL.validate_response(response, request)})

    def test_nonobject_invalid_request_accepts_only_empty_unavailable_envelope(self) -> None:
        response = {
            "schemaVersion": 2,
            "requestId": None,
            "mode": None,
            "root": None,
            "status": "unavailable",
            "manifest": "project-docs.json",
            "selectedDocuments": [],
            "excludedDocuments": [],
            "answers": [],
            "conflicts": [],
            "budgetUsed": {
                "manifestBytes": 0,
                "documentBytes": 0,
                "documents": 0,
                "maxDocuments": None,
                "maxBytes": None,
                "truncated": False,
            },
            "errors": [{"code": "request.invalid", "path": "$", "message": "invalid request"}],
        }
        for request in (None, [], "bad"):
            with self.subTest(request=request):
                self.assertEqual([], PROTOCOL.validate_response(response, request=request))
        self.assertEqual([], PROTOCOL.validate_response(response))

        response["excludedDocuments"] = [
            {"id": "invented", "path": "docs/invented.md", "reason": "not-relevant"}
        ]
        self.assertIn(
            "response.request",
            {item["code"] for item in PROTOCOL.validate_response(response, request=None)},
        )

    def test_schema_rejects_extra_fields_and_mode_extras(self) -> None:
        response = self.context_response(extra="no")
        response["affectedDocuments"] = []
        errors = PROTOCOL.validate_response(response)
        self.assertIn("schema.additional-property", {item["code"] for item in errors})

        response.pop("extra")
        errors = PROTOCOL.validate_response(response)
        self.assertIn("response.mode", {item["code"] for item in errors})


if __name__ == "__main__":
    unittest.main()
