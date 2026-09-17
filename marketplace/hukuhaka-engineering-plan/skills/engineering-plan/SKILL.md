---
name: engineering-plan
description: Develop repository-grounded engineering plans for changes involving shared contracts, cross-component dependencies, or material uncertainty. Skip routine changes with an established path.
---

# Engineering Plan

Develop a plan that solves the requested problem in the right place, fits the
existing system, and provides clear direction for implementation. Explain key
decisions and their rationale; leave routine implementation details to the
implementer.

## Ground the change

Understand the requested behavior, constraints, and what must remain unchanged.
Verify facts that could affect the plan against current source code and repository
instructions. Distinguish observed behavior, user requirements, and assumptions.

Trace relevant callers, data flow, ownership, consumers, and sources of
truth far enough to choose the change location and understand its consequences.
Include generation paths when generated artifacts are involved. Further
investigation should answer a concrete question that could change the plan.

Prefer existing concepts and shared implementations when they already own the
behavior. Avoid local workarounds that leave the underlying problem unresolved,
duplicate policy, or introduce abstractions without a concrete responsibility.
Keep changes within the requested scope.

## Make key decisions clear

Describe the intended behavior and why the proposed change belongs where it
does. Ground material changes in specific files or symbols, and explain affected
contracts and consumers.

Resolve choices that determine behavior, compatibility, scope, or shared
responsibilities. Do not prescribe internal helpers or routine details unless
they matter to correctness or coordination.

Order work by dependency. When work is divided across agents or sessions, clarify
shared contracts, ownership, and integration expectations.

Disclose material assumptions and open questions. Use available evidence to
resolve technical questions; ask the user when a remaining choice concerns
their intended outcome or an authorization boundary. For uncertainty that
requires implementation or experimentation, identify how and when to resolve it
before dependent work proceeds.

## Check that the plan can work

Challenge assumptions and boundaries most likely to invalidate the approach.
Trace a concrete example when it helps expose a contradiction or distinguish a
general solution from a patch tailored to the current case. Revise the plan
when evidence contradicts it.

Base verification on the required behavior and actual usage paths.
Use existing checks and valid evidence where sufficient. Add verification only
for a meaningful gap; neither test count nor a passing unrelated suite proves
the change works.

Keep planned checks separate from observed results. State what unavailable
evidence leaves unverified.

## Deliver and continue

Keep the plan proportional to the task. Communicate the proposed change,
key rationale, dependencies, verification, and material open questions in
whatever structure makes them easiest to understand. Do not repeat information
merely to fill a template.

IF the request is planning-only or the host is in Plan mode:
    Keep investigation read-only and deliver the plan.

IF implementation is already authorized:
    Continue into implementation and verification after the necessary planning.
    Pause dependent work only for a material user decision or a required gate.
    Do not ask again for authorization already given.

Planning is complete when subsequent work has enough direction to proceed and
remaining uncertainty has a clear resolution path. Implementation is complete
only when the requested outcome and its required verification are satisfied.
