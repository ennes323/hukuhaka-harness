---
role: optional design-direction reference
use_when: alignment, grid, anchor placement, or section wayfinding is unresolved after the concept exists
do_not_use_when: the medium is a single short prose column with no competing surfaces
style_risk: one grid recipe repeated across documents makes different jobs look alike
---

## Alignment axes

- Alignment is the cheapest order signal: commit to a small number of vertical axes and
  place every element on one of them. Fewer distinct left edges read as calmer and more
  deliberate; a new edge must mean something (a quote, a margin note, a nested level).
- Center only what is short and singular (a cover line, a hero value). Long centered prose
  and centered ragged groups break scan.

## Grid

- Derive the grid from the content: the widest anchor (a dense table, a timing diagram)
  sets the full-width track; prose keeps its capped measure (`typography.md`) inside it.
- An anchor either shares the prose column or takes the full width deliberately. Width
  variation should encode importance, not accident.
- Keep one grid per document. A page or slide may drop columns; it does not invent new ones.

## Section wayfinding

- A repeated device — section numbering, a band, a rule-plus-label — tells a scanning
  reader where they are. Pick one device and repeat it exactly.
- The device is chrome: visually quieter than the section's content, and never drawn from
  the semantic palette (`color.md`).

## Anchor placement

- Place an anchor where its unit discusses it; the reader must never scroll or page back
  to connect claim and evidence.
- When a caption or takeaway is necessary to prevent misunderstanding, keep it with the anchor
  inside its grid cell. Omit it when the visual encoding already communicates the meaning.

## Don'ts

- Many distinct left edges on one surface — order dissolves
- Full-bleed prose beside full-width anchors — the measure is lost
- A wayfinding device louder than the content it locates
- Symmetric layouts forced onto asymmetric content — balance comes from weight, not mirroring
