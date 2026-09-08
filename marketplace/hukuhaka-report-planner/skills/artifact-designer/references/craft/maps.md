---
role: optional anchor-selection reference
use_when: evidence has a genuinely spatial pattern — regional variation, site locations, routes, or coverage
do_not_use_when: geography is only a category label — a bar chart or table ranks regions faster and more accurately
style_risk: decorative basemaps and novelty projections turn evidence into wallpaper
---

## When a map earns its place

A map is justified only when the spatial arrangement itself carries the finding: clustering,
adjacency, coverage gaps, distance, or a route. If the reader question is "which region is
highest?", a sorted bar answers it more accurately than a choropleth — position on a map is
harder to compare than aligned lengths. Fewer than roughly five spatial units almost never
needs a map; name them in prose or a table.

## Message type → map form

- **Rate or intensity by region:** choropleth — only for normalized values (rate, share,
  per-capita), never raw counts; large areas otherwise dominate regardless of the data.
- **Discrete sites or facilities:** symbol or pin map; encode a value with symbol size only
  when magnitude comparison matters, and label the sites that carry the finding.
- **Movement or connection:** flow or route map; collapse minor flows so the dominant path
  stays readable.
- **Coverage or reach:** filled service areas with the uncovered gap annotated — the gap is
  usually the finding.

## Encoding rules

- Normalize before coloring. State the denominator in the legend title (`per 1k users`).
- Use an ordered, colorblind-safe ramp for magnitude; reserve the semantic palette for
  state (healthy / degraded), consistent with the rest of the document (`color.md`).
- Class breaks are a claim: state the method (quantile, equal interval, manual) in the
  caption when the break placement changes the reading.
- Strip basemap detail that does not answer the reader question — roads, terrain, and city
  labels beyond the ones the finding needs are noise.
- Label directly on the map where space allows; a legend hunt costs more on a map than on
  a chart.

## Don'ts

- Choropleth of raw counts — area size masquerades as magnitude
- Rainbow or diverging ramps on one-directional magnitude data
- 3D globes, tilted perspectives, or drop shadows — distance and area become unreadable
- A map when only three regions are discussed — name them in a sentence
- Interactive pan/zoom as the only way to see the finding — annotate the static view
- Unstated projection when area comparison is the message
