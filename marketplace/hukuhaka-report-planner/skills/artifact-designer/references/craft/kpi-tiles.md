---
role: optional anchor-selection reference
use_when: a small set of metrics directly answers the reader's primary status or comparison question
do_not_use_when: metrics lack context, comparability, or decision value
style_risk: default KPI strips and oversized numbers force every document into a dashboard grammar
---

## Selection rule

Use a metric anchor only when the metric has a verified definition, unit, time boundary,
comparison basis, and reader consequence. A document, page, or unit does not need a hero
number by default.

## Tile structure

A useful metric presentation includes only what the intended reader needs to interpret the
value correctly:

1. metric name; add a definition only when the audience needs it;
2. value and unit;
3. time or scope boundary when it changes interpretation;
4. baseline, target, or delta when relevant;
5. source or caveat when omission could mislead or prevent verification.

Scale, alignment, grouping, and whether metrics appear as tiles, a table, inline text, or a
chart belong to the document-specific design direction.

## Hero ladder

A metric presentation is a size ladder, not one big number:

1. **Value** — the largest element; readable before anything else on the surface.
2. **Unit** — set with the value but visibly smaller and lighter (roughly 40–60% of the
   value size), so `ms`, `%`, or a currency mark reads as part of the number without
   competing with it.
3. **Label** — label size; add a definition only when the intended reader cannot interpret the
   metric reliably without it.
4. **Delta** — compact adjacent text or a mark with explicit sign, baseline, and direction;
   do not default to a pill or chip.
5. **Source or caveat** — when needed, metadata size and adjacent, never inside the value's
   visual field.

For a hero metric the value is usually 3× the label size or more; a tile grid uses a
shorter ladder so tiles compare instead of shouting. Decks scale the ladder up — one hero
per slide reads farther than a grid of four.

## Tile grids

- Align value baselines and decimal points across tiles so the row scans as one comparison.
- Give equal-importance metrics equal size; give the decision metric the hero treatment
  instead of enlarging everything.
- Keep only metrics needed for direct comparison. Consider a table (`tables.md`) when the
  tile layout makes labels or comparisons harder to read.

## Don'ts

- Value without the unit, period, source, or comparison basis needed for correct interpretation
- Equal visual weight for metrics with different decision importance
- Delta without an explicit baseline or direction label
- KPI grid used to decorate an entry surface
