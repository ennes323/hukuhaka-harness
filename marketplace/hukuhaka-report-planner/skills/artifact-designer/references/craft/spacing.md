---
role: optional design-direction reference
use_when: density, grouping, reading rhythm, responsive behavior, or print margins are unresolved
do_not_use_when: density and grouping are already resolved
style_risk: fixed spacing scales and page recipes make different forms share one rhythm
---

## Design questions

- What must be visible in one scan, viewport, slide, or printed page?
- Which units should read as groups, and which need a strong break?
- Where does density help comparison, and where does it obstruct comprehension?
- What changes across target widths or print dimensions?
- Which anchors require stable aspect ratios, minimum widths, or overflow behavior?

The designer derives a compact scale, relative rhythm, and grouping from the chosen medium
and concept; these are design decisions, not content-planning tokens.

## Scan rhythm (density variation per page)

A scan-oriented artifact usually needs visible grouping and changes in emphasis. A lookup
surface may instead need deliberately consistent density. Derive rhythm from reading behavior;
do not require a hero metric or a breathable band on every page.

## Grouping scale

- Proximity is the grouping signal: the gap inside a group must be clearly smaller than the
  gap between groups — a 2× step is a workable floor.
- A group's label must sit visibly closer to its own group than to the previous one.
- Dense comparison surfaces (tables, tile grids) group by alignment and shared edges more
  than by whitespace; do not inflate them to match prose rhythm.

## Margins by medium

Workable defaults the designer may adapt to the concept; record deviations only when an
anchor depends on them.

- **Deck (16:9):** keep a consistent safe margin of roughly 4–6% of the slide width on all
  sides. Content crosses it only as a deliberate full-bleed device, never by overflow —
  when content presses the margin, split the slide.
- **Print/PDF:** set page margins for the trim, and keep running headers or footers out of
  the content rhythm.
- **Web:** margins follow the capped measure (`typography.md`); center the column
  rather than stretching it.

## Anti-defaults and failure modes

- Section gap = paragraph gap — sections dissolve into prose
- Margin-collapse not understood — vertical gaps double-count or disappear under flex/grid
- Edge-to-edge content on wide viewports — long lines unreadable; cap measure (see `typography.md`)
