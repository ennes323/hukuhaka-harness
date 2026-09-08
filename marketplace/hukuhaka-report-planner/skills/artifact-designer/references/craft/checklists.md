---
role: optional anchor-selection reference
use_when: the reader must perform, verify, or decide through discrete steps — runbooks, verification lists, decision procedures
do_not_use_when: the content is narrative or conceptual — bullets that no one will execute are prose wearing checkboxes
style_risk: checkbox styling applied to non-actions turns an executable contract into decoration
---

## When to use

The unit's job is execution: the reader does the steps, in order or as a gate, and can tell
when each is done. If no reader will ever perform or verify the items, it is a list of
points — write prose bullets, not a checklist. The test: every item has an observable
completion state.

## Forms

- **Verification checklist:** unordered gate ("all must hold before X"). Each item is a
  checkable condition, phrased so pass/fail is unambiguous.
- **Runbook:** ordered steps with commands or actions. Each step states the action and the
  expected observable result; a step whose success can't be observed will be skipped or
  botched.
- **Decision procedure:** short branch ("if A → step 3, else → step 5"). Past two or three
  branch points, this is a flow diagram (`diagrams.md`) — nested conditionals in list form
  don't survive contact with a stressed reader.

## Item discipline

- One action or condition per item. "Deploy and verify" is two items with two failure modes.
- Uniform granularity within one list — a 5-second check next to a half-day migration means
  the list's level was never chosen.
- Commands render in the document's code role (`code-blocks.md`) with expected output where
  the reader must compare; destructive or irreversible steps carry their warning **on the
  step**, not in a preamble.
- State the recovery path where a step can fail ("if this fails, see rollback") — a runbook
  that only describes the happy path is half a runbook.
- Number steps that will be referenced or performed under pressure; leave verification
  gates unnumbered when order is genuinely free.

## Don'ts

- Checkbox styling on narrative bullets — pure decoration
- Mixed granularity (one item hides ten steps, the next is trivial)
- Steps without observable completion ("ensure the system is healthy" — how?)
- Warnings after the destructive step they warn about
- A 30-item flat list — group into phases or split; nobody tracks position past ~10
- Deep nested conditionals as indented text — that is a diagram refusing its form
