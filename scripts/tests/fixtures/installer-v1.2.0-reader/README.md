# Reader installation fixture: v1.2.0

Frozen portable installation state from private source tag `v1.2.0`, commit
`ef31046ea69bc43067d317c09ff9b94d36bc4e47`.

The agent and helper bytes are copied unchanged from that tag. Their source
paths are `agents/project-doc-reader.toml` and
`marketplace/hukuhaka-project-docs/skills/project-docs/scripts/project_docs.py`.
The receipt is reconstructed from that tag's `scripts/install/codex.py` schema-4
manifest contract: relative targets, version 1.2.0, and SHA-256 of the frozen
bytes. It owns exactly one helper. No current deployment code generates this
fixture. Copy `codex-home/` into an isolated Codex home before the operation.

Do not refresh these files from current source when resource definitions change.
The receipt hashes are the byte-integrity and provenance checks for its payload.
