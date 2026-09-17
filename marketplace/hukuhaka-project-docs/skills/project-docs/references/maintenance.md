# Maintain the optional index

Keep root `project-docs.json` useful as navigation to repository-owned
documents. It records identity, location, lifecycle, authority labels, and
selection hints; it does not contain authoritative behavior or replace the
documents. Read [the schema](project-docs.schema.json) when creating or
diagnosing fields. Keep `schemaVersion: 1` and preserve valid unrelated entries.

## Deterministic helper

Resolve `scripts/project_docs.py` relative to the Skill directory and invoke it
with the host Python interpreter. The helper is read-only and emits JSON.

```text
<python> <script> inventory --root <project-root>
<python> <script> validate --root <project-root> [--manifest project-docs.json]
<python> <script> audit --root <project-root> [--manifest project-docs.json]
```

Exit `0` is clean, `1` is a completed validation or audit with findings, and
`2` is an invocation or I/O failure. Report stable error codes and locations;
do not reinterpret an invalid manifest as valid. Validation checks structure
and paths, not document accuracy or implementation compliance. The helper's
inventory is a candidate list, not a claim that every document belongs in the
index.

## Maintenance outcomes

- **Bootstrap:** Inventory documents and inspect the candidates needed to
  classify them. Distinguish observed metadata from inference, resolve material
  authority choices, and construct a complete schema-valid index.
- **Validate:** Run the validator and report its findings without changing files.
- **Audit:** Run the audit; distinguish structural errors, unindexed documents,
  duplicate current normative coverage, and lifecycle conflicts. Inspect
  originals when interpreting those findings. Audit alone does not repair them.
- **Sync:** Validate and inventory, then reconcile affected entries with the
  relevant repository changes. Explain additions, changes, retained entries,
  and removals. Do not remove an entry merely because its path is stale when
  the document may have moved or its lifecycle remains unclear.

## Apply and verify

```text
IF the user requested a proposal or analysis only:
    Return the proposed manifest or precise delta and unresolved choices.
IF creating or updating the index is authorized:
    Reconcile with the latest file and preserve unrelated entries and edits.
    Write the smallest complete change, then validate the resulting index.
IF authority or lifecycle cannot be established:
    Keep that uncertainty explicit; do not invent metadata to obtain a pass.
```

Index maintenance does not authorize document-content rewrites. When those
are also in scope, follow [impact](impact.md) for the affected originals. Never
execute `verifyWith` values automatically or change schema/path checks to make
a failing index pass. A failed write or validation leaves the maintenance
outcome incomplete; report the exact remaining issue and preserve user work.
