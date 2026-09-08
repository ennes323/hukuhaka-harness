---
role: optional anchor-selection reference
use_when: a long handbook or explainer carries recurring specialized terms, unavoidable acronyms, or needs an appendix boundary
do_not_use_when: fewer than roughly eight terms recur — first-use definitions in the flow serve the reader better than an apparatus
style_risk: a glossary used as a dumping ground signals that the document never chose its audience
---

## First-use beats apparatus

The default tool is a first-use definition in the flow: define the term in a clause the
first time it appears, or in a margin note (`callouts.md`). A glossary earns its place only
when terms recur across distant sections and the reader may enter mid-document — a
handbook, an onboarding guide, a reference the audience will dip into rather than read
linearly.

## Term discipline

- One canonical term per concept, used identically in prose, anchors, diagram labels, and
  code excerpts. If sources disagree, the document picks one and notes the alias once.
- Expand every acronym at first use even when a glossary exists; the glossary is a safety
  net, not permission to write in acronyms.
- Define terms the way this document uses them, in one or two sentences — not the general
  dictionary meaning. If the document's usage differs from the field's common usage, say so
  in the entry; that divergence is exactly what trips readers.
- Every glossary entry must actually appear in the document, and every recurring
  specialized term should have an entry — an incomplete glossary is worse than none,
  because the reader stops trusting it exactly when they need it.

## Appendix boundary

- The appendix holds material a minority of readers need for verification or depth: full
  data tables, extended derivations (`math.md`), raw excerpts, methodology. The main body
  must stand alone without it.
- Nothing load-bearing moves to the appendix — if a claim's only support lives there, the
  claim is under-supported where it is made.
- Each appendix section is referenced from the body at the point of relevance ("full query
  in Appendix B"); an unreferenced appendix is dead weight.
- Keep appendix formatting at the same quality bar as the body — it is where skeptical
  readers go, which makes it the wrong place to get sloppy.

## Don'ts

- A glossary for a five-page memo with three technical terms
- Entries for terms the document never uses
- Circular definitions ("orchestrator: the component that orchestrates")
- Different labels for one concept across prose, diagram, and table
- Load-bearing evidence exiled to the appendix
- Alphabetizing as organization when the reader would be served by grouping
