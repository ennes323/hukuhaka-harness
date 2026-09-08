---
role: optional anchor-selection reference
use_when: evidence concerns process, sequence, state, dependency, topology, or spatial relation
do_not_use_when: a list, table, or prose sequence answers the reader question more directly
style_risk: one diagram grammar repeated across domains creates visual convergence
---

## Representation choice

Choose the representation after identifying the relationship and expected takeaway. A
hand-authored SVG, diagram library, Mermaid source, HTML/CSS layout, canvas, or static export
may be appropriate depending on complexity, reproducibility, accessibility, and medium. The
designer chooses within the spec's explicit user constraints.

Flow-with-quantity diagrams, swimlanes, and event/duration timelines belong to this family
when their relationships answer the reader question. For events and durations on a time axis,
use `timing-diagrams.md` to specify the timing semantics before choosing implementation.

## Structural requirements

- Define what nodes, edges, regions, states, and direction mean.
- Preserve labels at the final viewing size.
- Make reading order and entry point visible.
- Encode critical paths, changes, or exceptions only when supported by evidence.
- Decompose or provide progressive disclosure when one surface cannot remain legible.

## Labels

- Use terminology from the verified source material.
- Label relationships whose meaning is not obvious from position or direction.
- Include units and time semantics for quantitative labels.
- Avoid relying on color or line style alone.

## Annotation

Annotate the critical path, bottleneck, changed component, or entry point when it answers the
reader question. Exploratory topology diagrams may support lookup instead of one finding.

## Don'ts

- Decorative nodes or dimensions that imply unsupported meaning
- Animation that prevents scan, comparison, or accessible fallback
- Leader lines crossing each other to reach labels outside the figure — restructure the layout
