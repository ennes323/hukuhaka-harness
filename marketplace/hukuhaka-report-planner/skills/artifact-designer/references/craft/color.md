---
role: optional design-direction reference
use_when: color must encode state, comparison, hierarchy, or interaction
do_not_use_when: the concept can remain monochrome or color is purely decorative
style_risk: a fixed palette or accent count turns unrelated documents into one house style
---

## Semantic roles

A document may need distinct color roles:

- **Base:** canvas, ink, dividers, and quiet surfaces.
- **Semantic:** status, comparison, category, sequence, or uncertainty.
- **Emphasis:** the limited elements that need priority in the reading path. Emphasis reads
  only while it is scarce — the fewer elements that share the role, the stronger each reads.

The number and temperature of colors follow the evidence, brand constraints, medium, and
design concept. Do not infer them from a document label such as report or dashboard.

## Contrast targets

- Screen body text: ≥4.5:1 against its surface.
- Large display text, chart strokes, and other essential non-text marks: ≥3:1.
- Quiet chrome (dividers, metadata) may sit below these targets only when it carries no
  meaning the reader must recover.

## Print / PDF contrast

If the report will be printed or exported to PDF:

- Body ink at ≥7:1 against the paper; hairlines and dividers need more weight or darkness
  than their screen equivalents.
- Semantic colors must remain distinguishable in greyscale (red vs green fails — pair with shape or label)
- Important emphasis must still read on a monochrome printer when print is in scope.

## Common failure modes

- **Same accent as a rule color** — chrome dissolves into accent
- **Semantic green/red applied to chrome** (e.g., section header in green) — semantic exhausted, deltas no longer pop
- **Dark mode auto-derived from light** — both modes must be intentionally designed; auto-invert reads as careless
- **Color without a documented role** — the builder cannot distinguish meaning from decoration
