---
role: optional design-direction reference
use_when: the form is a dashboard or reading behavior is live, and stability, staleness, or alert encoding is unresolved
do_not_use_when: the artifact reports on a moment in time — that is a document with charts, not a monitoring surface
style_risk: dashboard grammar (tile grids, status chips) leaking into documents forces monitoring aesthetics onto narrative jobs
---

## Live reading contract

- A dashboard is re-read: the reader knows yesterday's layout and scans for what changed.
  Positional stability is the interface — reordering or moving elements between visits
  destroys the comparison the reader is performing.
- Order by decision priority, not data availability: the metric that wakes someone at 3am
  sits first on the scan path.

## State encoding

- Every value that can go stale shows its freshness (last-updated or refresh cadence); a
  stale number that looks live is worse than no number.
- Design the empty, loading, error, and no-data states — a live surface meets them daily.
  `0`, `no data`, and `collection failed` are three different facts and must render
  differently.
- Alert states use the semantic palette with a label or icon, never color alone
  (`color.md`); the healthy state must be visibly quiet so the alert state can pop.
- Show each value's threshold or baseline; a bare number forces the reader to remember
  whether 87 is fine.

## Density

- Uniform density beats scan rhythm here (`spacing.md`): monitoring rewards a consistent
  grid the eye can sweep in one pass, not editorial variation.
- A dark surface must be designed for the medium, not derived by inversion (`color.md`).

## Don'ts

- Motion or live-update animation that defeats comparison between glances
- A hero number whose definition, window, or threshold lives somewhere else
- Gauges and dials — a number with its threshold reads faster and smaller
- Celebratory or alarming decoration; severity is the only drama a monitoring surface needs
