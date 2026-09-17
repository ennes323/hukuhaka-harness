# Assess documentation impact

Determine which explanations or contracts a concrete change affects and keep
them accurate within the authorized scope. A matching path is a candidate for
review, not proof that a document needs editing.

## Connect changes to claims

Use the proposed behavior or actual diff to identify changes to public behavior,
interfaces, configuration, operations, ownership, and verification. Preserve
the distinction between a proposal and an implemented change. If the change
is too vague to assess, resolve its intended behavior before making an impact
claim.

Locate relevant originals through repository entry points and targeted search;
use a valid `project-docs.json` as an optional hint. Include unindexed documents
when evidence connects them to the change. Read [context](context.md) if the
governing requirements are not yet understood. An absent or stale index does
not block the review or authorize its repair.

Compare the affected claims with current source, configuration, tests, and
the intended contract. Explain which statement must change and why, or why
the existing explanation remains accurate. Do not rewrite a normative contract
merely to conceal an implementation mismatch. Historical decisions and evidence
remain history; record a new decision or update the current entry point instead
of rewriting the old outcome.

## Carry through the authorized outcome

```text
IF the request is an impact review or asks for a proposal first:
    Return evidence-backed findings and concrete suggested changes.
IF documentation updates are within the authorized implementation scope:
    Update the affected originals, preserving unrelated content and edits.
    Verify the changed claims and relevant links or examples.
IF a finding requires a new product decision or broader authority:
    Present the concrete choice and complete independent authorized work.
```

Do not manufacture documentation changes for behavior-preserving edits when
the existing text remains accurate. Likewise, an unchanged interface does not
prove there is no impact on operational or verification guidance.

When an authorized update also changes indexed paths or lifecycle metadata,
use [maintenance](maintenance.md) for the affected index entries. A retained
Reader may assist a bounded review through [its own contract](reader.md), but
is not a prerequisite and cannot authorize an edit.

## Completion

Account for materially affected current documentation: updated and checked,
reviewed with no change needed, or unresolved with a reason and next action.
Cite the changed behavior and the document claims behind that conclusion.
Report the inspected scope rather than claiming repository-wide completeness
from a path match or limited search. Failed checks and inaccessible evidence
remain explicit acceptance gaps.
