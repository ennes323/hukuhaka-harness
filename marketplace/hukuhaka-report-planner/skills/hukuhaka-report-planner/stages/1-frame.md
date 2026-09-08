---
stage: 1
purpose: establish the reader, purpose, medium, explicit constraints, and initial sources
deliverable: draft content spec under .hukuhaka/reports/
---

## Frame

Read `references/principles.md` and `references/spec-schema.md` relative to the
planner skill root. Do not load design craft references.

1. Determine whether the user requested planning only or the artifact itself.
2. Inspect supplied material lightly. Establish the reader's prior knowledge,
   purpose, reading behavior, requested medium, output target, and success outcome.
3. Record explicit user requirements as `user constraints`, including any requested
   presentation choice. Distinguish these from assumptions; do not invent visual rules.
   A source's lack of visual style input is not a user prohibition on design choices.
   A facts-only source boundary limits claims, not the designer's visual language.
   `output target` means the artifact destination; do not fill it with the spec's save path
   for a planning-only request. Omit it when no artifact target was requested.
4. Start the Evidence block with source IDs and important gaps. Generated or stale
   documentation is not verified evidence merely because it exists.
5. Ask only if an unresolved choice materially changes the purpose, scope,
   evidence boundary, or intended outcome. Otherwise state necessary assumptions.
6. Write `.hukuhaka/reports/tmp-draft/spec.md` using `plan-format: content-v1`
   and `plan-state: draft`. If the draft directory already contains work, resume
   only when it belongs to this request; otherwise ask before overwriting it.
   Never reset an existing design or artifact as a side effect.

A continuation of an existing plan first follows `references/plan-compatibility.md`.
Frame does not create design.md or choose a visual style.
