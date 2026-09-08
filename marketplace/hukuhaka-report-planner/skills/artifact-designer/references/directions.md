---
role: optional vocabulary for testing or sharpening a reference-free comprehension thesis during artifact design
relationship: an archetype names the LOOK (palette temperature, canvas, accent strategy,
  type class); the Document Model's `form` names the CANVAS (web document / deck / dashboard /
  print/PDF / poster / one-pager). They are orthogonal. Figure validity and implementation
  constraints remain governed by evidence, the selected craft references, and the build contract.
---

## How to use

- Form the document's thesis before opening this file. Use an archetype only when its
  mechanisms help clarify density, voice, surface, color semantics, or anchor treatment.
- Treat names as vocabulary, not presets or menu choices. Record only the useful mechanism and
  a meaningful deviation in `design.md` rather than substituting an archetype name for the thesis.
- User-supplied references and stated preferences override these examples when they remain
  compatible with evidence, accessibility, and medium constraints.
- If combining mechanisms, name only the base and meaningful deviation needed to keep clone
  risk reviewable.
- `suits` lists are guidance, not gates — material and audience can justify other pairings.

## Archetypes

### fintech-crisp
- gestalt: cool-neutral chrome, engineering-tight, data-forward
- canvas / ink: cool near-white / cool near-black
- accent: one electric-cool hue (blue class), scarce; semantic pair for deltas
- type: sharp grotesque + matching mono
- suits: benchmark, dashboard, technical audit, status update
- avoid when: warm editorial material; long-form reading

### swiss-analytic
- gestalt: black-and-white grid discipline; typography carries all hierarchy
- canvas / ink: near-white / near-black
- accent: a single red-class hue, used almost never — once per page at most
- type: neo-grotesque + mono, tight display tracking
- suits: technical audit, engineering writeup, poster
- avoid when: the data needs a rich semantic palette (many status colors)

### paper-technical
- gestalt: warm-neutral engineering paper, mono-forward chrome
- canvas / ink: warm near-white / warm near-black
- accent: one subdued ochre-class hue
- type: humanist sans + mono
- suits: handbook, reference doc, walkthrough, code structure doc
- avoid when: hero-number-led decks; executive summaries

### editorial-warm
- gestalt: cream paper, serif display — a document that reads
- canvas / ink: cream / warm near-black
- accent: single rust/ochre
- type: serif display + grotesque body
- suits: research recap, explainer, long-form review
- avoid when: dashboards, incident reports; any user who has rejected warm looks

### institutional-navy
- gestalt: deep navy sets institutional gravity
- canvas / ink: near-white / near-black, with navy bands and cover
- accent: navy IS the committed hue; deltas use the semantic pair
- type: high-contrast display (serif licensed when the gravity demands it)
- suits: IR/earnings deck, executive brief, quarterly report
- avoid when: personal notes; playful material

### muted-incident
- gestalt: desaturated calm; nothing decorative, severity is the only color
- canvas / ink: cool near-white / desaturated near-black
- accent: none — semantic red/amber/green/grey only
- type: plain grotesque + mono
- suits: incident report, postmortem, risk review
- avoid when: everything else — this is a purpose-built look

### ink-poster
- gestalt: typography-dominant high contrast; inverted bands do the sectioning
- canvas / ink: near-white ↔ near-black inversion per band
- accent: color is secondary; the inversion is the depth device
- type: heavy display grotesque, oversized
- suits: poster, one-pager, cover-led deck
- avoid when: dense tables and long prose

### graphite-dark
- gestalt: intentionally dark, screen-native; one luminous accent
- canvas / ink: dark graphite / desaturated near-white (never pure black or pure white)
- accent: one luminous hue (cyan/green class); semantic colors lifted for dark contrast
- type: grotesque + mono, tabular-nums everywhere
- suits: screen-resident dashboards, monitoring reports
- avoid when: print/PDF; long prose. Design the dark surface deliberately — `craft/color.md`
  forbids auto-derived dark modes

### dense-academic
- gestalt: information-dense, tight grid, small sizes that stay legible
- canvas / ink: near-white / near-black
- accent: one muted accent; figures carry the semantic color
- type: dense humanist sans at small sizes + mono figures
- suits: academic poster, paper review, literature survey
- avoid when: executive audiences; scan-first decks

## Form is orthogonal

The `form` field (web doc / deck / print PDF / poster / one-pager) sets the canvas; the
archetype sets the look. Any pairing is legal. Per-form notes:

- **deck** (slides / ppt-like): one message per slide — slide grammar in `craft/decks.md`;
  scale the hero ladder up (`craft/kpi-tiles.md`); 16:9 margins from `craft/spacing.md`
- **dashboard**: positional stability and state encoding rules in `craft/dashboards.md`;
  `graphite-dark` is a natural pairing, not a required one
- **one-pager**: a single scan surface — every element earns its space; density variation
  (`craft/spacing.md` scan rhythm) matters most here; no cover — the title band IS the identity
- **poster**: section anchors are hero numbers or display type; `ink-poster` and
  `dense-academic` are natural pairings, not required ones
- **print PDF**: apply `craft/color.md` print-contrast rules (≥7:1 body ink,
  greyscale-distinguishable semantics)
- **web doc**: the default; nothing special — cap the measure (`craft/typography.md`,
  `craft/spacing.md`)
