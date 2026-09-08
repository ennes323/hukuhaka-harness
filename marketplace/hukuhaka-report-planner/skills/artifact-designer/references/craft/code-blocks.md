---
role: optional anchor-selection reference
use_when: code, configuration, logs, commands, or diffs are primary evidence
do_not_use_when: prose or a structured table communicates the finding more directly
style_risk: long excerpts shift the reader's task from understanding to reverse engineering
---

## When code belongs

- Use a code anchor when exact syntax or ordering supports the claim.
- Use a diff when the reader question is what changed.
- Use a log excerpt when sequence, timestamp, or exact error wording matters.
- Use prose or a table when syntax itself is not evidence.

If the snippet exceeds 15 lines, it likely belongs in an appendix or external link. The body should show the diff or the critical 3-5 lines.

## Representation

- Preserve exact text and whitespace when they are evidentiary.
- Include filename, location, command, or source context.
- Highlight only the lines or tokens discussed by the surrounding explanation.
- Plan wrapping, scrolling, or excerpting for the target medium.
- Syntax highlighting is optional and must not obscure the cited evidence.

## Line numbers

Use line numbers only when the surrounding text or review workflow refers to them.

The builder decides typography and surface treatment from the document's design direction.

## Don'ts

- 20+ line code blocks in body — break into 3-5 line excerpts with prose between
- Long lines that wrap — adjust measure or use horizontal scroll with caption marker
- Syntax highlighting that distracts from the finding — strip the syntax
