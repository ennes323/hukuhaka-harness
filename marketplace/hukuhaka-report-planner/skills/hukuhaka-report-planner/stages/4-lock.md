---
stage: 4
purpose: finalize the content spec and hand off only when the artifact was requested
prereq: complete editorial brief in spec.md
deliverable: finalized .hukuhaka/reports/<short-name>/spec.md
---

## Lock the content plan

Read the draft and `references/spec-schema.md` relative to the planner skill root.

1. Resolve material gaps or preserve them as explicit content boundaries. Never
   promote an assumption to fact to complete the plan.
2. Review the whole document for redundant content and qualifications, not only
   individual units. Preserve purpose, evidence, editorial priorities, and user constraints.
   Check that excerpts, supporting detail, and repeated caveats fit the requested document
   scope. Keep one editorial home for a qualification unless another use prevents a
   different misunderstanding; do not solve excess content by redefining a page limit.
   Do not finalize a compact brief that requires excerpts from every supporting module.
   Keep the decisive display excerpt; demote supporting ranges to evidence locators.
3. Write stable T# acceptance criteria for content fidelity and the intended reader
   outcome. Carry through user-required viewing conditions without inventing a design.
   State how a criterion can be checked; a timed human-reader outcome requires actual
   measurement and cannot be passed by the planner's confidence or a file-exists check.
4. Perform final self-review: every S# and U# reference resolves, every unit has necessary
   content and a reader outcome, and every T# is observable. The spec must not depend on
   a future A# or design.md to be a complete content plan.
5. Set `plan-state: finalized`. Derive a subject-based lowercase kebab-case short name
   of at most 24 characters, unless the user already specified the destination.
   Rename the draft directory only after review; never overwrite an existing final plan.
6. Match completion to the request:
   - Planning only: report spec.md and stop. Do not create design.md or delegate.
   - Artifact requested: read `references/build-handoff.md`, delegate once, and wait.
     The designer authors design.md. Do not design or build in the planner context.
7. On return, review content fidelity and the recorded verification against spec.md.
   Report missing or unperformed checks honestly; do not turn a receipt into human acceptance.

Existing plans follow `references/plan-compatibility.md`. Finalization does not authorize
migration, installation, publication, or changes outside the user's request.
