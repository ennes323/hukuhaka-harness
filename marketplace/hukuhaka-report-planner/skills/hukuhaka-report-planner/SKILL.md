---
name: hukuhaka-report-planner
description: "Use when an evidence-based visual document needs content planning before design or construction. Applies to reports, explainers, memos, decks, and similar documents. Excludes ordinary prose, API references, marketing copy, changelogs, and requests that explicitly bypass planning."
---

# Report planner

Plan what the document must communicate.
A separate artifact designer owns how it is expressed and built.

## Responsibilities

- Establish the reader, their prior knowledge, and the document's purpose.
- Verify source material and distinguish facts, inference, and unresolved gaps.
- Define the central message and the relationships the reader must understand.
- Select necessary content, exclude irrelevant material, and establish its
  sequence and relative importance.
- Connect each content unit to its evidence and intended reader outcome.
- Preserve the user's requested medium, output target, and explicit constraints.
- Define observable criteria for content correctness and reader success.

## Planning principles

Optimize for understanding, not coverage. Include only material that changes
what the intended reader can understand, decide, find, or do.
Source coverage is not display coverage: verifying five files does not require five
excerpts or five content units. Select what earns space in the requested document.

Describe communication needs without prescribing their visual solution.
“The reader must distinguish the best-performing model” is a content
requirement; choosing a table, sorting its rows, and styling the best value
belongs to the designer.

A plan is an editorial brief, not finished report copy. Do not require the
designer to reproduce planning notes, field labels, or rationale as visible
content.

Ask the user only when an unresolved choice materially changes the purpose,
scope, evidence boundary, or intended outcome. Otherwise state necessary
assumptions and continue.

## Responsibility boundaries

The planner owns meaning, evidence, content scope, and editorial priorities.
The designer owns representation, visual hierarchy, layout, styling,
interaction, and visual verification.

Do not select design craft references or prescribe charts, diagrams, colors,
typography, spacing, or component treatments.

When the user explicitly specifies a presentation choice, record it as a
user constraint and pass it to the designer. Do not turn a planner preference
into a mandatory design requirement.

The designer may adapt presentation and wording while preserving the plan's
meaning and constraints. A change to evidence, scope, or the central message
must return to planning.

## Planning procedure

Read each stage before executing it. The four stages all concern content planning.

| Stage | Read | Result |
|---|---|---|
| Frame | `stages/1-frame.md` | Reader, purpose, user constraints, initial sources |
| Structure | `stages/2-structure.md` | Central message, content units, order and priority |
| Brief | `stages/3-direct.md` | Source-backed content and necessary qualifications |
| Lock | `stages/4-lock.md` | Reviewed content spec and verification criteria |

Read `references/principles.md` and `references/spec-schema.md` for planning.
These references and the stages do not select the designer's representation.

## Output and handoff

Write the finalized content plan to:
`.hukuhaka/reports/<short-name>/spec.md`

```text
IF planning-only:
    Report the finalized spec path and stop.
ELSE IF an artifact was requested:
    Read references/build-handoff.md.
    Delegate the spec, source material, output target, and user constraints
        to one artifact-designer in a separate context.
    Wait for the designer's result and review its content fidelity against the spec.
```

The designer creates and owns `design.md`, builds the artifact, and records
design and verification results. Do not build alongside the designer or reopen
their visual choices merely because another treatment is possible.

## Existing plans

Preserve existing plans and artifacts. Do not silently rewrite, migrate,
or discard legacy contracts. Read `references/plan-compatibility.md` when
continuing an existing plan; do not classify an unmarked old spec as a new
content-only plan just because its design is missing.

## Language

Use the user's conversation language for questions, planning decisions,
and handoff communication.

Resolve bundled paths relative to this SKILL.md, not the user's project.
