---
role: optional anchor-selection reference
use_when: claims must stay traceable to sources — mixed-reliability evidence, external data, or a document that will be audited
do_not_use_when: every fact comes from one obvious source the reader already trusts — one attribution line covers it
style_risk: academic citation theater on an internal memo adds apparatus without adding trust
---

## Source apparatus

The spec's evidence map already assigns source IDs; the document's job is to keep each
claim attached to its source without breaking the reading flow. Match the apparatus to the
document's stakes: an audited report needs per-claim attribution, a team memo needs one
sources line. Never invent a heavier apparatus than the reader's verification behavior
requires.

## In-flow attribution

- Attribute at the claim, not in a distant bibliography: a short source tag near the
  number or statement (`(S3, 2026-06 export)`), or a caption line under the anchor that
  uses the source.
- Keep the document's epistemic marking visible: measured, reported, and inferred are
  different claims and must not flatten into one confident voice under a shared citation.
- When two sources disagree, show both values with their sources — silently picking one is
  an unmarked judgment call.
- A quotation used as evidence is verbatim, attributed, and dated; paraphrase outside the
  quotation marks.

## Forms

- **Inline tag:** shortest; for documents where most claims share a few sources.
- **Footnote or endnote:** when attribution detail (query, export date, caveat) would
  clutter the flow; keep the note content factual, not a second argument track.
- **Source table:** one row per source — ID, what it is, as-of date, known limitation.
  Earns its place when sources exceed roughly four or reliability varies.

## Freshness

- Every dataset-backed claim carries an as-of date somewhere the reader will see it —
  in the source table, the caption, or the tag. Undated data reads as current and
  eventually becomes a lie.
- State the collection window when it changes the reading (`30-day window ending 07-15`).

## Don'ts

- Bare long URLs in body text — name the source, put the locator in the apparatus
- A citation as a substitute for stating uncertainty — sourcing a guess doesn't firm it up
- Footnote overload where a source table would collapse the repetition
- Attribution styles mixed mid-document (inline tags in one section, footnotes in the next)
- Citing a source the document never actually uses — apparatus as costume
- Dead-end IDs: a tag in the text with no entry in the source table or spec
