---
role: optional anchor-selection reference
use_when: a definition, formula, derivation, or threshold is stated mathematically and exact form matters to the claim
do_not_use_when: a sentence or a labeled number carries the same meaning — notation is precision, not authority
style_risk: formula blocks used as credibility decoration make a document harder to read and no more true
---

## When math beats prose

Use notation when the reader must apply, verify, or re-derive the relationship: a scoring
formula, a capacity model, a statistical threshold, a unit conversion the argument depends
on. If the reader only needs the consequence ("cost grows with the square of replicas"),
prose with the key number is clearer. Notation is for exactness, not gravitas.

## Placement

- **Inline** for short expressions read as part of the sentence (`p < 0.01`, `O(n log n)`).
- **Display block** when the expression is referenced again, compared, or derived from —
  give it breathing room and, if referenced, a label (`(1)`).
- One expression per display block; a wall of stacked equations is an appendix candidate.

## Notation discipline

- Define every symbol at first use, adjacent to the formula — not in a distant glossary.
  A reader who must hunt for `λ` has already lost the argument thread.
- Map symbols to the document's data fields explicitly (`n = rows in source S2`); the
  formula must be checkable against the evidence tables around it.
- One symbol, one meaning, whole document. If two sources use conflicting notation,
  translate one — do not import both.
- Numbers substituted into a formula use the same precision and units as the source table
  they came from; a derivation whose inputs don't match the evidence reads as fabricated.

## Derivations

- Show only the steps that carry the argument — the step where the approximation happens,
  the bound that justifies the claim. Route mechanical algebra to an appendix.
- State assumptions where they are used, not just at the top (`assuming independent
  failures`), and mark which conclusions survive if the assumption is weakened.
- End a derivation with the sentence version of the result — the formula proves it, the
  sentence is what the reader carries away.

## Don'ts

- Undefined or overloaded symbols
- A formula whose inputs cannot be traced to any evidence source in the document
- Screenshotted equations — unreadable at print scale and unsearchable
- Notation for a relationship never used again ("as equation (4) shows" — it never does)
- Spurious precision: five significant figures from an estimate with one
- Derivation steps as filler — each retained step must carry weight in the argument
