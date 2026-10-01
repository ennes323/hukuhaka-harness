---
name: hukuhaka-paseo
description: Coordinate implementation, investigation, review, writing, or UI/UX work delegated through configured Paseo roles. Use for Paseo role coordination; ordinary Paseo administration uses the upstream paseo Skill.
---

# Hukuhaka Paseo

Use role specialization when it reduces the combined cost of doing, briefing,
reviewing, and correcting the work. Main remains accountable for the user's
outcome; children own bounded outcomes and choose their methods within them.
Small or tightly coupled work can stay with Main.

## Main and role selection

Main owns user requirements, material decisions about scope and authority,
allocation, final acceptance, Git, Worklog, and external actions. Workers may
make implementation judgments and edit assigned files within the authorized
scope. Keep unrelated changes intact and avoid overlapping write ownership.

Use the upstream `paseo` Skill for current profile discovery, launch settings,
workspace placement, follow-ups, and lifecycle behavior. For a second opinion,
reuse `paseo-advisor`. This package supplies coordination guidance; it does not
intercept runtime calls or guarantee that a child loads a Skill.

```text
IF delegation has a bounded outcome and useful independent work:
    Read the configured profiles and their notes through the paseo Skill.
    Honor an explicit user choice of role, profile, model, or effort.
    Otherwise select the role that fits the outcome.
    For an advisor, prefer advisor-claude when Main uses Codex,
        or advisor-gpt when Main uses Claude.
    Read only that role's block in references/roles.md.

IF the requested profile or provider is unavailable:
    Report the limitation and keep its work local within Main's capability
        and authority.
    Do not silently replace an explicit user model choice.

IF the default opposite-family advisor is unavailable:
    Report cross-family review as unavailable rather than silently choosing
        a same-family advisor. An explicit user override takes precedence.
```

The configured profiles are launch defaults, not evidence of model availability
or actual execution. The Paseo `designer` role owns UI/UX work.
Report Planner's artifact designer is a separate workflow with its own spec
and design contract; this role does not replace it.

## Brief and reconcile

Use the project's existing assignment and result protocol when one applies.
Otherwise give the child the objective, necessary context and source locations,
owned files or responsibilities, constraints, completion criteria, and evidence
needed for Main's next decision. Reuse the parent protocol rather than adding
a second result schema.

Include Shared child rules and the selected role rule from
[roles.md](references/roles.md) inline in the initial briefing.
The child need not discover or load this plugin; this also
supports an Antigravity writer. Give the child sufficient context to act
independently without pre-solving its assigned problem.

```text
WHEN a child returns:
    Reconcile its decisive evidence, changed paths, checks, and named gaps
        against the assignment before accepting the result.
    Keep command success, assignment completion, and Main's acceptance distinct.
    Reuse valid evidence without repeating completed work.

IF evidence is partial, contradictory, or unavailable:
    Resolve collectable gaps within scope, preferably with a targeted
        follow-up to the same child; report remaining uncertainty.
```

Main delivers the integrated outcome and its verification state. A running job
or missing child result remains pending; an advisor recommendation alone does
not establish implementation or acceptance.
