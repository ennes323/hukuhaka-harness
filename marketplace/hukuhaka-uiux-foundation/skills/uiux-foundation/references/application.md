# Application UI

Use this reference for user-visible application implementation and audits.

## Inspect before changing

Trace the existing route, layout shell, shared components, theme or token definitions, style entry points, icon and asset sources, and visual test path. Sample representative screens instead of assuming one route defines the whole system. Record established conventions, genuine inconsistencies, and missing decisions separately.

Do not replace a working component library or styling approach merely because another stack is familiar. Keep behavioral logic, data contracts, and unrelated frontend architecture outside a visual change unless they are required for the approved outcome.

## Complete the state contract

For each affected interactive component or screen, cover the states that materially exist:

- default, hover, focus, active or pressed, selected, and disabled;
- loading, empty, error, partial, stale, and success where data is involved;
- validation, help, destructive confirmation, and optimistic or pending feedback where applicable.

Do not invent unreachable states, but do not demonstrate only the ideal populated state when the application contract includes failure or absence.

## Responsive and content behavior

- Test the actual content and target widths rather than shrinking a desktop screenshot mentally.
- Define what resizes, wraps, reflows, collapses, scrolls, truncates, or changes order.
- Keep critical actions and information reachable; avoid horizontal page overflow unless the product explicitly owns a horizontal interaction surface.
- Exercise long labels, large numbers, empty values, validation text, localization growth, and user-generated content.

## Accessibility

- Preserve semantic elements, labels, accessible names, reading order, and heading hierarchy.
- Verify keyboard reachability, visible focus, dismissal, focus return, and non-hover access to information.
- Check text and non-text contrast, touch targets, zoom, reduced motion, and non-color cues.
- Treat ARIA as a supplement to correct native behavior, not a replacement for it.

## Alignment and visual consistency audits

When the user asks whether UI is aligned or consistent, inspect rendered and computed geometry. Compare shared edges, baselines, grid tracks, container widths, padding, gaps, type metrics, icon boxes, and state-specific movement. Distinguish optical alignment from mathematical alignment and identify the owning token, component, or composition before recommending a change.

Report verified-clean areas as well as divergences. Do not turn a bounded audit into an unsolicited redesign.
