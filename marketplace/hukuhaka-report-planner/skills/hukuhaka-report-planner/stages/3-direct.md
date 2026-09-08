---
stage: 3
purpose: complete the editorial brief without directing visual construction
prereq: verified Evidence and ordered Structure in the draft spec
deliverable: source-resolvable content, priorities, exclusions, and necessary qualifications
---

## Brief the content

Read the draft spec and `references/spec-schema.md` relative to the planner skill
root. This stage replaces visual direction with editorial preparation.

1. Check each unit's required content against its sources. State the relationship the
   reader must grasp and its relative importance, not a form or layout for showing it.
2. Make evidence locatable. For a required code excerpt, name its path and symbol and
   a current source range when it is needed to identify the decisive implementation.
   Require only the decisive excerpt needed for the reader's question. Other source
   locators remain evidence references, not a requirement to quote every related function.
   When the request asks for a decisive implementation excerpt, select that implementation;
   do not turn it into an anthology of schema, backend, frontend, and test code. Require
   another quotation only when it answers a distinct question the selected excerpt cannot.
   Do not prescribe panel geometry, highlighting, or excerpt styling.
3. Put each necessary qualification next to the content it qualifies in the brief.
   Avoid assigning the same explanation to multiple units without a distinct reader need.
4. Preserve explicit user presentation constraints separately from content requirements.
   A user's requested table remains a requirement; a planner's preferred table does not.
5. Review the plan as an editorial handoff: can a designer identify what must be
   communicated, what evidence supports it, and what cannot be claimed?
   Return to Structure if an evidence or content contradiction remains.
6. Update spec.md. Do not create design.md, select craft references, or spawn a designer.

Planning notes are not mandatory reader-facing copy. Do not write a color-role map,
component construction brief, or design rationale in this stage.
