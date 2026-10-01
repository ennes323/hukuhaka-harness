# UI verification

Choose evidence that can establish the result of the actual UI/UX task. A successful build is not proof of visual fidelity, usability, or accessible behavior.

## Expectation and coverage

Identify the relevant authority and affected views, states, content, viewports, themes, and input modes. Keep the coverage proportional to the change, but directly inspect each affected condition needed for the claim. A shared-component change can require evidence from consumers beyond the motivating screen.

Match verification to the artifact. A screenshot review can establish visible relationships in that image; it cannot prove keyboard interaction or runtime transitions. A design proposal can explain intended behavior without pretending that behavior was implemented.

For a change, compare equivalent before-and-after conditions when available. If the original cannot be reproduced, state that limitation and assess the result against the available authority. For a review-only request, preserve the inspected workspace.

## Rendered inspection

Use the in-app Browser when available for routine local interface inspection. Use project commands for deterministic checks and server health. If the Browser is unavailable or cannot supply the needed evidence, use available browser or UI tooling appropriate to the target platform; explain anything that remains unavailable.

Inspect actual content and state transitions rather than only a favorable populated view. Check relevant overflow, clipping, alignment, typography, layering, and visual hierarchy. Use computed style or geometry when an exact spatial discrepancy needs explanation, and screenshots or overlays when they make relationships easier to judge.

For affected interactions, exercise their reachable paths and feedback. Inspect keyboard reachability, visible focus, input/error association, dismissal or completion, and focus destination where relevant. Use suitable assistive-technology checks for claims that depend on them. Simulated input, DOM inspection, and a screenshot establish different kinds of evidence.

## Comparable conditions

Match content, state, theme, viewport, zoom, and asset loading before interpreting visual differences. Check the artifact version and whether the application actually loaded the changed code. Font fallback or unresolved media can resemble a spacing or layout defect.

Choose viewport evidence from the product's targets and the points where content relationships can fail. A desktop screenshot scaled down is not a responsive implementation check. Preserve realistic content variation instead of shortening fixtures to make a layout pass.

Record enough artifact identity and conditions for another reviewer to understand what was inspected. Do not collect a large screenshot set without knowing which uncertainty it resolves.

## Automated checks and their limits

Run the project's existing checks that apply to the change. Do not weaken a check to obtain a pass or create wording-matching tests as a substitute for design judgment. A snapshot test proves only the state and conditions it covers.

W3C's evaluation guidance combines tools and human assessment; no single tool establishes complete accessibility. Passing automated checks therefore does not resolve every interaction, assistive-technology, or design-quality question. [W3C evaluation overview](https://www.w3.org/WAI/test-evaluate/)

Distinguish normative requirements from informative ways to meet them. APG patterns are informative, and the guide describes browser and assistive-technology support limitations. Inspect the relevant environment rather than inferring interoperability from a library choice. [APG introduction](https://www.w3.org/WAI/ARIA/apg/about/introduction/), [APG support limits](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)

## Reuse and unavailable evidence

Reuse passing evidence when its relevant source, inputs, configuration, artifact, and environment are unchanged. Repeat affected checks after a change, failure, or named unresolved concern. A delegated owner should identify the inspected artifact and coverage so another reviewer can assess the delta without blindly repeating everything.

When a tool fails or a required state cannot be reached, distinguish an environmental limitation from a product failure. Continue independent checks, and report the exact claim that lacks evidence. Do not replace an unavailable rendered check with a build result and label it verified.

## Reporting verification

State what was inspected, what the evidence supports, and what remains unresolved. Report intentional exceptions and their authority when they affect acceptance. Keep mechanical results separate from design judgment and observed user behavior.

One clean screen does not establish application-wide consistency. Claims of improved usability need evidence of user behavior, beyond a reviewer's assessment of the interface.

## Basis and limits

The source links support accessibility-evidence boundaries. Tool preference, evidence reuse, and completion reporting are this Skill's workflow guidance. Their use does not establish compliance or visual quality without the corresponding inspected result.
