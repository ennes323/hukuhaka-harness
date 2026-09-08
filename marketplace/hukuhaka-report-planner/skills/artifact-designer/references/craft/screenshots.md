---
role: optional anchor-selection reference
use_when: an interface state, rendered output, or tool result is itself the evidence
do_not_use_when: the underlying text or data can be quoted directly and more legibly
style_risk: unedited screenshot walls shift the work of finding the evidence onto the reader
---

## When a screenshot

Use one when the visual state IS the claim: a rendered layout, a UI defect, a tool's actual
output. If the information is text — logs, config, terminal output — quote it as a code
block (`code-blocks.md`); text stays searchable, legible, and diffable.

## Capture

- Crop to the region that carries the evidence plus minimal orientation context;
  full-desktop and full-window captures bury the finding.
- Capture at native resolution at or above the final display size — an upscaled, blurry
  capture undermines the claim it supports.
- Include browser or app chrome only when the chrome is part of the claim (a URL proving
  the environment, a version in the title bar).
- State capture context in the caption when it affects interpretation: build or version,
  viewport, date.

## Annotation

- Mark the finding: one box or arrow per capture pointing at the evidence; a screenshot
  with nothing marked makes the reader hunt.
- Reserve one high-contrast annotation hue and keep it consistent across every capture. It
  must be distinct from the captured UI's own palette and from the document's semantic
  status colors — a red callout box reads as an error state.
- Redact secrets and personal data before the capture enters the document; prefer solid
  masks over blur (blur can be reversible). Note visible redactions so they do not read
  as defects.

## Accessibility

- Alt text describes the finding, not the pixels ("error banner overlaps the submit
  button", not "screenshot of the app").
- The claim must also exist in the surrounding text; a reader who cannot see the image
  still gets the finding.

## Don'ts

- A sequence of near-identical captures where one annotated capture would do
- Screenshots of text, tables, or code — quote the source instead
- Device frames, drop shadows, or perspective tilts — size without meaning
- Stretching or non-uniform scaling that distorts the captured interface
