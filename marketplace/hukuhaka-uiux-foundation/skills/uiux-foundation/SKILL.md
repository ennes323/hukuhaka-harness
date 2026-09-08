---
name: uiux-foundation
description: Use automatically for user-visible frontend and UI/UX work involving interface foundations, design systems, component styling, layout or alignment, responsive or accessibility behavior, mockup implementation, or visual consistency audits. Do not use for backend-only work, non-visual frontend logic, or report, deck, and document artifacts.
---

# UI/UX Foundation

Keep application design decisions complete, owned by the right artifact, and consistent from intent to rendered behavior.

## Ground the task

Inspect applicable project instructions and the current UI authority before proposing a design. Look for design or brand documents, tokens and themes, component libraries, global styles, representative routes, mockups, screenshots, and existing visual tests. Treat generic guidance as prompts for missing decisions, never as authority over an established project system.

Classify the task as `Create`, `Modify`, `Extend`, `Audit`, or `Parity`. An audit or review does not authorize edits. Do not create `DESIGN.md`, a token file, or a component kit by default; preserve the project's existing source of truth and introduce a new durable artifact only when the task requires one.

## Route only the needed detail

- Read [references/foundations.md](references/foundations.md) when creating a system, filling missing foundations, or deciding whether a visual value is reusable.
- Read [references/application.md](references/application.md) when implementing, modifying, or auditing application UI, components, states, responsiveness, content behavior, or accessibility.
- Read [references/synchronization.md](references/synchronization.md) when two or more of design system, mockup, and application are in scope, or when diagnosing visual drift.
- Read [references/verification.md](references/verification.md) before claiming an implementation or UI audit complete.

## Place each decision

Assign every material visual decision to the narrowest durable owner that can explain its reuse:

1. foundation or semantic token;
2. component rule, state, or variant;
3. screen composition;
4. intentional local exception.

Prefer existing tokens and components. Promote a repeated local choice into the system, but do not manufacture tokens for values that are genuinely specific to one composition. If a mockup reveals a reusable new rule, update or propose the owning system decision before copying it into application CSS.

## Preserve the artifact contract

- The design system owns reusable visual and interaction rules.
- The mockup owns screen-level visual intent and composition.
- The application owns working behavior and must implement both without silent one-off divergence.

When artifacts disagree, identify whether the difference is intentional, missing, stale, or accidental. Resolve or preview the owner-level change before propagating it. If an unresolved choice materially changes product behavior or broad visual direction, show the smallest comparable options and stop for approval under the project's change boundary.

## Finish with evidence

Verify the affected rendered states at the relevant viewport and input modes. Compare structure, state, spacing, typography, color, focus, overflow, and responsive behavior against the identified authority. Report the authority inspected, decisions added or reused, intentional exceptions, affected states and viewports, evidence obtained, and anything still unverified.
