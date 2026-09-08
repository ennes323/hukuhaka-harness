# Design foundations

Use this reference to discover missing decisions, not to impose fixed values. For each applicable area, distinguish `established`, `required now`, `conflicting`, and `deferred`. Completeness means the current work does not depend on a silent choice; it does not mean inventing every possible token or component.

## Visual direction

- What product personality, density, information hierarchy, and decorative level serve the user's job?
- Which existing products, brand assets, or screens are authoritative references?
- Which visual patterns are intentionally excluded?

Translate vague style requests into observable criteria such as density, contrast, edge treatment, imagery, or motion. Do not reduce direction to an unexplained product imitation.

## Color

- Identify background, surface, text, border, accent, and semantic roles.
- Separate raw palette values from semantic roles when the project benefits from that indirection.
- Define applicable hover, active, selected, focus, disabled, loading, success, warning, error, and info behavior.
- Check theme variants, contrast, grayscale or non-color cues, and how much accent is allowed in one view.

## Typography

- Identify family, size, weight, line height, letter spacing, and rendering constraints.
- Define the smallest useful role hierarchy: page and section titles, body, secondary text, caption, label, and control text.
- Preserve readable measure, wrapping, zoom behavior, and content-driven height.

## Spacing and sizing

- Discover the existing spacing scale before adding values.
- Define section rhythm, component padding and gap, control height, icon size, touch targets, and density variants only as needed.
- Prefer a coherent scale, but retain an intentional optical adjustment when it is truly local and documented by the composition.

## Layout and responsiveness

- Establish content width, page padding, grid or alignment rules, primary regions, and layering.
- Identify target widths and what wraps, reflows, collapses, scrolls, truncates, or changes order at each relevant boundary.
- Preserve reading order and interaction reachability when visual order changes.

## Shape and surface

- Reuse established radius, border, divider, shadow, elevation, and overlay conventions.
- Give each surface distinction a purpose such as hierarchy, grouping, interaction, or transient layering.
- Avoid decorative card nesting or inconsistent radii without a structural reason.

## Interaction and motion

- Define state changes and their visible cues, including keyboard focus.
- Use motion to explain continuity, hierarchy, or feedback rather than decorate delay.
- Respect reduced motion and ensure meaning survives without animation or hover.

## Content and visual assets

- Choose one coherent icon approach; do not silently mix emoji, arbitrary SVG, and unrelated icon families.
- Define image crop, aspect ratio, fallback, loading, and empty-state treatment when images matter.
- Test realistic labels, long values, missing values, errors, localization growth, and user-generated content.

## Components

Create or extend a component only when behavior or visual rules recur. Define anatomy, variants, sizes, state matrix, content constraints, composition rules, and accessibility contract. Prefer composition over an option-heavy universal component, and preserve native semantics where they already satisfy the behavior.
