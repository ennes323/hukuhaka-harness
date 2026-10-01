# Application UI

Translate design intent into an interface that works with the application's actual behavior, content, and constraints. Use the relevant sections to resolve implementation choices in the requested change.

## Scope

This reference covers implementation judgment. Web examples apply to web interfaces; for native interfaces, use the corresponding platform behavior and the project's components. Use [visual design](visual-design.md) when the unresolved question concerns appearance or composition, and [experience design](experience-design.md) when it concerns the intended flow or interaction. Use the project's existing design system as an implementation source; read [design systems](design-system.md) when shared rules themselves need construction or revision. Cross-artifact authority and propagation belong in [design synchronization](synchronization.md).

## Existing implementation context

Start from the affected interface and trace how its appearance and behavior are produced. Establish which decisions come from shared implementation and which belong to this screen. Inspect a relevant neighboring use when the local code alone does not explain an established pattern.

Distinguish an intentional convention from an incidental implementation detail. Repeated code can reveal a pattern, but does not by itself establish that the pattern is suitable. Resolve a conflict with project guidance or design intent before copying it into another screen.

Reuse the existing styling approach and component behavior when they satisfy the task. A visual change is not a reason to replace the framework, component library, or state-management approach. Identify a concrete limitation before proposing a broader change.

## Reuse and component boundaries

Check what an existing component already owns before changing its markup or styling. An apparently simple control may also own keyboard behavior, validation, pending feedback, or focus management. Preserve those responsibilities when changing its appearance. Prefer suitable native platform controls or established project primitives before building custom interaction machinery; check that they support the required behavior.

Use an existing variant when it expresses the intended meaning. Prefer composition for a screen-specific arrangement; extend a shared component when the new behavior or appearance has a coherent reusable role. A local override that depends on another component's internal markup can make a single screen look correct while leaving the shared contract unclear.

For example, extra space between a page title and its actions can belong to the page layout. A new compact control used consistently in dense interfaces may belong to the shared control. Giving every instance its own spacing override or adding a shared variant for one arbitrary offset obscures that distinction.

When changing a shared component, identify relevant consumers and supported variants. Verify the affected behavior beyond the motivating screen, with coverage proportional to the change. If a shared change exceeds the requested scope, keep that decision explicit rather than hiding it in a local exception.

## From design intent to working behavior

Interpret a design as relationships and behavior as well as visual values. Identify which dimensions are deliberately fixed, which depend on content, and which express alignment or hierarchy. A screenshot captures one content set and viewport; it does not specify every layout constraint or interaction state.

For working features, implement controls through the application's supported actions and data flow. Visible affordances need corresponding behavior: selection, sorting, navigation, and submission should produce the effect their presentation promises. Do not add decorative controls or success messages for capabilities the application does not have. Prototype work has the demonstration boundary described under Scope and preservation.

Resolve small unspecified details using established project behavior and the requested outcome. If a missing decision changes the product's interaction or broad design direction and cannot be inferred from available evidence, surface that decision while continuing independent work. Do not turn routine implementation choices into an approval checklist.

For example, a mockup may show a successful save but omit the request in progress. Existing form behavior can supply pending and error treatment. Showing success immediately because it matches the mockup would change the meaning of the action unless the application intentionally supports that optimistic behavior.

## Layout and styling in context

Express layout relationships in the owning container or component. When an element is misaligned, determine whether the cause is its own styling, the parent layout, or inherited typography before compensating at the child. An arbitrary offset can conceal the cause and fail when content or state changes; an intentional optical adjustment is appropriate when its local role is understood.

Use the project's semantic styling rules where their meaning fits. Replacing a semantic surface or text role with a sampled color can break other themes or states even when the current screenshot matches. Introduce or propose a missing role when needed; avoid mapping unrelated meanings together solely because their present values coincide.

Check layout in its actual surrounding shell. Content width, scroll ownership, overlays, and sticky regions can interact across component boundaries. A dialog or menu that works in isolation may be clipped, obscured, or positioned incorrectly in its real container.

## Runtime states and realistic content

Derive the relevant states from the application's actual transitions, including focus, selection, disabled behavior, and validation where applicable. An initial load and a refresh with usable content may need different presentation. No records, no matching results, and failed retrieval communicate different facts; preserve those distinctions when the product supports them.

Keep feedback connected to the action that caused it. Preserve entered values and useful context through a recoverable failure where the existing contract permits. Pending feedback should not silently lose selection, move focus away from the task, or make the result of repeated input ambiguous. Respect the application's established request and state handling rather than adding a competing local mechanism.

Connect form labels, validation, and submission behavior. Error text must explain the relevant problem and be associated with the affected input or action. A disabled action should not be the only indication that something is missing. For native web controls, use the existing disabled behavior when it fits. If an unavailable action needs to stay discoverable in the focus order, consider the appropriate ARIA pattern; aria-disabled alone neither changes focusability nor prevents activation, so do not substitute it without handling the behavior. Recovery messages should offer only actions the implementation can perform.

Use representative content and variation that matter to this screen. Check whether long text, missing media, changing counts, or localized content alter the relationships the layout depends on. Preserve product formatting and the meaning of values: a missing value is not automatically zero, and a shortened label must not conceal information needed to distinguish items.

For example, replacing a variable-length item name with a short fixture may hide an action being pushed out of view. Resolve the content constraint through the intended wrapping, truncation, or layout behavior; do not make the fixture artificially convenient and call the layout complete.

## Responsive and accessible implementation

Adapt the interface to available space and supported interaction methods while preserving the task. Decide what reflows and what remains available from the content and intended experience. A narrower view should not merely hide important information or actions to eliminate overflow. When a different interaction is needed, consult the experience guidance rather than inventing a new flow inside a styling fix.

Check widths where the content stops fitting, as well as the project's target viewports. Account for nested container widths, zoom, and content growth. Keep scroll behavior intentional: horizontal scrolling may be appropriate for a comparison surface, while unexpected page-wide scrolling can make unrelated controls difficult to reach.

Preserve native semantics and established accessible components. A visual restyle should not replace a link or button with an element that only responds to pointer clicks. For web interfaces, use a link with a real destination for navigation and a button for an action; style the appropriate element rather than changing its semantic role for appearance. Keep accessible names meaningful, associate labels and errors with controls, and retain the intended reading and focus order when changing layout. Check keyboard reachability and activation, visible focus, and usable pointer or touch targets in the rendered control.

Consider what happens to focus when content opens, closes, moves, or disappears. A dismissible surface needs a usable dismissal path and an appropriate focus destination. Distinguish restrictions on incidental dismissal, such as backdrop clicks, from trapping keyboard users. Verify a usable keyboard route out and appropriate focus handling; an existing dismissal restriction does not establish accessibility. APG's modal pattern uses Escape, while WCAG's No Keyboard Trap criterion permits other keyboard exit methods under its stated conditions.

Support access to relevant hover content through keyboard interaction, and provide an appropriate interaction for touch users. Additional content shown on hover or focus has conditions for dismissal, hoverability, and persistence under WCAG 1.4.13, with exceptions; do not reduce that criterion to an unconditional Escape rule. Avoid implementing a second interactive copy of a control for another layout unless hidden and visible states, focus, and shared state are handled coherently.

Preserve non-color cues and required contrast across the affected themes and states. Respect reduced-motion behavior in the implemented transition. These are observable behaviors to inspect in the result, not qualities established by adding an ARIA attribute or choosing a nominally accessible library.

## Fonts, assets, and transitions

Verify that the intended font, icon, and image resources actually load through the project's asset path. Fallback font metrics, unexpected image crops, or differing icon bounds can change layout despite apparently correct spacing values. Diagnose those causes before adjusting surrounding geometry.

Keep the surrounding layout usable while resources arrive or fail. Preserve intended media proportions and use the product's fallback treatment where available. Connect animation to real state changes without making access to controls or feedback depend on a decorative delay. The choice of visual treatment belongs to visual design; implementation must preserve its meaning under actual loading and interaction conditions.

## Scope and preservation

Keep design implementation tied to the requested outcome. Preserve application data meanings, permissions, navigation contracts, and unrelated behavior unless changing them is part of the task. If the design cannot be implemented faithfully within those constraints, explain the specific conflict and the decision required.

When the request is for a prototype, make the boundary between demonstrated behavior and real integration clear in the delivery. When it is for a working feature, static fixtures and simulated success are not substitutes for the supported application path. Do not manufacture product capabilities to make an interface appear finished.

## Implementation evidence

Inspect the affected interface in its real context and exercise the behavior changed by the work. Choose evidence that can reveal the likely failure: a layout change needs rendered content variation; an interaction change needs its transitions and focus behavior; a shared component change needs relevant consumers and variants.

Use applicable existing checks and [verification](verification.md) for evidence collection and reporting. A build establishes buildability, not visual fidelity or usability. Reuse still-valid evidence and report the specific coverage or integration that remains unavailable. Success at one state and width establishes only that condition; broader claims need evidence for the relevant variations and affected consumers.

## Basis and limits

Use the relevant sources to resolve a material implementation question, not as a requirement to reread every source for every edit.

- [MDN button](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/button), [links](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a), and [aria-disabled](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-disabled) explain web-control semantics; native disabling and ARIA have different responsibilities.
- [APG modal dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) is an informative interaction pattern. [No Keyboard Trap](https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap.html) and [Content on Hover or Focus](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html) explain specific WCAG criteria and their exceptions.
- [MDN responsive design](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design) supports flexible, content-aware layout. Its examples are not mandatory breakpoint values.
- [Carbon empty states](https://carbondesignsystem.com/patterns/empty-states-pattern/) provides contextual distinctions for missing content and possible next actions. It is not a requirement to copy Carbon presentation.

The component-boundary, preservation, and evidence guidance is the Skill's engineering synthesis. Examples are illustrative, not measured model-performance claims. Consult the target platform and existing library documentation when web examples do not cover the actual interface.
