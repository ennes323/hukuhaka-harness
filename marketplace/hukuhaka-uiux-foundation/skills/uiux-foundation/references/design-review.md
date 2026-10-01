# Design review

Use this reference to explain design problems, compare alternatives, and prioritize improvements. A review should help the next decision; it does not authorize implementation unless the request includes it.

## Review question and evidence

Establish what judgment is being requested and what can be inspected. A screenshot can support visual observations, a prototype can expose some interaction choices, and an application can supply runtime evidence. Keep claims within those boundaries.

Read relevant project design authority as evidence. Reviewing a screen against its design system does not require reading the guide to constructing a system. Use [visual design](visual-design.md), [experience design](experience-design.md), or [design principles](design-principles.md) for the actual criteria.

Heuristic evaluation identifies potential usability problems through informed inspection. It does not demonstrate how real users will perform a task. Keep that distinction when using professional principles or another agent's opinion. [NN/g heuristic evaluation](https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/)

## Observation, interpretation, and preference

Start with an observable condition and connect it to the task. “The action is below the visible content at this width” is an observation; “people may miss it before leaving” is a hypothesis unless behavior has been observed. “I prefer fewer cards” is not sufficient evidence of a design defect.

Distinguish an inconsistency with the established system, a violation of an applicable requirement, and a possible improvement to that system. Existing conventions can be internally consistent yet poorly suited to the task. Explain the difference rather than treating either the current interface or an external guide as unquestionable.

Aesthetic judgment can be legitimate without being a standard violation. Tie it to the intended direction and visible relationships, and name the judgment as such.

## Diagnosis and ownership

Investigate enough context to locate a meaningful cause. Repeated visual symptoms may originate in a shared component, while one awkward region may be a composition problem. Use [application UI](application.md) for implementation causes and [synchronization](synchronization.md) when artifacts disagree.

Do not manufacture a redesign from a bounded alignment review. Conversely, do not recommend scattered offsets when the evidence points to a shared rule. Describe the smallest change that addresses the cause and the consumers it may affect.

For example, a row of equal-weight cards may make unrelated facts appear equally important. The useful finding explains which decision the grouping obscures and a more suitable relationship; it does not merely replace cards with another fashionable pattern.

## Alternatives and tradeoffs

Compare plausible alternatives against the same purpose, content, state, and constraints. Change the dimension that matters to the decision so the comparison is interpretable. Show a small visual comparison when spatial relationships are difficult to explain in prose.

Explain what each option improves and what it costs. Greater density can preserve context but reduce separation; hiding detail can simplify a view but impede comparison. Do not announce a winner solely because an option is more minimal, novel, or familiar.

When the evidence cannot distinguish alternatives, identify the missing observation or targeted user test that would resolve the choice. Do not fabricate research or require a broad research program for a routine reversible adjustment.

## Prioritization

Prioritize by the consequence for the task, the scope of affected users or states when known, and the confidence in the finding. Distinguish a blocked action from added effort and from a local visual inconsistency.

Use severity labels only when they help the recipient act, and explain the reason. Do not invent measured frequency or numerical precision from a screenshot. A systematic issue with a clear cause can warrant attention before many low-impact polish changes.

## Findings and review completion

For material findings, identify the evidence location, the problem, its consequence, and the proposed direction or unresolved decision. Include relevant areas that were inspected without finding a problem when that helps define coverage. Avoid repeating a fixed report template when a short explanation suffices.

Use [verification](verification.md) to support claims about rendered or interactive behavior. If the necessary view, state, or tool is unavailable, continue with the review that the evidence permits and identify what remains unverified. A second reviewer supplies another judgment, not an automatic acceptance certificate.

## Basis and limits

The cited evaluation method supports inspection as a way to identify potential issues. The finding structure, ownership judgment, and prioritization guidance here are this Skill's synthesis. The examples are illustrative and do not establish measured usability or model performance.
