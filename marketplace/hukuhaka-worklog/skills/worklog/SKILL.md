---
name: worklog
description: Maintain ongoing progress in .hukuhaka/work.md and record work outcomes in .hukuhaka/changelog.md. Use automatically throughout project work when these files exist, or when explicitly asked to update Worklog.
---

# Worklog

Keep enough working memory for another session to understand the
work, continue it, and avoid repeating discarded approaches.

Write all new or updated records in English. Preserve unrelated
records; do not translate existing history as a separate task.
Only the primary agent updates these files.

IF either Worklog file is missing:
    Skip recording and continue the underlying task.
    IF recording was explicitly requested:
        Explain that `$hukuhaka-worklog:worklog setup` is needed first.

## Read existing context

Read `work.md` to understand current progress before starting or
continuing project work. Consult relevant `changelog.md` entries
when past outcomes or decisions matter.

## work.md

Maintain `.hukuhaka/work.md` as the current working context:
the objective, progress, useful findings, and remaining work.

Keep these sections:

- `## In Progress`
- `## Planned`
- `## On Hold`

Use top-level bullets for work items. Add nested steps and notes
when useful, including completed substeps, attempted approaches,
decisions, blockers, and the next action. Keep enough context to
resume without reconstructing the conversation.

WHEN meaningful progress or understanding changes:
    Update the matching item and relevant substeps.
    Reconcile outdated notes rather than appending contradictions.

WHEN work pauses or is handed off:
    Save the current position and what is needed to continue.
    Use On Hold when work is intentionally paused or blocked;
    a session ending alone does not change the work's status.

WHEN work is completed or intentionally closed:
    Record the outcome in changelog.md.
    Then remove the finished item from work.md.

## changelog.md

Maintain `.hukuhaka/changelog.md` as a useful history of the work,
including intermediate checkpoints, significant decisions,
completed work, and work stopped before completion.

Capture what happened, why it matters, and what was learned.
Include implementation, investigation, experiments, tests, or
limitations where relevant. Make partial and unverified outcomes
clear without imposing the same fields on every entry.

WHEN a meaningful outcome or checkpoint is worth retaining:
    Add or update a related entry.
    Keep unfinished work in work.md with its current context.

Keep entries newest first under `## Recent`, using:
`### YYYY-MM-DD — Short title`

Prefer concise explanations and durable references. Include paths,
commands, or measurements when they help someone resume or verify
the work; avoid incidental details that will quickly become stale.

Monthly archiving is handled by the plugin's hooks.
Report recording failures without claiming the records were updated.
