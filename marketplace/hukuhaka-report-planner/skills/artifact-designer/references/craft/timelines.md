---
role: optional anchor-selection reference
use_when: the material is narrative or project time — milestones, roadmap phases, historical sequence, or plan versus actual
do_not_use_when: the evidence is a machine-time trace or incident chronology (`timing-diagrams.md`) or a continuously sampled metric (`charts.md`)
style_risk: decorative winding roads and equal-spaced dots erase the durations and gaps the reader needs
---

## When to use

The material is human-scale time: what was delivered when, what is planned next, how a
system or decision evolved. Precision is days-to-quarters, actors are teams or projects,
and the reader compares order, duration, and distance-to-now. Millisecond traces, request
lifecycles, and incident chronology belong to `timing-diagrams.md`; a sampled metric over
time is a line chart.

## Forms

- **Milestone strip:** dated point events on one axis. Use when order and spacing carry the
  message; keep to the events the trunk actually references.
- **Phase or roadmap lanes:** one lane per workstream, spans for phases. Order lanes by the
  reader's priority, not org chart. Mark dependencies only where a slip propagates.
- **Plan vs actual:** paired spans per item (planned above, actual below, or outline vs
  fill). The delta is the finding — annotate the slip in units (`+3 wk`), not just visually.
- **Era band:** for history or evolution narratives; label eras by what changed, not by
  version number alone.

## Encoding rules

- One time axis, linear, with real dates. Spacing must be proportional to elapsed time — a
  break in the axis is annotated, never silent.
- Mark **today** whenever the timeline crosses it; everything to the right is a plan, and
  must read as one.
- Future and uncertain dates render differently from committed facts (outline, dashed edge,
  or an explicit `target` label) — a roadmap that draws plans like history overclaims.
- Annotate the interval that carries the finding (`design → launch: 14 mo`); the deltas are
  usually the takeaway, not the dots.
- Past ~10 items, group into phases or split by lane — a dense strip of labels is a table
  wearing a costume.

## Don'ts

- Equal spacing for unequal intervals — the whole point of the axis is proportion
- Winding roads, spirals, or arrows-through-mountains — decoration that destroys the axis
- Future milestones rendered identically to shipped ones
- Lane colors as team branding rather than evidence encoding
- A timeline with no annotated interval or today-marker — inert
- Mixing granularities silently (quarters on the left, exact dates on the right)
