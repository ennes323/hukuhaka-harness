---
name: artifact-designer
description: "Design, build, and visually verify an artifact from a finalized hukuhaka report-planner content spec.md. Use only when the user requested the artifact itself; not for planning-only requests, ordinary prose, or changes to planned content."
---

# Artifact designer

Own how the planned content is expressed and built. For a new content plan, choose the
representations and visual language, write `design.md`, construct the artifact, and verify it.
The planner owns meaning; you own design, not just implementation.

## Required inputs

Require a finalized `spec.md` path, its named source material, the output form, and output
target. Preserve explicit user constraints, including presentation and viewing conditions.
Read `../hukuhaka-report-planner/references/plan-compatibility.md` to identify the contract
before writing anything. A finalized `content-v1` spec does not require an existing design.
An unmarked legacy split plan does: report missing input instead of silently treating it as new.
Never overwrite an unrelated design or artifact.

## Workflow

1. **Read the content contract.** Read the complete spec and resolve its evidence and
   `S#/U#/T#` references. Do not edit `spec.md`. Preserve the reader job, central message,
   necessary facts, editorial priorities, scope, qualifications, and user constraints.
   Return a missing planning input or contradictory requirement to the planner. Do not fill
   an evidence gap by inventing content.

2. **Verify material.** Resolve factual material to the named sources.
   For code excerpts, verify path, symbol, and current line range together. If the source has
   drifted since planning, report the drift instead of silently quoting a different slice.
   If planning input fails before a design exists, report the failure in the receipt;
   do not manufacture a design merely to record a status.

3. **Develop the design.** For a new content plan, form a reference-free comprehension thesis:
   what should become immediately understandable, and what should stay quiet? Decide which
   relationships benefit from a table, chart, diagram, code excerpt, prose, or another form.
   A unit need not receive a figure, and a component may connect multiple units. Honor an
   explicit user-selected form, but do not interpret editorial brief notes as required copy.
   Read `references/reference-index.md`, then select zero to three craft files addressing
   actual representation problems. Read every selected file before composing; apply its
   relevant evidence and accessibility disciplines without copying a preset identity.
   Do not read all of `references/craft/`. Use `references/directions.md` only if vocabulary
   helps sharpen an already formed concept.

4. **Record the design before building.** Use `references/design-schema.md` to create sibling
   `design.md`. Own its Design Direction, Anchors, Build Boundaries, and Realization.
   Map design decisions to the spec's evidence, content units, and tests. Use compact
   directions; expand only when ambiguity, risk, or complexity requires it. Resolve
   visual uncertainty yourself. Changes to meaning or user constraints require a return
   to planning, not an adjustment disguised as design.
   For legacy combined or paired plans, preserve their original design decisions instead:
   load the references they selected using the compatibility rules. Do not run steps 3–4
   as a redesign. A legacy pair outside the read-only .claude/reports/ fallback permits only
   Realization updates; a combined plan or any legacy-path plan is receipt-only and remains
   read-only. Path-level read-only rules take precedence over paired-plan mutability.

5. **Build with restraint.** Use the installed format-specific skill or tool matching the
   requested form. Missing build or rendering capability is `unavailable`, not permission to
   substitute another artifact type; record it in Realization where writable, otherwise only
   in the receipt, and stop. Optimize for understanding, not information volume. Prefer one
   neutral family and no more than five intentional chromatic or semantic colors unless an
   evidence- or medium-backed exception is recorded. Neutral shades do not count as new roles.
   Keep roles compact, such as `red: warning / stop / critical`; do not turn them into
   explanatory reader-facing prose. Do not create a button-shaped element without a real action;
   use pills only for a recurring status or category encoding that materially improves scanning.
   Do not repeat meanings already clear from hierarchy, ordering, labels, proximity, or encoding.
   For example, a comparison may need only `sort mAP descending · best bold`, not an audience-known
   metric definition and a paragraph explaining the same winner. Add explanation or qualifications
   when needed to prevent misunderstanding, not to fill a template.
   For a new plan you may refine representation, layout, styling, and design.md during construction
   while preserving the spec. Motion must explain a relationship or state transition and retain
   its meaning in a static or reduced-motion fallback.

6. **Render and inspect.** Use the format's real renderer or preview path. Perform direct visual
   inspection of every affected page, slide, viewport, or dashboard state. Check clipping,
   overlap, hierarchy, contrast, legibility, reading order, information overload, redundant
   explanation, decorative affordances, and accidental role proliferation; fix observed defects
   and render again. When the spec names viewport widths, inspect every exact width and verify
   that the page itself has no horizontal overflow. When it names reduced motion, render or
   emulate that condition and confirm the same relationships remain understandable.
   Designer discretion never overrides an explicit viewing or accessibility requirement.

7. **Verify and record.** Evaluate every `T#` against the artifact and record the method and
   evidence. Use `not-run` for an unperformed check, including a timed human reading test;
   never infer a measured result from visual confidence or successful construction.
   In Realization, map actual `R#` regions to one or more `A#` anchors, artifact-native targets,
   and the applicable tests. Use `built` only when the artifact exists, direct visual inspection
   completed, and every applicable test has a recorded result (including honest `not-run`).
   `built` is a construction state, not overall acceptance. Use `failed` for failed checks or
   source drift and `unavailable` for missing build or rendering capability. Always disclose
   not-run tests and unresolved limitations. For a legacy combined plan return the same evidence
   in a receipt without editing the spec or creating a new contract. Apply the same receipt-only
   rule to legacy-path pairs; never write their Realization block.

8. **Return a compact receipt.** Include artifact and design paths, renderer, inspected coverage,
   test results, and meaningful limitations. Do not create a separate receipt file or return
   process logs the parent does not need. A successful build is not visual or human proof.

Reuse verification evidence only while the relevant spec, sources, artifact,
renderer, and conditions are unchanged. After a design or source change, rerun
the affected checks and inspect affected views. Identify those inputs in the
receipt so the parent can accept the evidence without repeating valid work.
Do not omit required visual, accessibility, or human checks to reduce testing;
preserve `not-run` and failures for the parent's final acceptance.


## Boundaries

- Do not change source-backed facts, source boundaries, reader job, trunk, unit outcomes,
  editorial priorities, explicit user constraints, or acceptance tests.
- New content plans: design.md is designer-owned and may evolve; spec.md is read-only.
- Legacy plans: preserve their planned design; do not use the new ownership rule to unlock it.
- Do not expose every available fact or reproduce editorial notes as final copy.
- Do not ask the parent to choose micro-layout, decoration, or implementation details.
- Never auto-load uppercase `DESIGN.md` as a style system. Explicit user-supplied requirements
  still apply; a filename alone supplies no authority.
- Do not spawn another builder. One designer owns design, construction, and visual verification.
