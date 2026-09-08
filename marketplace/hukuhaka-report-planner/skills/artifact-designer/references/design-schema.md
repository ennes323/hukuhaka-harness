# design.md schema — designer-owned design and realization

The artifact designer creates this file for a finalized content-v1 spec at

```
.hukuhaka/reports/<short-name>/design.md
```

`design.md` records how source-backed components realize sibling `spec.md`. The designer owns
all four blocks and may refine design decisions during construction without changing the spec.
This schema applies to new content-v1 plans. Classify existing files with the planner's
`../../hukuhaka-report-planner/references/plan-compatibility.md` before writing; legacy paired
plans retain their original Realization-only rule, except that legacy-path plans are entirely
read-only and return realization in the receipt.

## design.md — full template

```markdown
---
design-format: designer-v1
---
# <title> — design — <YYYY-MM-DD>

- specification: ./spec.md

## Design Direction

- thesis: <one sentence naming what should become immediately understandable and what stays quiet>
<!-- roles: -->
<!--   - <signal>: <meaning, for example red: warning / stop / critical> -->
<!-- Add only roles the artifact actually uses. Omit the block when the thesis and ordinary hierarchy are sufficient. Do not explain an obvious role unless ambiguity or an exception requires it. -->
<!-- references: <selected path — useful mechanism and meaningful deviation; omit when none> -->
<!-- exceptions: <baseline restraint exceeded, affected anchor, and evidence or medium reason; omit when none> -->

## Anchors

### A1 <anchor name>

- unit: <U1, or a list when one component serves multiple units>
- evidence: <S1, S2, fields/range, or explicit qualitative material>
- acceptance: <T1, T2>
- direction: <form · exact material · dominant arrangement or encoding; for example table · S1 model rows · sort mAP descending · best bold>

<!-- Use the compact direction above by default. Expand only when ambiguity, risk, or complexity cannot fit safely on one line: -->
<!-- - form: <chart | table | diagram | screenshot | code | checklist | quote | ...> -->
<!-- - material: <exact source slice, fields, path + symbol + current line range, states, or labels> -->
<!-- - composition: <dominant relationship, arrangement, reading order, and intentional omissions> -->
<!-- - treatment: <behavior, emphasis, annotation, and applicable fallback> -->
<!-- - takeaway: <only when the encoding does not make it reliably inferable> -->
<!-- - caveat: <only when omission could mislead the reader> -->

<!-- If every unit is intentionally prose-only, replace A1 with: -->
<!-- - prose only: <why prose is the clearest form> -->

## Build Boundaries

- preserves: <spec requirements and explicit user constraints that affect this design>
<!-- limitations: <known medium or capability limits, only when present> -->

## Realization

- status: not-built
```

After construction or a blocked attempt, update `## Realization` (the other design blocks
may also evolve for content-v1 plans; the spec stays read-only):

```markdown
## Realization

- status: <built | failed | unavailable>
- artifact: <path, or none>
- renderer: <renderer or preview path, or unavailable>
- inspected: <pages, slides, viewports, states, or none>

### R1 <realized region>

- realizes: <A1, A2>
- target: <artifact-native page, slide, region, selector, or state>
- verified by: <T1, T3>
- result: <passed | failed | not-run, with concise evidence>

### Acceptance results

- T1: <passed | failed | not-run> — <method and observed evidence, or why not run>
<!-- Record every applicable T#; do not infer human or timed results. -->

<!-- changes: <meaningful design refinements, if needed to explain the final design; omit when none> -->
<!-- limitations: <unresolved limitations; omit when none> -->
```

## Rules

- Every `A#` resolves to one or more `U#`, `S#`, and `T#` IDs in sibling `spec.md`.
- Lists are valid in both directions: one anchor may serve multiple units or realized regions,
  and one realized region may implement multiple anchors.
- Each non-prose anchor uses exactly one brief shape: a compact `direction`, or expanded
  `form`/`material`/`composition`/`treatment` fields when one line would hide ambiguity, risk,
  fallback behavior, or a load-bearing relationship.
- Do not duplicate a unit's reader question or outcome in an anchor. Add `takeaway`, `caveat`,
  references, exceptions, or other optional fields only when their omission could mislead the
  builder or reader; otherwise omit them instead of writing `none`.
- Role mappings are compact `signal: meaning` instructions, not essays or token definitions.
- A prose-only design records `- prose only:` and creates no fake anchor or realization mapping.
- All design sections belong to the designer for content-v1. Never edit sibling `spec.md`.
- Require `design-format: designer-v1` and a matching specification before resuming an existing
  new-format design. Do not overwrite an unmarked or unrelated file as though it were yours.
- `built` requires an artifact, direct visual inspection, and recorded results for every
  applicable acceptance test. Missing capability is `unavailable`; failed checks or source
  drift are `failed`, never `built`. A recorded `not-run` test remains unverified and must be
  disclosed in limitations and the receipt. `built` does not mean overall acceptance.
- A prose-only design still records every applicable T# result; it does not invent A#/R# IDs.
- This generated lowercase file is unrelated to any project-level uppercase `DESIGN.md`,
  which the planner never auto-loads.
