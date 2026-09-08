---
role: optional anchor-selection reference
use_when: the reader must compare exact values or look up records across shared fields
do_not_use_when: sequence, relationship, or overall pattern matters more than exact lookup
style_risk: one dense analytic table treatment can overpower documents with different jobs
---

## Density

Choose density from lookup frequency, row count, column count, medium, and accessibility.
Keep repeated values aligned and preserve enough separation to follow a row without ambiguity.

## Rules

- Use rules, spacing, grouping, or shading only when they improve row and column tracking.
- Preserve group boundaries and header relationships on narrow or paginated media.
- Provide sorting, filtering, or alternate representations when interactive lookup requires them.

## Alignment

- Align comparable numbers consistently; tabular numerals are usually useful for dense columns.
- Text: left-aligned. Headers: same alignment as their column
- Keep units explicit and visually associated with their values.
- Mixed-type columns (text + delta number): right-align the number, let the text fill leftward

## Color

- Encode deltas and states consistently with labels or symbols in addition to color.
- Use cell color only when it represents data, status, or interaction.

## Typography

- Keep headers distinguishable and preserve the document's terminology.
- Choose numeric and text roles for scan accuracy at the final size.

## Diff tables (before / after)

- Three-column core: `before | after | Δ` — the delta column is the finding; before/after
  are its evidence
- Δ column: semantic gain/loss pair with an explicit sign (`+12%`, `−3.4ms`), right-aligned,
  tabular-nums. The arrow glyph is optional; the sign is not
- Changed cells: subtle bg tint OR weight bump, never both; unchanged rows stay visible but
  dimmed — deleting them hides the base rate
- Long tables: collapse runs of unchanged rows into a single mono row (`… 14 unchanged …`)
- Emphasize the largest or most consequential delta through ordering or weight. Add an
  annotation only when that signal would still leave the decision meaning ambiguous.
- Config diffs (text, not numbers): show both values — changed value at weight 600, old
  value dimmed; never truncate the old value away

## Don'ts

- Decorative cells that obscure exact comparison
- Ambiguous units, truncated labels, or hidden sort order
- Responsive collapse that destroys row or column relationships
