---
name: codex-memory-audit
description: Review Codex local memories for stale, duplicate, or overly specific context when the user requests an audit or a memory-pressure warning suggests one.
---

# Codex Memory Audit

Retain useful context without treating historical details as current facts.
Propose precise, evidence-based cleanup while preserving durable preferences
and lessons. Generated memory files are not an editable source of truth.

## Review relevant context

Follow the current host's memory instructions to locate and inspect memories.
Use available summaries and indexes to identify relevant records, then read only
the supporting history needed to evaluate them. State the scope actually reviewed
and any access limits; do not imply full coverage from a partial review.

Separate durable preferences and lessons from volatile implementation state.
Split a record when its parts require different judgments. Check drift-prone
claims against the user's latest direction and current authoritative sources,
configuration, runtime evidence, or maintained project records.

Do not substitute historical evidence for current verification. When a claim
cannot be verified within the authorized scope, explain the uncertainty rather
than presenting it as current or treating it as disproven.

Measure size when the request concerns memory pressure. A size warning is a
reason to review, not proof of poor quality or permission to modify memories.

## Propose useful changes

Retain supported context that will help future work. Condense valuable experience
buried in episodic detail; replace contradicted claims only with a supported,
durable lesson. Remove duplicate, obsolete, or misleading context and details
with no useful future role. Do not replace one volatile snapshot with another.

Prefer authoritative sources for current values that are cheap to rediscover.
Required repository rules belong in AGENTS.md or maintained project documents.
Exclude secrets and unnecessary personal data.

For each proposed change, identify the source record, explain the reasoning and
evidence, and provide the exact replacement or removal. Keep the proposal within
the requested scope; a complete rewrite of memories or a fixed action taxonomy is
not required. Make unresolved claims and application status clear.

## Apply approved changes

IF the proposed changes are not yet approved:
    Present the concrete change set for approval without applying it.

WHEN the user approves a clear change set:
    Preserve exclusions and corrections; do not request the same approval again.
    Recheck facts that may have changed and would alter the approved action.
    Use the memory update mechanism permitted by the current host instructions.
    If the mechanism records a request or note, report that status rather than
    claiming the generated memories have already been updated.
    If no supported mechanism is available, provide the approved change set
    and explain the unavailable step.

Never manually edit generated summaries, indexes, rollout summaries, or evidence.
Do not alter repositories, Git state, services, or external systems merely to
make a memory claim true. Report only the application results actually observed.
