# Design systems

Use this reference when creating, extracting, extending, or restructuring shared design rules. Reading an existing project system during implementation or review does not itself require redesigning it.

## Scope and starting evidence

Identify the decisions the product needs to share and the problems a system should solve. Inspect representative uses to separate stable conventions, intentional differences, and accidental repetition. A new system can begin with the small set of rules needed for real interfaces; it need not begin with a complete component catalog.

For an existing system, extend its established source of truth unless there is a concrete reason to change ownership. USWDS describes incremental adoption rather than an all-at-once migration. Use that principle of proportional adoption without imposing its maturity levels or government requirements on another product. [USWDS maturity model](https://designsystem.digital.gov/maturity-model/)

## Decision ownership

Keep a rule with the narrowest owner that explains its meaning. Foundations and semantic tokens express shared visual roles; component rules express recurring behavior and appearance; compositions express screen relationships; intentional local exceptions remain local.

Repeated values do not automatically imply shared meaning. Two colors that happen to match today may need to vary independently by state or theme. Conversely, separately named values used for the same role may be evidence of drift rather than useful flexibility.

Document a new shared decision where its consumers already look for guidance. Introduce a dedicated design artifact only when the work needs one. Avoid creating a parallel token file or specification that has no clear update owner.

## Tokens and semantic roles

Choose names and relationships that let consumers express intent without repeatedly recreating styling decisions. Use aliases or semantic roles where that indirection has a purpose; retain direct values when an extra layer adds no useful responsibility.

When token tooling is involved, preserve its supported types, references, and generation path. Check changes at the authored source and the generated consumer; editing only generated output can leave the next generation inconsistent.

The DTCG format describes token data and reference relationships. It is a Community Group specification, not a W3C Recommendation or a prescribed token architecture. Use it when relevant to interoperability, not as a requirement to migrate an existing system to a new format. [DTCG format 2025.10](https://www.designtokens.org/tr/2025.10/format/)

## Components and variation

Define the responsibility that makes a component reusable. Include the behavior and content relationships that must stay coherent, not only its default appearance. Decide which variations express meaningful uses and which arrangements are better handled by composition.

A shared control can own its visual states and interaction contract while a screen owns where it sits. An option-heavy component that encodes unrelated page layouts can make reuse harder. A collection of copied controls with independently drifting behavior has the opposite problem.

GOV.UK's contribution criteria ask whether additions are useful and distinct, and whether they work across relevant contexts. These are useful questions when promoting a local pattern; its contribution process and formal publication gates are specific to that system. [GOV.UK contribution criteria](https://design-system.service.gov.uk/community/contribution-criteria/)

## Evolution and compatibility

Before changing a shared rule, identify the consumers whose appearance or behavior depends on it. Explain whether the change corrects an inconsistency, introduces a supported variation, or replaces an existing decision. Preserve supported behavior and avoid silently reinterpreting an established variant. In code-backed systems, also account for the component's public interface: changing properties, slots, or emitted events can break consumers even when the default appearance stays the same.

Check representative consumers and states that could expose the change's consequences. If consumers cannot migrate together, describe the supported transition and remaining exceptions. Use [design synchronization](synchronization.md) for propagation across design artifacts and [verification](verification.md) for evidence.

## Positive and negative guidance

Promote a local pattern when its semantics and change responsibility are genuinely shared. Do not promote it solely because it occurs twice. Reuse an existing role when it expresses the same intent; do not force an unrelated meaning into it because the current values match.

A system should make decisions easier to reuse and maintain. More tokens, variants, or documentation do not by themselves make it more complete.

## Basis and limits

The ownership and promotion rules are this Skill's design-engineering synthesis. The cited systems provide supporting examples and decision criteria, not a universal architecture or a required dependency.
