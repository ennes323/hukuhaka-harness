# Find project context

Find enough current documentation to ground the task's decisions, then connect
its requirements to the relevant source, configuration, or tests. The outcome
is usable constraints and verification guidance, not a separate summary of
every document.

## Locate and inspect originals

Start from applicable repository instructions, README and documentation entry
points, and the paths or symbols involved in the task. Search where those
routes leave a material question unanswered. Read current governing documents
before using drafts or history to resolve an ambiguity.

```text
IF project-docs.json exists:
    Use valid entries as navigation hints and check the relevant originals.
    Treat stale paths, labels, or missing coverage as index limitations.
IF the index is absent or unusable:
    Continue through repository entry points and targeted search.
    Do not create an index or require setup just to answer the task.
WHEN a material question remains unanswered:
    Follow relevant links or search additional documents, including unindexed ones.
```

The bundled validator described in [maintenance](maintenance.md#deterministic-helper)
can diagnose an index when needed. An invalid index is not usable evidence;
independent original-document inspection can still proceed. Report a material
index defect without turning discovery into an unsolicited repair task.

Direct reading is the default. Use [the optional Reader](reader.md) only when
an installed specialist and a valid index make a bounded assignment useful,
or when the user explicitly requests it. Its response does not replace the
original evidence needed to make the task's decisions.

## Apply the evidence

For each material decision, distinguish what the governing document requires
from what source or runtime evidence demonstrates. A mismatch may be a bug,
an outdated document, or an unresolved design decision; do not silently change
the requirement to match implementation. Identify the owner or evidence that
can settle a consequential conflict.

Reuse inspected material while the relevant inputs remain unchanged. Choose
searches and read batches to answer the task, without a fixed number of reads
or an exhaustive repository scan.

## Completion

Context is sufficient when the task's material questions have source-backed
answers, applicable constraints and checks are identified, and any uncertainty
that can change the decision is explicit. Report the relevant original
locations and their implications in the surrounding workflow. If evidence is
missing or inaccessible, name the unanswered question and how to resolve it;
do not infer that no constraint exists.
