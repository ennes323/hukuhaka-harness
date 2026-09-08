---
role: optional anchor-selection reference
use_when: quantitative evidence concerns distribution shape, tails, relationships, or a two-dimensional value grid
do_not_use_when: one value, ranking, or trend answers the reader question more clearly
style_risk: statistical form can imply rigor that the sample size, fit, or aggregation does not support
---

## When a plot (not a chart)

Charts (`charts.md`) carry ranking, trend, and composition messages. Reach for a
statistical plot when the message is about the SHAPE of the data: how values spread
(distribution), how two metrics move together (relationship), or how a value varies over a
2-D grid. If the message is a single comparison ("A is 2.3× B"), a bar or a KPI carries it
better — plot the shape only when the shape IS the finding.

## Histogram

- Choose bins from sample size and resolution; state the bin width in the axis label
  (`Latency (ms), 5 ms bins`) when it materially affects interpretation.
- Bars touch (0–1px gap) — the variable is continuous; gapped bars read as categories
- y-axis is a count or a share — label which
- Annotate the mode, the tail, or the outlier cluster — whichever carries the finding
- Two distributions: overlay as outline + low-opacity fill pair, or split into small multiples — never interleaved bars

## Box plot vs jittered dots

- Use a box plot only when each group has enough points for a summary to be meaningful;
  otherwise show the actual observations with jittered dots or a strip plot.
- State the whisker convention in the caption (e.g. `whiskers: 1.5×IQR`) — conventions
  differ and silent ones mislead
- Overlay raw points on the boxes at low opacity when n permits — the box summarizes, the
  dots keep it honest
- Avoid smoothed density when the sample cannot support it. Prefer box plus raw points when
  that exposes the evidence more honestly.

## Percentile / CDF curve

- The benchmark staple: latency or duration tails. Mark p50 / p95 / p99 with hairline
  rules + mono labels
- Log-scale the value axis when the tail spans decades; annotate the scale (`// log scale`)
- Multiple configurations require distinguishable encodings and direct labels where space
  permits; split into small multiples when overlap defeats comparison.
- A percentile curve with no marked percentile conveys no finding — mark the one the claim
  rests on

## Scatter

- Both axes labeled with units; tabular-nums on ticks
- Use small multiples when multiple series obscure the relationship (`charts.md`).
- Trend line only when the report makes a correlation claim — a fitted line on a cloud
  invites a conclusion the data may not support; if drawn, name the fit (`OLS`, `LOESS`)
- Label the outliers that matter, not every point — full labeling is noise, zero labeling
  hides the finding
- Point size as a third variable (bubble) only with a size legend; otherwise fix the size

## Heatmap

- Color scale: single-hue sequential (light = low, dark/accent = high). Diverging two-hue
  only when the data has a meaningful midpoint (zero delta, baseline) — and mark that midpoint
- Avoid unordered rainbow scales for ordered values; use a perceptually ordered scale.
- Print values in-cell when the grid remains legible at the target size; do not make color
  the only way to recover exact values.
- Order rows/columns by a meaningful key (magnitude, cluster), not alphabetically —
  ordering is where the pattern appears
- Annotate the cell or region the finding lives in

## Don'ts

- Smoothed density on a sample too small to support the apparent shape
- Histogram with gapped bars — reads as categorical
- A box plot that hides a very small group size instead of exposing the observations
- Scatter trend line without a stated fit — pseudo-rigor
- An unordered heatmap scale that obscures magnitude order
- Percentile plot without marked percentiles — no finding
- 3-D surface plots of any kind — chart-junk with occlusion
- Dual y-axes — that is two plots, not one
