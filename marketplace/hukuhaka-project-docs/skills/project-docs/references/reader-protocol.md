# Reader JSON v2 protocol

The caller owns request validation and acceptance. The Reader owns bounded
manifest selection and sourced interpretation. The manifest and catalog/read
helper keep schemaVersion 1; only the request/response wire uses version 2.

## Caller validation

The Skill's `scripts/project_docs.py` provides two stdin commands. A standalone
Reader installation provides the same commands through
`agents/project-doc-reader-tool.py`. No repository root is needed and these
commands do not inspect documents, execute routes, or modify files.

```sh
python3 <skill>/scripts/project_docs.py reader-validate-request < request.json
python3 <skill>/scripts/project_docs.py reader-validate-response < pair.json
```

Pass JSON through stdin or a file using structured tooling. Never interpolate
raw JSON, root paths, question text, or document text into a shell command.
`pair.json` contains exactly `{"request": <original>, "response": <returned>}`.
Strictly parse the raw returned object before constructing this pair; otherwise
an ordinary parser could discard duplicate keys before validation sees them.
The shared Python module provides `parse_json`, `validate_request`, and
`validate_response(response, request=original)` for consumers that already
hold the raw reply. Preserve raw text alongside accepted parsed data.

Both commands return `{schemaVersion: 2, command, status, errors}`. Exit 0 means
valid, 1 means invalid wire data, and 2 means the validator could not run.
Error entries have `code`, `path`, and `message`. The schemas own object shapes;
the stdlib validator implements their supported keyword subset and adds
cross-field invariants. It is not a general JSON Schema engine.
Wire integers use JSON integer tokens, without a fractional or exponent form;
booleans never count as integers. This is stricter than JSON Schema's numeric
equivalence for values such as `2.0`.

## Deterministic session transport

The Reader starts the installed helper once with `reader-session --root .
--max-documents <limit> --max-bytes <limit>`. The structured `exec_command`
argument sets `workdir` to the exact request root, `tty` to true, and
`yield_time_ms` to 1000. Return the whole tool result so its `session_id` remains
available; printing only stdout loses the continuation handle.

The process emits the existing `reader-catalog` JSON and keeps the validated
root, manifest path, and budgets in memory. The Reader sends only one JSON object,
`{"ids": ["chosen-document-id"]}`, followed by a newline to `write_stdin` using
that session ID. The process validates the selection and calls `reader_read`
directly. Its final output is the existing `reader-read` JSON, and it exits.
There is no second command or helper path for the model to reconstruct. No PATH
entry, shell alias, persistent state file, or additional installed resource is
needed. The original catalog/read CLI commands remain available for compatibility.

Selection accepts only unique catalog IDs. Extra root, budget, command, or other
fields are rejected. Input is bounded to 1 MiB and one newline-terminated frame,
with a 180-second deadline. EOF, malformed input, and timeout return unavailable
with `session.eof`, `session.invalid-selection`, or `session.timeout` errors.
The helper uses the existing path/budget/read checks, including revalidation
before reading. All state disappears when the process exits. The POSIX pipe/PTY
transport temporarily disables echo and canonical line buffering on its own
terminal and restores the original settings on exit.

An empty ID array closes the process without reading documents; its read envelope
is complete with zero documents and no errors. The final Reader response still
marks unanswered questions unknown and its bounded task partial. Invalid catalog
or manifest-only budget overflow exits immediately after the catalog and awaits
no input. Empty-input polling may retrieve pending output from the same process;
it never submits another selection. Missing/expired sessions are reported as
unavailable rather than causing a replacement process or shell retry.

## Example request

This is illustrative input, not an observed model result:

```json
{
  "schemaVersion": 2,
  "requestId": "listener-context-1",
  "mode": "context",
  "root": "/workspace/project",
  "task": "Identify the current listener-port constraint.",
  "action": "inspect",
  "paths": ["src/service.py"],
  "symbols": ["listener_port"],
  "questions": [
    {"id": "port", "question": "Which port is required and why?"}
  ],
  "budget": {"maxDocuments": 4, "maxBytes": 65536}
}
```

An answer uses the same `questionId`, with a source such as
`{"path": "docs/contract.md", "line": 3}`. Multiple supporting locations are
separate array entries. An unresolved answer has status `unknown`, answer `""`,
sources `[]`, and a concrete nonblank `reason`; do not omit the question.

## States and evidence

| Situation | Response and evidence |
|---|---|
| All questions answered within budget | `complete`, no errors, no truncation |
| Unanswered question or necessary document omitted | `partial`, unknown answer and/or truncation |
| Manifest alone exceeds byte limit | `partial`, measured manifest bytes, no selected documents, truncation and error |
| Batched read fails after catalog | `partial`, helper errors, no selected documents or content claims; planned reads are not evidence |
| Invalid request, unusable root, or unavailable catalog | `unavailable`, errors, no factual claims |

The helper's `selection.read-error` and `selection.byte-limit` errors require
partial status, truncation, unknown answers, and empty selected, conflict,
required-check, and affected-document arrays. Do not retain metadata conclusions
from that failed selection as accepted results. Budget/read exclusions also
require truncation and partial status, except during an unavailable lookup.

For an invalid request, echo individually valid requestId, mode, root, and
limits; otherwise use null. Answers are empty. For a valid request whose lookup
is unavailable, echo its values and return one unknown answer per question.
Unknown mode has no mode-specific fields. Context requires `requiredChecks`;
impact requires `affectedDocuments` and omits `requiredChecks`.

The validator checks strict JSON, shapes, answer coverage, exact correlation,
selection identity, source membership, budget arithmetic, and state consistency.
An impact item with `basis: "metadata"` has no content sources and must describe
its reason as an inference. Content-based impacts require read-document sources.
Complete answers can still report conflicting source statements without deciding
which authority wins.

Each required check has `route`, `documentId`, `basis`, and `sources`. Its
document ID joins a selected or excluded catalog entry. A route found only in
that entry's `verifyWith` uses metadata basis and empty sources; a route supported
by read content uses content basis and selected-document sources. The caller
checks metadata routes against catalog output, rather than accepting an invented
document line citation.

Validation does not prove that files were actually read, a line supports a
claim, the catalog is exhaustive for the task, or the allowed tool trace was
followed. The primary checks these against helper output and current originals
before relying on material conclusions. The response is advisory and never
authorizes edits or verifies a command's outcome.

## Compatibility

The current role accepts only v2. Install its helper, validator, schemas, and
caller guidance as one component update. Retain v1 schemas and old eval packets
unchanged; their results describe the old contract. No automatic v1 conversion
can supply missing request/question IDs or reconstruct structured evidence.
