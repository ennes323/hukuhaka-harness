# Existing plan compatibility

Read when an existing plan is continued or handed to a designer. This is the
compatibility authority for both skills; no existing file is silently migrated.

## Classify before writing

| Existing input | Meaning | Permitted behavior |
|---|---|---|
| `plan-format: content-v1`, `plan-state: finalized`, complete content blocks | New content plan | Designer may create design.md; absence of design is normal |
| content-v1 without finalized state or with missing required fields | Incomplete new plan | Return the missing planning input; do not build |
| Unmarked spec with Anchors, Design Direction, and Build Contract | Legacy combined plan | Keep the whole spec read-only; build from its original direction and return a receipt |
| Unmarked split spec with a matching sibling design.md | Legacy paired plan | Preserve spec and planned design; only Realization is designer-mutable outside read-only legacy paths |
| Unmarked split spec without design.md | Incomplete legacy pair | Report the missing design path and stop; do not reinterpret it as content-v1 |
| Unknown marker or unrecognizable contract | Unsupported input | Report the ambiguity and stop without mutation |

A marker is not sufficient proof of completeness. Resolve source/unit/test references
and verify the actual content before accepting a new plan.

For content-v1, an existing design may be revised only when it belongs to the same
spec and request. Never overwrite an unrelated design or artifact. Read
`../../artifact-designer/references/design-schema.md` relative to this file before
deciding whether the document is designer-owned.

## Locations and revisions

- Prefer .hukuhaka/reports/; if no matching plan exists there, .claude/reports/ is a
  read-only legacy fallback. Legacy paths are read-only.
- Never dual-write a plan to both locations. A build from a legacy-path pair returns
  realization in the receipt without mutating that read-only path.
- Build existing plans under their original contract. An explicit request to revise
  their planning meaning creates a new content-v1 revision under .hukuhaka/reports/,
  with a distinct destination that preserves the original files and source boundaries.
- Never auto-load a project-level uppercase `DESIGN.md` or treat its filename as a
  visual authority. Explicit user requirements still pass through as user constraints.

## Legacy bundled references

Design references now live under skills/artifact-designer/references/.
The designer may resolve a recorded bundled `references/craft/<name>.md` or
`references/directions.md` against its own reference directory. This only resolves
known bundled paths; it does not authorize arbitrary archived absolute paths.
Preserve the legacy plan's meaning and selected mechanisms. Report a missing or
incompatible reference instead of silently selecting a different design direction.
