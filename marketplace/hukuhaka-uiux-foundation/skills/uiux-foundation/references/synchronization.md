# Design system, mockup, and application synchronization

Use this reference when more than one design artifact is relevant or a change may affect other consumers. Work with the artifacts the project actually has; this guidance does not require creating all three.

## Ownership and authority

Use the project's declared authority for each decision. The following responsibility model helps identify a conflict; an explicit project contract can assign ownership differently.

| Artifact | Typical responsibility | Evidence limit |
|---|---|---|
| Design system | Reusable visual and interaction rules | Does not determine every screen composition |
| Mockup | Screen hierarchy, composition, and visual intent | Does not prove runtime behavior or complete state coverage |
| Application | Working behavior and accessible, responsive execution | Does not prove that every existing value is an intentional design rule |

When a separate system document is absent, existing shared implementation can provide evidence of conventions. Distinguish that observed practice from an approved design decision. A newer file or a more polished screenshot is not automatically authoritative.

## Comparing a difference

Compare the same content, state, theme, and viewport before interpreting a mismatch. Confirm that fonts and assets loaded and that the compared versions correspond to the same intended change. A pixel difference can arise from rendering conditions rather than a design decision.

Distinguish an intentional variation, a missing decision, an outdated artifact, and accidental divergence. Keep the result unresolved when available evidence cannot determine intent. Do not average conflicting values or silently choose whichever artifact is easiest to edit.

For spatial problems, compare rendered relationships and use computed geometry where exact alignment matters. For interaction differences, compare actual behavior; a static mockup cannot establish keyboard or asynchronous behavior.

## Change impact and propagation

Find the owner of the changed decision before propagating it. A screen-specific composition adjustment may remain local, while a shared state or token change can affect many consumers. Identify the relevant consumers without treating every visual edit as a system-wide migration.

```text
WHEN a change affects more than one artifact:
    Establish the intended decision and its owner.
    Update or propose the owner-level decision within the authorized scope.
    Carry that decision to the affected dependent artifacts.
    Verify the affected consumers and identify remaining differences.
```

If the request is review-only, report the proposed correction and ownership without editing. If a material choice remains outside existing authorization, show the smallest useful comparison and ask for that decision. Continue independent authorized work.

## Mappings and generated artifacts

Use existing mappings between design components, tokens, and implementation where they are available. Verify that a mapping points to the actual component and variant rather than a similarly named artifact.

For example, Figma Code Connect connects design components to code representations. Such a connection can improve traceability, but does not itself prove that a running screen is current or visually correct. It is an optional project tool, not a dependency of this Skill. [Code Connect](https://developers.figma.com/docs/code-connect/)

When generated styles or documentation are involved, establish the upstream authoring source and preserve the generation direction. It may be a design file, a repository asset, or another declared source; do not infer ownership from the output you happen to be editing. Token references can carry changes into consumers, but the existence of an alias does not prove every consuming artifact was regenerated. Inspect actual outputs before claiming propagation. [DTCG token references](https://www.designtokens.org/tr/2025.10/format/)

## Exceptions and completion

Keep intentional differences explainable by the artifact or use case that needs them. A mockup may omit implementation detail, and platform-specific behavior can differ without being drift. A mismatch that hides an unmade shared decision is not a justified exception.

For several differences, a compact record of decision, owner, observed mismatch, and disposition can help. Do not require a ledger for one obvious correction. If a dependent artifact is inaccessible or outside scope, identify what remains out of sync and the consequence; do not imply full parity.

Use [verification](verification.md) to match completion claims to inspected evidence.

## Basis and limits

The ownership model and synchronization procedure are this Skill's guidance for reasoning about artifact boundaries. The external sources support traceability mechanisms; they do not establish which artifact should win a particular project conflict.
