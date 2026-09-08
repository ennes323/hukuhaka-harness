# Design system, mockup, and application synchronization

Use this reference whenever more than one UI artifact is relevant.

## Ownership

| Artifact | Owns | Does not prove |
|---|---|---|
| Design system | Reusable foundations, semantic roles, components, variants, and interaction rules | The correct composition of every screen |
| Mockup | Screen hierarchy, composition, emphasis, content shape, and visual intent | Runtime behavior, complete states, accessibility, or implementation feasibility |
| Application | Working behavior, data and interaction states, responsive execution, and accessible implementation | That an observed one-off value is an intentional system rule |

When no explicit design-system artifact exists, current tokens, shared components, and repeated implementation may be de facto evidence. Treat them as observed authority, not automatically as a well-designed system.

## Synchronization loop

1. Identify the decision and its current owner.
2. Compare the same state, content, theme, and viewport across available artifacts.
3. Classify a difference as:
   - `intentional`: an explained artifact-specific distinction;
   - `missing`: the owner has not recorded a required decision;
   - `stale`: another artifact reflects an older valid decision;
   - `accidental`: implementation or mockup diverged without a product decision;
   - `unresolved`: evidence cannot determine the intended owner or value.
4. Change or propose the owning artifact first, then propagate the decision to dependent artifacts.
5. Verify the affected consumers and record any intentional exception.

Do not average conflicting values, choose whichever looks newer, or silently make the application match a screenshot. A difference may reveal that the system should change, but the application is not the place to hide that decision.

## Practical comparison

Use a compact ledger when several decisions differ:

| Decision | Owner | Expected | Observed | Classification | Action |
|---|---|---|---|---|---|

Compare rendered mockup and application at the same viewport when spatial judgment matters. Normalize content, state, theme, font loading, and browser zoom before interpreting pixel differences. Prefer computed geometry and DOM state for exact alignment; use screenshots or overlays for relationships that need visual judgment.
