# Reference index

The artifact designer uses this file only after creating a reference-free comprehension thesis. Select zero to three
craft files that answer a specific unresolved problem. Do not read the directory wholesale.

| Need | Read | Do not use it to decide |
|---|---|---|
| comparison, change, distribution, relationship, composition | `craft/charts.md` | overall page style |
| distribution shape, tails, correlation, two-dimensional grids | `craft/plots.md` | whether the evidence supports a statistical claim |
| events, spans, traces, waterfalls, incident chronology | `craft/timing-diagrams.md` | implementation technology |
| process, sequence, dependency, topology, state | `craft/diagrams.md` | implementation technology |
| lookup, matrix comparison, dense facts | `craft/tables.md` | typography or palette |
| source excerpt, config, command, diff | `craft/code-blocks.md` | document structure |
| central metric or status summary | `craft/kpi-tiles.md` | whether every page needs a large number |
| caveat, evidence note, recommendation, quotation | `craft/callouts.md` | decorative emphasis |
| interface state, rendered output, or tool result as evidence | `craft/screenshots.md` | whether the underlying text should be quoted instead |
| regional variation, site locations, routes, coverage | `craft/maps.md` | whether the evidence is genuinely spatial |
| milestones, roadmap phases, history, plan vs actual | `craft/timelines.md` | implementation technology |
| formula, derivation, threshold, symbolic definition | `craft/math.md` | whether the underlying claim is correct |
| runbook, verification gate, decision procedure | `craft/checklists.md` | document structure |
| source attribution, provenance, data freshness | `craft/citations.md` | whether the evidence itself is sufficient |
| photograph, illustration, icon system | `craft/imagery.md` | decorative emphasis |
| recurring terms, acronyms, appendix boundary | `craft/glossary.md` | document structure |
| entry surface for a deck, poster, or long document | `craft/cover.md` | a mandatory hero layout |
| slide grammar, per-slide density, deck reading distance | `craft/decks.md` | the document job or trunk |
| live status surface, staleness, alert-state encoding | `craft/dashboards.md` | whether the job is really monitoring |
| tabs, accordions, disclosure in interactive HTML | `craft/interaction.md` | the document trunk or the output target |
| semantic color and accessible state encoding | `craft/color.md` | a fixed palette or accent count |
| density, grouping, responsive rhythm | `craft/spacing.md` | exact token values |
| reading voice, hierarchy, numeric or code roles | `craft/typography.md` | a fixed font pairing |
| alignment axes, grid, anchor placement, section wayfinding | `craft/layout.md` | exact grid or column values |
| design-direction vocabulary after a reference-free concept exists | `directions.md` | the document job, structure, or source facts |

## Selection record

For each selected reference, write one compact line in designer-owned `design.md`:

```yaml
reference: <path> — <useful mechanism> · <meaningful deviation>
```

Selected references are bundled craft knowledge, not style targets or templates. They resolve
named representation problems without supplying an artifact's identity, layout, or full
design. Do not record a rationale essay or an empty reference block.
