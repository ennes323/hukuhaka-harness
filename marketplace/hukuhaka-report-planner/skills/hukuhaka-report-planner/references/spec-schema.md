# spec.md — content plan

The planner writes `.hukuhaka/reports/<short-name>/spec.md`.
A finalized content-v1 spec is complete without design.md. The designer owns
representation and creates design.md only when the artifact is requested.

## Template

```markdown
---
plan-format: content-v1
plan-state: draft
---
# <subject> — content plan — <date>

## Document Model

- job: <decide | explain | reference | monitor | persuade | teach | record>
- reading behavior: <linear | scan | random-access | live>
- form: <requested medium, or stated assumption>
- audience: <reader, context, prior knowledge>
- success test: <observable reader outcome>
- prose level: <brief | balanced | full>
<!-- output target: <user-requested artifact destination; needed before build handoff> -->
<!-- user constraints: <explicit user requirements, including requested presentation choices> -->
<!-- assumptions: <only consequential choices not supplied by the user> -->

## Evidence

- established: <verified facts necessary to the document>
- source S1: <path, symbol/range, dataset, or verified URL> — supports: <content/claim>
<!-- conflict: <unresolved contradiction> -->
<!-- gap: <missing evidence and its effect on the content boundary> -->
<!-- freshness: <applicable time-sensitive limit> -->

## Structure

- trunk: <central message or organizing relationship>
- U1 <content unit>
  - reader question: <question this content answers>
  - reader outcome: <what the reader must understand or do>
  - content: <necessary facts and relationship, not finished copy>
  - evidence: <S1, or explicit inference tied to sources>
  <!-- priority: <relative emphasis only when the order is insufficient> -->
  <!-- qualification: <necessary limitation; do not automatically repeat elsewhere> -->
  <!-- exclude: <material that must not be inferred or introduced> -->

## Acceptance Tests

- [ ] T1 <observable reader outcome and how it will be checked>
- [ ] T2 <evidence fidelity and source boundary>
- [ ] T3 <recoverable central message and content relationships>
<!-- Add user-required medium or accessibility conditions without selecting their design solution. -->
```

## Contract

- Required frontmatter is `plan-format: content-v1` and `plan-state: draft | finalized`.
  Stage 4 changes the state only after content review.
- Required level-two blocks are Document Model, Evidence, Structure, and Acceptance Tests.
  Every source, content unit, and acceptance criterion has a stable S#, U#, or T# ID.
- Each unit states its reader question, outcome, necessary content, and evidence.
  Content order represents editorial order; the designer may realize it in different layouts.
- Record explicit user presentation requirements in user constraints. Other representation
  choices, A# anchors, color roles, craft selection, and implementation do not belong here.
- Omit empty optional fields. Make source slices resolvable without copying all evidence.
- The designer keeps the finalized spec read-only. Changed facts, scope, central message,
  editorial priorities, or user constraints return to the planner.
- This is a human-readable contract, not an executable schema. Structure checks do not
  prove that evidence is valid or that a reader understood the finished artifact.
- Existing unmarked plans follow `plan-compatibility.md`; never infer content-v1
  from a missing design file.
