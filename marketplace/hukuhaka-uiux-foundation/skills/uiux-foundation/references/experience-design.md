# Experience design

Use this reference to decide how people find information, act, and understand what happened. It applies to a new flow and to diagnosis of friction in an existing one. Use [visual design](visual-design.md) for expression and [application UI](application.md) for runtime realization.

## Information and navigation

Organize information around the task and the concepts people need, rather than exposing the application's internal data model by default. Keep related choices together and make the current location, active scope, and available next actions understandable.

Choose whether information needs scanning, comparison, exploration, or a sequence of decisions. Those purposes can call for different navigation and disclosure. Hiding advanced detail can simplify an initial view, but hiding information required for the current decision forces guessing or repeated navigation.

For example, filters should make the scope of the visible results understandable. A view that silently retains a filter can suggest that records are missing; an active-filter indication and a relevant way to change it clarify the situation. The exact presentation depends on the product.

## User flows and control

Follow the task from its entry condition to a meaningful outcome. Include interruptions or recovery paths that the product actually supports. Establish what state should survive going back, changing a choice, or encountering failure; do not assume every action resets the experience.

Make the consequence of an action understandable before commitment. Choose supported correction, cancellation, recovery, or confirmation according to reversibility, the cost of a mistake, and the effort of recovery. A confirmation on every harmless action can add friction without clarifying anything.

Nielsen's heuristics connect feedback, familiar language, user control, and recovery to usability. Use them as prompts to examine a flow, not as proof that a particular layout or fixed step count is correct. [NN/g usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)

## States and feedback

Decide what the user needs to understand at a transition: whether an action was accepted, whether work continues, what changed, and what can happen next. Keep feedback close to its cause when that relationship would otherwise be unclear.

Absence of content can have different meanings. Initial setup, a query with no matches, and a retrieval problem can call for different explanations and actions. Carbon provides contextual empty-state patterns; use the distinction, while choosing content that is accurate for this product. Do not add an action simply because an empty-state template has a button. [Carbon empty states](https://carbondesignsystem.com/patterns/empty-states-pattern/)

Use blocking feedback when continuation would be invalid or misleading. Preserve useful context when only part of a view is unavailable. A visually complete success state must not imply that an unconfirmed action has finished; implementation details belong in [application UI](application.md).

## Content and language

Use labels that describe the actual object or effect. Distinguish controls with different consequences even if a short generic label would make the layout tidier. Place instructions where they inform the decision or input, and associate errors with what needs correction.

Treat the data's meaning as a constraint. An unknown result, an estimate, and a measured value should not become interchangeable in the interface. Represent a missing value accurately rather than choosing a convenient substitute.

Adapt language to context and audience. Preserve useful domain terminology where it carries precision; explain unfamiliar concepts where understanding is required. Avoid invented promotional claims, fake counts, or reassuring messages unsupported by behavior.

## Accessibility and different environments

Consider how the intended task works with keyboard, touch, assistive technology, magnification, and other relevant input or presentation modes. Retain access to essential information and actions when hover, fine pointing, or motion is unavailable.

Use the target platform's interaction conventions and applicable accessibility requirements. Web patterns are not a complete native-platform specification. APG explicitly notes limits in its mobile/touch compatibility guidance, so validate the combinations the product actually supports. [APG applicability](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)

A change in available space may require a different arrangement or disclosure, but it should retain the task's meaning. If adaptation materially changes the flow, make that design decision explicit instead of treating it as an incidental styling adjustment.

## Positive and negative guidance

Show the meaningful consequence of a choice, rather than requiring people to discover it after commitment. Preserve enough context for recovery, rather than displaying an error and discarding work unnecessarily. Explain why an action is unavailable where that reason matters, rather than relying on an unexplained inactive appearance.

These are contextual judgments. Do not prescribe always-enabled submission, always-disabled submission, or confirmation for every destructive-looking control without understanding the actual consequence.

## Basis and limits

This is a synthesis of the cited usability and interaction guidance with product-contract reasoning. The examples are illustrative. A walkthrough can reveal plausible friction; claims about actual user comprehension or success need suitable user evidence.
