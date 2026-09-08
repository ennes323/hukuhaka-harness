---
name: worklog
description: Use automatically when a project has .hukuhaka/work.md and .hukuhaka/changelog.md and the user starts, resumes, pauses, completes, or abandons non-trivial project work, even if they do not mention Worklog. Also use for explicit requests to record or change work state. Do not use for analysis-only requests, implementation planning, routine one-off edits, mechanical setup/status/archive commands, or issue-tracker synchronization.
---

# Worklog

Use `.hukuhaka/work.md` for current work and `.hukuhaka/changelog.md` for completed or closed history. Never read, migrate, or write a legacy `backlog.md`.

## Orient the session

When both Worklog files exist, read `work.md` before changing project files for the first non-trivial project task in a new session. Read `changelog.md` only when resuming, completing, closing, or checking a prior decision. This orientation does not by itself authorize a Worklog update.

## Manage lifecycle

1. If the user explicitly asks to record or change Worklog state and either file is missing, stop and ask them to invoke `$hukuhaka-worklog:worklog setup` in Codex. For automatic use, missing files do not block the underlying task: continue without creating or changing Worklog files. If a setup command reached the model instead of the hook, tell the user to open `/hooks`, review and trust the worklog hook, then retry; do not emulate setup in the Skill.
2. Read both files and identify an existing matching item before adding a new one. Preserve the user's language and do not invent IDs, priorities, owners, or schedules.
3. Reread the relevant entries before writing. Uncommitted, staged, or untracked status alone must not block a lifecycle update. Preserve existing notes and unrelated entries while adding or updating the matching item; never stage, commit, stash, reset, or discard changes just to write Worklog. If the same item's meaning or user intent still conflicts with the update after considering the latest request and evidence, leave that item unchanged and report the exact conflict; independent items may still be updated. If the file changed since it was read, reread and reconcile instead of overwriting it. Report malformed records and read/write failures explicitly without claiming the affected update succeeded.
4. Only the primary agent changes Worklog state. Delegated agents may read it for context but must not modify it.
5. Inspect the code or evidence needed to make the wording factual. Use at most three focused search rounds; pure ideas do not need a code anchor.
6. Choose the state from the observed intent:
   - active now → `In Progress`
   - intended but not active → `Planned`
   - intentionally paused or waiting on a condition → `On Hold`
   - finished with evidence → completed changelog entry
   - intentionally not pursuing → closed changelog entry
7. For completion or closure, write the changelog first and remove the current item second. Then resolve the bundled `scripts/worklog.py` relative to this Skill and run it through the host's Python interpreter as `<python> <script> --root <project-root> archive`. Run it after every successful completion or closure: it is a no-op while Recent has at most 25 entries and otherwise moves the oldest entries to monthly archive files. Never hand-edit those archive files. If the command fails, keep the lifecycle update, report the exact failure, and leave recovery to the same idempotent command.
8. Report the exact item, state, archive result, and files changed. For an applicable lifecycle request, explicitly say whether the record was updated, no update was needed, or recording was blocked, with the reason. Completing the underlying task does not mean a blocked Worklog update succeeded.

Ask one concise question only when different state choices would materially change the record.

## Write the files

Record completion from the requested outcome and its required evidence, not
from a finished plan, a successful build, or a child's completion message alone.
Preserve required checks that failed or remain unverified. Reuse valid product
verification when recording work; a Worklog edit is not a reason to repeat
unchanged product tests. Only the primary reconciles final acceptance and writes
lifecycle state.

Keep exactly these `work.md` sections:

```markdown
## In Progress
## Planned
## On Hold
```

Start every current item with one top-level list line. Indent optional evidence, next gate, action, or reconsideration condition beneath it. Planned work needs a current fact or purpose and one concrete next action. In Progress needs verified current state and the next gate. On Hold needs the pause reason and an observable reconsideration condition. Do not keep completed or closed items in `work.md`.

Start every history entry under `## Recent` with:

```markdown
### YYYY-MM-DD — Short title
```

Put the newest entry first. Completed entries state the result, verification, and any material caveat. Closed entries state the decision, reason, and a concrete `Reopen when` condition. Do not impose IDs, priority tiers, fixed owners, or a rigid field order.
