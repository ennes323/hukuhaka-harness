---
role: optional design-direction reference
use_when: the output target is interactive HTML and content depth exceeds one reading pass — considering tabs, accordions, or disclosure
do_not_use_when: the artifact may be printed, exported to PDF, or read as a static page — hidden content simply disappears
style_risk: interactivity used as chrome hides the argument and breaks print, search, and skim reading
---

## Disclosure contract

The default, nothing-clicked state must satisfy the primary reader job on its own. Anything
behind a click is secondary by definition — detail for the second reading, appendix depth,
per-item drill-down. If the finding, a load-bearing anchor, or an acceptance-test target
sits behind interaction, the disclosure design has failed.

Decide the export story first: if the document will ever be printed or PDF'd, either all
disclosed content must render expanded in that medium, or the interactive layer must carry
nothing that matters.

## Form choices

- **Collapsible section (details/accordion):** appendix-grade depth attached to its
  subject — full query text, per-host logs, methodology. The collapsed summary line must
  say what is inside and why one would open it.
- **Tabs:** parallel alternatives of the same shape (per-platform commands, per-scenario
  results). Never sequential narrative — readers do not click through a story, and
  nondefault tabs receive far less attention, so their content must stay supplemental.
  Label tabs with content, not "Tab 2".
- **Hover:** never the sole carrier of any information — it does not exist on touch,
  keyboard, or paper. Acceptable only as acceleration for something also visible statically.
- **Long-document navigation:** a table of contents or section anchor links is low-risk
  interaction that aids wayfinding (`layout.md`); prefer it before any content-hiding
  device.

## Discipline

- Every interactive element must be operable by keyboard and readable by assistive
  technology; a div that looks like a button is neither.
- State must be shallow: one click to any content, no interaction chains, no state the
  reader must remember between sections.
- No motion beyond the disclosure itself; animation that plays while the reader scans is
  competing with the document.
- Interaction never gates comprehension of adjacent static content — collapsed sections
  must not orphan the prose around them.

## Don'ts

- The main finding behind a tab, accordion, or hover
- Tabs for a sequence the reader is meant to follow in order
- Hover-only tooltips carrying evidence, definitions, or caveats
- Scroll-triggered animation or parallax in an evidence document
- Disclosure used to hide how little content exists
- Interactive charts whose static fallback shows nothing
