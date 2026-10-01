# Visual design

Use this reference to compose an interface or assess how its visual choices work together. Reuse the project's established visual language while resolving the decisions needed by the task.

## Composition and hierarchy

Organize the view around relationships in the content. Determine what should be noticed first and how supporting information connects to it. Scale, contrast, placement, and grouping can reinforce that order; competing signals can make every element appear equally important.

Proximity can imply a relationship even without a container. Check whether spacing groups the correct label, value, control, and explanation. An arrangement can be mathematically regular yet communicate the wrong grouping. These principles describe perception, not a required number of sizes or colors. [NN/g visual principles](https://www.nngroup.com/articles/principles-visual-design/)

Choose presentation from the information relationship. Aligned attributes can help comparison; independently browsed items may benefit from cards. Do not put unrelated facts into equal cards merely to fill a grid. Use representative content before deciding that the composition works.

## Density, spacing, and alignment

Set density according to what must remain visible together and how the interface is used. Large gaps can separate unrelated work, but may also push comparison targets or controls out of view. Compact layouts can support frequent work while still needing clear grouping and usable interaction targets.

Use established spacing relationships as a starting point. When an edge or baseline looks wrong, distinguish the layout box from the visible shape and the text metrics. An optical adjustment can be appropriate; it should not conceal a parent layout or asset problem. Use [application UI](application.md) for diagnosis in the rendered implementation.

Preserve rhythm across related sections while allowing differences that communicate hierarchy. Do not force equal heights or symmetric layouts when content and intended emphasis make those relationships misleading.

## Typography and color

Give text roles distinguishable emphasis without using every available styling dimension at once. Check actual labels, numerals, longer reading passages, and the fonts that will render. Reducing text contrast to make it secondary can undermine legibility; use spacing, position, or relative emphasis as well.

Carbon distinguishes task-focused and expressive typography, and describes circumstances where they can coexist. This supports choosing type treatment by the moment of use, not importing Carbon's font, scale, or fixed pairings into another system. [Carbon typography strategies](https://carbondesignsystem.com/elements/typography/style-strategies/)

Use color roles consistently across affected states and themes. Keep meaning available without color alone. Evaluate accessibility against the applicable criteria and their conditions, rather than treating a palette's appearance as evidence of contrast. [WCAG contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

## Surfaces, assets, and motion

Give a boundary, fill, shadow, or elevation a role in grouping or interaction. Extra containers can fragment a continuous task; removing every container can erase useful structure. Choose according to what the user should perceive.

Use imagery and icons with a coherent visual character and a clear contribution to the product. Inspect crop, proportion, optical size, and their relationship to text. Meaningful illustration or photography can establish identity; interchangeable decoration may make the product less specific.

Motion can convey a state change or continuity between views. It can also compete with the task when many elements move at once. Carbon's distinction between productive and expressive motion is one contextual model; its exact curves, timing, and exclusions are IBM choices. Preserve meaning when motion is reduced. [Carbon motion](https://carbondesignsystem.com/elements/motion/overview/)

## Adaptation and visual judgment

Check how the composition changes with content, available space, and theme. Decide which relationships must survive a reflow, not just which dimensions get smaller. Keep the actual reading and interaction order coherent; consult [experience design](experience-design.md) if adaptation changes the flow.

When polishing, inspect the whole view after fixing local details. A correctly aligned card may still have the wrong prominence. Remove or simplify an element when that improves focus without losing meaning; keep expressive elements when they contribute to the intended direction.

## Basis and limits

The cited sources supply principles and contextual examples. The implementation judgments here are a synthesis, not a fixed style recipe or a guarantee of aesthetic quality. Treat numerical prescriptions in external design systems as system-specific unless the current project adopts them.
