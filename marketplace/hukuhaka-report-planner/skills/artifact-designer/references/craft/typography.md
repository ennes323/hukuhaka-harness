---
role: optional design-direction reference
use_when: reading voice, hierarchy, long-form comfort, numeric alignment, or code roles are unresolved
do_not_use_when: the host design system already defines typography
style_risk: prescribed pairings and mono-eyebrow roles create a recognizable house style
---

## Core principle

Typography serves the reader's job, medium, language, and content density. Record role
relationships and constraints; do not prescribe a font family merely to avoid a popular one.

## Role mapping

| Role | Planning question |
|---|---|
| Entry/title | What identity and hierarchy must be established? |
| Headings | Can the unit sequence be recovered by scanning? |
| Body | Is sustained reading comfortable at the target size and language? |
| Labels/metadata | Are taxonomy and status distinct without dominating content? |
| Numbers/code | Do alignment and exact syntax remain legible? |

## Measure

- Body prose reads best at roughly 45–75 characters per line; cap the measure on wide
  viewports instead of letting text run edge to edge.
- Dense reference tables, code, and wide figures may exceed the body measure, but give them
  their own surface (scroll container, full-width band) rather than widening the prose
  column to match.
- A very short measure (under ~35 characters) breaks ragged-right reading; widen the column
  or reduce the type size before resorting to hyphenation.

## Hierarchy ladder

- Build hierarchy from a small scale whose adjacent steps are distinguishable at a glance;
  if two levels are hard to tell apart, merge them or widen the ratio.
- Documents usually need modest steps (about 1.2–1.33 between levels); decks and posters
  are read at distance and need display sizes several times body size.
- Create only the levels the structure uses — an unused heading level weakens the ones the
  reader must learn.
- Size, weight, spacing, and case are separate hierarchy channels; spending several at once
  on one level burns contrast the ladder may need elsewhere.

## Selection constraints

- Verify glyph coverage for the document language and symbols.
- Plan fallback behavior for offline, PDF, and restricted-network contexts.
- Use a small number of roles and make their hierarchy distinguishable without relying on
  color alone.
- Prefer tabular numerals where columns or changing metrics must align.
- Keep code and identifiers distinguishable from narrative without forcing mono elsewhere.

## Failure modes

- Font choice without verified availability or fallback
- Heading scale that overflows compact surfaces
- Low-contrast metadata used to hide weak hierarchy
- Too many type roles for the reader to learn
- Numeric or code content that loses alignment or exact characters
