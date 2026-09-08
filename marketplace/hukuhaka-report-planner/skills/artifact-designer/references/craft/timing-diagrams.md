---
role: optional anchor-selection reference
use_when: evidence consists of discrete events, spans, messages, stages, or incident chronology on a time axis
do_not_use_when: the reader question concerns a continuously sampled metric rather than what happened when
style_risk: decorative lanes and arrows can obscure duration, ordering, and uncertainty
---

## When to use

The material is events, stages, or spans laid out on a time axis: a pipeline trace, a
request lifecycle, a scheduler run, an incident from detection to resolution. If the
message is a metric sampled over time, that is a line chart (`charts.md`) — a timing
diagram is for WHAT HAPPENED WHEN: discrete events and durations, not a continuous series.

Choose implementation only after specifying the timing semantics. Apply `diagrams.md` to
evaluate reproducibility, accessibility, label density, and the final viewing size.

## Shared anatomy

- **Time axis**: one axis, one unit, labeled with the unit (`t (ms)`, `UTC`). Ticks mono,
  tabular-nums, ≤7 major ticks. A broken or cropped axis is annotated, never silent
- **Lanes**: one horizontal lane per actor / stage / resource; lane labels short and
  left-anchored; hairline lane separators or none — alignment can carry the lanes alone
- **Duration = bar, instant = marker**: spans render as bars in the lane; instantaneous
  events as a tick or dot with a short mono label. Never stretch an instant into a
  decorative bar
- **Labels and captions**: inherit the terminology, accessibility, and annotation rules from
  `diagrams.md`.

## Waterfall / gantt (cascading spans)

- Order lanes by start time so the cascade reads top-left → bottom-right
- A gap between consecutive bars is information (waiting, queueing) — annotate the gap
  that matters, don't close it up
- When the evidence establishes a critical path, distinguish that chain and annotate the
  span or wait that determines total duration.
- Total duration as a mono label at the cascade's end — the number the reader takes away

## Sequence (actors exchanging messages)

- Lifelines vertical, actors labeled at top; messages as horizontal arrows with short
  labels in the document's code role; time flows down
- Arrow style carries meaning (solid = call, dashed = return) — pick the convention once;
  state it in the caption if both appear
- Collapse uninteresting round-trips (`× N`) — a sequence diagram past ~12 arrows needs
  decomposing, not shrinking

## Incident timeline

- Absolute timestamps (mono, one timezone, stated) — relative offsets hide the 3am-ness
  an incident review needs
- Mark the state-change moments: detection, escalation, mitigation, resolution — these are
  the anchors the postmortem's claims hang on
- Severity uses the report's semantic palette (red/amber/green) as markers or lane tints —
  never a decorative accent
- Annotate the durations between anchors (`detection → mitigation: 43 min`) — the deltas
  ARE the findings

## Don'ts

- Auto-layout that obscures timing, overlap, or message order
- Lane colors or actor icons that add decoration without encoding evidence
- Unlabeled time axis, or mixed units (ms bars on a seconds axis)
- Curved, swooping arrows — horizontal and vertical rules read faster
- Animated playback — this is a static artifact
- A timing diagram with nothing marked — no critical path, no bottleneck, no delta: inert
