---
name: engineering-plan
description: Plan non-trivial implementation involving multiple layers, public APIs, CLIs, schemas, migrations, risky refactors, or coordinated verification. Use automatically as a planning phase within implementation requests, and for explicit engineering planning or Plan mode. Do not use for routine local edits, visual-document planning, or hukuhaka-codex plan/full workflows.
---

# Engineering Plan Protocol

Produce a repository-grounded, decision-complete plan that another engineer or
agent can execute without making hidden product or implementation decisions.

## Planning phase boundary

This skill governs the planning phase, not the entire user task. Planning is
read-only: do not modify workspace files, generate artifacts there, or perform
Git or lifecycle mutations during this phase.

For an explicit planning-only request or host Plan mode, return the plan without
implementation. Within an authorized implementation request, once the plan is
sufficient and applicable approval gates are satisfied, exit this skill and
continue implementation and required verification. A plan is not completion of
an implementation request.

Disclose routine implementation assumptions without blocking work. Pause for
unresolved decisions that materially change requested behavior, scope,
compatibility, or operational effects. Follow the user's latest scope and
applicable authorization rules; this skill grants no additional permissions.

## 1. Ground the plan

- Read every applicable repository instruction before planning.
- Inspect the implementation, tests, generated sources, documentation, and
  repository commands that can affect the requested outcome. Further inspection
  must resolve a concrete question that can change the plan or its correctness.
- Inspect Git state and branch ancestry when worktree safety or multi-branch
  execution matters.
- Prefer discovered facts over questions. Ask only about product choices or
  tradeoffs that inspection cannot resolve.
- Never invent a file, symbol, command, test, or line number.

Keep three evidence classes distinct:

- **Confirmed** — explicitly requested or approved by the user.
- **Verified** — observed in the current repository or environment.
- **Assumed** — a disclosed default selected because the first two are silent.

Do not ask the user to reconfirm confirmed decisions.
Treat every implementation-shaping choice that is neither Confirmed nor
Verified as Assumed, including conventional defaults. Do not silently promote
it to Confirmed or omit it from the final status.

## 2. Close the impact surface

Start from the requested observable behavior and identify verified change
seeds: entry points, symbols, routes, schemas, persisted state, configuration,
or generated sources. Trace the applicable:

- definitions and direct callers;
- transitive consumers whose behavior or contract can change;
- sources of truth and generated projections;
- tests, documentation, migration, deployment, and operational paths.

Classify each discovered surface as:

- **Change** — implementation must change;
- **Verify** — behavior may be affected but no edit is currently required;
- **Unaffected** — inspected and excluded with a concrete reason;
- **Unresolved** — the repository cannot establish the relationship or behavior.

Record the file or symbol and evidence establishing each material relationship,
and state the inspection boundary. Do not call the impact surface closed while a
repository-discoverable caller, consumer, source-of-truth, or generation edge
remains unresolved. If an unresolved edge can change the contract or
implementation, mark the plan Blocked.

## 3. Define the contract

Define observable behavior before proposing file changes. Cover only dimensions
that materially apply: public interfaces, input/output shapes, null and missing
semantics, ordering, state transitions, errors, exit codes, compatibility,
partial results, read-only guarantees, accessibility, and security boundaries.

For API, CLI, schema, persisted-state, or finite-state changes, read
[references/contract-checklist.md](references/contract-checklist.md). Use a truth
table when a finite set of combinations would otherwise remain ambiguous.

Separate required work from non-goals and deferred work. When requirements
conflict, demonstrate the conflict and expose only the viable decisions.

## 4. Construct the change plan

Order changes by dependency. For each material slice, identify:

- the requirement or contract row it satisfies;
- the current flow and evidence at a verified file or symbol;
- the exact behavior, shape, signature, state, or data-flow delta;
- affected downstream consumers and invariants that remain unchanged;
- files or symbols to change versus verify only;
- tests or runtime evidence and the expected result;
- the exact verified gate that closes the slice.

Express each slice as
`current evidence → exact delta → downstream effect → verification`. Do not use
placeholders such as "update the schema", "adjust the client", or "add tests"
when the implementer would still need to choose the behavior. Separate
behavior-preserving refactors from new behavior when that improves
reviewability. Keep branch, commit, migration, and rollout ordering feasible in
the observed repository.

Reuse observed repository test infrastructure and commands. If no existing gate
can prove a material requirement, propose the smallest new test or harness as a
planned delta, verify that its runtime or dependency exists, and do not describe
the future command as an already verified repository gate. Do not add a file,
tool, or documentation solely to satisfy the plan format.

## 5. Try to break the plan

For each material identity or invariant, construct at least one concrete
boundary or adversarial example and calculate or trace the expected result.

Read only the applicable sections of
[references/adversarial-checklist.md](references/adversarial-checklist.md):
numeric, temporal, filesystem/state, scale, or integration.

Classify every failed invariant as:

- resolved by revising the implementation or contract;
- accepted with explicit user-visible behavior;
- blocked on a product or architecture decision.

Revise the main plan after this audit. Never leave a stale plan in place and
bury its contradiction in a risk list.

## 6. Design verification

Map every material requirement to evidence:

- test level and fixture or scenario;
- exact expected result;
- verified repository command;
- manual or runtime check when automation cannot prove it.

Include before/after evidence for read-only or state-preservation guarantees.
Distinguish unit, contract, integration, generation-drift, build, and live-host
checks instead of treating one passing suite as universal proof.

## 7. Publish the revised plan

Use the host's native plan envelope and interaction rules. Do not impose a
Claude- or Codex-specific wrapper from this skill.

Keep the output proportional: summarize repeated evidence instead of restating
the same contract in the impact surface and every slice. Include:

- readiness and the decisive reason;
- confirmed work and non-goals;
- the closed impact surface and its inspection boundary;
- contracts and invariants;
- dependency-ordered implementation;
- verification evidence;
- assumptions and blockers.

Close the planning phase with one status:

- **Ready** — no unresolved contract or implementation decision remains.
- **Ready with assumptions** — only disclosed routine implementation defaults
  remain; no unapproved material behavior, scope, compatibility, or operational
  decision is hidden in an assumption.
- **Blocked** — implementation requires such an unresolved material decision
  or an unmet required gate.

For an implementation request, `Ready` and `Ready with assumptions` lead back
to the authorized implementation workflow when applicable gates are satisfied.
Only a material unresolved decision blocks dependent work; routine disclosed
assumptions do not create a new approval gate. Keep the plan and handoff
proportional to the task rather than repeating every planning section.

Do not mark the plan Ready when requirements are mathematically or behaviorally
incompatible, public failure semantics are missing, referenced repository facts
were not verified, the impact surface is not closed, or the implementer would
still need to choose the behavior.
