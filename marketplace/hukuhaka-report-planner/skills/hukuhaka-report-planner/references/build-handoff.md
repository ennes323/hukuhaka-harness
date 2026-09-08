# Build handoff

Read only after Stage 4 finalizes the content spec and the user requested the artifact.
Planning-only requests stop at spec.md.

## Payload

Send one designer:

Resolve `../artifact-designer/SKILL.md` from the planner SKILL.md's directory and include
that absolute skill path in the delegation. Use this plugin's sibling skill, not a same-named
installed copy from another version.

```yaml
spec path: .hukuhaka/reports/<short-name>/spec.md
source material: <paths and verified URLs named in spec.md>
form: <requested medium>
output target: <user-requested destination>
user constraints: <explicit requirements from spec.md, or omitted>
verification: <T# criteria from spec.md>
```

For content-v1, the designer reads the spec and sources, selects its own craft references, and writes
sibling design.md. Do not send a planner-authored design or a selected craft list for
content-v1 plans. Pass contract paths, not duplicated contract bodies.

For an existing unmarked plan, read `plan-compatibility.md` and additionally pass its
legacy kind and existing design path when required. Do not silently change its ownership.
Pass a legacy pair's existing design unchanged; for a combined plan pass its combined spec.
The designer loads the recorded references and preserves original direction, not a new
selection. Missing required legacy input stops the handoff. Legacy .claude/reports/ paths
remain read-only, so their realization is returned in the receipt only.

## Codex handoff

Spawn one write-capable worker and explicitly instruct it to use the bundled
`artifact-designer` skill at that resolved absolute path with this payload.
Run the worker in the foreground and do not install a user-level agent.

## Completion

Wait for the one designer. Do not build in the parent or run a competing designer.
Review source-backed meaning and explicit constraints against the spec, not personal
visual preferences. The designer owns design choices and visual verification.

Require artifact paths, design/realization records, verification evidence, and limitations.
The receipt must identify the inspected artifact and source inputs, actual
coverage, failed checks, and required `not-run` checks. Reuse valid evidence
while those inputs and the renderer remain unchanged; do not repeat checks
merely for the handoff. The parent owns final acceptance: `built` records
construction, and cannot close a required check that failed or was not run.
Do not claim that unperformed checks passed. If Codex cannot delegate, report that
capability as unavailable rather than constructing in the planner context.
