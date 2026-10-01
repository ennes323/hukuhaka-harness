---
name: memory-audit
description: Review local memories for stale, duplicate, or overly specific context, English wording, and suitable procedural pseudocode when the user requests an audit or a memory-pressure warning suggests one.
---

# Memory Audit

Retain useful context without treating historical details as current facts.
Propose precise, evidence-based cleanup while preserving durable preferences
and lessons. Retained memory should use English, with concise pseudocode for
procedures and conditional behavior where it preserves meaning. Keep facts,
preferences, context, and reasoning in clear prose.

Read memories through the current host's instructions, propose concrete changes,
and submit approved changes only through its supported update mechanism.
Read `references/hosts/codex.md` for Codex or `references/hosts/claude.md` for
Claude Code before locating or updating memory. The adapter identifies editable
native memory and generated evidence; do not infer one host's rules from another.

## Review relevant context

Follow the current host's memory instructions to locate and inspect memories.
Use available summaries and indexes to identify relevant records, then read only
the supporting history needed to evaluate them. State the scope actually reviewed
and any access limits; do not imply full coverage from a partial review.

FOR each memory record within the review scope:
    Separate durable context from volatile implementation state.
    Split parts that require different judgments.

    IF a claim may have drifted:
        Check the user's latest direction and current authoritative sources,
        configuration, runtime evidence, or maintained project records.

    IF a claim cannot be verified within the authorized scope:
        Explain the uncertainty; do not present it as current or disproven.

    IF useful retained content is not in English:
        Propose an English replacement that preserves its meaning.

    IF useful retained content describes a procedure or conditional behavior:
        IF concise pseudocode can preserve its meaning and clarify its actions:
            Propose explicit conditions and actions.
        ELSE:
            Preserve prose and identify any material ambiguity.

Do not substitute historical evidence for current verification. Review only
the requested scope; language or style differences alone do not justify deletion.

IF the request concerns memory pressure:
    Measure the relevant memory size.

A size warning is a reason to review, not proof of poor quality or permission
to modify memories.

## Propose useful changes

Retain supported context that will help future work. Condense valuable experience
buried in episodic detail; replace contradicted claims only with a supported,
durable lesson. Remove duplicate, obsolete, or misleading context and details
with no useful future role. Do not replace one volatile snapshot with another.

Prefer authoritative sources for current values that are cheap to rediscover.
Required repository rules belong in AGENTS.md or maintained project documents.
Exclude secrets and unnecessary personal data.

Write all newly authored audit reports, proposals, replacement memory text,
and update notes in English. Preserve exact source quotes, paths, identifiers,
and commands. Do not translate supporting history.

WHEN drafting a proposed change:
    Identify the source record, reasoning, and supporting evidence.
    Provide the exact replacement or removal.

    IF translating or restructuring retained content:
        Preserve scope, conditions, exceptions, uncertainty, and user intent.
        Use IF for conditions, WHEN for events, and indentation for actions.
        Do not turn a historical observation into a standing rule.
        Do not duplicate the same guidance in prose and pseudocode.

Keep the proposal within the requested scope; a complete rewrite of memories
or a fixed action taxonomy is not required. Leave already suitable content intact.

## Apply approved changes

IF the proposed changes are not yet approved:
    Present the concrete change set for approval without applying it.

WHEN the user approves a clear change set:
    Preserve exclusions and corrections; do not request the same approval again.
    Recheck facts that may have changed and would alter the approved action.

    IF the host provides a supported memory update mechanism:
        Submit the approved changes through that mechanism.
        IF it records only a request or note:
            Report submission, not confirmed memory regeneration.
        ELSE:
            Report only the application result actually observed.
    ELSE:
        Provide the approved change set and explain the unavailable step.

Report the scope actually reviewed and any unresolved claims. Distinguish a
completed review from a partial review, a proposed change from a submitted update,
and submission from confirmed application. Report failed or unavailable steps.

Never manually edit generated memory stores, rollout summaries, or evidence.
Native editable memory indexes follow the host adapter and still require approval.
Do not alter repositories, Git state, services, or external systems merely to
make a memory claim true. Report only the application results actually observed.
