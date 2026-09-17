# Optional indexed Reader

Use this reference only when delegating a bounded `context` or `impact` lookup
to an installed `project-doc-reader`. Direct discovery and impact review do not
require this agent. The retained Reader is read-only, requires a valid root
`project-docs.json`, and uses the JSON v2 handoff below. Its model remains Luna
xhigh. Manifest format and catalog/read helper output remain version 1.

```text
IF the Reader is unavailable or its index is invalid:
    Report the requested delegation as unavailable.
    Continue direct inspection where it can satisfy the user's request.
    Do not invent a Reader response or silently replace an explicitly required delegation.
WHEN using the Reader:
    Confirm the root manifest has schemaVersion 1 and a documents array.
    Build a v2 request with a requestId and one stable ID per question.
    Validate the raw request with reader-validate-request before dispatch.
    If invalid: correct the caller's request; do not spawn the Reader.
    Send the exact validated object with fork_turns="none".
    Let the Reader's catalog perform full path and lifecycle validation.
    Strictly parse its one returned JSON object; preserve the raw response.
    Validate {request: original request, response: parsed response} with
        reader-validate-response before accepting any Reader claims.
    If invalid: reject the handoff and report the validation errors.
    Do not silently repair fields, citations, limits, or answer IDs.
```

Read [the request schema](reader-request-v2.schema.json),
[the response schema](reader-response-v2.schema.json), and
[the protocol guide](reader-protocol.md) for this handoff. Supply the
absolute repository root, faithful task, known paths and symbols, concrete
questions, and a budget within the schema's 32-document and 1 MiB limits.
Reuse a still-applicable response instead of delegating the same question again.

A `complete` response completes the bounded Reader assignment, not source
verification or repository-wide coverage. Inspect the relevant originals and
current implementation to ground the primary workflow's material conclusions.
For `partial`, retain unknown answers, errors, exclusions, and truncation as gaps;
resolve them by direct inspection when possible. For `unavailable`, make no
Reader-derived claim. Reader recommendations never authorize changes.

The Reader starts one `reader-session` helper, then sends selected IDs as JSON
to that same process. The process retains root and budget and performs one
batched read. No second shell command or helper path is constructed. Empty-input
polls may retrieve pending output but cannot create another read. These transport
rules and structured `{path, line}` citations belong to the bounded assignment;
they do not constrain the primary workflow's independent discovery.

This is a breaking wire change: update the caller and Reader together when
installing. The unversioned `reader-request.schema.json` and
`reader-response.schema.json` files retain v1 for historical evidence; the
current Reader rejects v1 requests. Old evaluation packets are not v2 evidence.
