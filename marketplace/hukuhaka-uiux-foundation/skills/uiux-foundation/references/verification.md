# UI verification

A successful build is not proof that the interface matches its design contract. Verify the evidence that closes the user's actual request.

## Establish the expectation

Name the authority, affected routes or components, states, target viewports, themes, and input modes. For a change, compare the same expectation before and after. For an audit, preserve the workspace and report the inspection boundary.

## Automated checks

Run the project's existing lint, type, unit, component, accessibility, visual, and build checks that apply. Do not add or weaken a check solely to obtain a green result. A snapshot or screenshot test proves only the state and viewport it actually covers.

Reuse passing evidence while its relevant source, inputs, configuration, rendered
artifact, and environment are unchanged. Rerun affected checks for a change,
failure, or named unresolved concern. This does not remove required rendered
or accessibility coverage. A delegated owner supplies the inspected artifact
identity and coverage; the parent reviews the delta and evidence without
repeating unchanged automated checks.

## Rendered inspection

- Use the in-app Browser when available for routine local UI, DOM, responsive, and interaction checks.
- Use terminal commands for deterministic tests, builds, and server health.
- Inspect computed style or geometry when exact alignment, inherited values, stacking, overflow, or font metrics matter.
- Use screenshots, overlays, or visual diffs when the relationship is genuinely spatial; compare canonical references at the same viewport and state.
- Use deeper browser tooling only when the routine path cannot provide the required style, network, performance, or accessibility evidence.

Inspect applicable:

- clipping, overlap, page and component overflow;
- hierarchy, reading order, alignment, spacing, type, color, and icon consistency;
- hover, focus, pressed, selected, disabled, loading, empty, error, and partial states;
- keyboard navigation, visible focus, accessible names, announcements, dismissal, and focus return;
- narrow, wide, zoomed, reduced-motion, and alternate-theme behavior named by the contract.

## Completion receipt

Report:

- authority and current source inspected;
- modes, routes, components, states, viewports, and themes covered;
- reusable decisions added, changed, or intentionally reused;
- local exceptions and why they remain local;
- automated and rendered evidence with results;
- unresolved mismatches or unavailable verification.

State unverified areas plainly. Do not generalize one clean screen into application-wide consistency.
